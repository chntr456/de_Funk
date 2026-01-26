# Data Pipelines

**ETL pipeline system for data ingestion**

---

## Overview

de_Funk's pipeline architecture orchestrates data ingestion from external APIs to the Bronze layer using a three-component pattern:

```
Provider → Ingestor → Facet → Bronze (Parquet)
```

---

## Documents

| Document | Description |
|----------|-------------|
| [Pipeline Architecture](pipeline-architecture.md) | System overview |
| [Facet System](facet-system.md) | Data normalization framework |
| [Ingestors](ingestors.md) | Orchestration components |
| [Providers](providers.md) | API client implementations |

---

## Architecture

```
┌──────────────┐
│  API Client  │  ← HTTP requests to external APIs
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   Provider   │  ← API-specific logic (auth, endpoints)
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   Ingestor   │  ← Orchestrates fetching + writing
└──────┬───────┘
       │
       ▼
┌──────────────┐
│    Facet     │  ← Normalizes JSON to DataFrame
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Bronze Layer │  ← Partitioned Parquet files
└──────────────┘
```

---

## Components

### Providers

**Purpose**: API-specific data fetching

**Location**: `datapipelines/providers/{provider}/`

| Provider | API | Data |
|----------|-----|------|
| `alpha_vantage/` | Alpha Vantage | Stock prices, fundamentals |
| `bls/` | Bureau of Labor Statistics | Economic indicators |
| `chicago/` | Chicago Data Portal | Municipal finance |

### Facets

**Purpose**: Normalize raw JSON to type-safe DataFrames

**Key Features**:
- Schema normalization
- Type coercion
- Column mapping
- Derived columns

### Ingestors

**Purpose**: Orchestrate fetching and writing

**Responsibilities**:
- Call provider to fetch data
- Pass data to facet for normalization
- Write to Bronze layer
- Handle errors and retries

---

## Bronze Layer Output

```
storage/bronze/
├── alpha_vantage/
│   ├── securities_reference/     # Ticker reference data
│   │   └── snapshot_dt=YYYY-MM-DD/
│   │       └── asset_type=stocks/*.parquet
│   └── securities_prices_daily/  # Daily OHLCV
│       └── trade_date=YYYY-MM-DD/
│           └── asset_type=stocks/*.parquet
├── bls/
│   └── unemployment/*.parquet
└── chicago/
    └── building_permits/*.parquet
```

---

## Running Pipelines

```bash
# Full pipeline (recommended)
python -m scripts.ingest.run_full_pipeline --top-n 100

# Specific provider
python -m scripts.ingest.ingest_alpha_vantage_bulk

# Bronze pull only
python -m scripts.ingest.Bronze_pull
```

---

## Related Documentation

- [Data Providers](../03-data-providers/) - Provider terms of use
- [Scripts Reference](../08-scripts-reference/) - Pipeline scripts
- [Configuration](../11-configuration/) - API configuration
