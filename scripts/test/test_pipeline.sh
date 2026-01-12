#!/bin/bash
# ==============================================================================
# Unified Pipeline Test Script
# ==============================================================================
# Tests the full pipeline using IngestorEngine paradigm on Spark cluster.
#
# Usage:
#   ./scripts/test/test_pipeline.sh [OPTIONS]
#
# Options:
#   --profile PROFILE    Use named profile (quick_test, dev, staging, production)
#   --max-tickers N      Override max tickers to process
#   --skip-seed          Skip ticker seeding (use existing Bronze data)
#   --skip-ingest        Skip Bronze ingestion
#   --skip-silver        Skip Silver model building
#   --with-financials    Include company financials (income, balance, cash flow, earnings)
#   --with-reference     Include reference data (COMPANY_OVERVIEW - for market_cap updates)
#   --storage-path PATH  Override storage path (default: from run_config.json)
#   --local              Run locally (ignore SPARK_MASTER_URL)
#   --help               Show this help message
#
# Examples:
#   ./scripts/test/test_pipeline.sh --profile dev               # Full test (Bronze + Silver)
#   ./scripts/test/test_pipeline.sh --profile dev --skip-silver # Bronze only
#   ./scripts/test/test_pipeline.sh --with-financials           # Include financial statements
#   ./scripts/test/test_pipeline.sh --profile production --skip-seed
#
# Author: de_Funk Team
# Date: January 2026
# ==============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
PROFILE=""
MAX_TICKERS=""
SKIP_SEED=false
SKIP_INGEST=false
SKIP_SILVER=false     # Test everything by default
WITH_FINANCIALS=false  # Skip financials by default (saves API calls)
WITH_REFERENCE=false   # Skip reference by default (seed has basic info, only need for market_cap)
STORAGE_PATH=""
RUN_LOCAL=false
BULK_PROVIDERS=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --profile)
            PROFILE="$2"
            shift 2
            ;;
        --max-tickers)
            MAX_TICKERS="$2"
            shift 2
            ;;
        --skip-seed)
            SKIP_SEED=true
            shift
            ;;
        --skip-ingest)
            SKIP_INGEST=true
            shift
            ;;
        --skip-silver)
            SKIP_SILVER=true
            shift
            ;;
        --with-financials)
            WITH_FINANCIALS=true
            shift
            ;;
        --with-reference)
            WITH_REFERENCE=true
            shift
            ;;
        --storage-path)
            STORAGE_PATH="$2"
            shift 2
            ;;
        --local)
            RUN_LOCAL=true
            shift
            ;;
        --help)
            head -50 "$0" | grep -E "^#" | sed 's/^# //' | sed 's/^#//'
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Determine repo root first (needed for config loading)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

# Source .env file if it exists (for API keys)
if [ -f "$REPO_ROOT/.env" ]; then
    set -a  # automatically export all variables
    source "$REPO_ROOT/.env"
    set +a
fi

# Load profile settings from run_config.json if profile is specified
if [ -n "$PROFILE" ] && [ -f "$REPO_ROOT/configs/pipelines/run_config.json" ]; then
    # Read max_tickers from profile if not overridden by CLI
    if [ -z "$MAX_TICKERS" ]; then
        PROFILE_MAX_TICKERS=$(python3 -c "
import json
with open('$REPO_ROOT/configs/pipelines/run_config.json') as f:
    cfg = json.load(f)
profile = cfg.get('profiles', {}).get('$PROFILE', {})
print(profile.get('max_tickers', '') or '')
" 2>/dev/null || echo "")
        [ -n "$PROFILE_MAX_TICKERS" ] && MAX_TICKERS="$PROFILE_MAX_TICKERS"
    fi

    # Read with_financials from profile (CLI --with-financials still overrides)
    PROFILE_WITH_FINANCIALS=$(python3 -c "
import json
with open('$REPO_ROOT/configs/pipelines/run_config.json') as f:
    cfg = json.load(f)
profile = cfg.get('profiles', {}).get('$PROFILE', {})
print('true' if profile.get('with_financials') else 'false')
" 2>/dev/null || echo "false")

    # Only use profile setting if CLI didn't explicitly set --with-financials
    if [ "$WITH_FINANCIALS" = false ] && [ "$PROFILE_WITH_FINANCIALS" = "true" ]; then
        WITH_FINANCIALS=true
    fi
fi

# Print header
echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}     de_Funk Pipeline Test - IngestorEngine Paradigm        ${NC}"
echo -e "${BLUE}============================================================${NC}"
echo ""

echo -e "Repository root: ${GREEN}$REPO_ROOT${NC}"

# Check Spark environment
if [ "$RUN_LOCAL" = false ] && [ -n "$SPARK_MASTER_URL" ]; then
    echo -e "Spark master: ${GREEN}$SPARK_MASTER_URL${NC}"
    SPARK_MODE="cluster"
else
    echo -e "Spark mode: ${YELLOW}local${NC}"
    SPARK_MODE="local"
    unset SPARK_MASTER_URL
fi

# Display configuration
echo ""
echo -e "${YELLOW}Configuration:${NC}"
[ -n "$PROFILE" ] && echo "  Profile: $PROFILE"
[ -n "$MAX_TICKERS" ] && echo "  Max tickers: $MAX_TICKERS"
[ -n "$STORAGE_PATH" ] && echo "  Storage path: $STORAGE_PATH"
echo "  Skip seed: $SKIP_SEED"
echo "  Skip ingest: $SKIP_INGEST"
echo "  Build silver: $([ "$SKIP_SILVER" = false ] && echo 'yes' || echo 'no')"
echo "  With financials: $WITH_FINANCIALS"
echo "  With reference: $WITH_REFERENCE"
echo ""

# Build Python arguments
PYTHON_ARGS=""
[ -n "$PROFILE" ] && PYTHON_ARGS="$PYTHON_ARGS --profile $PROFILE"
[ -n "$MAX_TICKERS" ] && PYTHON_ARGS="$PYTHON_ARGS --max-tickers $MAX_TICKERS"
[ -n "$STORAGE_PATH" ] && PYTHON_ARGS="$PYTHON_ARGS --storage-path $STORAGE_PATH"

# Check if Alpha Vantage is enabled
ALPHA_VANTAGE_ENABLED=$(python3 -c "
import json
with open('$REPO_ROOT/configs/pipelines/run_config.json') as f:
    cfg = json.load(f)
print('true' if cfg.get('providers', {}).get('alpha_vantage', {}).get('enabled') else 'false')
" 2>/dev/null || echo "false")

if [ "$ALPHA_VANTAGE_ENABLED" = "false" ]; then
    echo -e "${YELLOW}Alpha Vantage is disabled in run_config.json${NC}"
fi

# ==============================================================================
# Task 1: Seed Tickers (Alpha Vantage)
# ==============================================================================
if [ "$SKIP_SEED" = false ] && [ "$ALPHA_VANTAGE_ENABLED" = "true" ]; then
    echo -e "${BLUE}============================================================${NC}"
    echo -e "${BLUE}Testing task: seed tickers${NC}"
    echo -e "${BLUE}============================================================${NC}"

    python -c "
import sys
sys.path.insert(0, '$REPO_ROOT')

from config.logging import setup_logging, get_logger
setup_logging()
logger = get_logger('test_pipeline')

logger.info('Testing task: seed tickers')

# Import provider
from datapipelines.providers.alpha_vantage.alpha_vantage_provider import create_alpha_vantage_provider
from datapipelines.ingestors.bronze_sink import BronzeSink
from orchestration.common.spark_session import get_spark
from config.markdown_loader import get_markdown_loader
from pathlib import Path
import json
import os

# Load config from markdown (v2.6)
loader = get_markdown_loader(Path('$REPO_ROOT'))
av_config = loader.get_provider_config('alpha_vantage')
if not av_config:
    logger.error('Could not load Alpha Vantage config from markdown')
    sys.exit(1)

# Load API keys from environment variable
api_keys_str = os.environ.get('ALPHA_VANTAGE_API_KEYS', '')
api_keys = [k.strip() for k in api_keys_str.split(',') if k.strip()]
if not api_keys:
    logger.warning('No ALPHA_VANTAGE_API_KEYS environment variable set - API calls may fail')
av_config['credentials'] = {'api_keys': api_keys}

# Get storage path
storage_path = '${STORAGE_PATH:-/shared/storage}'
logger.info(f'Storage path: {storage_path}')

# Initialize Spark
spark = get_spark(app_name='test_pipeline_seed')

# Create provider
provider = create_alpha_vantage_provider(av_config, spark=spark)

# Seed tickers
df = provider.seed_tickers(state='active', filter_us_exchanges=True)

# Write to Bronze - load config from storage.json (single source of truth)
with open('$REPO_ROOT/configs/storage.json') as f:
    storage_cfg = json.load(f)
# Override roots to use storage_path from CLI
storage_cfg['roots'] = {k: v.replace('storage/', f'{storage_path}/') for k, v in storage_cfg['roots'].items()}

sink = BronzeSink(storage_cfg)
# Partitions come from storage.json config, not hardcoded here
table_cfg = storage_cfg['tables'].get('ticker_seed', {})
sink.write(df, 'ticker_seed', partitions=table_cfg.get('partitions'), mode='overwrite')

logger.info(f'Seeded {df.count()} tickers to Bronze layer')
spark.stop()
"

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Seed tickers completed${NC}"
    else
        echo -e "${RED}✗ Seed tickers failed${NC}"
        exit 1
    fi
    echo ""
fi

# ==============================================================================
# Task 2: Bronze Ingestion (Alpha Vantage)
# ==============================================================================
if [ "$SKIP_INGEST" = false ] && [ "$ALPHA_VANTAGE_ENABLED" = "true" ]; then
    echo -e "${BLUE}============================================================${NC}"
    echo -e "${BLUE}Testing task: bronze ingestion (Alpha Vantage)${NC}"
    echo -e "${BLUE}============================================================${NC}"

    python -c "
import sys
sys.path.insert(0, '$REPO_ROOT')

from config.logging import setup_logging, get_logger
setup_logging()
logger = get_logger('test_pipeline')

logger.info('Testing task: bronze ingestion')

# Import components
from datapipelines.providers.alpha_vantage.alpha_vantage_provider import create_alpha_vantage_provider
from datapipelines.base.ingestor_engine import IngestorEngine
from datapipelines.base.provider import DataType
from orchestration.common.spark_session import get_spark
from config.markdown_loader import get_markdown_loader
from pathlib import Path
import json
import os

# Load configs from markdown (v2.6)
loader = get_markdown_loader(Path('$REPO_ROOT'))
av_config = loader.get_provider_config('alpha_vantage')
if not av_config:
    logger.error('Could not load Alpha Vantage config from markdown')
    sys.exit(1)

with open('$REPO_ROOT/configs/pipelines/run_config.json') as f:
    run_config = json.load(f)

# Load API keys from environment variable
api_keys_str = os.environ.get('ALPHA_VANTAGE_API_KEYS', '')
api_keys = [k.strip() for k in api_keys_str.split(',') if k.strip()]
if not api_keys:
    logger.warning('No ALPHA_VANTAGE_API_KEYS environment variable set - API calls may fail')
av_config['credentials'] = {'api_keys': api_keys}

# Get settings
storage_path = '${STORAGE_PATH:-/shared/storage}'
max_tickers = ${MAX_TICKERS:-10}
with_financials = True if '${WITH_FINANCIALS}' == 'true' else False
with_reference = True if '${WITH_REFERENCE}' == 'true' else False

logger.info(f'Storage path: {storage_path}')
logger.info(f'Max tickers: {max_tickers}')
logger.info(f'With financials: {with_financials}')
logger.info(f'With reference: {with_reference}')

# Initialize Spark
spark = get_spark(app_name='test_pipeline_ingest')

# Create provider
provider = create_alpha_vantage_provider(av_config, spark=spark)

# Load storage config from storage.json (single source of truth for partitions, keys, etc.)
with open('$REPO_ROOT/configs/storage.json') as f:
    storage_cfg = json.load(f)

# Override roots to use storage_path from CLI (replace 'storage/' prefix with custom path)
storage_cfg['roots'] = {k: v.replace('storage/', f'{storage_path}/') for k, v in storage_cfg['roots'].items()}

# Try to get tickers by market cap from securities_reference
tickers = provider.get_tickers_by_market_cap(max_tickers=max_tickers, storage_cfg=storage_cfg)

# Fall back to ticker_seed if no tickers with market cap
if not tickers:
    from pathlib import Path
    ticker_seed_path = Path(storage_cfg['roots']['bronze']) / 'ticker_seed'

    if ticker_seed_path.exists():
        logger.info('No market cap data yet - reading from ticker_seed')
        if (ticker_seed_path / '_delta_log').exists():
            df = spark.read.format('delta').load(str(ticker_seed_path))
        else:
            df = spark.read.parquet(str(ticker_seed_path))

        # Get unique tickers, limited to max_tickers
        tickers = [row.ticker for row in df.select('ticker').distinct().limit(max_tickers).collect()]
        logger.info(f'Loaded {len(tickers)} tickers from ticker_seed')
    else:
        logger.error('No tickers found. Run seed first.')
        sys.exit(1)

if not tickers:
    logger.error('No tickers available for ingestion.')
    sys.exit(1)

logger.info(f'Found {len(tickers)} tickers for ingestion')

# Create engine and run
engine = IngestorEngine(provider, storage_cfg)

# Build data types list - prices is always included
data_types = [DataType.PRICES]

# Add reference if requested (not needed if seed already has basic info)
if with_reference:
    logger.info('Including reference data (COMPANY_OVERVIEW)')
    data_types.append(DataType.REFERENCE)

# Add financial statements if requested (uses ticker-based lookups, not CIK)
if with_financials:
    logger.info('Including financial statements (income, balance, cash flow, earnings)')
    data_types.extend([
        DataType.INCOME_STATEMENT,
        DataType.BALANCE_SHEET,
        DataType.CASH_FLOW,
        DataType.EARNINGS,
    ])

logger.info(f'Data types: {[dt.value for dt in data_types]}')
results = engine.run(tickers, data_types)

logger.info(f'Ingestion complete. Completed: {results.completed_tickers}, Errors: {results.total_errors}')
spark.stop()
"

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Bronze ingestion completed${NC}"
    else
        echo -e "${RED}✗ Bronze ingestion failed${NC}"
        exit 1
    fi
    echo ""
fi

# ==============================================================================
# Task 2b: Chicago/Cook County Ingestion (Bulk Providers)
# ==============================================================================
if [ "$SKIP_INGEST" = false ]; then
    # Check if bulk providers are enabled in run_config.json
    BULK_PROVIDERS=$(python3 -c "
import json
with open('$REPO_ROOT/configs/pipelines/run_config.json') as f:
    cfg = json.load(f)
providers = cfg.get('providers', {})
enabled = []
if providers.get('chicago', {}).get('enabled'):
    enabled.append('chicago')
if providers.get('cook_county', {}).get('enabled'):
    enabled.append('cook_county')
print(' '.join(enabled))
" 2>/dev/null || echo "")

    if [ -n "$BULK_PROVIDERS" ]; then
        echo -e "${BLUE}============================================================${NC}"
        echo -e "${BLUE}Testing task: bulk provider ingestion (Chicago/Cook County)${NC}"
        echo -e "${BLUE}============================================================${NC}"
        echo -e "Enabled providers: ${GREEN}$BULK_PROVIDERS${NC}"

        python -c "
import sys
sys.path.insert(0, '$REPO_ROOT')

from config.logging import setup_logging, get_logger
setup_logging()
logger = get_logger('test_pipeline')

logger.info('Testing task: bulk provider ingestion')

# Import components
from datapipelines.base.ingestor_engine import create_engine
from orchestration.common.spark_session import get_spark
from config.markdown_loader import get_markdown_loader
from utils.env_loader import load_dotenv
from pathlib import Path
import json
import os

# Load .env file first
env_path = Path('$REPO_ROOT/.env')
if env_path.exists():
    load_dotenv(env_path)
    logger.info(f'Loaded environment from {env_path}')
else:
    logger.warning(f'.env file not found at {env_path}')

# Load configs
loader = get_markdown_loader(Path('$REPO_ROOT'))

with open('$REPO_ROOT/configs/pipelines/run_config.json') as f:
    run_config = json.load(f)

with open('$REPO_ROOT/configs/storage.json') as f:
    storage_cfg = json.load(f)

# Get storage path
storage_path = '${STORAGE_PATH:-/shared/storage}'
storage_cfg['roots'] = {k: v.replace('storage/', f'{storage_path}/') for k, v in storage_cfg['roots'].items()}

logger.info(f'Storage path: {storage_path}')

# Initialize Spark
spark = get_spark(app_name='test_pipeline_bulk')

# Docs path for markdown loader
docs_path = Path('$REPO_ROOT/Documents')

# Run each enabled bulk provider
bulk_providers = '$BULK_PROVIDERS'.split()
for provider_name in bulk_providers:
    provider_cfg = run_config.get('providers', {}).get(provider_name, {})
    if not provider_cfg.get('enabled'):
        continue

    logger.info(f'Processing provider: {provider_name}')

    # Get API config from markdown
    api_cfg = loader.get_provider_config(provider_name.replace('_', ' ').title().replace(' ', '_').lower())
    if not api_cfg:
        # Try alternate name format
        api_cfg = loader.get_provider_config(provider_name)

    if not api_cfg:
        logger.warning(f'Could not load config for {provider_name} - skipping')
        continue

    # Load API keys from environment - FAIL if not found
    env_key = f'{provider_name.upper()}_API_KEYS'
    api_keys_str = os.environ.get(env_key, '')
    api_keys = [k.strip() for k in api_keys_str.split(',') if k.strip()]

    if not api_keys:
        raise ValueError(
            f'API key required for {provider_name}. '
            f'Set {env_key} in .env file or environment. '
            f'Example: {env_key}=your_app_token_here'
        )

    logger.info(f'{provider_name}: Found API key ({api_keys[0][:4]}...{api_keys[0][-4:]})')
    api_cfg['credentials'] = {'api_keys': api_keys}

    # Create provider
    provider = create_engine(provider_name, api_cfg, storage_cfg, spark, docs_path)

    # Get endpoints to ingest from run_config
    endpoints = provider_cfg.get('endpoints', [])
    max_records = run_config.get('profiles', {}).get('${PROFILE}', {}).get('max_records_per_endpoint', 10000)

    if endpoints:
        logger.info(f'Ingesting endpoints: {endpoints}')
        results = provider.ingest_all(endpoint_ids=endpoints, max_records_per_endpoint=max_records)
    else:
        logger.info(f'Ingesting all active endpoints (max {max_records} records each)')
        results = provider.ingest_all(max_records_per_endpoint=max_records)

    # Summary
    success_count = sum(1 for r in results.values() if r.success)
    total_records = sum(r.record_count for r in results.values() if r.success)
    logger.info(f'{provider_name}: {success_count}/{len(results)} endpoints, {total_records} total records')

spark.stop()
logger.info('Bulk provider ingestion complete')
"

        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✓ Bulk provider ingestion completed${NC}"
        else
            echo -e "${RED}✗ Bulk provider ingestion failed${NC}"
            exit 1
        fi
        echo ""
    fi
fi

# ==============================================================================
# Task 3: Silver Build
# ==============================================================================
if [ "$SKIP_SILVER" = false ]; then
    echo -e "${BLUE}============================================================${NC}"
    echo -e "${BLUE}Testing task: silver model build${NC}"
    echo -e "${BLUE}============================================================${NC}"

    STORAGE_ARG=""
    [ -n "$STORAGE_PATH" ] && STORAGE_ARG="--storage-path $STORAGE_PATH"

    python -m scripts.build.build_models $STORAGE_ARG

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Silver build completed${NC}"
    else
        echo -e "${RED}✗ Silver build failed${NC}"
        exit 1
    fi
    echo ""
fi

# ==============================================================================
# Summary
# ==============================================================================
echo -e "${BLUE}============================================================${NC}"
echo -e "${GREEN}Pipeline test completed successfully!${NC}"
echo -e "${BLUE}============================================================${NC}"
echo ""
echo "Results:"
[ "$SKIP_SEED" = false ] && [ "$ALPHA_VANTAGE_ENABLED" = "true" ] && echo "  ✓ Tickers seeded (Alpha Vantage)"
[ "$SKIP_SEED" = false ] && [ "$ALPHA_VANTAGE_ENABLED" = "false" ] && echo "  ○ Ticker seed skipped (Alpha Vantage disabled)"
[ "$SKIP_INGEST" = false ] && [ "$ALPHA_VANTAGE_ENABLED" = "true" ] && echo "  ✓ Bronze data ingested (Alpha Vantage: prices$([ "$WITH_FINANCIALS" = true ] && echo ', financials'))"
[ "$SKIP_INGEST" = false ] && [ "$ALPHA_VANTAGE_ENABLED" = "false" ] && echo "  ○ Alpha Vantage ingestion skipped (disabled)"
[ "$SKIP_INGEST" = false ] && [ -n "$BULK_PROVIDERS" ] && echo "  ✓ Bulk providers ingested ($BULK_PROVIDERS)"
[ "$SKIP_SILVER" = false ] && echo "  ✓ Silver models built"
[ "$SKIP_SILVER" = true ] && echo "  ○ Silver build skipped (--skip-silver)"
echo ""
