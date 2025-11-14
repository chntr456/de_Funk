# Equity Pipeline Analysis & Solution

## Issues Identified

### 1. **Missing Silver Data Persistence** ⚠️ CRITICAL
**File:** `scripts/build_all_models.py:562`

```python
dims, facts = model.build()  # ✓ Builds DataFrames in memory
# ❌ MISSING: model.write_tables() to persist to disk
```

**Impact:** Bronze data is transformed but never written to Silver parquet files.

---

### 2. **Missing storage.json Entries** ⚠️ BLOCKER
**File:** `configs/storage.json`

**Missing Entries:**
- `equity_silver` root path
- `dim_equity` table definition
- `dim_exchange` (equity version) table definition
- `fact_equity_prices` table definition
- `fact_equity_technicals` table definition
- `fact_equity_news` table definition

**Current state:** Only old `company` model tables exist (dim_company, fact_prices, etc.)

---

### 3. **Bronze → Silver Mapping is Configured But Not Executing**
**File:** `configs/models/equity.yaml:140-183`

**Configuration EXISTS and is CORRECT:**
```yaml
graph:
  nodes:
    - id: dim_equity
      from: bronze.ref_ticker          # ✓ Correct
    - id: dim_exchange
      from: bronze.exchanges            # ✓ Correct
    - id: fact_equity_prices
      from: bronze.prices_daily         # ✓ Correct
    - id: fact_equity_news
      from: bronze.news                 # ✓ Correct
```

**Bronze Data Status:**
```bash
✓ storage/bronze/ref_ticker       # EXISTS
✓ storage/bronze/exchanges        # EXISTS
✓ storage/bronze/prices_daily     # EXISTS
✓ storage/bronze/news             # EXISTS
```

**Silver Data Status:**
```bash
✗ storage/silver/equity/          # DOES NOT EXIST
```

---

## Root Cause Analysis

### The Problem Chain:
1. `build_all_models.py` calls `model.build()` ✓
2. `model.build()` reads Bronze and creates in-memory DataFrames ✓
3. **MISSING:** `model.write_tables()` to persist DataFrames to Silver ✗
4. Silver parquet files never created ✗
5. Streamlit app tries to read non-existent Silver files ✗
6. Domain measures fail with "No files found" ✗

---

## Solution

### Fix 1: Add `write_tables()` to build_all_models.py

**Location:** `scripts/build_all_models.py:562`

**Change:**
```python
# Current (BROKEN)
dims, facts = model.build()

# Report results
logger.info(f"  ✓ Built {len(dims)} dimensions, {len(facts)} facts")
```

**To:**
```python
# Fixed (WORKING)
dims, facts = model.build()

# Report results
logger.info(f"  ✓ Built {len(dims)} dimensions, {len(facts)} facts")

# ✅ ADD THIS: Write to Silver layer
logger.info(f"  Writing {model_name} tables to Silver...")
stats = model.write_tables(use_optimized_writer=True)
logger.info(f"  ✓ Wrote tables to Silver layer")
```

---

### Fix 2: Update storage.json

**Location:** `configs/storage.json`

**Add these entries:**

```json
{
  "connection": {
    "type": "spark"
  },
  "roots": {
    "bronze": "storage/bronze",
    "silver": "storage/silver",
    "core_silver": "storage/silver/core",
    "company_silver": "storage/silver/company",
    "equity_silver": "storage/silver/equity",        ← ADD THIS
    "corporate_silver": "storage/silver/corporate",  ← ADD THIS (for future)
    "forecast_silver": "storage/silver/forecast",
    "macro_silver": "storage/silver/macro",
    "city_finance_silver": "storage/silver/city_finance"
  },
  "tables": {
    "calendar_seed": { "root": "bronze", "rel": "calendar_seed", "partitions": [] },

    "ref_all_tickers": { "root": "bronze", "rel": "ref_all_tickers", "partitions": ["snapshot_dt"] },
    "exchanges": { "root": "bronze", "rel": "exchanges", "partitions": ["snapshot_dt"] },
    "ref_ticker": { "root": "bronze", "rel": "ref_ticker", "partitions": ["snapshot_dt"] },
    "prices_daily": { "root": "bronze", "rel": "prices_daily", "partitions": ["trade_date"] },
    "news": { "root": "bronze", "rel": "news", "partitions": ["publish_date"] },
    "fundamentals": { "root": "bronze", "rel": "fundamentals", "partitions": ["fiscal_year","fiscal_period"] },

    "bls_unemployment": { "root": "bronze", "rel": "bls/unemployment", "partitions": ["year"] },
    "bls_cpi": { "root": "bronze", "rel": "bls/cpi", "partitions": ["year"] },
    "bls_employment": { "root": "bronze", "rel": "bls/employment", "partitions": ["year"] },
    "bls_wages": { "root": "bronze", "rel": "bls/wages", "partitions": ["year"] },

    "chicago_unemployment": { "root": "bronze", "rel": "chicago/unemployment", "partitions": ["date"] },
    "chicago_building_permits": { "root": "bronze", "rel": "chicago/building_permits", "partitions": ["issue_date"] },
    "chicago_business_licenses": { "root": "bronze", "rel": "chicago/business_licenses", "partitions": ["start_date"] },
    "chicago_economic_indicators": { "root": "bronze", "rel": "chicago/economic_indicators", "partitions": ["date"] },

    // OLD COMPANY MODEL TABLES (keep for backward compatibility)
    "dim_company": { "root": "silver", "rel": "company/dims/dim_company" },
    "dim_exchange": { "root": "silver", "rel": "company/dims/dim_exchange" },
    "fact_prices": { "root": "silver", "rel": "company/facts/fact_prices" },
    "fact_news": { "root": "silver", "rel": "company/facts/fact_news" },
    "prices_with_company": { "root": "silver", "rel": "company/facts/prices_with_company" },
    "news_with_company": { "root": "silver", "rel": "company/facts/news_with_company" },

    // ✅ NEW EQUITY MODEL TABLES (ADD THESE)
    "dim_equity": { "root": "equity_silver", "rel": "dims/dim_equity" },
    "fact_equity_prices": { "root": "equity_silver", "rel": "facts/fact_equity_prices", "partitions": ["trade_date"] },
    "fact_equity_technicals": { "root": "equity_silver", "rel": "facts/fact_equity_technicals", "partitions": ["trade_date"] },
    "fact_equity_news": { "root": "equity_silver", "rel": "facts/fact_equity_news", "partitions": ["publish_date"] },
    "equity_prices_with_company": { "root": "equity_silver", "rel": "facts/equity_prices_with_company", "partitions": ["trade_date"] },
    "equity_news_with_company": { "root": "equity_silver", "rel": "facts/equity_news_with_company", "partitions": ["publish_date"] }
  }
}
```

---

## Quick Fix Script

Create: `scripts/build_equity_silver.py`

```python
#!/usr/bin/env python3
"""
Build Equity Silver Layer from existing Bronze data.

This script:
1. Loads equity model configuration
2. Reads from Bronze (ref_ticker, prices_daily, exchanges, news)
3. Transforms and builds Silver tables
4. Writes parquet files to storage/silver/equity/

Usage:
    python scripts/build_equity_silver.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.context import RepoContext
from models.api.session import UniversalSession

def main():
    print("=" * 70)
    print("Building Equity Silver Layer")
    print("=" * 70)

    # Initialize with Spark (required for writes)
    ctx = RepoContext.from_repo_root(connection_type="spark")

    # Create session
    session = UniversalSession(
        connection=ctx.spark,
        storage_cfg=ctx.storage,
        repo_root=Path.cwd()
    )

    # Load equity model
    print("\n1. Loading equity model...")
    equity_model = session.get_model_instance('equity')
    print("   ✓ Equity model loaded")

    # Build Silver layer (in-memory DataFrames from Bronze)
    print("\n2. Building Silver tables from Bronze...")
    dims, facts = equity_model.build()

    print(f"   ✓ Built {len(dims)} dimensions:")
    for table_name in dims.keys():
        print(f"     - {table_name}")

    print(f"   ✓ Built {len(facts)} facts:")
    for table_name in facts.keys():
        print(f"     - {table_name}")

    # Write to Silver parquet files
    print("\n3. Writing tables to Silver storage...")
    stats = equity_model.write_tables(use_optimized_writer=True)
    print("   ✓ Tables written successfully")

    # Report row counts
    print("\n4. Verifying Silver tables:")
    for table_name, df in {**dims, **facts}.items():
        try:
            count = df.count()
            print(f"   ✓ {table_name}: {count:,} rows")
        except Exception as e:
            print(f"   ⚠ {table_name}: Unable to count rows ({e})")

    print("\n" + "=" * 70)
    print("✓ Equity Silver layer built successfully!")
    print("=" * 70)
    print("\nSilver files written to: storage/silver/equity/")
    print("\nYou can now run:")
    print("  streamlit run app/ui/notebook_app_duckdb.py")

    ctx.spark.stop()

if __name__ == "__main__":
    main()
```

---

## Execution Plan

### Step 1: Fix build_all_models.py
```bash
# Add model.write_tables() call at line 562
```

### Step 2: Update storage.json
```bash
# Add equity_silver root and table entries
```

### Step 3: Build Equity Silver Layer
```bash
python scripts/build_equity_silver.py
```

**Expected Output:**
```
Building Equity Silver Layer
======================================================================

1. Loading equity model...
   ✓ Equity model loaded

2. Building Silver tables from Bronze...
   ✓ Built 2 dimensions:
     - dim_equity
     - dim_exchange
   ✓ Built 2 facts:
     - fact_equity_prices
     - fact_equity_news

3. Writing tables to Silver storage...
   ✓ Tables written successfully

4. Verifying Silver tables:
   ✓ dim_equity: 2,000 rows
   ✓ dim_exchange: 15 rows
   ✓ fact_equity_prices: 500,000 rows
   ✓ fact_equity_news: 10,000 rows

======================================================================
✓ Equity Silver layer built successfully!
======================================================================

Silver files written to: storage/silver/equity/
```

### Step 4: Test Domain Measures
```bash
python examples/domain_strategy_measures_example.py
```

### Step 5: View in Streamlit
```bash
streamlit run app/ui/notebook_app_duckdb.py
# Navigate to "Domain Strategy Measures Showcase"
```

---

## Verification

After running the fixes, verify:

1. **Silver files exist:**
```bash
ls -la storage/silver/equity/dims/
ls -la storage/silver/equity/facts/
```

2. **Table counts:**
```bash
python -c "
from core.context import RepoContext
ctx = RepoContext.from_repo_root(connection_type='duckdb')
from models.api.session import UniversalSession
session = UniversalSession(ctx.connection, ctx.storage, ctx.repo)
equity = session.get_model_instance('equity')
prices = equity.get_table('fact_equity_prices').df()
print(f'Prices: {len(prices)} rows')
"
```

3. **Domain measures work:**
```bash
python examples/domain_strategy_measures_example.py
# Should show weighted indices data, not errors
```

---

## Summary

**Root Issue:** `build_all_models.py` builds DataFrames but doesn't persist them.

**Quick Fix:** Run `python scripts/build_equity_silver.py` (create this script)

**Proper Fix:**
1. Update `build_all_models.py` to call `model.write_tables()`
2. Update `storage.json` with equity table definitions
3. Rebuild all models

**Timeline:**
- Quick fix: 5 minutes (create + run script)
- Proper fix: 15 minutes (update files + test)

---

*Generated: 2025-11-14*
