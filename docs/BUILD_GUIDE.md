# de_Funk Build Guide

**Comprehensive guide to building and maintaining de_Funk data models**

**Last Updated:** 2025-11-20
**Version:** 2.0 (Modular YAML Architecture + Alpha Vantage)

---

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Build Architecture](#build-architecture)
4. [Complete Build Reference](#complete-build-reference)
5. [Optimization Strategies](#optimization-strategies)
6. [Common Workflows](#common-workflows)
7. [Performance Tuning](#performance-tuning)
8. [Troubleshooting](#troubleshooting)
9. [Advanced Topics](#advanced-topics)

---

## Overview

The de_Funk build system orchestrates the complete ETL pipeline from raw API data (Bronze layer) to dimensional models (Silver layer).

### What is `build_all_models.py`?

The main orchestration script that:
- **Discovers** all configured models in `configs/models/`
- **Ingests** data from external APIs (Alpha Vantage, BLS, Chicago)
- **Transforms** bronze data into dimensional models (Silver layer)
- **Validates** data quality and model integrity
- **Reports** progress and results

### Architecture Layers

```
┌─────────────────────────────────────────────────────┐
│  EXTERNAL APIS                                      │
│  ├─ Alpha Vantage (securities)                     │
│  ├─ BLS (economic data)                            │
│  └─ Chicago Data Portal (municipal finance)        │
└──────────────────┬──────────────────────────────────┘
                   │ HTTP/REST APIs
                   ↓
┌─────────────────────────────────────────────────────┐
│  BRONZE LAYER (Raw Data - Parquet)                 │
│  ├─ storage/bronze/securities_reference/           │
│  ├─ storage/bronze/securities_prices_daily/        │
│  ├─ storage/bronze/calendar_seed/                  │
│  └─ storage/bronze/{provider}/{table}/             │
└──────────────────┬──────────────────────────────────┘
                   │ Facet Transformations
                   ↓
┌─────────────────────────────────────────────────────┐
│  SILVER LAYER (Dimensional Models - Parquet)       │
│  ├─ storage/silver/core/dims/dim_calendar          │
│  ├─ storage/silver/company/dims/dim_company        │
│  ├─ storage/silver/stocks/dims/dim_stock           │
│  ├─ storage/silver/stocks/facts/fact_stock_prices  │
│  └─ storage/silver/{model}/{dims|facts}/{table}    │
└──────────────────┬──────────────────────────────────┘
                   │ DuckDB Views
                   ↓
┌─────────────────────────────────────────────────────┐
│  ANALYTICS (DuckDB + Streamlit)                    │
│  ├─ Query interface (Universal Session)            │
│  ├─ Python measures (Sharpe, RSI, MACD)            │
│  └─ Interactive notebooks                          │
└─────────────────────────────────────────────────────┘
```

---

## Quick Start

### Prerequisites

1. **API Keys Configured** (`.env` file):
   ```bash
   ALPHA_VANTAGE_API_KEYS=your_key_here
   BLS_API_KEYS=your_key_here
   CHICAGO_API_KEYS=your_token_here
   ```

2. **Python Environment** with PySpark installed

3. **Storage Space**: ~500MB for Bronze, ~200MB for Silver (depends on universe size)

### Basic Commands

```bash
# 1. Full production build (all models, all data)
python -m scripts.build.build_all_models --date-from 2024-01-01

# 2. Development build (limited tickers, specific models)
python -m scripts.build.build_all_models \
  --models stocks company \
  --max-tickers 10 \
  --date-from 2025-01-01

# 3. Daily refresh (optimized - 50% faster)
python -m scripts.build.build_all_models \
  --date-from 2025-11-20 \
  --skip-reference-refresh \
  --outputsize compact

# 4. Rebuild Silver from existing Bronze (no API calls)
python -m scripts.build.build_all_models --skip-ingestion
```

---

## Build Architecture

### Two-Phase Build Process

#### Phase 1: Bronze Ingestion (API → Parquet)

**What it does:**
- Calls external APIs (Alpha Vantage, BLS, Chicago)
- Applies facet transformations (normalize schemas)
- Writes partitioned Parquet files to Bronze layer
- Handles rate limiting and retries

**Key Features:**
- **Bulk discovery**: LISTING_STATUS endpoint discovers all tickers (1 API call)
- **Concurrent requests**: Premium tier supports parallel fetching
- **Deduplication**: Tracks completed data sources to avoid redundant calls
- **Partitioning**: By snapshot_dt, trade_date, asset_type

#### Phase 2: Silver Build (Bronze → Dimensional Models)

**What it does:**
- Loads Bronze Parquet files
- Applies graph transformations (joins, aggregations, filters)
- Builds dimensions and facts per model YAML config
- Writes dimensional models to Silver layer

**Key Features:**
- **Cross-model joins**: Company ← Stocks via CIK/company_id
- **Automatic deduplication**: unique_key constraints enforced
- **Schema validation**: Column types validated against YAML
- **Incremental builds**: Can filter by date ranges

### Model Build Order

Models are built in dependency order:

```
Tier 0: core (calendar dimension)
  ↓
Tier 1: company (standalone - CIK-based entities)
  ↓
Tier 2: stocks (depends on: core, company)
  ↓
Tier 3: options, etfs, futures (planned)

Other Models:
  - macro (BLS data - independent)
  - city_finance (Chicago data - independent)
  - forecast (derived from stocks - no ingestion)
```

---

## Complete Build Reference

### Command-Line Interface

```bash
python -m scripts.build.build_all_models [OPTIONS]
```

### All Available Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--models` | list | all | Specific models to build (e.g., `--models stocks company`) |
| `--date-from` | date | None | Start date for market data (YYYY-MM-DD) |
| `--date-to` | date | yesterday | End date for market data (YYYY-MM-DD) |
| `--days` | int | None | Alternative to date-from/date-to (e.g., `--days 7`) |
| `--max-tickers` | int | all | Limit number of tickers (for testing) |
| `--skip-ingestion` | flag | False | Skip Bronze ingestion (use existing data) |
| `--skip-reference-refresh` | flag | False | Skip OVERVIEW calls (saves ~50% time) ⚡ NEW |
| `--outputsize` | choice | full | Price data: `compact` (100 days) or `full` (20+ years) ⚡ NEW |
| `--no-bulk-discovery` | flag | False | Disable bulk ticker discovery |
| `--parallel` | flag | False | Build models in parallel |
| `--max-workers` | int | 3 | Max parallel workers |
| `--dry-run` | flag | False | Show what would be done without executing |
| `--output` | path | None | Save results to JSON file |
| `--config-dir` | path | configs/models | Model config directory |

### Key Options Explained

#### 🎯 Date Range Options

**`--date-from` / `--date-to`**: Explicit date range
```bash
# Full historical data (2015 to yesterday)
python -m scripts.build.build_all_models --date-from 2015-01-01

# Specific range
python -m scripts.build.build_all_models \
  --date-from 2024-01-01 \
  --date-to 2024-12-31
```

**`--days`**: Recent data (relative to yesterday)
```bash
# Last 7 days
python -m scripts.build.build_all_models --days 7

# Last 30 days
python -m scripts.build.build_all_models --days 30
```

#### ⚡ Performance Options (NEW!)

**`--skip-reference-refresh`**: Skip fundamentals (saves ~50% time)

**When to use:**
- ✅ Daily price updates
- ✅ Intraday refreshes
- ✅ When fundamentals haven't changed

**When NOT to use:**
- ❌ Initial data load
- ❌ New tickers added
- ❌ After earnings reports

```bash
# Daily refresh (skip fundamentals)
python -m scripts.build.build_all_models \
  --date-from 2025-11-20 \
  --skip-reference-refresh
```

**`--outputsize compact|full`**: Price data size

- **`compact`**: Last 100 trading days (~4.5 months)
- **`full`**: 20+ years of historical data (default)

**When to use compact:**
- ✅ Daily incremental updates
- ✅ Recent data analysis
- ✅ After initial full load

**When to use full:**
- ✅ Initial data load
- ✅ Backfilling historical gaps
- ✅ New tickers

```bash
# Daily refresh (recent prices only)
python -m scripts.build.build_all_models \
  --date-from 2025-11-20 \
  --outputsize compact
```

#### 🎛️ Model Selection Options

**`--models`**: Build specific models only
```bash
# Just stocks and company
python -m scripts.build.build_all_models \
  --models stocks company \
  --date-from 2024-01-01

# Just core (calendar dimension)
python -m scripts.build.build_all_models --models core
```

**`--max-tickers`**: Limit universe size (development/testing)
```bash
# Test with 10 tickers
python -m scripts.build.build_all_models \
  --max-tickers 10 \
  --date-from 2025-01-01
```

#### 🚀 Execution Options

**`--skip-ingestion`**: Rebuild Silver without calling APIs
```bash
# Bronze data already exists, just rebuild Silver
python -m scripts.build.build_all_models --skip-ingestion
```

**`--parallel`**: Build models concurrently (experimental)
```bash
# Build multiple models in parallel (3 workers)
python -m scripts.build.build_all_models \
  --parallel \
  --max-workers 3
```

**`--dry-run`**: Preview what would happen
```bash
# See what would be built without executing
python -m scripts.build.build_all_models \
  --date-from 2024-01-01 \
  --dry-run
```

---

## Optimization Strategies

### Strategy 1: Fast Daily Refresh (Recommended)

**Goal:** Update prices only, skip fundamentals

**Time Savings:** ~50% faster (13 mins vs 26 mins for 1,000 tickers)

**Command:**
```bash
python -m scripts.build.build_all_models \
  --date-from $(date -d "yesterday" +%Y-%m-%d) \
  --skip-reference-refresh \
  --outputsize compact
```

**What happens:**
1. ✅ Bulk discovery: 1 API call (discovers all tickers)
2. ⚡ SKIP: OVERVIEW endpoint (fundamentals unchanged)
3. ✅ Prices: N API calls with `outputsize=compact` (last 100 days only)
4. ✅ Silver build: Process recent data only

**API Call Count:**
- OLD: 1 (bulk) + N (OVERVIEW) + N (prices) = 2N+1 calls
- NEW: 1 (bulk) + 0 (skipped) + N (prices) = N+1 calls
- **Savings: N calls (50% reduction!)**

### Strategy 2: Weekly Fundamentals Refresh

**Goal:** Update fundamentals + recent prices

**Command:**
```bash
python -m scripts.build.build_all_models \
  --days 7 \
  --outputsize compact
```

**What happens:**
1. ✅ Bulk discovery: 1 API call
2. ✅ OVERVIEW: N API calls (update fundamentals)
3. ✅ Prices: N API calls with `outputsize=compact`
4. ✅ Silver build: Full dimensional models

**When to run:** Once per week (Sundays recommended)

### Strategy 3: Development Testing

**Goal:** Test pipeline with minimal API calls

**Command:**
```bash
python -m scripts.build.build_all_models \
  --max-tickers 5 \
  --date-from 2025-11-01 \
  --skip-reference-refresh \
  --outputsize compact
```

**API Call Count:** 1 (bulk) + 5 (prices) = 6 calls total

**Time:** ~1 minute @ 75 calls/min premium tier

---

## Common Workflows

### Workflow 1: Initial Setup (First Time)

**Goal:** Build complete historical database

```bash
# Step 1: Initial full load (all data)
python -m scripts.build.build_all_models --date-from 2015-01-01

# What this does:
# - Bulk discovery: Finds all 12,000+ active tickers
# - Reference data: Fetches fundamentals for all tickers (~12,000 calls)
# - Prices: Fetches full price history (~12,000 calls)
# - Total: ~24,000 API calls @ 75/min = ~5.3 hours

# Step 2: Verify data
ls -lh storage/bronze/securities_*/
ls -lh storage/silver/stocks/
ls -lh storage/silver/company/

# Step 3: Test queries
python
>>> from core.session.universal_session import UniversalSession
>>> session = UniversalSession(backend="duckdb")
>>> df = session.query("SELECT * FROM stocks.dim_stock LIMIT 10")
>>> print(df)
```

### Workflow 2: Daily Production Update

**Goal:** Refresh yesterday's data (automated cron job)

```bash
#!/bin/bash
# daily_refresh.sh - Run at 7 AM ET daily

# Calculate yesterday's date
YESTERDAY=$(date -d "yesterday" +%Y-%m-%d)

# Fast daily refresh (skip fundamentals, compact prices)
python -m scripts.build.build_all_models \
  --date-from $YESTERDAY \
  --skip-reference-refresh \
  --outputsize compact

# Check for errors
if [ $? -eq 0 ]; then
  echo "✅ Daily refresh completed: $YESTERDAY"
else
  echo "❌ Daily refresh failed: $YESTERDAY"
  exit 1
fi
```

**Crontab entry:**
```cron
# Run daily at 7 AM ET (after market close + data availability)
0 7 * * * /path/to/de_Funk/daily_refresh.sh >> /var/log/de_funk_daily.log 2>&1
```

### Workflow 3: Weekly Fundamentals Update

**Goal:** Refresh fundamentals + prices (Sunday morning)

```bash
#!/bin/bash
# weekly_refresh.sh - Run on Sundays

# Refresh last 7 days with fundamentals
python -m scripts.build.build_all_models \
  --days 7 \
  --outputsize compact

echo "✅ Weekly refresh completed"
```

**Crontab entry:**
```cron
# Run Sundays at 8 AM ET
0 8 * * 0 /path/to/de_Funk/weekly_refresh.sh >> /var/log/de_funk_weekly.log 2>&1
```

### Workflow 4: Backfill Historical Data

**Goal:** Fill gaps in historical data

```bash
# Backfill specific date range
python -m scripts.build.build_all_models \
  --date-from 2020-01-01 \
  --date-to 2020-12-31 \
  --outputsize full

# Backfill for specific tickers
python -m scripts.build.build_all_models \
  --models stocks \
  --date-from 2015-01-01 \
  --max-tickers 100  # Process in batches
```

### Workflow 5: Model-Specific Rebuild

**Goal:** Rebuild one model without affecting others

```bash
# Rebuild stocks model only (use existing Bronze)
python -m scripts.build.build_all_models \
  --models stocks \
  --skip-ingestion

# Rebuild with fresh ingestion
python -m scripts.build.build_all_models \
  --models stocks company \
  --date-from 2024-01-01
```

---

## Performance Tuning

### API Rate Limits

**Alpha Vantage Tiers:**

| Tier | Calls/Minute | Calls/Day | Cost/Month |
|------|-------------|-----------|------------|
| Free | 5 | 25 | $0 |
| Premium | 75 | ~108,000 | $50 |

**Time Estimates (1,000 tickers):**

| Operation | Free Tier | Premium Tier |
|-----------|-----------|--------------|
| Bulk discovery | ~12 sec | ~1 sec |
| Reference data (OVERVIEW) | ~3.3 hours | ~13 mins |
| Prices (compact) | ~3.3 hours | ~13 mins |
| **Total (with skip-reference)** | ~3.3 hours | ~13 mins |
| **Total (full refresh)** | ~6.6 hours | ~26 mins |

### Concurrent Requests

**Premium Tier Only** - The ingestor uses `use_concurrent=True` by default:

```python
# In alpha_vantage_ingestor.py (automatically used)
tickers = ingestor.run_all(
    use_concurrent=True,  # Enabled for premium tier
    ...
)
```

**Benefits:**
- Utilizes full 75 calls/min rate limit
- ~3-5x faster than sequential
- Handles thread pool management automatically

### Storage Optimization

**Bronze Layer:**
- Partitioned by: `snapshot_dt`, `trade_date`, `asset_type`
- Compact writes: Single file per partition
- Compression: Snappy (default Parquet)

**Silver Layer:**
- Coalesced to 1 file per table (small data)
- Optimized for analytical queries
- DuckDB memory-maps files (no duplication)

**Disk Usage Estimates:**

| Universe Size | Bronze | Silver | Total |
|---------------|--------|--------|-------|
| 100 tickers | ~50 MB | ~20 MB | ~70 MB |
| 1,000 tickers | ~500 MB | ~200 MB | ~700 MB |
| 12,000 tickers | ~6 GB | ~2.4 GB | ~8.4 GB |

---

## Troubleshooting

### Common Issues

#### 1. API Key Errors

**Error:**
```
WARNING: No API keys found for alpha_vantage
```

**Solution:**
```bash
# Check .env file exists
cat .env

# Add API key
echo "ALPHA_VANTAGE_API_KEYS=your_key_here" >> .env

# Verify
python -c "from config import ConfigLoader; print(ConfigLoader().load().apis['alpha_vantage'])"
```

#### 2. Rate Limit Exceeded

**Error:**
```
Note: API call frequency is 5 calls per minute
```

**Solutions:**
- **Wait 60 seconds** and retry
- **Reduce tickers**: `--max-tickers 10`
- **Upgrade to premium**: $50/month for 75 calls/min

#### 3. Timestamp Casting Error (Fixed!)

**Error:**
```
[CAST_INVALID_INPUT] The value 'null' cannot be cast to TIMESTAMP
```

**Status:** ✅ FIXED in commit bea6e74 (null string handling)

#### 4. KeyError: 'ticker' in Bulk Listing (Fixed!)

**Error:**
```
KeyError: 'ticker'
```

**Status:** ✅ FIXED in commit e87c131 (use `row['symbol']`)

#### 5. Model Build Failures

**Error:**
```
Silver build failed: [PATH_NOT_FOUND] storage/bronze/bls/unemployment
```

**Cause:** Bronze data doesn't exist (BLS ingestion not implemented)

**Solution:**
```bash
# Skip models without bronze data
python -m scripts.build.build_all_models \
  --models core stocks company
```

#### 6. Duplicate Data

**Symptom:** Same dates/tickers appearing multiple times

**Solution:**
```bash
# Models have unique_key constraints - they auto-deduplicate
# But to clean Bronze layer:
rm -rf storage/bronze/securities_*
python -m scripts.build.build_all_models --date-from 2024-01-01
```

### Performance Diagnostics

```bash
# Check Bronze data exists
ls -lh storage/bronze/securities_reference/
ls -lh storage/bronze/securities_prices_daily/

# Check Silver data exists
ls -lh storage/silver/stocks/dims/
ls -lh storage/silver/stocks/facts/

# Count records in Bronze
python -c "
from pyspark.sql import SparkSession
spark = SparkSession.builder.getOrCreate()
ref = spark.read.parquet('storage/bronze/securities_reference')
prices = spark.read.parquet('storage/bronze/securities_prices_daily')
print(f'Reference records: {ref.count():,}')
print(f'Price records: {prices.count():,}')
"

# Check Silver via DuckDB
python -c "
from core.session.universal_session import UniversalSession
session = UniversalSession(backend='duckdb')
result = session.query('SELECT COUNT(*) as cnt FROM stocks.dim_stock')
print(f'Stocks in Silver: {result.iloc[0].cnt:,}')
"
```

---

## Advanced Topics

### Custom Model Selection

```bash
# Build dependency chain only
python -m scripts.build.build_all_models --models core company stocks

# Build independent models in parallel
python -m scripts.build.build_all_models \
  --models core macro city_finance \
  --parallel
```

### Output Results to JSON

```bash
# Save build results
python -m scripts.build.build_all_models \
  --date-from 2024-01-01 \
  --output build_results.json

# Check results
cat build_results.json | jq '.model_results'
```

### Environment-Specific Builds

```bash
# Development environment
export CONNECTION_TYPE=spark
export SPARK_SHUFFLE_PARTITIONS=50
python -m scripts.build.build_all_models --max-tickers 100

# Production environment
export CONNECTION_TYPE=spark
export SPARK_SHUFFLE_PARTITIONS=400
python -m scripts.build.build_all_models --date-from 2015-01-01
```

### Incremental Model Updates

```bash
# Update only recent data in Silver (use existing Bronze)
python -m scripts.build.build_all_models \
  --models stocks \
  --skip-ingestion \
  --date-from 2025-11-01
```

---

## Summary Table

### Quick Reference: When to Use What

| Scenario | Command | Time (1K tickers) |
|----------|---------|-------------------|
| **Initial load** | `--date-from 2015-01-01` | ~26 mins |
| **Daily refresh** | `--date-from yesterday --skip-reference-refresh --outputsize compact` | ~13 mins |
| **Weekly refresh** | `--days 7 --outputsize compact` | ~26 mins |
| **Development** | `--max-tickers 10 --skip-reference-refresh --outputsize compact` | ~1 min |
| **Rebuild Silver** | `--skip-ingestion` | ~2 mins |
| **Backfill** | `--date-from 2020-01-01 --date-to 2020-12-31` | varies |

### Optimization Quick Reference

| Goal | Flags | Savings |
|------|-------|---------|
| Skip fundamentals | `--skip-reference-refresh` | ~50% API calls |
| Recent prices only | `--outputsize compact` | ~70% faster response |
| Use existing Bronze | `--skip-ingestion` | 100% API calls |
| **Combined daily** | `--skip-reference-refresh --outputsize compact` | **~50% total time** |

---

## Related Documentation

- **Quick Start:** `ALPHA_VANTAGE_SETUP.md` - API setup and testing
- **Architecture:** `CLAUDE.md` - Complete system architecture
- **Configuration:** `docs/configuration.md` - Config system details
- **Testing:** `TESTING_GUIDE.md` - Testing procedures
- **Model Guide:** `docs/MODEL_RESET_REBUILD_GUIDE.md` - Model lifecycle

---

## Support & Feedback

- **Issues:** Report bugs at GitHub Issues
- **API Status:** https://status.alphavantage.co/
- **Documentation:** See `docs/` directory

---

**Last Updated:** 2025-11-20
**Contributors:** Claude Code AI Assistant
**License:** See LICENSE file
