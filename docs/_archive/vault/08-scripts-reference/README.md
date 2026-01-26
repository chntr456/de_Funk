# Scripts Reference

**Operational scripts for de_Funk**

---

## Overview

Scripts are organized by function in the `scripts/` directory:

| Category | Location | Purpose |
|----------|----------|---------|
| [Build](build-scripts.md) | `scripts/build/` | Silver layer construction |
| [Ingestion](ingestion-scripts.md) | `scripts/ingest/` | API data ingestion |
| [Forecast](forecast-scripts.md) | `scripts/forecast/` | Time series predictions |
| [Maintenance](maintenance-scripts.md) | `scripts/maintenance/` | Data cleanup and reset |
| [Debug](debug-scripts.md) | `scripts/debug/` | Diagnostics and troubleshooting |
| [Quick Reference](quick-reference.md) | - | Command cheatsheet |

---

## Running Scripts

All scripts should be run using the `python -m` module syntax:

```bash
# Correct
python -m scripts.build.build_all_models

# Incorrect (may have import issues)
python scripts/build/build_all_models.py
```

---

## Common Operations

### Full Pipeline

```bash
# Ingest data and build all models
python -m scripts.ingest.run_full_pipeline --top-n 100
```

### Build Models

```bash
# Build all models
python -m scripts.build.build_all_models

# Build specific model
python -m scripts.build.rebuild_model --model stocks
```

### Forecasting

```bash
# Run all forecasts
python -m scripts.forecast.run_forecasts
```

### Maintenance

```bash
# Clear and refresh all data
python -m scripts.maintenance.clear_and_refresh

# Reset specific model
python -m scripts.maintenance.reset_model --model stocks
```

### Diagnostics

```bash
# Check Bronze data
python -m scripts.diagnose_bronze_data

# Check Silver data
python -m scripts.diagnose_silver_data

# Test API connectivity
python -m scripts.test.test_alpha_vantage_api
```

---

## Script Categories

### Build Scripts

| Script | Purpose |
|--------|---------|
| `build_all_models.py` | Build all Silver layer models |
| `build_silver_layer.py` | Build Silver from Bronze |
| `rebuild_model.py` | Rebuild specific model |
| `build_weighted_aggregates_duckdb.py` | Build weighted aggregates |

### Ingestion Scripts

| Script | Purpose |
|--------|---------|
| `run_full_pipeline.py` | Complete ETL pipeline |
| `Bronze_pull.py` | Pull raw Bronze data |
| `ingest_alpha_vantage_bulk.py` | Bulk Alpha Vantage ingestion |

### Forecast Scripts

| Script | Purpose |
|--------|---------|
| `run_forecasts.py` | Generate all forecasts |
| `run_forecasts_large_cap.py` | Large cap forecasts |
| `verify_forecast_config.py` | Validate forecast config |

### Maintenance Scripts

| Script | Purpose |
|--------|---------|
| `clear_and_refresh.py` | Clear cache and refresh |
| `clear_bronze.py` | Clear Bronze layer |
| `clear_silver.py` | Clear Silver layer |
| `reset_model.py` | Reset model state |

### Debug Scripts

| Script | Purpose |
|--------|---------|
| `debug_weighted_views.py` | Debug weighted views |
| `debug_forecast_view.py` | Debug forecast views |
| `check_parquet_path.py` | Check Parquet paths |
| `diagnose_view_data.py` | Diagnose view data |

---

## Examples Directory

The `scripts/examples/` directory contains runnable code examples:

```
scripts/examples/
├── 00_QUICKSTART.py              # Start here
├── README.md                     # Examples guide
├── parameter_interface/          # Calculator interface
├── weighting_strategies/         # Portfolio weighting
├── measure_calculations/         # Measure usage
├── queries/                      # Query examples
├── extending/                    # Extension examples
└── backend_comparison/           # DuckDB vs Spark
```

See [Examples Catalog](../09-examples-catalog/README.md) for details.

---

## Script Arguments

Common arguments across scripts:

| Argument | Description | Example |
|----------|-------------|---------|
| `--model` | Target model name | `--model stocks` |
| `--top-n` | Limit to N tickers | `--top-n 100` |
| `--days` | Number of days | `--days 30` |
| `--backend` | Database backend | `--backend duckdb` |
| `--dry-run` | Preview without executing | `--dry-run` |

---

## Related Documentation

- [Quick Reference](quick-reference.md) - Command cheatsheet
- [Examples Catalog](../09-examples-catalog/README.md) - Code examples
- [Testing Guide](../10-testing-guide/README.md) - Test scripts
- [Pipelines](../06-pipelines/README.md) - ETL documentation
