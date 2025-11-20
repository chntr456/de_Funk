# DuckDB Setup Guide

**Fast analytical queries on Silver layer data without data duplication**

**Last Updated:** 2025-11-20
**Version:** 2.0

---

## Overview

DuckDB provides 10-100x faster query performance compared to Spark for analytical workloads. The setup creates views that point directly to Silver layer Parquet files - no data duplication!

### Benefits

- ✅ **Fast queries**: 10-100x faster than Spark
- ✅ **Zero duplication**: Views point to existing Parquet files
- ✅ **SQL interface**: Standard SQL queries
- ✅ **Cross-model joins**: Join stocks, company, core seamlessly
- ✅ **Persistent catalog**: Views survive restarts
- ✅ **Memory efficient**: DuckDB memory-maps files

### Architecture

```
┌─────────────────────────────────────────────────────┐
│  SILVER LAYER (Parquet Files)                      │
│  ├─ storage/silver/core/dims/dim_calendar/         │
│  ├─ storage/silver/company/dims/dim_company/       │
│  ├─ storage/silver/stocks/dims/dim_stock/          │
│  └─ storage/silver/stocks/facts/fact_stock_prices/ │
└──────────────────┬──────────────────────────────────┘
                   │
                   │ CREATE VIEW ... AS SELECT * FROM read_parquet()
                   ↓
┌─────────────────────────────────────────────────────┐
│  DUCKDB DATABASE (Views Only)                      │
│  File: storage/duckdb/analytics.db (~1 MB)        │
│  ├─ core.dim_calendar → read_parquet(...)         │
│  ├─ company.dim_company → read_parquet(...)       │
│  ├─ stocks.dim_stock → read_parquet(...)          │
│  └─ stocks.fact_stock_prices → read_parquet(...)  │
└──────────────────┬──────────────────────────────────┘
                   │
                   │ Query interface
                   ↓
┌─────────────────────────────────────────────────────┐
│  APPLICATIONS                                       │
│  ├─ Streamlit notebooks                            │
│  ├─ Python scripts                                  │
│  └─ Direct SQL clients                              │
└─────────────────────────────────────────────────────┘
```

**Key Point**: The DuckDB file is tiny (~1 MB) because it only stores view definitions, NOT data!

---

## Quick Start

### 1. Build Silver Layer (if not done yet)

```bash
# Initial full build
python -m scripts.build.build_all_models --date-from 2024-01-01

# Or daily refresh
python -m scripts.build.build_all_models \
  --date-from 2025-11-20 \
  --skip-reference-refresh \
  --outputsize compact
```

### 2. Create DuckDB Views

```bash
# Create database with all views
python -m scripts.setup.setup_duckdb_views

# What this does:
# - Creates storage/duckdb/analytics.db
# - Creates schemas: core, company, stocks, options, etfs, futures, analytics
# - Creates views for all Silver tables
# - Creates helper views for common queries
```

**Output:**
```
DUCKDB VIEW SETUP (v2.0)
================================================================================
Database: storage/duckdb/analytics.db
...

CORE MODEL VIEWS
================================================================================
✓ Created view: core.dim_calendar

COMPANY MODEL VIEWS
================================================================================
✓ Created view: company.dim_company
⚠ Skipping company.dim_exchange - path not found

STOCKS MODEL VIEWS
================================================================================
✓ Created view: stocks.dim_stock
✓ Created view: stocks.fact_stock_prices
...

SETUP SUMMARY
================================================================================
Created views: 8
Skipped views: 6 (missing Parquet files)
✓ DuckDB setup complete!
```

### 3. Test Setup

```bash
# Validate views and run sample queries
python -m scripts.test.test_duckdb_setup

# List all views
python -m scripts.test.test_duckdb_setup --list-views

# Test specific models
python -m scripts.test.test_duckdb_setup --models stocks company
```

### 4. Query Data

**Python:**
```python
from core.session.universal_session import UniversalSession

# Use DuckDB backend (fast!)
session = UniversalSession(backend="duckdb")

# Query stocks
df = session.query("""
    SELECT
        ticker,
        trade_date,
        close,
        volume
    FROM stocks.fact_stock_prices
    WHERE trade_date >= '2024-01-01'
    ORDER BY trade_date DESC
    LIMIT 10
""")

print(df)
```

**Direct DuckDB:**
```python
import duckdb

conn = duckdb.connect('storage/duckdb/analytics.db', read_only=True)

# Query
result = conn.execute("""
    SELECT * FROM stocks.fact_stock_prices LIMIT 10
""").fetchdf()

print(result)
conn.close()
```

---

## Available Views

### Core Model

| View | Description | Typical Rows |
|------|-------------|--------------|
| `core.dim_calendar` | Calendar dimension (2000-2050) | ~18,000 |

### Company Model

| View | Description | Typical Rows |
|------|-------------|--------------|
| `company.dim_company` | Company dimension (CIK-based) | ~5,000 |
| `company.dim_exchange` | Exchange dimension | ~50 |
| `company.fact_company_fundamentals` | Company fundamentals (PE, market cap) | ~5,000 |
| `company.fact_company_metrics` | Derived metrics | varies |

### Stocks Model

| View | Description | Typical Rows |
|------|-------------|--------------|
| `stocks.dim_stock` | Stock dimension | ~5,000 |
| `stocks.fact_stock_prices` | Daily OHLCV prices | ~5M |
| `stocks.fact_stock_technicals` | Technical indicators | ~5M |
| `stocks.fact_stock_fundamentals` | Stock-level fundamentals | ~5,000 |

### Options Model (Planned)

| View | Description | Typical Rows |
|------|-------------|--------------|
| `options.dim_option` | Option contracts | varies |
| `options.fact_option_prices` | Option prices | varies |
| `options.fact_option_greeks` | Greeks (delta, gamma, etc.) | varies |

### ETFs Model (Planned)

| View | Description | Typical Rows |
|------|-------------|--------------|
| `etfs.dim_etf` | ETF dimension | varies |
| `etfs.fact_etf_prices` | ETF prices | varies |
| `etfs.fact_etf_holdings` | ETF holdings | varies |

### Futures Model (Planned)

| View | Description | Typical Rows |
|------|-------------|--------------|
| `futures.dim_future` | Future contracts | varies |
| `futures.fact_future_prices` | Future prices | varies |
| `futures.fact_future_margins` | Margin requirements | varies |

### Helper Views

| View | Description | Purpose |
|------|-------------|---------|
| `analytics.stock_prices_enriched` | Prices + company info | Common analytical queries |

---

## Common Queries

### Latest Stock Prices

```sql
SELECT
    ticker,
    trade_date,
    open,
    high,
    low,
    close,
    volume
FROM stocks.fact_stock_prices
WHERE ticker = 'AAPL'
ORDER BY trade_date DESC
LIMIT 30;
```

### Stock Prices with Company Info

```sql
SELECT
    p.ticker,
    p.trade_date,
    p.close,
    p.volume,
    c.company_name,
    c.sector,
    c.market_cap
FROM stocks.fact_stock_prices p
JOIN stocks.dim_stock s ON p.ticker = s.ticker
JOIN company.dim_company c ON s.company_id = c.company_id
WHERE p.ticker = 'AAPL'
    AND p.trade_date >= '2024-01-01'
ORDER BY p.trade_date DESC;
```

### Top Gainers Today

```sql
WITH today_prices AS (
    SELECT
        ticker,
        close as today_close
    FROM stocks.fact_stock_prices
    WHERE trade_date = (SELECT MAX(trade_date) FROM stocks.fact_stock_prices)
),
yesterday_prices AS (
    SELECT
        ticker,
        close as yesterday_close
    FROM stocks.fact_stock_prices
    WHERE trade_date = (SELECT MAX(trade_date) - INTERVAL '1 day' FROM stocks.fact_stock_prices)
)
SELECT
    t.ticker,
    c.company_name,
    c.sector,
    t.today_close,
    y.yesterday_close,
    ((t.today_close - y.yesterday_close) / y.yesterday_close * 100) as pct_change
FROM today_prices t
JOIN yesterday_prices y ON t.ticker = y.ticker
JOIN stocks.dim_stock s ON t.ticker = s.ticker
JOIN company.dim_company c ON s.company_id = c.company_id
ORDER BY pct_change DESC
LIMIT 10;
```

### Sector Performance

```sql
SELECT
    c.sector,
    COUNT(DISTINCT p.ticker) as stock_count,
    AVG(p.close) as avg_price,
    SUM(p.volume) as total_volume
FROM stocks.fact_stock_prices p
JOIN stocks.dim_stock s ON p.ticker = s.ticker
JOIN company.dim_company c ON s.company_id = c.company_id
WHERE p.trade_date >= '2025-11-01'
    AND c.sector IS NOT NULL
GROUP BY c.sector
ORDER BY total_volume DESC;
```

### Using Helper View

```sql
-- Much simpler!
SELECT
    ticker,
    trade_date,
    close,
    company_name,
    sector,
    market_cap
FROM analytics.stock_prices_enriched
WHERE ticker = 'AAPL'
ORDER BY trade_date DESC
LIMIT 30;
```

---

## Maintenance

### Update Views After New Build

```bash
# Rebuild Silver layer
python -m scripts.build.build_all_models --skip-ingestion

# Update views (recreate them)
python -m scripts.setup.setup_duckdb_views --update
```

### Add New Models

When new models are built, update views:

```bash
python -m scripts.setup.setup_duckdb_views --update
```

### Compact Database (Optional)

DuckDB databases can be vacuumed to reclaim space:

```python
import duckdb
conn = duckdb.connect('storage/duckdb/analytics.db')
conn.execute("VACUUM")
conn.close()
```

**Note**: Usually not needed since views don't store data!

---

## Advanced Usage

### Custom Views

Create your own views for specific analyses:

```python
import duckdb

conn = duckdb.connect('storage/duckdb/analytics.db')

# Create custom view
conn.execute("""
CREATE OR REPLACE VIEW analytics.my_analysis AS
SELECT
    ticker,
    AVG(close) as avg_close,
    MAX(high) as max_high,
    MIN(low) as min_low
FROM stocks.fact_stock_prices
WHERE trade_date >= '2024-01-01'
GROUP BY ticker
""")

# Query it
result = conn.execute("SELECT * FROM analytics.my_analysis").fetchdf()
print(result)

conn.close()
```

### Materialized Tables (For Speed)

For frequently accessed queries, materialize results:

```python
import duckdb

conn = duckdb.connect('storage/duckdb/analytics.db')

# Create materialized table (stores data)
conn.execute("""
CREATE OR REPLACE TABLE analytics.daily_summary AS
SELECT
    trade_date,
    COUNT(DISTINCT ticker) as active_stocks,
    AVG(close) as avg_close,
    SUM(volume) as total_volume
FROM stocks.fact_stock_prices
GROUP BY trade_date
ORDER BY trade_date
""")

# Query is now instant
result = conn.execute("SELECT * FROM analytics.daily_summary ORDER BY trade_date DESC LIMIT 10").fetchdf()
print(result)

conn.close()
```

**Trade-off**: Materialized tables duplicate data but are faster for complex aggregations.

### Export to CSV

```python
import duckdb

conn = duckdb.connect('storage/duckdb/analytics.db', read_only=True)

# Export query results to CSV
conn.execute("""
COPY (
    SELECT * FROM stocks.fact_stock_prices
    WHERE ticker = 'AAPL'
) TO 'output/aapl_prices.csv' (HEADER, DELIMITER ',')
""")

conn.close()
```

### Parquet Export

```python
import duckdb

conn = duckdb.connect('storage/duckdb/analytics.db', read_only=True)

# Export to Parquet
conn.execute("""
COPY (
    SELECT * FROM analytics.stock_prices_enriched
    WHERE trade_date >= '2024-01-01'
) TO 'output/enriched_prices.parquet' (FORMAT PARQUET)
""")

conn.close()
```

---

## Troubleshooting

### Database Not Found

**Error:**
```
❌ Database not found: storage/duckdb/analytics.db
```

**Solution:**
```bash
# Create it
python -m scripts.setup.setup_duckdb_views
```

### View Not Found

**Error:**
```
❌ View not found: stocks.fact_stock_prices
```

**Cause:** Model hasn't been built yet

**Solution:**
```bash
# Build the model first
python -m scripts.build.build_all_models --models stocks

# Then update views
python -m scripts.setup.setup_duckdb_views --update
```

### Empty View (0 rows)

**Cause:** Parquet files exist but are empty

**Solution:**
```bash
# Check Bronze data
ls -lh storage/bronze/securities_prices_daily/

# If empty, run ingestion
python -m scripts.build.build_all_models --date-from 2024-01-01
```

### Slow Queries

**Check:**
1. Are you filtering on partitioned columns (trade_date, snapshot_dt)?
2. Are you using LIMIT for large result sets?
3. Is DuckDB memory limit sufficient?

**Optimize:**
```python
import duckdb

conn = duckdb.connect('storage/duckdb/analytics.db')

# Increase memory limit
conn.execute("SET memory_limit='8GB'")

# Increase threads
conn.execute("SET threads=8")

# Your query
result = conn.execute("SELECT ...").fetchdf()
```

### View Points to Wrong Path

**Cause:** Silver path moved or renamed

**Solution:**
```bash
# Recreate views with current paths
python -m scripts.setup.setup_duckdb_views --update
```

---

## Performance Tips

### 1. Use Date Filters

Parquet files are partitioned by date - always filter on dates!

```sql
-- GOOD: Uses partition pruning
SELECT * FROM stocks.fact_stock_prices
WHERE trade_date >= '2024-01-01'

-- BAD: Scans all partitions
SELECT * FROM stocks.fact_stock_prices
```

### 2. Use LIMIT

Avoid scanning unnecessary data:

```sql
-- GOOD: Stops after 100 rows
SELECT * FROM stocks.fact_stock_prices
LIMIT 100

-- BAD: Scans everything
SELECT * FROM stocks.fact_stock_prices
```

### 3. Project Only Needed Columns

```sql
-- GOOD: Reads only needed columns
SELECT ticker, trade_date, close
FROM stocks.fact_stock_prices

-- BAD: Reads all columns
SELECT *
FROM stocks.fact_stock_prices
```

### 4. Use Indexes (Materialized Tables)

For frequently filtered columns, materialize and index:

```python
conn.execute("""
CREATE TABLE analytics.prices_indexed AS
SELECT * FROM stocks.fact_stock_prices
""")

conn.execute("""
CREATE INDEX idx_ticker ON analytics.prices_indexed(ticker)
""")
```

---

## Integration with Applications

### Streamlit Notebooks

Notebooks automatically use DuckDB when `backend="duckdb"`:

```python
from core.session.universal_session import UniversalSession

session = UniversalSession(backend="duckdb")
df = session.query("SELECT * FROM stocks.fact_stock_prices LIMIT 100")
```

### Jupyter Notebooks

```python
import duckdb
import pandas as pd

conn = duckdb.connect('storage/duckdb/analytics.db', read_only=True)

# Run query
df = conn.execute("""
    SELECT * FROM stocks.fact_stock_prices
    WHERE ticker = 'AAPL'
    ORDER BY trade_date DESC
    LIMIT 100
""").fetchdf()

# Analyze with pandas
print(df.describe())
print(df.info())

# Visualize
df.plot(x='trade_date', y='close', title='AAPL Price History')

conn.close()
```

### Python Scripts

```python
from core.context import RepoContext

# Get DuckDB connection
ctx = RepoContext.from_repo_root(connection_type="duckdb")

# Query
result = ctx.connection.execute("""
    SELECT * FROM stocks.fact_stock_prices LIMIT 10
""")

# Convert to pandas
df = result.df()
print(df)
```

---

## Summary

### Quick Reference

| Task | Command |
|------|---------|
| Create database | `python -m scripts.setup.setup_duckdb_views` |
| Update views | `python -m scripts.setup.setup_duckdb_views --update` |
| Test setup | `python -m scripts.test.test_duckdb_setup` |
| List views | `python -m scripts.test.test_duckdb_setup --list-views` |
| Dry run (show SQL) | `python -m scripts.setup.setup_duckdb_views --dry-run` |

### Files Created

| File | Size | Purpose |
|------|------|---------|
| `storage/duckdb/analytics.db` | ~1 MB | View definitions (NO data!) |
| `storage/duckdb/analytics.db.wal` | varies | Write-ahead log (transient) |

### Key Benefits

✅ 10-100x faster than Spark
✅ Zero data duplication
✅ Standard SQL interface
✅ Cross-model joins
✅ Persistent catalog
✅ Memory efficient

---

## Related Documentation

- **Build Guide:** `docs/BUILD_GUIDE.md` - Building Silver layer
- **Architecture:** `CLAUDE.md` - System architecture
- **Alpha Vantage:** `ALPHA_VANTAGE_SETUP.md` - API setup

---

**Last Updated:** 2025-11-20
**Contributors:** Claude Code AI Assistant
**License:** See LICENSE file
