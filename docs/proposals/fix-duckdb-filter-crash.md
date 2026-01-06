# Proposal: Fix DuckDB Filter System Crashes

**Date**: 2025-12-07
**Updated**: 2026-01-06
**Status**: ✅ COMPLETED
**Priority**: High
**Author**: Claude (AI Assistant)

## ✅ Resolution Summary

All crash issues have been resolved. The root causes were:

1. **Bronze reads during queries** - Session was falling back to `model.get_table()` which triggered `ensure_built()` → graph_builder → Bronze Delta reads for 22M+ rows
2. **fetchdf() loading all data** - DuckDB queries were calling `.fetchdf()` which materialized entire result sets into pandas memory
3. **Stale DuckDB views** - Views pointed to wrong storage paths and weren't auto-refreshed

## Fixes Applied (January 2026)

### 1. Removed ALL Bronze Fallbacks from Query Paths

**Files Changed:**
- `models/api/session.py`
- `models/api/auto_join.py`

**Changes:**
- `_get_table_from_view_or_build()`: Strategy 4 (Bronze fallback) now raises `ValueError` instead of calling `model.get_table()`
- `get_table()`: Removed try/except fallback to `model.get_table()`
- `_execute_join_with_temp_tables()`: Changed exception handler to raise `RuntimeError` instead of falling back to Bronze
- Materialized view lookup now uses `_get_table_from_view_or_build()` with `allow_build=False`

### 2. Fixed fetchdf() Memory Issues

**Files Changed:**
- `models/api/auto_join.py`

**Changes:**
- `_execute_duckdb_joins_via_views()`: Changed from `result.fetchdf()` to `conn.sql(sql)` for lazy evaluation
- `_execute_join_with_temp_tables()`: Changed from `result.fetchdf()` to `conn.sql(sql)` for lazy evaluation

### 3. Fixed _build_select_cols() Bronze Trigger

**Files Changed:**
- `models/api/auto_join.py`

**Changes:**
- `_build_select_cols()`: Changed from calling `model.get_table()` to using `DESCRIBE {temp_table}` on already-registered temp tables

### 4. DuckDB View Auto-Refresh

**Files Changed:**
- `core/duckdb_connection.py`
- `scripts/setup/setup_duckdb_views.py`

**Changes:**
- View validation now checks BOTH dimensions AND facts (e.g., `dim_stock` AND `fact_stock_prices`)
- If any view fails validation, ALL views are recreated with correct storage paths
- Setup script now reads `storage_path` from `run_config.json` (default: `/shared/storage`)
- Added `--storage-path` CLI argument for manual override

### 5. Storage Path Resolution

**Files Changed:**
- `models/api/session.py`
- `scripts/setup/setup_duckdb_views.py`
- `core/duckdb_connection.py`

**Changes:**
- `_get_table_from_view_or_build()`: Uses `self.storage_cfg['roots']['silver']` which resolves to `/shared/storage/silver`
- Setup script reads from `run_config.json` defaults instead of repo-relative paths

## Query Path After Fixes

```
Query Request
  → Check DuckDB View
    → If valid: Return lazy DuckDB relation
    → If invalid: Auto-refresh views, retry
  → If no view: Read from Silver Delta files directly
    → Use delta_scan('/shared/storage/silver/...')
  → If no Silver: Raise ValueError with build instructions
  → NEVER: Read from Bronze (removed entirely)
```

## Commits

1. `fix: Prevent memory crash and Bronze reads in auto-join`
2. `fix: Auto-refresh stale DuckDB views on app load`
3. `fix: Use DESCRIBE instead of model.get_table() in _build_select_cols`
4. `fix: Remove Bronze fallbacks and improve view validation`
5. `refactor: Remove all Bronze fallbacks from query paths`

---

# Next Steps: Bronze Ingestion Expansion & Airflow

**Status**: Ready for Implementation
**Priority**: Medium
**Target**: Next Session

## Objective

Expand the Bronze ingestion pipeline and integrate with Apache Airflow for orchestration.

## Current State

- Bronze ingestion works via `scripts/ingest/run_bronze_ingestion.py`
- Uses Alpha Vantage as sole securities provider
- Spark-based processing with Delta Lake storage at `/shared/storage/bronze/`
- Profile-based configuration via `run_config.json`

## Proposed Enhancements

### 1. Additional Alpha Vantage Endpoints

Currently supported:
- `time_series_daily` - Daily OHLCV
- `company_overview` - Company fundamentals
- `income_statement` - Income statements
- `balance_sheet` - Balance sheets
- `cash_flow` - Cash flow statements
- `earnings` - Earnings data

Potential additions:
- `global_quote` - Real-time quotes
- `time_series_intraday` - Intraday data
- `technical_indicators` - Pre-computed technicals (SMA, EMA, RSI, etc.)
- `news_sentiment` - News and sentiment data
- `economic_indicators` - Economic data (from Alpha Vantage)

### 2. Airflow Integration

**DAG Structure:**
```
bronze_ingestion_dag/
├── seed_tickers_task       # Seed from LISTING_STATUS (daily)
├── ingest_prices_task      # Daily OHLCV (hourly)
├── ingest_fundamentals_task # Company overview (daily)
├── ingest_financials_task  # Quarterly financials (weekly)
└── build_silver_task       # Build Silver models (after ingestion)
```

**Key Considerations:**
- Rate limiting: Alpha Vantage free tier = 5 calls/min, premium = 75 calls/min
- Incremental ingestion: Only fetch new/updated data
- Error handling: Retry with exponential backoff
- Monitoring: Track API usage and costs

### 3. Configuration Updates

**run_config.json additions:**
```json
{
  "airflow": {
    "enabled": true,
    "dag_schedule": "@hourly",
    "max_concurrent_tasks": 5,
    "retry_count": 3
  },
  "providers": {
    "alpha_vantage": {
      "endpoints": [
        "time_series_daily",
        "company_overview",
        "technical_indicators"  // NEW
      ],
      "rate_limit_calls_per_min": 75,
      "incremental": true
    }
  }
}
```

### 4. Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `orchestration/airflow/dags/bronze_dag.py` | CREATE | Main Bronze ingestion DAG |
| `orchestration/airflow/dags/silver_dag.py` | CREATE | Silver model build DAG |
| `orchestration/airflow/operators/alpha_vantage.py` | CREATE | Custom AV operator |
| `datapipelines/providers/alpha_vantage/technical_indicators.py` | CREATE | Technical indicators facet |
| `configs/pipelines/alpha_vantage_endpoints.json` | MODIFY | Add new endpoints |
| `scripts/ingest/run_bronze_ingestion.py` | MODIFY | Add Airflow hooks |

### 5. Testing Strategy

1. Unit tests for new facets
2. Integration tests with mock API responses
3. End-to-end test with sample tickers
4. Airflow DAG validation (dry run)

## Key Code Locations

| Component | Location |
|-----------|----------|
| Bronze ingestion | `scripts/ingest/run_bronze_ingestion.py` |
| Alpha Vantage provider | `datapipelines/providers/alpha_vantage/` |
| Pipeline config | `configs/pipelines/run_config.json` |
| Endpoint config | `configs/pipelines/alpha_vantage_endpoints.json` |
| Silver build | `scripts/build/build_models.py` |

## References

- Alpha Vantage API docs: https://www.alphavantage.co/documentation/
- Airflow docs: https://airflow.apache.org/docs/
- Current ingestion guide: `docs/guide/PIPELINE_GUIDE.md`
