# Ingestors

**Orchestration layer for data ingestion**

Files: `datapipelines/ingestors/`
Related: [Pipeline Architecture](pipeline-architecture.md), [Facet System](facet-system.md)

---

## Overview

**Ingestors** orchestrate the data ingestion process: they coordinate between Providers (API fetching) and Facets (data normalization) to write clean data to the Bronze layer.

**Design Pattern**: Orchestrator - coordinates but doesn't implement business logic

---

## Architecture

```
Ingestor
├── Uses Provider → Fetch raw data from API
├── Uses Facet → Normalize to DataFrame
└── Writes Bronze → Parquet files
```

**Responsibilities**:
1. Call facet to get API call specifications
2. Call provider to fetch data
3. Pass raw data to facet for normalization
4. Write normalized DataFrame to Bronze (Parquet)
5. Handle errors and retries

---

## Base Ingestor

**File**: `datapipelines/base/ingestor.py`

```python
class BaseIngestor(ABC):
    """Base class for all ingestors."""

    def __init__(self, spark, provider, storage_router):
        self.spark = spark
        self.provider = provider
        self.storage_router = storage_router

    def run(self, **params):
        """Main ingestion workflow."""
        # 1. Create facet
        facet = self.create_facet(**params)

        # 2. Get API call specs from facet
        calls = list(facet.calls())

        # 3. Fetch data via provider
        raw_batches = self.provider.fetch_batch(calls)

        # 4. Normalize via facet
        df = facet.normalize(raw_batches)

        # 5. Write to Bronze
        self.write_bronze(df, table_name)

    @abstractmethod
    def create_facet(self, **params):
        """Child ingestor implements to create specific facet."""
        pass
```

---

## Ingestor Implementations

### Alpha Vantage Ingestor

**File**: `datapipelines/ingestors/alpha_vantage_ingestor.py`

**Purpose**: Ingest stock market data from Alpha Vantage

**Tables Ingested**:
- `securities_prices_daily` - OHLCV data
- `securities_reference` - Ticker reference data with CIK

**Example**:
```python
from datapipelines.ingestors.alpha_vantage_ingestor import AlphaVantageIngestor

ingestor = AlphaVantageIngestor(spark, api_keys, storage_router)
ingestor.run(
    tickers=['AAPL', 'MSFT', 'GOOGL'],
    date_from='2024-01-01',
    date_to='2024-12-31'
)
```

---

### BLS Ingestor

**File**: `datapipelines/ingestors/bls_ingestor.py`

**Purpose**: Ingest economic data from Bureau of Labor Statistics

**Tables Ingested**:
- `bls_unemployment` - Unemployment rates
- `bls_cpi` - Consumer Price Index

---

### Chicago Ingestor

**File**: `datapipelines/ingestors/chicago_ingestor.py`

**Purpose**: Ingest municipal data from Chicago Data Portal

**Tables Ingested**:
- `chicago_unemployment` - Local unemployment
- `chicago_building_permits` - Building permits

---

## Ingestion Flow

```
1. User calls ingestor.run()
   ↓
2. Ingestor creates facet
   ↓
3. Facet.calls() → List of API call specs
   ↓
4. Provider.fetch_batch(calls) → Raw JSON batches
   ↓
5. Facet.normalize(batches) → Clean DataFrame
   ↓
6. Ingestor.write_bronze(df) → Parquet files
```

---

## Error Handling

**Retry Logic**:
```python
def fetch_with_retry(self, call_spec, max_retries=3):
    for attempt in range(max_retries):
        try:
            return self.provider.fetch(call_spec)
        except TransientError:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
            raise
```

**Partial Failures**:
- Continue processing remaining batches if one fails
- Log failures for manual review
- Write successful batches to Bronze

---

## Bronze Output

**Path Pattern**: `storage/bronze/{table}/`

**Partitioning**:
```python
# Partition by date and asset type
df.write.partitionBy('trade_date', 'asset_type').parquet(bronze_path)

# Result:
# storage/bronze/securities_prices_daily/
#   ├── asset_type=stocks/
#   │   ├── year=2024/
#   │   │   └── month=01/*.parquet
```

---

## Running Ingestors

### Via Script

```bash
# Full pipeline (all providers)
python run_full_pipeline.py --top-n 100

# Single provider
python scripts/run_alpha_vantage_ingestion.py --tickers AAPL,MSFT
```

### Programmatic

```python
from core.context import RepoContext
from datapipelines.ingestors.alpha_vantage_ingestor import AlphaVantageIngestor

ctx = RepoContext.from_repo_root()
ingestor = AlphaVantageIngestor(
    ctx.spark,
    ctx.alpha_vantage_cfg['api_keys'],
    ctx.storage_router
)

ingestor.run(
    tickers=['AAPL'],
    date_from='2024-01-01',
    date_to='2024-01-31'
)
```

---

## Related Documentation

- [Facet System](facet-system.md) - Data normalization
- [Providers](providers.md) - API clients
- [Pipeline Architecture](pipeline-architecture.md) - Overall design
- [Bronze Layer](../00-overview/architecture.md#bronze-layer-raw-data) - Storage details
