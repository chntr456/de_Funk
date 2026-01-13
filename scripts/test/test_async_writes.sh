#!/bin/bash
#
# Test Async Writes Performance
#
# Compares async vs sync write performance using the Chicago provider.
# Runs both modes and reports throughput difference.
#
# Usage:
#   ./scripts/test/test_async_writes.sh [--endpoints N]
#
# Options:
#   --endpoints N    Number of endpoints to test (default: 3)
#
# Example:
#   ./scripts/test/test_async_writes.sh --endpoints 5

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Defaults
NUM_ENDPOINTS=3
MAX_RECORDS=50000

# Parse args
while [[ $# -gt 0 ]]; do
    case $1 in
        --endpoints)
            NUM_ENDPOINTS="$2"
            shift 2
            ;;
        --max-records)
            MAX_RECORDS="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Get repo root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}     Async Writes Performance Test                          ${NC}"
echo -e "${BLUE}============================================================${NC}"
echo ""
echo "Configuration:"
echo "  Endpoints: $NUM_ENDPOINTS"
echo "  Max records per endpoint: $MAX_RECORDS"
echo ""

# Run benchmark
python3 -c "
import sys
sys.path.insert(0, '$REPO_ROOT')

from config.logging import setup_logging, get_logger
setup_logging()
logger = get_logger('test_async_writes')

import json
import time
from pathlib import Path

from datapipelines.base.ingestor_engine import IngestorEngine, create_engine
from datapipelines.providers.chicago.chicago_provider import create_chicago_provider
from orchestration.common.spark_session import get_spark

# Config
storage_path = '${STORAGE_PATH:-/shared/storage}'
docs_path = Path('$REPO_ROOT/Documents')
num_endpoints = $NUM_ENDPOINTS
max_records = $MAX_RECORDS

# Load storage config
with open('$REPO_ROOT/configs/storage.json') as f:
    storage_cfg = json.load(f)
storage_cfg['roots'] = {k: v.replace('storage/', f'{storage_path}/') for k, v in storage_cfg['roots'].items()}

# Initialize Spark
spark = get_spark(app_name='test_async_writes')

# Create provider
provider = create_chicago_provider(spark=spark, docs_path=docs_path)

# Get first N endpoints
all_endpoints = provider.list_work_items(status='active')
test_endpoints = all_endpoints[:num_endpoints]
print(f'Testing endpoints: {test_endpoints}')
print()

# Test 1: Async writes (default)
print('=' * 60)
print('TEST 1: ASYNC WRITES (fetch + write overlap)')
print('=' * 60)

engine_async = IngestorEngine(
    provider, storage_cfg,
    max_pending_writes=3,
    writer_threads=2
)

start_async = time.time()
results_async = engine_async.run(
    work_items=test_endpoints,
    write_batch_size=10000,
    max_records=max_records,
    async_writes=True,
    silent=False
)
async_time = time.time() - start_async
async_throughput = results_async.total_records / async_time if async_time > 0 else 0

# Test 2: Sync writes (for comparison)
print()
print('=' * 60)
print('TEST 2: SYNC WRITES (sequential fetch-write)')
print('=' * 60)

engine_sync = IngestorEngine(provider, storage_cfg)

start_sync = time.time()
results_sync = engine_sync.run(
    work_items=test_endpoints,
    write_batch_size=10000,
    max_records=max_records,
    async_writes=False,
    silent=False
)
sync_time = time.time() - start_sync
sync_throughput = results_sync.total_records / sync_time if sync_time > 0 else 0

# Shutdown executor
IngestorEngine.shutdown_executor()

# Print comparison
print()
print('=' * 60)
print('PERFORMANCE COMPARISON')
print('=' * 60)
print(f'  Async writes:')
print(f'    Time: {async_time:.1f}s')
print(f'    Records: {results_async.total_records:,}')
print(f'    Throughput: {async_throughput:,.0f} records/sec')
print()
print(f'  Sync writes:')
print(f'    Time: {sync_time:.1f}s')
print(f'    Records: {results_sync.total_records:,}')
print(f'    Throughput: {sync_throughput:,.0f} records/sec')
print()

if async_throughput > sync_throughput:
    speedup = async_throughput / sync_throughput if sync_throughput > 0 else 0
    print(f'  Async is {speedup:.1f}x faster!')
else:
    print(f'  Sync was faster (may happen with small datasets)')

print('=' * 60)

spark.stop()
"

echo ""
echo -e "${GREEN}✓ Async writes benchmark complete${NC}"
