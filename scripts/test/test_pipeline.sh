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
#   --storage-path PATH  Override storage path (default: from run_config.json)
#   --local              Run locally (ignore SPARK_MASTER_URL)
#   --help               Show this help message
#
# Examples:
#   ./scripts/test/test_pipeline.sh --profile dev
#   ./scripts/test/test_pipeline.sh --max-tickers 50
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
SKIP_SILVER=false
STORAGE_PATH=""
RUN_LOCAL=false

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

# Print header
echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}     de_Funk Pipeline Test - IngestorEngine Paradigm        ${NC}"
echo -e "${BLUE}============================================================${NC}"
echo ""

# Determine repo root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

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
echo "  Skip silver: $SKIP_SILVER"
echo ""

# Build Python arguments
PYTHON_ARGS=""
[ -n "$PROFILE" ] && PYTHON_ARGS="$PYTHON_ARGS --profile $PROFILE"
[ -n "$MAX_TICKERS" ] && PYTHON_ARGS="$PYTHON_ARGS --max-tickers $MAX_TICKERS"
[ -n "$STORAGE_PATH" ] && PYTHON_ARGS="$PYTHON_ARGS --storage-path $STORAGE_PATH"

# ==============================================================================
# Task 1: Seed Tickers
# ==============================================================================
if [ "$SKIP_SEED" = false ]; then
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
from datapipelines.providers.alpha_vantage.provider import create_alpha_vantage_provider
from datapipelines.ingestors.bronze_sink import BronzeSink
from orchestration.common.spark_session import get_spark
import json

# Load config
with open('$REPO_ROOT/configs/pipelines/alpha_vantage_endpoints.json') as f:
    av_config = json.load(f)
av_config['credentials'] = {'api_keys': []}  # Will use env var

# Get storage path
storage_path = '${STORAGE_PATH:-/shared/storage}'
logger.info(f'Storage path: {storage_path}')

# Initialize Spark
spark = get_spark(app_name='test_pipeline_seed')

# Create provider
provider = create_alpha_vantage_provider(av_config, spark=spark)

# Seed tickers
df = provider.seed_tickers(state='active', filter_us_exchanges=True)

# Write to Bronze
storage_cfg = {
    'roots': {'bronze': f'{storage_path}/bronze'},
    'tables': {'ticker_seed': {'rel': 'ticker_seed'}}
}
sink = BronzeSink(storage_cfg)
sink.write(df, 'ticker_seed', partitions=['asset_type'], mode='overwrite')

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
# Task 2: Bronze Ingestion
# ==============================================================================
if [ "$SKIP_INGEST" = false ]; then
    echo -e "${BLUE}============================================================${NC}"
    echo -e "${BLUE}Testing task: bronze ingestion${NC}"
    echo -e "${BLUE}============================================================${NC}"

    python -c "
import sys
sys.path.insert(0, '$REPO_ROOT')

from config.logging import setup_logging, get_logger
setup_logging()
logger = get_logger('test_pipeline')

logger.info('Testing task: bronze ingestion')

# Import components
from datapipelines.providers.alpha_vantage.provider import create_alpha_vantage_provider
from datapipelines.base.ingestor_engine import IngestorEngine, create_engine
from datapipelines.base.provider import DataType
from orchestration.common.spark_session import get_spark
import json

# Load configs
with open('$REPO_ROOT/configs/pipelines/alpha_vantage_endpoints.json') as f:
    av_config = json.load(f)
with open('$REPO_ROOT/configs/pipelines/run_config.json') as f:
    run_config = json.load(f)

av_config['credentials'] = {'api_keys': []}

# Get settings
storage_path = '${STORAGE_PATH:-/shared/storage}'
max_tickers = ${MAX_TICKERS:-10}

logger.info(f'Storage path: {storage_path}')
logger.info(f'Max tickers: {max_tickers}')

# Initialize Spark
spark = get_spark(app_name='test_pipeline_ingest')

# Create provider
provider = create_alpha_vantage_provider(av_config, spark=spark)

# Get tickers - try market cap ranking first, fall back to ticker_seed
storage_cfg = {
    'roots': {'bronze': f'{storage_path}/bronze', 'silver': f'{storage_path}/silver'},
    'tables': {
        'ticker_seed': {'rel': 'ticker_seed'},
        'securities_reference': {'rel': 'securities_reference'},
        'securities_prices_daily': {'rel': 'securities_prices_daily'}
    }
}

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
engine = create_engine(
    provider=provider,
    storage_cfg=storage_cfg,
    spark=spark
)

# Ingest prices and reference data
data_types = [DataType.PRICES, DataType.REFERENCE]
results = engine.run(tickers, data_types)

logger.info(f'Ingestion complete. Success: {results.success_count}, Failed: {results.failure_count}')
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
[ "$SKIP_SEED" = false ] && echo "  ✓ Tickers seeded"
[ "$SKIP_INGEST" = false ] && echo "  ✓ Bronze data ingested"
[ "$SKIP_SILVER" = false ] && echo "  ✓ Silver models built"
echo ""
