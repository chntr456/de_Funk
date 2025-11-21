# de_Funk Scripts Guide

**Last Updated**: 2025-11-21
**Version**: 2.0

This guide documents all operational scripts for building, running, and testing the de_Funk system.

---

## Table of Contents

1. [Running the Application](#running-the-application)
2. [Data Ingestion Scripts](#data-ingestion-scripts)
3. [Model Building Scripts](#model-building-scripts)
4. [Diagnostic Scripts](#diagnostic-scripts)
5. [Testing Scripts](#testing-scripts)
6. [Workflow Examples](#workflow-examples)

---

## Running the Application

### Start Streamlit UI (DuckDB-powered)

**Script**: `run_app.py` or `run_app.sh`

**Purpose**: Launch the interactive Streamlit-based notebook application with DuckDB backend.

**Benefits**:
- ⚡ Instant startup (~1s vs ~15s with Spark)
- 🚀 10-100x faster queries than Spark
- 💾 No JVM overhead
- 📦 No pyspark required

**Usage**:
```bash
# Python script
python run_app.py

# Or shell script
./run_app.sh
```

**What it does**:
1. Validates repository structure
2. Locates `app/ui/notebook_app_duckdb.py`
3. Launches Streamlit on `http://localhost:8501`
4. Opens browser automatically

**Requirements**:
- Run from repository root
- DuckDB database exists at `storage/duckdb/analytics.db`
- Silver layer models built (see [Model Building](#model-building-scripts))

**Output**:
```
==================================================
  Starting Notebook Application (DuckDB)
==================================================

Starting Streamlit application...

The app will open in your browser at: http://localhost:8501

Press Ctrl+C to stop the server.
```

---

## Data Ingestion Scripts

### Test Alpha Vantage Ingestion

**Script**: `scripts/test_alpha_vantage_ingestion.py`

**Purpose**: Test Alpha Vantage data provider integration by ingesting reference data and prices for a small set of tickers.

**Usage**:
```bash
# Default tickers (AAPL, MSFT, GOOGL)
python -m scripts.test_alpha_vantage_ingestion

# Custom tickers
python -m scripts.test_alpha_vantage_ingestion --tickers AAPL MSFT TSLA NVDA

# Specify date range for prices
python -m scripts.test_alpha_vantage_ingestion \
    --tickers AAPL MSFT \
    --date-from 2024-01-01 \
    --date-to 2024-12-31
```

**What it does**:
1. **Validates API key** - Checks `ALPHA_VANTAGE_API_KEYS` in `.env`
2. **Creates Spark session** - Initializes PySpark for ingestion
3. **Ingests reference data** - Calls Alpha Vantage OVERVIEW endpoint
4. **Ingests price data** - Calls TIME_SERIES_DAILY_ADJUSTED endpoint
5. **Writes bronze tables** - Saves to `storage/bronze/securities_reference/` and `storage/bronze/securities_prices_daily/`
6. **Shows sample data** - Displays first 3 rows for verification

**API Rate Limits**:
- **Free tier**: 25 requests/day, 5 requests/minute
- **Premium tier**: 75 requests/second

**Requirements**:
- Alpha Vantage API key in `.env` file
- PySpark installed (`pip install pyspark`)

**Output**:
```
============================================================
📋 STEP 1: Ingesting Reference Data (Company Overview)
============================================================
Tickers: AAPL, MSFT, GOOGL
Endpoint: Alpha Vantage OVERVIEW
Rate Limit: 5 calls/minute (free tier)

✅ SUCCESS: Reference data written to:
   /home/user/de_Funk/storage/bronze/securities_reference/

Sample data (first 3 rows):
+------+---------------+------------+-----------+------------------+---------+
|ticker|security_name  |asset_type  |sector     |market_cap        |pe_ratio |
+------+---------------+------------+-----------+------------------+---------+
|AAPL  |Apple Inc.     |Common Stock|TECHNOLOGY |2850000000000     |28.5     |
|MSFT  |Microsoft Corp.|Common Stock|TECHNOLOGY |2420000000000     |32.1     |
|GOOGL |Alphabet Inc.  |Common Stock|TECHNOLOGY |1680000000000     |24.8     |
+------+---------------+------------+-----------+------------------+---------+
```

**Get API Key**:
1. Visit: https://www.alphavantage.co/support/#api-key
2. Fill out form (name, email)
3. Copy API key to `.env`:
   ```bash
   ALPHA_VANTAGE_API_KEYS=YOUR_API_KEY_HERE
   ```

---

## Model Building Scripts

Currently, model building is done via notebooks or direct Python API. The v2.0 architecture uses:

**Silver Layer Building**:
```python
from models.api.registry import get_model_registry
from core.context import RepoContext

# Create context
ctx = RepoContext.from_repo_root(connection_type="duckdb")

# Get model registry
registry = get_model_registry()

# Build specific model
stocks_model = registry.get_model("stocks")
stocks_model.build()  # Builds all tables (dim_stock, fact_stock_prices, fact_stock_technicals)

# Or build via session
from models.api.session import UniversalSession
session = UniversalSession(backend="duckdb")
session.build_model("stocks")
```

**Build All Models** (in dependency order):
```python
# Models build in order: core → company → stocks → options/etfs/futures
for model_name in ["core", "company", "stocks"]:
    model = registry.get_model(model_name)
    model.build()
```

**DuckDB Views Creation**:

After building silver Parquet files, create DuckDB views:
```python
import duckdb
from pathlib import Path

conn = duckdb.connect('storage/duckdb/analytics.db')

# Create schema
conn.execute("CREATE SCHEMA IF NOT EXISTS stocks")

# Create views pointing to Parquet files
conn.execute("""
    CREATE OR REPLACE VIEW stocks.dim_stock AS
    SELECT * FROM read_parquet('storage/silver/stocks/dim_stock/*.parquet', hive_partitioning=true)
""")

conn.execute("""
    CREATE OR REPLACE VIEW stocks.fact_stock_prices AS
    SELECT * FROM read_parquet('storage/silver/stocks/fact_stock_prices/**/*.parquet', hive_partitioning=true)
""")

conn.execute("""
    CREATE OR REPLACE VIEW stocks.fact_stock_technicals AS
    SELECT * FROM read_parquet('storage/silver/stocks/fact_stock_technicals/**/*.parquet', hive_partitioning=true)
""")
```

**Recommended Workflow**:
1. **Ingest bronze data** - Use `test_alpha_vantage_ingestion.py`
2. **Build silver models** - Use Python API or notebooks
3. **Create DuckDB views** - Point to Parquet files
4. **Launch UI** - Use `run_app.py`

---

## Diagnostic Scripts

### Diagnose Bronze Data

**Script**: `scripts/diagnose_bronze_data.py`

**Purpose**: Diagnose bronze data schema and v2.0 compatibility. Essential for troubleshooting ingestion issues.

**Usage**:
```bash
python -m scripts.diagnose_bronze_data
```

**What it does**:
1. **Scans bronze directory** - Finds all Parquet tables
2. **Reads schemas** - Shows columns for each table
3. **Shows sample data** - Displays first 3 rows
4. **Checks v2.0 compatibility** - Detects presence of `asset_type`, `is_active`, `cik`, `primary_exchange`
5. **Detects data source** - Identifies Polygon vs Alpha Vantage data
6. **Provides recommendations** - Suggests next steps

**Output**:
```
================================================================================
BRONZE DATA DIAGNOSTICS
================================================================================

✓ Found 428 parquet files

Bronze tables found: ['securities_reference', 'securities_prices_daily']

================================================================================
TABLE: securities_reference
================================================================================
Files: 42
Example: securities_reference/snapshot_dt=2025-11-20/asset_type=stocks/part-00000.parquet

Columns (21):
  - ticker
  - security_name
  - asset_type
  - cik
  - composite_figi
  - exchange_code
  - currency
  - market
  - locale
  - type
  - primary_exchange
  - shares_outstanding
  - market_cap
  - sic_code
  - sic_description
  - ticker_root
  - base_currency_symbol
  - currency_symbol
  - delisted_utc
  - last_updated_utc
  - is_active

Rows: 386

Sample data:
  ticker  security_name  asset_type  ...  market_cap  is_active
0  AAPL   Apple Inc.     stocks      ...  2850000000000  True
1  MSFT   Microsoft Corp. stocks     ...  2420000000000  True
2  GOOGL  Alphabet Inc.   stocks     ...  1680000000000  True

V2.0 Compatibility Check:
  ✓ Has v2.0 columns: ['asset_type', 'is_active', 'cik', 'primary_exchange']
  📍 Detected: Alpha Vantage data (v2.0)

================================================================================
TABLE: securities_prices_daily
================================================================================
Files: 386
Example: securities_prices_daily/trade_date=2025-01-15/asset_type=stocks/part-00000.parquet

Columns (11):
  - ticker
  - trade_date
  - asset_type
  - year
  - month
  - open
  - high
  - low
  - close
  - volume
  - volume_weighted

Rows: 107,860

V2.0 Compatibility Check:
  ✓ Has v2.0 columns: ['asset_type']
  📍 Detected: Alpha Vantage data (v2.0)

================================================================================
RECOMMENDATIONS
================================================================================

✅ You have v2.0-compatible bronze data!

Next steps:
1. Build silver layer models: stocks, options, etfs, futures
2. Create DuckDB views pointing to silver Parquet files
3. Run Streamlit UI: python run_app.py

For stocks model specifically:
- Filter: asset_type = 'stocks'
- Join to company model via CIK-based company_id
```

**Use Cases**:
- **After ingestion** - Verify data landed correctly
- **Debugging UI errors** - Check if bronze data has required columns
- **Migration validation** - Confirm v1.x → v2.0 migration
- **Partition troubleshooting** - See if partition columns are readable

---

### Diagnose Silver Data

**Script**: `scripts/diagnose_silver_data.py`

**Purpose**: Diagnose silver layer tables, DuckDB views, and cross-model relationships. Essential for troubleshooting model build and query issues.

**Usage**:
```bash
# Check all models (default: show top 3 rows per table)
python -m scripts.diagnose_silver_data

# Show more sample rows
python -m scripts.diagnose_silver_data --top-n 5

# Check specific models only
python -m scripts.diagnose_silver_data --models stocks company
```

**What it does**:
1. **Scans silver directory** - Finds all model directories and Parquet tables
2. **Reads schemas** - Shows columns for each table
3. **Shows sample data** - Displays top N rows (configurable)
4. **Checks row counts** - Total records per table
5. **Validates DuckDB views** - Checks if views exist and are queryable
6. **Compares counts** - Verifies Parquet vs DuckDB view row counts match
7. **Tests cross-model joins** - Validates stocks → company relationship
8. **Tests aggregations** - Verifies queries work correctly
9. **Provides recommendations** - Suggests fixes for issues

**Output**:
```
================================================================================
SILVER LAYER DIAGNOSTICS
================================================================================

✓ Found 3 model(s): ['company', 'core', 'stocks']
✓ DuckDB database: /home/user/de_Funk/storage/duckdb/analytics.db
✓ Connected to DuckDB

================================================================================
MODEL: stocks
================================================================================

Tables found: ['dim_stock', 'fact_stock_prices', 'fact_stock_technicals']

--------------------------------------------------------------------------------
TABLE: stocks.dim_stock
--------------------------------------------------------------------------------
Files: 1
Path: /home/user/de_Funk/storage/silver/stocks/dim_stock

Columns (15):
  - ticker
  - security_name
  - asset_type
  - cik
  - company_id
  - exchange_code
  - shares_outstanding
  - market_cap
  - sector
  - industry
  ... and 5 more

Rows: 386

Sample data (top 3 rows):
ticker  security_name     asset_type  cik         company_id        ...
AAPL    Apple Inc.        stocks      0000320193  COMPANY_0000320193 ...
MSFT    Microsoft Corp.   stocks      0000789019  COMPANY_0000789019 ...
GOOGL   Alphabet Inc.     stocks      0001652044  COMPANY_0001652044 ...

✅ Table readable from Parquet
✅ DuckDB view exists: stocks.dim_stock
   View rows: 386

--------------------------------------------------------------------------------
TABLE: stocks.fact_stock_prices
--------------------------------------------------------------------------------
Files: 386
Path: /home/user/de_Funk/storage/silver/stocks/fact_stock_prices

Columns (11):
  - ticker
  - trade_date
  - asset_type
  - year
  - month
  - open
  - high
  - low
  - close
  - volume
  - volume_weighted

Rows: 107,860

Sample data (top 3 rows):
ticker  trade_date  open    high    low     close   volume
AAPL    2024-01-02  185.00  187.50  184.25  186.75  52341200
AAPL    2024-01-03  186.50  188.00  185.75  187.25  48623400
AAPL    2024-01-04  187.00  189.25  186.50  188.75  55891600

✅ Table readable from Parquet
✅ DuckDB view exists: stocks.fact_stock_prices
   View rows: 107,860

================================================================================
SUMMARY
================================================================================
Total tables found: 8
Working tables: 8
Failed tables: 0

✅ All tables readable!

================================================================================
CROSS-MODEL RELATIONSHIPS
================================================================================

[1] Testing stocks → company join (via CIK)...
✅ Join successful! Sample:
ticker  cik         company_id          company_name      sector
AAPL    0000320193  COMPANY_0000320193  Apple Inc.        TECHNOLOGY
MSFT    0000789019  COMPANY_0000789019  Microsoft Corp.   TECHNOLOGY
GOOGL   0001652044  COMPANY_0001652044  Alphabet Inc.     TECHNOLOGY

Join coverage:
  Total stocks: 386
  With company: 285 (73.8%)
  Without company: 101 (26.2%)

[2] Testing stocks price aggregation...
✅ Aggregation successful! Top 5 tickers by data:
ticker  price_records  earliest_date  latest_date  avg_close_price
AAPL    250           2024-01-02     2024-12-31   186.45
MSFT    250           2024-01-02     2024-12-31   412.78
GOOGL   250           2024-01-02     2024-12-31   168.23
AMZN    250           2024-01-02     2024-12-31   178.56
NVDA    250           2024-01-02     2024-12-31   495.32

================================================================================
RECOMMENDATIONS
================================================================================

✅ All tables working correctly!

Next steps:
1. Launch UI: python run_app.py
2. Create notebooks referencing silver tables
3. Test measure calculations
```

**Use Cases**:
- **After model build** - Verify silver tables created correctly
- **Debugging query errors** - Check if tables/views exist and are queryable
- **View validation** - Ensure DuckDB views point to correct Parquet files
- **Join troubleshooting** - Verify cross-model relationships work
- **Data quality** - Check sample data and row counts

---

## Testing Scripts

### Test Modular Architecture

**Script**: `scripts/test_modular_architecture.py`

**Purpose**: Test v2.0 modular YAML architecture with inheritance and Python measures.

**Usage**:
```bash
python -m scripts.test_modular_architecture
```

**What it tests**:
1. **ModelConfigLoader** - YAML loading with `extends` and `inherits_from`
2. **Schema inheritance** - Verify child inherits all base fields
3. **Graph inheritance** - Verify nodes/edges merge correctly
4. **Measure inheritance** - Verify YAML + Python measures load
5. **Python measure execution** - Test calling Python measure functions

**Output**:
```
Testing Stocks Model (v2.0 modular architecture)
=================================================

✓ Config loaded successfully
✓ Model: stocks
✓ Dependencies: ['core', 'company']

Schema Check:
  ✓ dim_stock has 15 columns
  ✓ Inherited from base: ticker, asset_type, exchange_code
  ✓ Added fields: company_id, cik, shares_outstanding

Graph Check:
  ✓ 3 nodes defined
  ✓ 5 edges defined
  ✓ Base edges inherited

Measures Check:
  ✓ 15 simple measures (7 inherited + 8 stock-specific)
  ✓ 3 computed measures
  ✓ 6 Python measures

Python Measures Test:
  ✓ Sharpe ratio calculated for AAPL
  ✓ Correlation matrix generated

✅ All tests passed!
```

### Validate All Scripts

**Script**: `scripts/validate_all_scripts.py`

**Purpose**: Ensure all scripts use correct import patterns and can be executed.

**Usage**:
```bash
python -m scripts.validate_all_scripts
```

**What it checks**:
1. **Import syntax** - All scripts use `utils.repo.setup_repo_imports()`
2. **Module execution** - All scripts runnable via `python -m scripts.{name}`
3. **Config usage** - Scripts use `ConfigLoader` correctly
4. **Documentation** - Scripts have docstrings

---

## Workflow Examples

### Complete Setup from Scratch

**Scenario**: Fresh clone, no data, want to get UI running.

```bash
# 1. Setup environment
cp .env.example .env
# Edit .env and add ALPHA_VANTAGE_API_KEYS=your_key

# 2. Install dependencies
pip install -r requirements.txt

# 3. Ingest bronze data (small test)
python -m scripts.test_alpha_vantage_ingestion --tickers AAPL MSFT GOOGL AMZN NVDA

# 4. Build silver layer models
python
>>> from models.api.registry import get_model_registry
>>> registry = get_model_registry()
>>>
>>> # Build in dependency order
>>> registry.get_model("core").build()
>>> registry.get_model("company").build()
>>> registry.get_model("stocks").build()
>>> exit()

# 5. Create DuckDB views
python
>>> import duckdb
>>> conn = duckdb.connect('storage/duckdb/analytics.db')
>>>
>>> # Create schemas
>>> conn.execute("CREATE SCHEMA IF NOT EXISTS stocks")
>>> conn.execute("CREATE SCHEMA IF NOT EXISTS company")
>>> conn.execute("CREATE SCHEMA IF NOT EXISTS core")
>>>
>>> # Create views (example for stocks)
>>> conn.execute("""
...     CREATE OR REPLACE VIEW stocks.dim_stock AS
...     SELECT * FROM read_parquet('storage/silver/stocks/dim_stock/*.parquet', hive_partitioning=true)
... """)
>>>
>>> conn.execute("""
...     CREATE OR REPLACE VIEW stocks.fact_stock_prices AS
...     SELECT * FROM read_parquet('storage/silver/stocks/fact_stock_prices/**/*.parquet', hive_partitioning=true)
... """)
>>>
>>> # Repeat for other tables...
>>> exit()

# 6. Launch UI
python run_app.py
# Opens browser at http://localhost:8501
```

### Diagnose and Fix UI Errors

**Scenario**: UI showing errors like "column not found" or "table not found".

```bash
# 1. Diagnose bronze data
python -m scripts.diagnose_bronze_data

# Look for:
# - "✓ Has v2.0 columns" - Good!
# - "✗ Missing v2.0 columns" - Need to re-ingest with Alpha Vantage

# 2. If bronze data is v1.x (Polygon), re-ingest
python -m scripts.test_alpha_vantage_ingestion --tickers AAPL MSFT

# 3. Rebuild silver layer
python
>>> from models.api.registry import get_model_registry
>>> registry = get_model_registry()
>>> registry.get_model("stocks").build(force=True)  # Force rebuild
>>> exit()

# 4. Check DuckDB views
python
>>> import duckdb
>>> conn = duckdb.connect('storage/duckdb/analytics.db')
>>>
>>> # Test query
>>> result = conn.execute("SELECT COUNT(*) FROM stocks.dim_stock").fetchone()
>>> print(f"Stocks in DuckDB: {result[0]}")
>>>
>>> # If error "table not found", recreate views (see Complete Setup step 5)
>>> exit()

# 5. Relaunch UI
python run_app.py
```

### Add More Tickers

**Scenario**: Have working UI, want to add more stocks.

```bash
# 1. Ingest new tickers
python -m scripts.test_alpha_vantage_ingestion \
    --tickers TSLA META NFLX ORCL INTC \
    --date-from 2024-01-01 \
    --date-to 2024-12-31

# 2. Rebuild stocks model (incremental)
python
>>> from models.api.registry import get_model_registry
>>> registry = get_model_registry()
>>> registry.get_model("stocks").build()  # Merges with existing data
>>> exit()

# 3. DuckDB views auto-update (reading from Parquet files)
# No need to recreate views!

# 4. Refresh UI
# Just refresh the browser page - new stocks appear automatically
```

### Test New Model Development

**Scenario**: Developing new v2.0 model (e.g., options, etfs).

```bash
# 1. Create modular YAML files
mkdir -p configs/models/options
# Create: model.yaml, schema.yaml, graph.yaml, measures.yaml

# 2. Test YAML loading
python -m scripts.test_modular_architecture

# 3. Implement model class
# Create: models/implemented/options/model.py

# 4. Test model build
python
>>> from models.api.registry import get_model_registry
>>> registry = get_model_registry()
>>> options_model = registry.get_model("options")
>>> options_model.build()  # Test build
>>> exit()

# 5. Create DuckDB views
python
>>> import duckdb
>>> conn = duckdb.connect('storage/duckdb/analytics.db')
>>> conn.execute("CREATE SCHEMA IF NOT EXISTS options")
>>> conn.execute("""
...     CREATE OR REPLACE VIEW options.dim_option AS
...     SELECT * FROM read_parquet('storage/silver/options/dim_option/*.parquet')
... """)
>>> exit()

# 6. Test in UI
python run_app.py
# Create notebook referencing options model
```

---

## Script Conventions

### Import Pattern

All scripts use the standardized import pattern:

```python
#!/usr/bin/env python3
"""Script description."""

# Setup repo imports
from utils.repo import setup_repo_imports
setup_repo_imports()

# Now can import from anywhere in repo
from config import ConfigLoader
from models.api.registry import get_model_registry
# ... etc
```

### Execution Pattern

All scripts are executable as modules:

```bash
# ✅ Correct
python -m scripts.script_name

# ❌ Incorrect (may have import issues)
python scripts/script_name.py
```

### Configuration Access

All scripts use `ConfigLoader`:

```python
from config import ConfigLoader

loader = ConfigLoader()
config = loader.load()

# Access typed configuration
print(f"Repo root: {config.repo_root}")
print(f"DuckDB path: {config.connection.duckdb.database_path}")

# Access API configs
alpha_vantage_cfg = config.apis.get('alpha_vantage', {})
api_keys = alpha_vantage_cfg.get('credentials', {}).get('api_keys', [])
```

---

## Troubleshooting

### Common Issues

#### Script Import Errors

**Error**: `ModuleNotFoundError: No module named 'config'`

**Solution**:
```bash
# Run as module, not direct execution
python -m scripts.script_name  # ✅ Correct
python scripts/script_name.py  # ❌ Wrong
```

#### API Key Errors

**Error**: `❌ ERROR: No Alpha Vantage API key found!`

**Solution**:
```bash
# Check .env file
cat .env | grep ALPHA_VANTAGE

# If missing, add it
echo "ALPHA_VANTAGE_API_KEYS=your_key_here" >> .env
```

#### DuckDB Table Not Found

**Error**: `Catalog Error: Table with name stocks.dim_stock does not exist!`

**Solution**:
```python
import duckdb
conn = duckdb.connect('storage/duckdb/analytics.db')

# Recreate view
conn.execute("""
    CREATE OR REPLACE VIEW stocks.dim_stock AS
    SELECT * FROM read_parquet('storage/silver/stocks/dim_stock/*.parquet', hive_partitioning=true)
""")
```

#### Hive Partitioning Error

**Error**: `Binder Error: Referenced column "asset_type" not found`

**Solution**:
```python
# Ensure hive_partitioning=True when reading
conn.execute("""
    CREATE OR REPLACE VIEW stocks.fact_stock_prices AS
    SELECT * FROM read_parquet(
        'storage/silver/stocks/fact_stock_prices/**/*.parquet',
        hive_partitioning=true  -- IMPORTANT: Reads partition columns from paths
    )
""")
```

---

## Future Scripts (Planned)

These scripts don't exist yet but would be valuable additions:

### Build Scripts
- `scripts/build_all_models.py` - Build all models in dependency order
- `scripts/rebuild_model.py` - Rebuild specific model with force flag
- `scripts/create_duckdb_views.py` - Auto-create all DuckDB views

### Ingestion Scripts
- `scripts/ingest_bulk_tickers.py` - Ingest large ticker lists with rate limiting
- `scripts/update_fundamentals.py` - Refresh company fundamental data
- `scripts/backfill_prices.py` - Backfill historical prices for date ranges

### Maintenance Scripts
- `scripts/clean_bronze.py` - Remove old snapshots
- `scripts/optimize_parquet.py` - Compact Parquet files
- `scripts/verify_data_quality.py` - Check for data gaps and anomalies

### Testing Scripts
- `scripts/test_all_models.py` - Test all model builds
- `scripts/test_cross_model_joins.py` - Verify model relationships
- `scripts/benchmark_queries.py` - Performance benchmarking

---

## Additional Resources

- **CLAUDE.md** - Comprehensive codebase guide
- **RUNNING.md** - Application startup guide
- **PIPELINE_GUIDE.md** - Data pipeline documentation
- **docs/configuration.md** - Configuration system details
- **docs/sessions/2025-11-21-streamlit-ui-fixes.md** - Recent UI fixes session
- **docs/sessions/polygon-to-alpha-vantage-pathways.md** - Migration analysis

---

*Last Updated: 2025-11-21*
*Version: 2.0*
