#!/bin/bash
# ==============================================================================
# Unified Pipeline Test Script
# ==============================================================================
# Tests the full pipeline using IngestorEngine paradigm on Spark cluster.
# Configuration loaded from run_config.json profiles.
#
# Usage:
#   ./scripts/test/test_pipeline.sh --profile <PROFILE> [OPTIONS]
#
# Options:
#   --profile PROFILE    Use named profile (quick_test, dev, silver_only, staging, production)
#   --models MODELS      Specify models to build (space-separated, e.g., "temporal stocks")
#   --max-tickers N      Override max tickers to process
#   --skip-seed          Skip ticker seeding (use existing Bronze data)
#   --force-seed         Force re-seed even if ticker data exists
#   --skip-ingest        Skip Bronze ingestion
#   --skip-financials    Skip company financials (included by default)
#   --with-reference     Include reference data (COMPANY_OVERVIEW - for market_cap updates)
#   --storage-path PATH  Override storage path (default: from run_config.json)
#   --local              Run locally (ignore SPARK_MASTER_URL)
#   --help               Show this help message
#
# Profiles (defined in run_config.json):
#   dev          - Bronze only: alpha_vantage + chicago + cook_county
#   silver_only  - Silver only: build models from existing bronze data
#   staging      - Full pipeline: bronze + silver (500 tickers)
#   production   - Full pipeline: all tickers
#
# Examples:
#   ./scripts/test/test_pipeline.sh --profile dev                    # Bronze ingestion only
#   ./scripts/test/test_pipeline.sh --profile silver_only            # Build silver from existing bronze
#   ./scripts/test/test_pipeline.sh --profile silver_only --models temporal  # Build specific model
#   ./scripts/test/test_pipeline.sh --profile staging                # Full pipeline
#
# Author: de_Funk Team
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
FORCE_SEED=false
SKIP_INGEST=false
BUILD_SILVER=false     # Test everything by default
MODELS=""             # Empty = build all discovered models
WITH_FINANCIALS=true   # Include financials by default
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
        --force-seed)
            FORCE_SEED=true
            shift
            ;;
        --skip-ingest)
            SKIP_INGEST=true
            shift
            ;;
        --models)
            MODELS="$2"
            shift 2
            ;;
        --skip-financials)
            WITH_FINANCIALS=false
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
PROFILE_PROVIDERS=""
PROFILE_HAS_PROVIDERS="false"
PROFILE_BUILD_SILVER=""
if [ -n "$PROFILE" ] && [ -f "$REPO_ROOT/configs/pipelines/run_config.json" ]; then
    # Export for Python heredoc
    export REPO_ROOT PROFILE

    # Read all profile settings at once
    eval $(python3 << 'PYEOF'
import json
import os

repo_root = os.environ.get('REPO_ROOT', '.')
profile_name = os.environ.get('PROFILE', '')

with open(f'{repo_root}/configs/pipelines/run_config.json') as f:
    cfg = json.load(f)

profile = cfg.get('profiles', {}).get(profile_name, {})

# max_tickers - empty string if not set or null
max_tickers = profile.get('max_tickers')
if max_tickers:
    print(f'PROFILE_MAX_TICKERS="{max_tickers}"')
else:
    print('PROFILE_MAX_TICKERS=""')

# with_financials - default is true, only set false if explicitly disabled
if profile.get('with_financials') is False:
    print('PROFILE_WITH_FINANCIALS="false"')
else:
    print('PROFILE_WITH_FINANCIALS="true"')

# build_silver from profile
if profile.get('build_silver'):
    print('PROFILE_BUILD_SILVER="true"')
else:
    print('PROFILE_BUILD_SILVER="false"')

# providers list - track if profile explicitly defines providers (even if empty)
if 'providers' in profile:
    providers = profile.get('providers', [])
    print(f'PROFILE_PROVIDERS="{" ".join(providers)}"')
    print('PROFILE_HAS_PROVIDERS="true"')  # Profile explicitly set providers
else:
    print('PROFILE_PROVIDERS=""')
    print('PROFILE_HAS_PROVIDERS="false"')  # Use global config

# write_batch_size - records to buffer before Delta write (default 500000)
write_batch_size = profile.get('write_batch_size', 500000)
print(f'PROFILE_WRITE_BATCH_SIZE="{write_batch_size}"')
PYEOF
)

    # Apply profile settings if not overridden by CLI
    [ -z "$MAX_TICKERS" ] && [ -n "$PROFILE_MAX_TICKERS" ] && MAX_TICKERS="$PROFILE_MAX_TICKERS"
    [ "$PROFILE_WITH_FINANCIALS" = "false" ] && WITH_FINANCIALS=false

    # Apply profile's build_silver setting
    [ "$PROFILE_BUILD_SILVER" = "true" ] && BUILD_SILVER=true
fi

# If --models is specified, we want to build them
if [ -n "$MODELS" ]; then
    BUILD_SILVER=true
fi

# Print header
echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}     de_Funk Pipeline Test - IngestorEngine Paradigm        ${NC}"
echo -e "${BLUE}============================================================${NC}"
echo ""

echo -e "Repository root: ${GREEN}$REPO_ROOT${NC}"

# Check Spark environment - detect from cluster.yaml or env var
if [ "$RUN_LOCAL" = false ]; then
    # Try to get master URL from cluster.yaml if not already set
    if [ -z "$SPARK_MASTER_URL" ] && [ -f "$REPO_ROOT/configs/cluster.yaml" ]; then
        CLUSTER_HEAD=$(python3 -c "
import yaml
with open('$REPO_ROOT/configs/cluster.yaml') as f:
    cfg = yaml.safe_load(f)
# cluster.yaml structure: cluster.head.ip or cluster.head.hostname, spark.master.port
cluster = cfg.get('cluster', {})
head_cfg = cluster.get('head', {})
head = head_cfg.get('ip') or head_cfg.get('hostname', '')
port = cfg.get('spark', {}).get('master', {}).get('port', 7077)
print(f'spark://{head}:{port}' if head else '')
" 2>/dev/null || echo "")
        [ -n "$CLUSTER_HEAD" ] && export SPARK_MASTER_URL="$CLUSTER_HEAD"
    fi
fi

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
echo "  Build silver: $([ "$BUILD_SILVER" = true ] && echo 'yes' || echo 'no')"
[ -n "$MODELS" ] && echo "  Models to build: $MODELS"
echo "  With financials: $WITH_FINANCIALS"
echo "  With reference: $WITH_REFERENCE"
echo ""

# Build Python arguments
PYTHON_ARGS=""
[ -n "$PROFILE" ] && PYTHON_ARGS="$PYTHON_ARGS --profile $PROFILE"
[ -n "$MAX_TICKERS" ] && PYTHON_ARGS="$PYTHON_ARGS --max-tickers $MAX_TICKERS"
[ -n "$STORAGE_PATH" ] && PYTHON_ARGS="$PYTHON_ARGS --storage-path $STORAGE_PATH"

# Check if Alpha Vantage is enabled - respect profile's providers list
if [ "$PROFILE_HAS_PROVIDERS" = "true" ]; then
    # Profile explicitly defines providers list - use only those (may be empty)
    if [ -n "$PROFILE_PROVIDERS" ] && echo "$PROFILE_PROVIDERS" | grep -qw "alpha_vantage"; then
        ALPHA_VANTAGE_ENABLED="true"
    else
        ALPHA_VANTAGE_ENABLED="false"
        if [ -z "$PROFILE_PROVIDERS" ]; then
            echo -e "${YELLOW}Profile has no providers (silver-only mode)${NC}"
        else
            echo -e "${YELLOW}Alpha Vantage not in profile providers: $PROFILE_PROVIDERS${NC}"
        fi
    fi
else
    # No profile providers defined - fall back to global enabled flag
    ALPHA_VANTAGE_ENABLED=$(python3 -c "
import json
with open('$REPO_ROOT/configs/pipelines/run_config.json') as f:
    cfg = json.load(f)
print('true' if cfg.get('providers', {}).get('alpha_vantage', {}).get('enabled') else 'false')
" 2>/dev/null || echo "false")

    if [ "$ALPHA_VANTAGE_ENABLED" = "false" ]; then
        echo -e "${YELLOW}Alpha Vantage is disabled in run_config.json${NC}"
    fi
fi

# ==============================================================================
# Task 1: Seed Tickers (Alpha Vantage)
# ==============================================================================
if [ "$SKIP_SEED" = false ] && [ "$ALPHA_VANTAGE_ENABLED" = "true" ]; then
    # Check if seed data already exists
    SEED_PATH="${STORAGE_PATH:-/shared/storage}/bronze/ticker_seed"
    if [ -d "$SEED_PATH/_delta_log" ] && [ "$FORCE_SEED" != "true" ]; then
        echo -e "${YELLOW}○ Ticker seed exists at $SEED_PATH - skipping (use --force-seed to override)${NC}"
    else
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
from pathlib import Path
import json

# Get storage path
storage_path = '${STORAGE_PATH:-/shared/storage}'
logger.info(f'Storage path: {storage_path}')

# Docs path for markdown config
docs_path = Path('$REPO_ROOT')

# Initialize Spark
spark = get_spark(app_name='test_pipeline_seed')

# Create provider (config loaded from markdown)
provider = create_alpha_vantage_provider(spark=spark, docs_path=docs_path)

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
    fi  # end else (seed doesn't exist)
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

logger.info('Testing task: bronze ingestion (Alpha Vantage)')

# Import components
from datapipelines.base.ingestor_engine import IngestorEngine
from datapipelines.providers.alpha_vantage.alpha_vantage_provider import create_alpha_vantage_provider
from orchestration.common.spark_session import get_spark
from pathlib import Path
import json

# Get settings
storage_path = '${STORAGE_PATH:-/shared/storage}'
max_tickers = ${MAX_TICKERS:-10}
with_financials = True if '${WITH_FINANCIALS}' == 'true' else False
with_reference = True if '${WITH_REFERENCE}' == 'true' else False

logger.info(f'Storage path: {storage_path}')
logger.info(f'Max tickers: {max_tickers}')
logger.info(f'With financials: {with_financials}')
logger.info(f'With reference: {with_reference}')

# Docs path for markdown config
docs_path = Path('$REPO_ROOT')

# Initialize Spark
spark = get_spark(app_name='test_pipeline_ingest')

# Load storage config from storage.json (single source of truth for partitions, keys, etc.)
with open('$REPO_ROOT/configs/storage.json') as f:
    storage_cfg = json.load(f)

# Override roots to use storage_path from CLI (replace 'storage/' prefix with custom path)
storage_cfg['roots'] = {k: v.replace('storage/', f'{storage_path}/') for k, v in storage_cfg['roots'].items()}

# Create provider (config loaded from markdown)
provider = create_alpha_vantage_provider(spark=spark, docs_path=docs_path)

# Create IngestorEngine
engine = IngestorEngine(provider, storage_cfg)

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

# Set tickers on provider
provider.set_tickers(tickers)

# Build work items list (data types) - prices is always included
work_items = ['prices']

# Add reference if requested (not needed if seed already has basic info)
if with_reference:
    logger.info('Including reference data (COMPANY_OVERVIEW)')
    work_items.append('reference')

# Add financial statements if requested (uses ticker-based lookups, not CIK)
if with_financials:
    logger.info('Including financial statements (income, balance, cash flow, earnings)')
    work_items.extend(['income', 'balance', 'cashflow', 'earnings'])

logger.info(f'Work items (data types): {work_items}')

# Get write_batch_size from profile (default 500k for streaming Delta writes)
write_batch_size = int('${PROFILE_WRITE_BATCH_SIZE:-500000}')
logger.info(f'write_batch_size: {write_batch_size} records per batch')

# Run ingestion engine
results = engine.run(
    work_items=work_items,
    write_batch_size=write_batch_size,
    silent=False
)

logger.info(f'Ingestion complete. Completed: {results.completed_work_items}/{results.total_work_items}, Records: {results.total_records:,}')
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
    # Determine which bulk providers to run
    if [ "$PROFILE_HAS_PROVIDERS" = "true" ]; then
        # Profile explicitly defines providers - use only those (filter to bulk providers)
        BULK_PROVIDERS=""
        for p in $PROFILE_PROVIDERS; do
            if [ "$p" = "chicago" ] || [ "$p" = "cook_county" ]; then
                BULK_PROVIDERS="$BULK_PROVIDERS $p"
            fi
        done
        BULK_PROVIDERS=$(echo "$BULK_PROVIDERS" | xargs)  # trim whitespace
    else
        # No profile providers defined - fall back to global enabled flags
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
    fi

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
from datapipelines.base.ingestor_engine import IngestorEngine
from datapipelines.providers.chicago.chicago_provider import create_chicago_provider
from datapipelines.providers.cook_county.cook_county_provider import create_cook_county_provider
from orchestration.common.spark_session import get_spark
from pathlib import Path
import json

# Get storage path
storage_path = '${STORAGE_PATH:-/shared/storage}'

with open('$REPO_ROOT/configs/pipelines/run_config.json') as f:
    run_config = json.load(f)

with open('$REPO_ROOT/configs/storage.json') as f:
    storage_cfg = json.load(f)

storage_cfg['roots'] = {k: v.replace('storage/', f'{storage_path}/') for k, v in storage_cfg['roots'].items()}

logger.info(f'Storage path: {storage_path}')

# Initialize Spark
spark = get_spark(app_name='test_pipeline_bulk')

# Docs path for markdown config
docs_path = Path('$REPO_ROOT')

# Factory mapping
provider_factories = {
    'chicago': create_chicago_provider,
    'cook_county': create_cook_county_provider,
}

# Run each bulk provider from the list (profile or global enabled)
bulk_providers = '$BULK_PROVIDERS'.split()
logger.info(f'Bulk providers to process: {bulk_providers}')

for provider_name in bulk_providers:
    try:
        provider_cfg = run_config.get('providers', {}).get(provider_name, {})
        logger.info(f'Processing provider: {provider_name}')

        # Get factory function
        factory = provider_factories.get(provider_name)
        if not factory:
            logger.warning(f'Unknown provider: {provider_name} - skipping')
            continue

        # Create provider (config loaded from markdown, storage_path for raw layer)
        provider = factory(spark=spark, docs_path=docs_path, storage_path=storage_path)
        logger.info(f'Created provider: {provider.provider_id}')

        # Create IngestorEngine
        engine = IngestorEngine(provider, storage_cfg)

        # Get work items (endpoints) to ingest from run_config
        work_items = provider_cfg.get('endpoints', []) or None  # None = discover from provider
        if work_items:
            logger.info(f'Work items from config: {len(work_items)} endpoints')
        else:
            logger.info('Work items: auto-discover from provider')

        # Get max_records from profile - null/None means no limit (fetch all)
        # DO NOT default to a number - explicit null means fetch everything
        profile_cfg = run_config.get('profiles', {}).get('${PROFILE}', {})
        max_records = profile_cfg.get('max_records_per_endpoint')  # None if not set or null

        if max_records is None:
            logger.info(f'max_records_per_endpoint is null - fetching ALL records (no limit)')

        # Get write_batch_size from profile (default 500k for streaming Delta writes)
        write_batch_size = int('${PROFILE_WRITE_BATCH_SIZE:-500000}')
        logger.info(f'write_batch_size: {write_batch_size} records per batch')

        # Run ingestion engine
        results = engine.run(
            work_items=work_items,
            write_batch_size=write_batch_size,
            max_records=max_records,
            silent=False
        )

        # Summary from IngestionResults
        logger.info(f'{provider_name}: {results.completed_work_items}/{results.total_work_items} work items, {results.total_records:,} total records')

    except Exception as e:
        logger.error(f'Error processing {provider_name}: {e}', exc_info=True)
        raise

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
if [ "$BUILD_SILVER" = true ]; then
    echo -e "${BLUE}============================================================${NC}"
    echo -e "${BLUE}Testing task: silver model build${NC}"
    echo -e "${BLUE}============================================================${NC}"

    # Get models to build: CLI --models overrides silver_models.models from config
    if [ -z "$MODELS" ]; then
        # Read from silver_models.models in run_config.json
        MODELS=$(python3 -c "
import json
with open('$REPO_ROOT/configs/pipelines/run_config.json') as f:
    cfg = json.load(f)
models = cfg.get('silver_models', {}).get('models', [])
print(' '.join(models))
" 2>/dev/null || echo "")
    fi

    # Build arguments for build_models.py
    # Always pass storage-root (default to /shared/storage for cluster mode)
    BUILD_STORAGE="${STORAGE_PATH:-/shared/storage}"
    BUILD_ARGS="--storage-root $BUILD_STORAGE"
    [ -n "$MODELS" ] && BUILD_ARGS="$BUILD_ARGS --models $MODELS"

    echo -e "Building models: ${GREEN}${MODELS:-all discovered}${NC}"

    # Use spark-submit via submit-job.sh wrapper for proper Spark cluster execution
    "$REPO_ROOT/scripts/spark-cluster/submit-job.sh" "$REPO_ROOT/scripts/build/build_models.py" $BUILD_ARGS --verbose

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
[ "$BUILD_SILVER" = true ] && echo "  ✓ Silver models built"
[ "$BUILD_SILVER" = false ] && echo "  ○ Silver build skipped"
echo ""
