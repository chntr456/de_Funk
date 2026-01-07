# Proposal 011: Pipeline Orchestration - IngestorEngine Architecture

**Status**: Implemented (January 2026)
**Author**: de_Funk Team
**Date**: December 2025 (Updated January 2026)
**Priority**: High

---

## Executive Summary

This document describes the **IngestorEngine paradigm** for data ingestion in de_Funk. This is the canonical reference for:
1. Understanding how the ingestion pipeline works
2. Adding new endpoints to existing providers
3. Creating new data providers
4. Troubleshooting ingestion issues

The architecture is now fully implemented and running on the Spark cluster.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           INGESTION FLOW                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌───────────┐ │
│  │  Provider    │───►│   Facets     │───►│ IngestorEngine│───►│ BronzeSink│ │
│  │ (API client) │    │ (normalize)  │    │ (orchestrate) │    │ (Delta)   │ │
│  └──────────────┘    └──────────────┘    └──────────────┘    └───────────┘ │
│         │                   │                   │                  │        │
│         ▼                   ▼                   ▼                  ▼        │
│   ┌──────────┐       ┌──────────┐       ┌──────────┐       ┌──────────┐    │
│   │ HttpClient│       │  Schema  │       │  Batch   │       │  Delta   │    │
│   │ KeyPool  │       │ Transform│       │ Progress │       │  Tables  │    │
│   │ Registry │       │  Filter  │       │ Metrics  │       │ Compact  │    │
│   └──────────┘       └──────────┘       └──────────┘       └──────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| **BaseProvider** | `datapipelines/base/provider.py` | Abstract interface for all data providers |
| **IngestorEngine** | `datapipelines/base/ingestor_engine.py` | Generic orchestrator for batch ingestion |
| **BronzeSink** | `datapipelines/ingestors/bronze_sink.py` | Writes to Delta Lake with upsert/append |
| **Facets** | `datapipelines/providers/{provider}/facets/` | Transform raw API data to Spark DataFrames |
| **HttpClient** | `datapipelines/base/http_client.py` | Rate-limited HTTP client with retries |
| **ApiKeyPool** | `datapipelines/base/key_pool.py` | Rotating API key pool with cooldowns |
| **MetricsCollector** | `datapipelines/base/metrics.py` | Performance timing and reporting |
| **BatchProgressTracker** | `datapipelines/base/progress_tracker.py` | Real-time progress display |

---

## Configuration Files Reference

### 1. API Endpoints: `configs/pipelines/alpha_vantage_endpoints.json`

Defines all Alpha Vantage API endpoints.

```json
{
  "credentials": {
    "api_keys": [],
    "comment": "Set ALPHA_VANTAGE_API_KEYS environment variable"
  },
  "base_urls": {
    "core": "https://www.alphavantage.co/query"
  },
  "rate_limit_per_sec": 1.0,
  "endpoints": {
    "endpoint_name": {
      "base": "core",
      "method": "GET",
      "required_params": ["symbol"],
      "default_query": {
        "function": "FUNCTION_NAME"
      },
      "response_key": null,
      "comment": "Description"
    }
  }
}
```

### 2. Storage Configuration: `configs/storage.json`

**Single source of truth** for table definitions, partitions, and keys.

```json
{
  "defaults": { "format": "delta" },
  "roots": {
    "bronze": "storage/bronze",
    "silver": "storage/silver"
  },
  "tables": {
    "table_name": {
      "root": "bronze",
      "rel": "relative/path",
      "partitions": ["partition_col"],
      "write_strategy": "upsert|append",
      "key_columns": ["key_col1", "key_col2"],
      "date_column": "date_col_for_append",
      "comment": "Description"
    }
  }
}
```

### 3. Run Profiles: `configs/pipelines/run_config.json`

Controls pipeline execution parameters.

```json
{
  "profiles": {
    "quick_test": { "max_tickers": 5, "with_financials": false },
    "dev": { "max_tickers": 50, "with_financials": false },
    "staging": { "max_tickers": 500, "with_financials": true },
    "production": { "max_tickers": null, "with_financials": true }
  },
  "defaults": {
    "storage_path": "/shared/storage",
    "batch_size": 20
  }
}
```

---

## Step-by-Step: Adding a New Endpoint

Follow these steps to add a new data endpoint (e.g., ETF holdings, options data, or new financial statement type).

### Step 1: Add Endpoint to API Config

**File:** `configs/pipelines/alpha_vantage_endpoints.json`

Add the new endpoint definition:

```json
{
  "endpoints": {
    "etf_profile": {
      "base": "core",
      "method": "GET",
      "path_template": "",
      "required_params": ["symbol"],
      "default_query": {
        "function": "ETF_PROFILE"
      },
      "response_key": null,
      "default_path_params": {},
      "comment": "ETF profile including holdings, sector weights, expense ratio, AUM."
    }
  }
}
```

### Step 2: Add Table to Storage Config

**File:** `configs/storage.json`

Add the Bronze table definition:

```json
{
  "tables": {
    "etf_profiles": {
      "root": "bronze",
      "rel": "etf_profiles",
      "partitions": [],
      "write_strategy": "upsert",
      "key_columns": ["ticker"],
      "comment": "Alpha Vantage ETF_PROFILE"
    }
  }
}
```

**Important fields:**
- `write_strategy`: Use `"upsert"` for mutable data, `"append"` for immutable time-series
- `key_columns`: Columns that uniquely identify a row (for deduplication/updates)
- `partitions`: Partition columns (improves query performance for large tables)
- `date_column`: Required if using `"append"` strategy

### Step 3: Add DataType Enum

**File:** `datapipelines/base/provider.py`

Add the new data type:

```python
class DataType(Enum):
    """Standard data types supported by providers."""
    REFERENCE = "reference"
    PRICES = "prices"
    INCOME_STATEMENT = "income"
    BALANCE_SHEET = "balance"
    CASH_FLOW = "cashflow"
    EARNINGS = "earnings"
    OPTIONS = "options"
    ETF_PROFILE = "etf_profile"  # <-- NEW
```

### Step 4: Create Facet Class

**File:** `datapipelines/providers/alpha_vantage/facets/etf_profile_facet.py`

Create a new facet to transform API response to Spark DataFrame:

```python
"""
ETFProfileFacet - Alpha Vantage ETF profile facet.

Maps Alpha Vantage ETF_PROFILE endpoint to Bronze schema.
Bronze table: bronze/etf_profiles/
"""

from __future__ import annotations
from typing import List
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, lit, current_timestamp
from datapipelines.providers.alpha_vantage.facets.alpha_vantage_base_facet import (
    AlphaVantageFacet, safe_double, safe_long
)


class ETFProfileFacet(AlphaVantageFacet):
    """
    ETF profile data from Alpha Vantage ETF_PROFILE endpoint.
    """

    name = "etf_profiles"

    # Output schema - define all columns you want in Bronze
    OUTPUT_SCHEMA = [
        ("ticker", "string"),
        ("fund_name", "string"),
        ("description", "string"),
        ("expense_ratio", "double"),
        ("net_assets", "double"),
        ("nav", "double"),
        ("pe_ratio", "double"),
        ("dividend_yield", "double"),
        ("snapshot_date", "date"),
        ("ingestion_timestamp", "timestamp"),
    ]

    def __init__(self, spark: SparkSession, *, ticker: str):
        """
        Initialize ETF profile facet.

        Args:
            spark: SparkSession
            ticker: ETF ticker symbol
        """
        super().__init__(spark, tickers=[ticker])
        self.ticker = ticker

    def normalize(self, raw_data: dict):
        """
        Normalize ETF_PROFILE API response to Spark DataFrame.

        Args:
            raw_data: Raw API response dict

        Returns:
            Spark DataFrame with normalized data
        """
        from datetime import datetime

        if not raw_data:
            return None

        # Map API fields to our schema
        # (Check Alpha Vantage docs for actual field names)
        row = {
            "ticker": self.ticker,
            "fund_name": raw_data.get("fund_family"),
            "description": raw_data.get("fund_description"),
            "expense_ratio": safe_double(raw_data.get("expense_ratio")),
            "net_assets": safe_double(raw_data.get("net_assets")),
            "nav": safe_double(raw_data.get("nav")),
            "pe_ratio": safe_double(raw_data.get("pe_ratio")),
            "dividend_yield": safe_double(raw_data.get("dividend_yield")),
            "snapshot_date": datetime.now().date(),
            "ingestion_timestamp": datetime.now(),
        }

        # Create single-row DataFrame
        df = self.spark.createDataFrame([row])

        return df

    def validate(self, df):
        """Validate the output DataFrame."""
        # Check for null tickers
        null_tickers = df.filter(col("ticker").isNull()).count()
        if null_tickers > 0:
            raise ValueError(f"Found {null_tickers} rows with null ticker")
        return df
```

### Step 5: Export Facet in `__init__.py`

**File:** `datapipelines/providers/alpha_vantage/facets/__init__.py`

Add the import:

```python
from datapipelines.providers.alpha_vantage.facets.etf_profile_facet import ETFProfileFacet

__all__ = [
    # ... existing exports ...
    "ETFProfileFacet",
]
```

### Step 6: Update Provider Mappings

**File:** `datapipelines/providers/alpha_vantage/provider.py`

Add mappings for the new data type:

```python
class AlphaVantageProvider(BaseProvider):

    # Add endpoint mapping
    ENDPOINT_MAP = {
        # ... existing mappings ...
        DataType.ETF_PROFILE: "etf_profile",
    }

    # Add response key (null if top-level, or string if nested)
    RESPONSE_KEYS = {
        # ... existing mappings ...
        DataType.ETF_PROFILE: None,  # Top-level response
    }

    # Add Bronze table name
    TABLE_NAMES = {
        # ... existing mappings ...
        DataType.ETF_PROFILE: "etf_profiles",
    }

    # Add key columns for upsert
    KEY_COLUMNS = {
        # ... existing mappings ...
        DataType.ETF_PROFILE: ["ticker"],
    }
```

### Step 7: Add Normalization Logic

**File:** `datapipelines/providers/alpha_vantage/provider.py`

In the `normalize_data()` method, add handling for the new type:

```python
def normalize_data(
    self,
    ticker_data: TickerData,
    data_type: DataType
) -> Optional[Any]:
    """Normalize raw data to Spark DataFrame."""
    from datapipelines.providers.alpha_vantage.facets import (
        # ... existing imports ...
        ETFProfileFacet,
    )

    ticker = ticker_data.ticker

    try:
        # ... existing handlers ...

        elif data_type == DataType.ETF_PROFILE:
            # Get raw data (stored in appropriate TickerData field)
            raw = getattr(ticker_data, 'etf_profile', None)
            if raw:
                facet = ETFProfileFacet(self.spark, ticker=ticker)
                return facet.normalize(raw)

    except Exception as e:
        logger.warning(f"Failed to normalize {data_type.value} for {ticker}: {e}")

    return None
```

### Step 8: Update TickerData Class

**File:** `datapipelines/base/provider.py`

Add field to TickerData if needed:

```python
@dataclass
class TickerData:
    """All data fetched for a single ticker."""
    ticker: str
    reference: Optional[Any] = None
    prices: Optional[Any] = None
    income_statement: Optional[Any] = None
    balance_sheet: Optional[Any] = None
    cash_flow: Optional[Any] = None
    earnings: Optional[Any] = None
    options: Optional[Any] = None
    etf_profile: Optional[Any] = None  # <-- NEW
    errors: List[str] = field(default_factory=list)

    # Update attr_map in set_data() method
    def set_data(self, data_type: DataType, data: Any) -> None:
        attr_map = {
            # ... existing mappings ...
            DataType.ETF_PROFILE: 'etf_profile',
        }
```

### Step 9: Add to Supported Data Types

**File:** `datapipelines/providers/alpha_vantage/provider.py`

In `create_alpha_vantage_provider()`:

```python
def create_alpha_vantage_provider(
    alpha_vantage_cfg: Dict,
    spark=None
) -> AlphaVantageProvider:
    config = ProviderConfig(
        name="alpha_vantage",
        base_url="https://www.alphavantage.co/query",
        rate_limit=alpha_vantage_cfg.get("rate_limit_per_sec", 1.25),
        batch_size=20,
        credentials_env_var="ALPHA_VANTAGE_API_KEYS",
        supported_data_types=[
            DataType.REFERENCE,
            DataType.PRICES,
            DataType.INCOME_STATEMENT,
            DataType.BALANCE_SHEET,
            DataType.CASH_FLOW,
            DataType.EARNINGS,
            DataType.ETF_PROFILE,  # <-- NEW
        ]
    )
    # ...
```

### Step 10: Test the New Endpoint

```bash
# Test with a single ETF ticker
./scripts/test/test_pipeline.sh --profile quick_test --max-tickers 1
```

Or in Python:

```python
from datapipelines.providers.alpha_vantage.provider import create_alpha_vantage_provider
from datapipelines.base.ingestor_engine import IngestorEngine
from datapipelines.base.provider import DataType

provider = create_alpha_vantage_provider(config, spark=spark)
engine = IngestorEngine(provider, storage_cfg)

results = engine.run(
    tickers=["SPY", "QQQ", "IWM"],
    data_types=[DataType.ETF_PROFILE],
    batch_size=5
)
```

---

## Checklist: Adding a New Endpoint

Use this checklist when adding new endpoints:

```
[ ] 1. configs/pipelines/alpha_vantage_endpoints.json
      - Add endpoint definition with function, params, response_key

[ ] 2. configs/storage.json
      - Add table with rel path, partitions, key_columns, write_strategy

[ ] 3. datapipelines/base/provider.py
      - Add DataType enum value
      - Add field to TickerData dataclass
      - Update set_data() attr_map

[ ] 4. datapipelines/providers/alpha_vantage/facets/{name}_facet.py
      - Create facet class with OUTPUT_SCHEMA
      - Implement normalize() method
      - Implement validate() method

[ ] 5. datapipelines/providers/alpha_vantage/facets/__init__.py
      - Export the new facet

[ ] 6. datapipelines/providers/alpha_vantage/provider.py
      - Add to ENDPOINT_MAP
      - Add to RESPONSE_KEYS
      - Add to TABLE_NAMES
      - Add to KEY_COLUMNS
      - Add handler in normalize_data()
      - Add to supported_data_types in create_alpha_vantage_provider()

[ ] 7. Test the endpoint
      - Run with single ticker first
      - Verify data in Bronze layer
      - Check Delta table structure
```

---

## Pipeline Execution Flow

### 1. Seed Tickers (Optional First Run)

```bash
./scripts/test/test_pipeline.sh --profile dev
```

Calls:
- `provider.seed_tickers()` → fetches LISTING_STATUS CSV (1 API call)
- Writes to `bronze/ticker_seed/`

### 2. Bronze Ingestion

```python
engine = IngestorEngine(provider, storage_cfg)
results = engine.run(tickers, data_types, batch_size=20)
```

Flow:
1. **Batch Loop**: Process tickers in batches of 20
2. **Fetch**: Call API for each ticker/data_type combo
3. **Normalize**: Transform via Facet to Spark DataFrame
4. **Accumulate**: Collect DataFrames in memory
5. **Write Batch**: Write to Delta using BronzeSink
6. **Clear**: Free memory, GC
7. **Compact**: After all batches, run Delta OPTIMIZE

### 3. Compaction Strategy

**Current behavior:** Compaction runs ONCE after ALL batches complete.

```python
# In IngestorEngine.run():
if auto_compact and results.tables_written:
    self._compact_tables(results.tables_written, silent)
```

**Why after all batches?**
- Compaction (OPTIMIZE) is expensive I/O
- Running once at end minimizes overhead
- For production, set `auto_compact=False` and schedule separately

### 4. Write Strategies

| Strategy | Use Case | Method |
|----------|----------|--------|
| `upsert` | Reference data that changes | `BronzeSink.upsert()` |
| `append` | Immutable time-series | `BronzeSink.append_immutable()` |
| `overwrite` | Full table replacement | `BronzeSink.write(mode="overwrite")` |

Configured in `storage.json` per table:
```json
"securities_prices_daily": {
  "write_strategy": "append",
  "key_columns": ["ticker", "trade_date"],
  "date_column": "trade_date"
}
```

---

## Currently Implemented Endpoints

| Endpoint | DataType | Bronze Table | Status |
|----------|----------|--------------|--------|
| LISTING_STATUS | seed | ticker_seed | ✅ Working |
| COMPANY_OVERVIEW | REFERENCE | securities_reference, company_reference | ✅ Working |
| TIME_SERIES_DAILY_ADJUSTED | PRICES | securities_prices_daily | ✅ Working |
| INCOME_STATEMENT | INCOME_STATEMENT | income_statements | ✅ Working |
| BALANCE_SHEET | BALANCE_SHEET | balance_sheets | ✅ Working |
| CASH_FLOW | CASH_FLOW | cash_flows | ✅ Working |
| EARNINGS | EARNINGS | earnings | ✅ Working |
| HISTORICAL_OPTIONS | OPTIONS | historical_options | Partial |
| ETF_PROFILE | ETF_PROFILE | etf_profiles | Not started |

---

## Running the Pipeline

### Quick Test (5 tickers, prices only)
```bash
./scripts/test/test_pipeline.sh --profile quick_test
```

### Development (50 tickers, prices only)
```bash
./scripts/test/test_pipeline.sh --profile dev
```

### Development with Financials
```bash
./scripts/test/test_pipeline.sh --profile dev --with-financials
```

### Production (all tickers)
```bash
./scripts/test/test_pipeline.sh --profile production
```

### Skip Steps
```bash
# Skip seeding (use existing tickers)
./scripts/test/test_pipeline.sh --skip-seed

# Bronze only (skip Silver build)
./scripts/test/test_pipeline.sh --skip-silver

# Silver only (skip ingestion)
./scripts/test/test_pipeline.sh --skip-ingest
```

---

## Troubleshooting

### API Rate Limits
```
Error: API limit reached
```
- Check `rate_limit_per_sec` in `alpha_vantage_endpoints.json`
- Free tier: 5 calls/min (0.08/sec)
- Premium: 75 calls/min (1.25/sec)

### Missing Tickers
```
Error: No tickers found
```
- Run seed first: `./scripts/test/test_pipeline.sh` (without --skip-seed)
- Check `bronze/ticker_seed/` exists

### Schema Mismatch
```
Error: Cannot merge schema
```
- Facet output schema doesn't match existing table
- Either update facet to match, or delete existing table

### Partition Mismatch
```
Error: Partition columns don't match
```
- Partitions are defined in `storage.json`
- Delete existing table if partitions changed

---

## Session Summary (January 2026)

### What Was Done

1. **IngestorEngine Implementation**
   - Generic provider-agnostic orchestrator
   - Batch processing with configurable size (default: 20)
   - Progress tracking with real-time display
   - Performance metrics collection

2. **Compaction Strategy**
   - Delta OPTIMIZE runs after all batches complete
   - Controlled by `auto_compact` parameter (default: True)
   - For production: set `auto_compact=False`, schedule compaction separately

3. **Configuration Consolidation**
   - `storage.json` is single source of truth for partitions
   - Provider no longer hardcodes partition columns
   - All table configs centralized

4. **Financial Statement Endpoints**
   - Added: income_statement, balance_sheet, cash_flow, earnings
   - Registry pattern for endpoint consolidation

5. **Test Pipeline Script**
   - Unified `test_pipeline.sh` with profile support
   - Options for skipping steps, selecting data types
   - Automatic environment variable loading

### Files Changed

| File | Change |
|------|--------|
| `datapipelines/base/ingestor_engine.py` | Core orchestration engine |
| `datapipelines/base/provider.py` | BaseProvider interface with DataType enum |
| `datapipelines/ingestors/bronze_sink.py` | Delta Lake writes with upsert/append |
| `datapipelines/providers/alpha_vantage/provider.py` | AlphaVantageProvider implementation |
| `datapipelines/providers/alpha_vantage/facets/*.py` | Normalization facets |
| `configs/storage.json` | Table configurations |
| `configs/pipelines/alpha_vantage_endpoints.json` | API endpoints |
| `scripts/test/test_pipeline.sh` | Unified test script |

---

## Next Steps

1. **Add ETF_PROFILE endpoint** - Follow step-by-step guide above
2. **Add REALTIME_OPTIONS endpoint** - For options data
3. **Create BLS provider** - Economic data (unemployment, CPI)
4. **Create Chicago provider** - Municipal data
5. **Scheduled compaction** - Separate compaction job for production

---

**For questions or issues, check the logs at `logs/de_funk.log`**
