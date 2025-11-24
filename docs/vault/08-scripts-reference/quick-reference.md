# Scripts Quick Reference

**Command cheatsheet for common operations**

---

## Data Ingestion

```bash
# Full pipeline (recommended)
python -m scripts.ingest.run_full_pipeline --top-n 100

# Full pipeline with more tickers
python -m scripts.ingest.run_full_pipeline --top-n 500

# Bulk Alpha Vantage ingestion
python -m scripts.ingest.ingest_alpha_vantage_bulk

# Pull Bronze data only
python -m scripts.ingest.Bronze_pull
```

---

## Model Building

```bash
# Build all models (in dependency order)
python -m scripts.build.build_all_models

# Build Silver layer only
python -m scripts.build.build_silver_layer

# Rebuild specific model
python -m scripts.build.rebuild_model --model stocks
python -m scripts.build.rebuild_model --model company
python -m scripts.build.rebuild_model --model macro

# Build weighted aggregates
python -m scripts.build.build_weighted_aggregates_duckdb
```

---

## Forecasting

```bash
# Run all forecasts
python -m scripts.forecast.run_forecasts

# Large cap forecasts only
python -m scripts.forecast.run_forecasts_large_cap

# Verify forecast configuration
python -m scripts.forecast.verify_forecast_config
```

---

## Maintenance

```bash
# Clear all and refresh
python -m scripts.maintenance.clear_and_refresh

# Clear Bronze layer
python -m scripts.maintenance.clear_bronze

# Clear Silver layer
python -m scripts.maintenance.clear_silver

# Reset specific model
python -m scripts.maintenance.reset_model --model stocks
```

---

## Diagnostics

```bash
# Check Bronze data
python -m scripts.diagnose_bronze_data

# Check Silver data
python -m scripts.diagnose_silver_data

# Test Alpha Vantage API
python -m scripts.test.test_alpha_vantage_api

# Check DuckDB setup
python -m scripts.test.test_duckdb_setup

# Check Parquet paths
python -m scripts.debug.check_parquet_path
```

---

## Testing

```bash
# Run all tests
pytest

# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# Validation tests
pytest scripts/test/validation/

# Specific test file
pytest tests/unit/test_measure_framework.py -v

# Backend compatibility
bash scripts/test/validation/run_backend_tests.sh
```

---

## Application

```bash
# Start Streamlit UI
python run_app.py

# Or directly
streamlit run app/ui/notebook_app_duckdb.py

# Using shell script
./run_app.sh
```

---

## Examples

```bash
# Quickstart (start here)
python -m scripts.examples.00_QUICKSTART

# Measure calculations
python -m scripts.examples.measure_calculations.01_basic_measures

# Weighting strategies
python -m scripts.examples.weighting_strategies.01_basic_weighted_price

# Query examples
python -m scripts.examples.queries.01_auto_join
```

---

## Environment

```bash
# Create/update .env from example
cp .env.example .env

# Edit with your API keys
nano .env

# Required keys:
# ALPHA_VANTAGE_API_KEYS=your_key
# BLS_API_KEYS=your_key (optional)
# CHICAGO_API_KEYS=your_key (optional)
```

---

## Common Workflows

### Initial Setup

```bash
# 1. Set up environment
cp .env.example .env
# Edit .env with API keys

# 2. Ingest initial data
python -m scripts.ingest.run_full_pipeline --top-n 50

# 3. Build models
python -m scripts.build.build_all_models

# 4. Verify data
python -m scripts.diagnose_silver_data

# 5. Start UI
python run_app.py
```

### Daily Update

```bash
# 1. Ingest latest data
python -m scripts.ingest.run_full_pipeline --days 1

# 2. Rebuild models
python -m scripts.build.build_all_models

# 3. Run forecasts
python -m scripts.forecast.run_forecasts
```

### Reset and Rebuild

```bash
# 1. Clear all data
python -m scripts.maintenance.clear_and_refresh

# 2. Re-ingest
python -m scripts.ingest.run_full_pipeline --top-n 100

# 3. Rebuild
python -m scripts.build.build_all_models
```

---

## Flags Reference

| Flag | Used In | Description |
|------|---------|-------------|
| `--model NAME` | rebuild_model, reset_model | Target model |
| `--top-n N` | run_full_pipeline | Limit tickers |
| `--days N` | run_full_pipeline | Days of data |
| `--backend NAME` | Various | duckdb or spark |
| `--dry-run` | Various | Preview only |
| `-v` / `--verbose` | Various | Verbose output |

---

## Related Documentation

- [Scripts Reference](README.md) - Detailed script docs
- [Pipelines](../06-pipelines/README.md) - ETL details
- [Testing Guide](../10-testing-guide/README.md) - Test docs
