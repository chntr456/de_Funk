# Quick Start Guide

## Running the Application

### Option 1: Run Current UI (Immediate)

The simplest way to start the application:

```bash
streamlit run src/ui/notebook_app_professional.py
```

This runs the existing notebook UI that reads from Bronze data.

**Features:**
- Vault-style directory navigation
- Multiple notebook tabs
- YAML editor
- Filters in sidebar
- Light/dark theme toggle
- Metric cards, charts, and tables

---

### Option 2: Build Silver Layer First (Recommended for Performance)

For better performance with pre-computed measures:

#### Step 1: Build Silver Layer

Run the test script:

```bash
python test_build_silver.py
```

**What this does:**
1. Reads from Bronze layer (`storage/bronze/`)
2. Builds dimension tables:
   - `dim_company` (tickers, company names, exchanges)
   - `dim_exchange` (exchange codes and names)
3. Builds fact tables:
   - `fact_prices` (daily price data)
   - `prices_with_company` (pre-joined with company/exchange info)
4. Writes to Silver layer (`storage/silver/`)
5. Shows sample data from each table
6. Displays row counts

**Expected output:**
```
============================================================
Silver Layer Build Test
============================================================

1. Loading dependencies...
   ✓ Dependencies loaded

2. Initializing Spark context...
   ✓ Repo root: /home/user/de_Funk
   ✓ Spark session: 3.5.0

3. Loading configurations...
   ✓ Storage config loaded
   ✓ Model config loaded (model: company)

4. Checking Bronze data...
   ✓ Bronze data found: 120 parquet files

   Bronze tables:
     • ref_all_tickers
     • exchanges
     • ref_ticker
     • prices_daily
     • news
     • fundamentals

5. Building Silver layer...
   This may take a minute...

   Building with snapshot_date=2024-01-05
   --------------------------------------------------------
Building dim_company...
  Rows: 50
Building dim_exchange...
  Rows: 3
Building fact_prices...
  Rows: 250
Building prices_with_company...
  Rows: 250

Writing to Silver layer...
Writing dim_company...
Writing dim_exchange...
Writing fact_prices...
Writing prices_with_company...

✓ Silver layer build complete!
   --------------------------------------------------------
   ✓ Silver layer build complete!

6. Verifying Silver layer...
   ✓ Silver data created: 40 parquet files

   Silver tables created:
     • dim_company: 50 rows
     • dim_exchange: 3 rows
     • fact_prices: 250 rows
     • prices_with_company: 250 rows

7. Sample data from Silver layer:
   --------------------------------------------------------

   dim_company (first 5 rows):
   [Shows sample data]

============================================================
✓ SUCCESS: Silver layer built successfully!
============================================================

Silver layer location: storage/silver

You can now:
  1. Run the UI: streamlit run src/ui/notebook_app_professional.py
  2. Update UI to use new NotebookService
  3. Query Silver layer directly for analysis
```

#### Step 2: Run UI

After Silver layer is built:

```bash
streamlit run src/ui/notebook_app_professional.py
```

---

## Architecture Overview

### Current Architecture (Option 1)
```
UI → NotebookSession → Bronze Data → Calculate Measures → Display
```

### New Architecture (Option 2 - After Silver Build)
```
UI → NotebookService → Silver Data (Pre-computed) → Display
```

**Benefits of Silver Layer:**
- ⚡ **Faster**: Measures pre-computed
- 🎯 **Cleaner**: Separation of concerns
- 📊 **Better**: Optimized for analytics
- 🔧 **Scalable**: ETL runs offline

---

## Troubleshooting

### PySpark Not Found

If you get `ModuleNotFoundError: No module named 'pyspark'`:

```bash
pip install pyspark
```

### Bronze Data Not Found

If the script says Bronze layer not found, you need to run the data pipeline first:

```bash
python scripts/run_company_pipeline.py
```

This will fetch data from Polygon API and populate Bronze layer.

### Streamlit Not Found

```bash
pip install streamlit plotly pandas
```

---

## What's in the Silver Layer?

After running `test_build_silver.py`, you'll have:

```
storage/silver/
├── company/
│   ├── dims/
│   │   ├── dim_company/      # Companies (ticker, name, exchange)
│   │   └── dim_exchange/     # Exchanges (code, name)
│   └── facts/
│       ├── fact_prices/      # Daily prices
│       └── prices_with_company/  # Prices joined with company info
└── _meta/
    └── manifests/            # Build metadata
```

Each table is versioned and partitioned for efficient querying.

---

## Next Steps

1. ✅ Run `test_build_silver.py` to build Silver layer
2. ✅ Run `streamlit run src/ui/notebook_app_professional.py`
3. 📖 Open `stock_analysis` notebook from sidebar
4. 🎛️ Adjust filters (date range, tickers)
5. 📊 View metric cards, charts, and tables
6. 🌙 Toggle light/dark theme

---

## Files

- `test_build_silver.py` - Build Silver layer test script
- `scripts/build_silver_layer.py` - Production Silver layer builder
- `docs/ARCHITECTURE_REFACTORING.md` - Full architecture documentation
- `src/services/notebook_service.py` - New simplified service
- `src/services/storage_service.py` - Silver layer access service
- `src/model/silver/company_silver_builder.py` - ETL builder
