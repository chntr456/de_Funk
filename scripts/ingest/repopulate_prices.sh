#!/bin/bash
# ==============================================================================
# Repopulate Alpha Vantage Time Series Daily Adjusted
# ==============================================================================
# Fetches historical price data for all tickers in listing_status.
# Uses append strategy to preserve existing data.
#
# Usage:
#   ./scripts/ingest/repopulate_prices.sh [--max-tickers N]
#
# Examples:
#   ./scripts/ingest/repopulate_prices.sh                    # All tickers
#   ./scripts/ingest/repopulate_prices.sh --max-tickers 100  # First 100
# ==============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Defaults
MAX_TICKERS=""
STORAGE_PATH="/shared/storage"

# Parse args
while [[ $# -gt 0 ]]; do
    case $1 in
        --max-tickers)
            MAX_TICKERS="$2"
            shift 2
            ;;
        --storage-path)
            STORAGE_PATH="$2"
            shift 2
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Determine repo root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

# Source .env
if [ -f "$REPO_ROOT/.env" ]; then
    set -a
    source "$REPO_ROOT/.env"
    set +a
fi

echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}Repopulate Alpha Vantage Prices${NC}"
echo -e "${BLUE}============================================================${NC}"
echo -e "Storage path: ${GREEN}$STORAGE_PATH${NC}"
echo -e "Max tickers: ${GREEN}${MAX_TICKERS:-ALL}${NC}"
echo ""

python3 -c "
import sys
sys.path.insert(0, '$REPO_ROOT')

from config.logging import setup_logging, get_logger
setup_logging()
logger = get_logger('repopulate_prices')

from datapipelines.base.ingestor_engine import IngestorEngine
from datapipelines.providers.alpha_vantage.alpha_vantage_provider import create_alpha_vantage_provider
from datapipelines.ingestors.bronze_sink import BronzeSink
from orchestration.common.spark_session import get_spark
from pathlib import Path
import json

storage_path = '$STORAGE_PATH'
max_tickers_str = '${MAX_TICKERS}'
max_tickers = int(max_tickers_str) if max_tickers_str.strip() else None

logger.info(f'Storage path: {storage_path}')
logger.info(f'Max tickers: {max_tickers if max_tickers else \"ALL\"}')

# Initialize Spark
spark = get_spark(app_name='repopulate_prices')

# Load configs
with open('$REPO_ROOT/configs/storage.json') as f:
    storage_cfg = json.load(f)
storage_cfg['roots'] = {k: v.replace('storage/', f'{storage_path}/') for k, v in storage_cfg['roots'].items()}

docs_path = Path('$REPO_ROOT')

# Create provider
provider = create_alpha_vantage_provider(spark=spark, docs_path=docs_path)

# Get tickers from listing_status
listing_status_path = Path(storage_path) / 'bronze' / 'alpha_vantage' / 'listing_status'
if not listing_status_path.exists():
    logger.error('listing_status not found. Run: ./scripts/test/test_pipeline.sh --profile listing_status')
    sys.exit(1)

logger.info('Loading tickers from listing_status...')
if (listing_status_path / '_delta_log').exists():
    tickers_df = spark.read.format('delta').load(str(listing_status_path))
else:
    tickers_df = spark.read.parquet(str(listing_status_path))

# Get distinct tickers
ticker_list = [row.ticker for row in tickers_df.select('ticker').distinct().collect()]
logger.info(f'Found {len(ticker_list)} tickers in listing_status')

# Apply limit if specified
if max_tickers:
    ticker_list = ticker_list[:max_tickers]
    logger.info(f'Limited to {len(ticker_list)} tickers')

# Set tickers on provider
provider.set_tickers(ticker_list)

# Create engine with async writes disabled for stability
engine = IngestorEngine(provider, storage_cfg, max_pending_writes=0)

# Run prices ingestion only
logger.info('Starting prices ingestion (write_strategy=append)...')
results = engine.run(
    work_items=['prices'],
    write_batch_size=100000,
    silent=False
)

logger.info(f'Ingestion complete!')
logger.info(f'  Completed: {results.completed_work_items}/{results.total_work_items}')
logger.info(f'  Records: {results.total_records:,}')

# Show final count
prices_path = Path(storage_path) / 'bronze' / 'alpha_vantage' / 'time_series_daily_adjusted'
if prices_path.exists() and (prices_path / '_delta_log').exists():
    final_df = spark.read.format('delta').load(str(prices_path))
    logger.info(f'  Total rows in table: {final_df.count():,}')

spark.stop()
"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Prices repopulation completed${NC}"
else
    echo -e "${RED}✗ Prices repopulation failed${NC}"
    exit 1
fi
