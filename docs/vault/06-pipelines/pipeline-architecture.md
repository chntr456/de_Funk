# Pipeline Architecture

**ETL pipeline system for Bronze layer ingestion**

Files: `datapipelines/`, `orchestration/`

---

## Overview

de_Funk's pipeline architecture orchestrates data ingestion from external APIs to the Bronze layer using a three-component pattern:

```
Provider → Ingestor → Facet → Bronze (Parquet)
```

**Design Philosophy**: Separate concerns - **Providers** fetch data, **Facets** normalize it, **Ingestors** orchestrate the process.

---

## Architecture

```
┌──────────────┐
│  API Client  │  ← HTTP requests
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   Provider   │  ← API-specific logic
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   Ingestor   │  ← Orchestrates fetching
└──────┬───────┘
       │
       ▼
┌──────────────┐
│    Facet     │  ← Normalizes to DataFrame
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Bronze Layer │  ← Parquet files
└──────────────┘
```

---

## Components

### 1. Providers

**Purpose**: API-specific data fetching logic

**Location**: `datapipelines/providers/{provider_name}/`

**Examples**:
- `alpha_vantage/` - Stock market data (Alpha Vantage - sole securities provider v2.0+)
- `bls/` - Economic data (Bureau of Labor Statistics)
- `chicago/` - Municipal data (Chicago Data Portal)

> **Note**: Polygon.io was removed in v2.0. Alpha Vantage is the exclusive securities provider.

**Implementation**:
```python
class AlphaVantageIngestor:
    def __init__(self, spark, storage_cfg):
        self.spark = spark
        self.sink = BronzeSink(storage_cfg)

    def run_comprehensive(self, tickers, from_date, max_tickers):
        # Comprehensive ingestion with prices & fundamentals
        return results
```

---

### 2. Facets

**Purpose**: Normalize raw JSON to type-safe DataFrames

**Location**: `datapipelines/facets/`

**Key Features**:
- Schema normalization
- Type coercion (prevent int/float/string mismatches)
- Column mapping
- Derived columns

**See**: [Facet System](facet-system.md) for complete documentation

---

### 3. Ingestors

**Purpose**: Orchestrate fetching and writing

**Location**: `datapipelines/ingestors/`

**Responsibilities**:
- Call provider to fetch data
- Pass data to facet for normalization
- Write to Bronze layer (Delta Lake v2.3+)
- Handle errors and retries

**See**: [Ingestors](ingestors.md) for details

---

## Data Flow

```
1. Run ingestor
   ↓
2. Ingestor calls facet.calls() → API call specs
   ↓
3. Ingestor calls provider.fetch() → Raw JSON batches
   ↓
4. Ingestor calls facet.normalize() → Clean DataFrame
   ↓
5. Write DataFrame to Bronze (Delta Lake)
   ↓
6. Bronze → Silver (model build process)
```

---

## Configuration

### API Endpoints

**Files**: `configs/*_endpoints.json`

**Example** (`alpha_vantage_endpoints.json`):
```json
{
  "base_urls": {"core": "https://www.alphavantage.co"},
  "endpoints": {
    "time_series_daily_adjusted": {
      "base": "core",
      "path_template": "/query",
      "method": "GET",
      "required_params": ["symbol"],
      "default_query": {"function": "TIME_SERIES_DAILY_ADJUSTED"}
    }
  }
}
```

### Storage Paths

**File**: `configs/storage.json`

```json
{
  "roots": {"bronze": "storage/bronze"},
  "defaults": {"format": "delta"},
  "tables": {
    "securities_prices_daily": {
      "rel": "securities_prices_daily",
      "partitions": ["asset_type", "year", "month"]
    }
  }
}
```

---

## Pipeline Execution

### Full Pipeline

```bash
# Run all providers
python run_full_pipeline.py --top-n 100
```

### Single Provider

```python
from datapipelines.providers.alpha_vantage.alpha_vantage_ingestor import AlphaVantageIngestor

ingestor = AlphaVantageIngestor(spark, storage_cfg)
ingestor.run_comprehensive(tickers=['AAPL', 'MSFT'], from_date='2024-01-01')
```

---

## Bronze Layer Output

**Format**: Delta Lake tables (v2.3+) with schema evolution

**Structure**:
```
storage/bronze/
├── securities_reference/      # Unified reference data (v2.0+)
│   └── _delta_log/
├── securities_prices_daily/   # Unified OHLCV prices (v2.0+)
│   └── _delta_log/
├── income_statements/         # Fundamentals
├── balance_sheets/
├── cash_flows/
├── earnings/
├── bls/
│   └── unemployment/
└── chicago/
    └── building_permits/
```

---

## Error Handling

**Retry Logic**: Exponential backoff for transient errors

**Rate Limiting**: Respect API rate limits (configured per provider)

**Partial Failures**: Continue processing remaining batches if one fails

---

## Related Documentation

- [Facet System](facet-system.md) - Data normalization
- [Ingestors](ingestors.md) - Orchestration logic
- [Providers](providers.md) - Provider implementations
- [Bronze Layer](../CLAUDE.md#bronze-layer-raw-data) - Storage details
