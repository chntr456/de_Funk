# Build All Models Guide

Complete guide for building all domain models with paginated data ingestion from real data sources.

## Overview

`build_all_models.py` orchestrates complete data pipelines across all domains:

1. **Model Discovery**: Automatically finds all models in `configs/models/`
2. **Paginated Ingestion**: Pulls real data from APIs (Polygon, BLS, Chicago) to Bronze layer
3. **Silver Layer Build**: Transforms Bronze data to Silver layer using model configurations
4. **Progress Reporting**: Tracks success/failure across all models

**This is NOT a testing script** - it works with real data from production APIs.

## Quick Start

### Build All Models (Default Settings)

```bash
# Build all models with last 30 days of data
python scripts/build_all_models.py
```

### Build Specific Models

```bash
# Build only equity and corporate models
python scripts/build_all_models.py --models equity corporate

# Build single model
python scripts/build_all_models.py --models company
```

### With Date Range

```bash
# Full year of data
python scripts/build_all_models.py --date-from 2024-01-01 --date-to 2024-12-31

# Last 90 days
python scripts/build_all_models.py --days 90
```

### Development Mode (Limited Data)

```bash
# Test with small dataset (20 tickers, recent data)
python scripts/build_all_models.py --max-tickers 20 --days 30

# Quick rebuild from existing Bronze (skip ingestion)
python scripts/build_all_models.py --skip-ingestion
```

### Parallel Execution

```bash
# Build models in parallel (faster)
python scripts/build_all_models.py --parallel

# Control parallel workers
python scripts/build_all_models.py --parallel --max-workers 4
```

### Dry Run

```bash
# See what would be done without executing
python scripts/build_all_models.py --dry-run
```

## How It Works

### 1. Model Discovery

Automatically discovers all models from `configs/models/`:

- **Polygon Models**: company, equity, corporate (market data from Polygon API)
- **BLS Models**: macro (economic data from Bureau of Labor Statistics)
- **Chicago Models**: city_finance (municipal data from Chicago Data Portal)
- **Derived Models**: forecast, etf (built from other models, no direct ingestion)
- **Core Models**: core (reference data like calendar)

### 2. Dependency Ordering

Models are built in dependency order:

1. Core models (calendar, reference data)
2. Data models with ingestion (company, equity, macro, etc.)
3. Derived models (forecast, etf)

### 3. Paginated Ingestion

Each data source uses appropriate pagination:

**Polygon API** (company, equity, corporate):
- Cursor-based pagination via `next_url`
- Date range partitioning (prices_daily, news)
- Snapshot partitioning (ref_ticker, exchanges)
- Skip-if-exists logic (partition level)
- Ticker filtering (MAJOR_COMPANIES list for top-N)

**BLS API** (macro):
- POST with JSON body (series IDs + year range)
- No pagination needed (returns complete dataset)
- Series-based data model

**Chicago Data Portal** (city_finance):
- Offset-based pagination ($offset, $limit)
- Socrata API standard
- Auto-pagination through all pages

### 4. Silver Layer Building

For each model:
1. Load model configuration (YAML)
2. Instantiate model class (or BaseModel)
3. Execute `model.build()` to create Silver tables
4. Report row counts and status

### 5. Progress Reporting

Real-time progress tracking:
- Per-model status (SUCCESS/FAILED)
- Row counts per table
- Duration tracking
- Error details
- JSON output for historical tracking

## Usage Examples

### Production: Full Data Build

```bash
# Build all models with complete data for 2024
python scripts/build_all_models.py \
  --date-from 2024-01-01 \
  --date-to 2024-12-31 \
  --output build_results/$(date +%Y%m%d)_full_build.json
```

### Development: Quick Test

```bash
# Test with limited data
python scripts/build_all_models.py \
  --models equity \
  --max-tickers 10 \
  --days 7 \
  --dry-run

# Execute after verifying
python scripts/build_all_models.py \
  --models equity \
  --max-tickers 10 \
  --days 7
```

### Maintenance: Rebuild from Bronze

```bash
# Rebuild Silver layer without re-ingesting
python scripts/build_all_models.py --skip-ingestion
```

### CI/CD: Parallel Build

```bash
# Fast parallel build for automated pipelines
python scripts/build_all_models.py \
  --parallel \
  --max-workers 4 \
  --output build_results/ci_build_$(date +%Y%m%d_%H%M%S).json
```

### Incremental: Specific Domains

```bash
# Update only market data models
python scripts/build_all_models.py \
  --models company equity corporate \
  --days 1  # Just today's data

# Update only macro models
python scripts/build_all_models.py \
  --models macro \
  --skip-ingestion  # Use existing Bronze
```

## Output Example

```
======================================================================
BUILDING ALL MODELS
======================================================================
Models: 8
Date range: 2024-01-01 to 2024-12-31
Max tickers: None
Skip ingestion: False
Parallel: True
Dry run: False

Discovered 8 model(s): core, company, equity, corporate, macro, city_finance, forecast, etf

Running builds in parallel with 3 workers...

======================================================================
MODEL 1/8: core
======================================================================
Step 1/2: Ingestion skipped for core
Step 2/2: Building core Silver layer...
  Building core graph...
  ✓ Built 1 dimensions, 0 facts
    - dim_calendar: 365 rows
  ✓ Silver layer built for core
✓ All steps completed for core

======================================================================
MODEL 2/8: company
======================================================================
Step 1/2: Running company ingestion...
  Running Polygon ingestion (paginated)...
  ✓ Ingested data for 8,234 tickers
  ✓ Ingestion completed for company
Step 2/2: Building company Silver layer...
  Building company graph...
  ✓ Built 2 dimensions, 2 facts
    - dim_company: 8,234 rows
    - dim_exchange: 23 rows
    - fact_prices: 1,523,450 rows
    - fact_news: 45,678 rows
  ✓ Silver layer built for company
✓ All steps completed for company

✓ equity - SUCCESS
✓ corporate - SUCCESS
✓ company - SUCCESS
✓ core - SUCCESS
✓ macro - SUCCESS
✓ city_finance - SUCCESS
✓ forecast - SUCCESS
✓ etf - SUCCESS

======================================================================
ALL MODELS BUILD SUMMARY
======================================================================

Total duration: 342.56s

Models processed: 8
Succeeded: 8
Failed: 0

Per-model results:
  ✓ SUCCESS - core
  ✓ SUCCESS - company
  ✓ SUCCESS - equity
  ✓ SUCCESS - corporate
  ✓ SUCCESS - macro
  ✓ SUCCESS - city_finance
  ✓ SUCCESS - forecast
  ✓ SUCCESS - etf

======================================================================
✓ ALL MODELS BUILT SUCCESSFULLY
======================================================================

Results saved to: build_results/20251113_full_build.json
```

## Results JSON Format

```json
{
  "start_time": "2025-11-13T10:00:00",
  "end_time": "2025-11-13T10:05:42",
  "models_processed": 8,
  "models_succeeded": 8,
  "models_failed": 0,
  "model_results": {
    "core": {
      "success": true,
      "timestamp": "2025-11-13T10:00:15"
    },
    "company": {
      "success": true,
      "timestamp": "2025-11-13T10:03:45"
    },
    "equity": {
      "success": true,
      "timestamp": "2025-11-13T10:04:30"
    }
  }
}
```

## Command Reference

### Required Arguments

None - all arguments are optional with sensible defaults.

### Optional Arguments

**Model Selection:**
- `--models MODEL [MODEL ...]` - Specific models to build (default: all)
- `--config-dir DIR` - Model config directory (default: `configs/models`)

**Date Range (for market data):**
- `--date-from YYYY-MM-DD` - Start date
- `--date-to YYYY-MM-DD` - End date
- `--days N` - Alternative to date range (recent N days)
- Default: Last 30 days

**Data Control:**
- `--max-tickers N` - Limit tickers (for development/testing, Polygon models only)
- `--skip-ingestion` - Skip Bronze ingestion (use existing Bronze data)

**Execution:**
- `--parallel` - Build models in parallel
- `--max-workers N` - Max parallel workers (default: 3)
- `--dry-run` - Show what would be done without executing

**Output:**
- `--output FILE` - Save results to JSON file

## Common Workflows

### 1. Initial Setup - Full Historical Build

```bash
# Build all models with full year of data
python scripts/build_all_models.py \
  --date-from 2024-01-01 \
  --date-to 2024-12-31 \
  --output build_results/initial_build.json
```

**Use case**: First-time setup, populate all models with historical data

**Duration**: ~30-60 minutes (depending on data volume and API rate limits)

### 2. Daily Incremental Update

```bash
# Update with yesterday's data
python scripts/build_all_models.py --days 1

# Or use specific date
python scripts/build_all_models.py \
  --date-from 2025-01-13 \
  --date-to 2025-01-13
```

**Use case**: Daily scheduled job to keep data current

**Duration**: ~2-5 minutes

### 3. Development Testing

```bash
# Quick test with small dataset
python scripts/build_all_models.py \
  --models equity \
  --max-tickers 5 \
  --days 7 \
  --dry-run

# Run after verifying
python scripts/build_all_models.py \
  --models equity \
  --max-tickers 5 \
  --days 7
```

**Use case**: Testing changes to model configurations

**Duration**: < 1 minute

### 4. Schema Migration - Rebuild Silver

```bash
# Rebuild Silver from existing Bronze (after schema change)
python scripts/build_all_models.py --skip-ingestion
```

**Use case**: After updating model YAML configs or transformation logic

**Duration**: ~5-10 minutes

### 5. Specific Domain Update

```bash
# Update only market data models
python scripts/build_all_models.py \
  --models company equity corporate \
  --days 7

# Update only macro models
python scripts/build_all_models.py \
  --models macro
```

**Use case**: Selective updates when only certain data sources have new data

**Duration**: Varies by domain

### 6. Parallel Production Build

```bash
# Fast build for CI/CD pipelines
python scripts/build_all_models.py \
  --parallel \
  --max-workers 4 \
  --days 30 \
  --output build_results/$(date +%Y%m%d_%H%M%S)_build.json
```

**Use case**: Automated builds in CI/CD with time constraints

**Duration**: ~60% faster than sequential

## Model Categories

### Polygon Models (Market Data)

**Models**: company, equity, corporate

**Data Sources**:
- ref_all_tickers (snapshot of all active tickers)
- exchanges (exchange reference data)
- ref_ticker (per-ticker details)
- prices_daily (OHLCV data, partitioned by trade_date)
- news (news articles, partitioned by publish_date)

**Pagination**: Cursor-based (next_url), partition-level skip-if-exists

**API Rate Limits**:
- Free tier: 5 requests/minute
- Paid tier: varies by plan

**Data Volume** (typical):
- Tickers: ~8,000 active US equities
- Daily prices: ~1.5M rows/year
- News: ~50k articles/year

### BLS Models (Economic Data)

**Models**: macro

**Data Sources**:
- bls_unemployment (unemployment rates by series)
- bls_cpi (Consumer Price Index)
- bls_employment (employment statistics)
- bls_wages (wage statistics)

**Pagination**: None (full dataset returned in single response)

**API**: POST with JSON body (series IDs + year range)

**API Rate Limits**:
- Registered: 500 queries/day, 50 series/query

**Data Volume** (typical):
- Series: ~100 tracked series
- Data points: ~1,000 rows/year

### Chicago Models (Municipal Data)

**Models**: city_finance

**Data Sources**:
- chicago_unemployment (local unemployment by community area)
- chicago_building_permits (building permit records)

**Pagination**: Offset-based ($offset, $limit)

**API**: Socrata open data platform

**API Rate Limits**:
- Anonymous: 1,000 requests/day
- Registered: 100,000 requests/day

**Data Volume** (typical):
- Permits: ~40,000 rows/year
- Unemployment: ~800 rows/year

### Derived Models

**Models**: forecast, etf

**Dependencies**: Built from other models (equity, company, etc.)

**Ingestion**: None (uses existing Silver data)

**Build Process**: Applies transformations to source models

### Core Models

**Models**: core

**Data Sources**: Reference data (calendar dimension)

**Ingestion**: Typically static or rarely updated

## Integration with Other Scripts

### Relationship to Other Tools

**build_all_models.py** (this script):
- Purpose: Production data ingestion and model building
- Data: Real API data with pagination
- Use case: Daily updates, full builds, CI/CD

**test_all_models.py**:
- Purpose: Testing and validation
- Data: Sample/mock data for testing
- Use case: Pre-deployment checks, regression tests

**rebuild_model.py**:
- Purpose: Single model rebuild from Bronze
- Data: Existing Bronze data
- Use case: Schema changes, corrupted data recovery

**reset_model.py**:
- Purpose: Delete model data
- Data: N/A (destructive operation)
- Use case: Development, testing, fresh starts

### Workflow Integration

```bash
# 1. Initial production build (this script)
python scripts/build_all_models.py --date-from 2024-01-01

# 2. Daily updates (this script)
python scripts/build_all_models.py --days 1

# 3. Pre-deployment testing (test_all_models.py)
python scripts/test_all_models.py --parallel --quick

# 4. Schema change rebuild (rebuild_model.py)
python scripts/rebuild_model.py --model equity

# 5. Development reset (reset_model.py)
python scripts/reset_model.py --model equity --force
```

## Troubleshooting

### Error: "Polygon API rate limit exceeded"

**Solution**: Use `--max-tickers` to limit data volume, or spread ingestion over multiple runs:

```bash
# Build with limited tickers
python scripts/build_all_models.py --max-tickers 50 --days 1
```

### Error: "Bronze data not found for model X"

**Cause**: Bronze ingestion was skipped or failed

**Solution**: Run without `--skip-ingestion`:

```bash
python scripts/build_all_models.py --models X
```

### Error: "Model build failed: column not found"

**Cause**: Schema mismatch between Bronze and model config

**Solution**:
1. Check model YAML configuration
2. Verify Bronze data structure
3. Update model config or Bronze ingestion logic

### Models stuck in "Building Silver layer"

**Cause**: Large data volume or resource constraints

**Solution**:
1. Check Spark executor logs
2. Increase Spark memory (`spark.executor.memory`)
3. Use `--max-tickers` for development

### Parallel build slower than sequential

**Cause**: Resource contention (CPU, memory, I/O)

**Solution**:
```bash
# Reduce parallel workers
python scripts/build_all_models.py --parallel --max-workers 2
```

### "Module not found" errors

**Cause**: Missing dependencies

**Solution**:
```bash
pip install -r requirements.txt
```

## Best Practices

1. **Start with dry-run**: Always test with `--dry-run` first
2. **Use max-tickers for development**: Limit data for faster iteration
3. **Schedule daily incremental builds**: Use `--days 1` in cron jobs
4. **Monitor API rate limits**: Track usage across all scripts
5. **Save build results**: Use `--output` for historical tracking
6. **Parallel for CI/CD**: Use `--parallel` in automated pipelines
7. **Skip ingestion for schema changes**: Use `--skip-ingestion` when only model logic changed
8. **Test specific models first**: Use `--models` to test changes incrementally
9. **Version control configs**: Track changes to model YAML files
10. **Monitor disk space**: Ingestion can create large Bronze files

## Scheduling Examples

### Cron (Daily Updates)

```bash
# Daily at 6 AM - ingest previous day's data
0 6 * * * cd /path/to/de_Funk && python scripts/build_all_models.py --days 1 --output logs/daily_$(date +\%Y\%m\%d).json >> logs/build.log 2>&1
```

### GitHub Actions

```yaml
name: Daily Data Build
on:
  schedule:
    - cron: '0 6 * * *'  # Daily at 6 AM UTC

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.9'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Build all models
        env:
          POLYGON_API_KEY: ${{ secrets.POLYGON_API_KEY }}
        run: |
          python scripts/build_all_models.py \
            --days 1 \
            --parallel \
            --output build_results/$(date +%Y%m%d).json

      - name: Upload results
        uses: actions/upload-artifact@v2
        with:
          name: build-results
          path: build_results/
```

## See Also

- [Pipeline Testing Guide](PIPELINE_TESTING_GUIDE.md) - Testing framework
- [Model Reset/Rebuild Guide](MODEL_RESET_REBUILD_GUIDE.md) - Single model operations
- [Delta Lake Usage Guide](DELTA_LAKE_USAGE_GUIDE.md) - Delta format details
- [Model Documentation](../configs/models/) - Model configurations

## Support

For issues:
1. Check logs with `--output` for detailed error messages
2. Try `--dry-run` first to verify configuration
3. Test with limited data (`--max-tickers`, `--days`)
4. Verify Bronze data exists and is accessible
5. Check API keys and rate limits
6. Review model YAML configurations
