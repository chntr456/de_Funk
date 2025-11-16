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
- `polygon/` - Stock market data (Polygon.io)
- `bls/` - Economic data (Bureau of Labor Statistics)
- `chicago/` - Municipal data (Chicago Data Portal)

**Implementation**:
```python
class PolygonProvider:
    def __init__(self, api_keys):
        self.client = HttpClient(api_keys)

    def fetch_prices(self, tickers, date_from, date_to):
        # API-specific fetching logic
        return raw_responses
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
- Write to Bronze layer (Parquet)
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
5. Write DataFrame to Bronze (Parquet)
   ↓
6. Bronze → Silver (model build process)
```

---

## Configuration

### API Endpoints

**Files**: `configs/*_endpoints.json`

**Example** (`polygon_endpoints.json`):
```json
{
  "base_url": "https://api.polygon.io",
  "endpoints": {
    "prices_daily": {
      "path": "/v2/aggs/ticker/{ticker}/range/{mult}/{timespan}/{from}/{to}",
      "method": "GET",
      "rate_limit": {"calls": 5, "period": 60}
    }
  }
}
```

### Storage Paths

**File**: `configs/storage.json`

```json
{
  "bronze_root": "storage/bronze",
  "tables": {
    "polygon_daily_prices": {
      "path": "polygon/daily_prices",
      "partition_by": ["dt"]
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
from datapipelines.ingestors.polygon_ingestor import PolygonIngestor

ingestor = PolygonIngestor(spark, api_keys)
ingestor.run(tickers=['AAPL', 'MSFT'], date_from='2024-01-01')
```

---

## Bronze Layer Output

**Format**: Partitioned Parquet files

**Structure**:
```
storage/bronze/
├── polygon/
│   ├── daily_prices/
│   │   ├── dt=2024-01-01/*.parquet
│   │   └── dt=2024-01-02/*.parquet
│   └── ref_tickers/*.parquet
├── bls/
│   └── unemployment/*.parquet
└── chicago/
    └── building_permits/*.parquet
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
