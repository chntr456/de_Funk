# Pipeline Testing Guide

Comprehensive guide for testing the complete data pipeline from ingestion to UI.

## Overview

Three test scripts validate the entire pipeline:

1. **`test_pipeline_e2e.py`** - End-to-end pipeline testing (Bronze → Silver → Gold → UI)
2. **`test_ui_integration.py`** - UI component and query pattern testing
3. **Model-specific tests** - Unit tests for models, measures, and transformations

## Quick Start

### Full Pipeline Test

```bash
# Generate sample data and test full pipeline
python scripts/test_pipeline_e2e.py --model equity --generate-sample

# Test with existing data
python scripts/test_pipeline_e2e.py --model equity

# Quick test (minimal data)
python scripts/test_pipeline_e2e.py --model equity --quick --generate-sample
```

### UI Integration Test

```bash
# Test all UI components
python scripts/test_ui_integration.py --model equity

# Test specific components
python scripts/test_ui_integration.py --model equity --components filters charts

# Run with performance benchmarks
python scripts/test_ui_integration.py --model equity --benchmark
```

## Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         BRONZE LAYER                         │
│                     (Raw Data Ingestion)                     │
│  - API data (Polygon, Yahoo, etc.)                          │
│  - CSV/Parquet files                                        │
│  - Real-time streams                                        │
└──────────────────────┬──────────────────────────────────────┘
                       │ ETL Process
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                         SILVER LAYER                         │
│                    (Cleaned & Structured)                    │
│  - Dimension tables (companies, exchanges, etc.)             │
│  - Fact tables (prices, news, filings)                      │
│  - Schema-compliant, validated data                         │
└──────────────────────┬──────────────────────────────────────┘
                       │ Measure Calculation
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                         GOLD LAYER                           │
│                  (Aggregated & Ready-to-Use)                 │
│  - Measures (avg_price, total_volume, etc.)                 │
│  - Indicators (SMA, RSI, MACD)                              │
│  - Risk metrics (Beta, Sharpe, Volatility)                  │
└──────────────────────┬──────────────────────────────────────┘
                       │ Query Layer
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                           UI LAYER                           │
│                    (Streamlit/Visualization)                 │
│  - Interactive filters                                       │
│  - Charts and graphs                                        │
│  - Tables and reports                                       │
└─────────────────────────────────────────────────────────────┘
```

## test_pipeline_e2e.py

### Purpose

Validates the complete data flow from raw ingestion to query-ready data.

### Test Stages

#### 1. Bronze Layer (Ingestion)

Tests raw data availability and quality:

```bash
# What's tested:
✓ Bronze files exist
✓ Data is readable
✓ Row counts > 0
✓ Key columns have no nulls
✓ Data types are correct
```

**Example Output:**
```
STAGE 1: BRONZE LAYER (Ingestion)
======================================================================
Testing Bronze layer...
  Checking prices_daily...
    ✓ prices_daily: 2,700 rows, 7 columns
  Checking company...
    ✓ company: 20 rows, 8 columns
```

#### 2. Silver Layer (Transformation)

Tests transformed model tables:

```bash
# What's tested:
✓ Silver tables exist
✓ Data format (Parquet/Delta)
✓ Schema compliance
✓ Referential integrity
✓ Data quality rules
```

**Example Output:**
```
STAGE 2: SILVER LAYER (Transformation)
======================================================================
Testing Silver layer...
  Checking fact_equity_prices...
    ✓ fact_equity_prices: 2,700 rows (delta)
  Checking dim_equity...
    ✓ dim_equity: 20 rows (delta)
```

#### 3. Gold Layer (Aggregation)

Tests measure calculations:

```bash
# What's tested:
✓ Measures execute successfully
✓ Results are non-empty
✓ Query performance < threshold
✓ Results match expected patterns
```

**Example Output:**
```
STAGE 3: GOLD LAYER (Aggregation)
======================================================================
Testing Gold layer (measures)...
  Testing measure: avg_close_price
    ✓ avg_close_price: 20 results (0.12s)
  Testing measure: total_volume
    ✓ total_volume: 20 results (0.08s)
```

#### 4. UI Layer (Queries)

Tests common UI query patterns:

```bash
# What's tested:
✓ Latest data queries
✓ Filtered queries
✓ Summary aggregations
✓ Time series data
✓ Query performance
```

**Example Output:**
```
STAGE 4: UI LAYER (Query Patterns)
======================================================================
Testing UI layer...
  Testing query: latest_prices
    ✓ latest_prices: 10 results (0.015s)
  Testing query: price_summary
    ✓ price_summary: 5 results (0.023s)
```

### Usage Examples

#### Basic Usage

```bash
# Test entire pipeline
python scripts/test_pipeline_e2e.py --model equity

# Test specific stages
python scripts/test_pipeline_e2e.py --model equity --stages bronze silver

# Verbose logging
python scripts/test_pipeline_e2e.py --model equity --verbose
```

#### Generate Sample Data

```bash
# Full sample dataset
python scripts/test_pipeline_e2e.py --model equity --generate-sample

# Quick test dataset (5 tickers, 30 days)
python scripts/test_pipeline_e2e.py --model equity --generate-sample --quick

# Custom Bronze path
python scripts/test_pipeline_e2e.py --model equity \
    --generate-sample \
    --bronze-path storage/bronze/custom
```

#### Sample Data Details

When using `--generate-sample`:

**Quick Mode** (--quick):
- 5 tickers (TEST00-TEST04)
- 30 days of data
- ~150 price records
- 5 company records

**Full Mode** (default):
- 20 tickers (TEST00-TEST19)
- 90 days of data
- ~1,800 price records
- 20 company records

**Data Characteristics:**
- Realistic price movements (random walk)
- Random volume (1M - 100M)
- Multiple exchanges (NYSE, NASDAQ, AMEX)
- Various sectors (Technology, Finance, Healthcare, Energy)

### Test Results

Results are saved to `test_results/pipeline_e2e_<model>_<timestamp>.json`:

```json
{
  "bronze": {
    "prices_daily": {
      "exists": true,
      "row_count": 2700,
      "col_count": 7,
      "has_data": true
    }
  },
  "silver": {
    "fact_equity_prices": {
      "exists": true,
      "format": "delta",
      "row_count": 2700,
      "has_data": true
    }
  },
  "gold": {
    "avg_close_price": {
      "success": true,
      "row_count": 20,
      "query_time": 0.12
    }
  },
  "ui": {
    "latest_prices": {
      "success": true,
      "row_count": 10,
      "query_time": 0.015
    }
  },
  "overall": {
    "start_time": "2025-11-13T10:30:00",
    "end_time": "2025-11-13T10:30:15",
    "success": true
  }
}
```

## test_ui_integration.py

### Purpose

Validates UI components and query patterns used in the Streamlit application.

### Test Components

#### 1. Filter Components

Tests filter-style queries:

```python
# Tested patterns:
- Date range filters
- Ticker selection
- Volume thresholds
- Price ranges
- Sector/industry filters
```

**Example:**
```sql
SELECT ticker, trade_date, close
FROM prices
WHERE trade_date BETWEEN '2024-01-01' AND '2024-01-31'
  AND ticker IN ('AAPL', 'GOOGL', 'MSFT')
LIMIT 100
```

#### 2. Selector Components

Tests dropdown/multiselect queries:

```python
# Tested patterns:
- Unique ticker list
- Date range discovery
- Ticker with record counts
- Sector/industry lists
```

**Example:**
```sql
SELECT DISTINCT ticker
FROM prices
ORDER BY ticker
```

#### 3. Chart Data Queries

Tests visualization data queries:

```python
# Tested patterns:
- Time series (line charts)
- OHLC data (candlestick)
- Volume bars
- Distribution histograms
- Comparison charts
```

**Example:**
```sql
SELECT trade_date, ticker, close
FROM prices
WHERE ticker IN ('AAPL', 'GOOGL')
ORDER BY trade_date
```

#### 4. Table Display Queries

Tests table component queries:

```python
# Tested patterns:
- Recent data (sorted by date)
- Sorted data (by volume, price, etc.)
- Summary statistics
- Paginated results
```

**Example:**
```sql
SELECT ticker, trade_date, open, high, low, close, volume
FROM prices
ORDER BY trade_date DESC
LIMIT 50
```

#### 5. Measure Calculations

Tests Gold layer measures:

```python
# Tested patterns:
- Average aggregations
- Sum aggregations
- Min/max calculations
- Weighted calculations
- Window functions
```

**Example:**
```python
model.calculate_measure('avg_close_price', limit=10)
model.calculate_measure('total_volume', filters={'ticker': ['AAPL']})
```

### Performance Benchmarks

With `--benchmark`, runs performance tests:

```bash
python scripts/test_ui_integration.py --model equity --benchmark
```

**Benchmark Queries:**
- Full table scan
- Filtered aggregation
- Group by operations
- Join queries
- Window functions

**Output:**
```
--- Performance Benchmarks ---
  full_scan: avg=0.045s, min=0.042s, max=0.051s
  filtered_count: avg=0.023s, min=0.021s, max=0.026s
  aggregation: avg=0.031s, min=0.029s, max=0.035s
```

### Usage Examples

```bash
# Test all components
python scripts/test_ui_integration.py --model equity

# Test specific components
python scripts/test_ui_integration.py --model equity --components filters charts

# With specific tickers
python scripts/test_ui_integration.py --model equity --tickers AAPL GOOGL MSFT

# With benchmarks
python scripts/test_ui_integration.py --model equity --benchmark
```

## Integration with CI/CD

### Pre-commit Checks

Add to `.git/hooks/pre-commit`:

```bash
#!/bin/bash
# Run quick pipeline test before commit
python scripts/test_pipeline_e2e.py --model equity --quick --stages silver gold

if [ $? -ne 0 ]; then
    echo "Pipeline tests failed. Commit aborted."
    exit 1
fi
```

### GitHub Actions

```yaml
# .github/workflows/pipeline-test.yml
name: Pipeline Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v2

      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt

      - name: Run pipeline tests
        run: |
          python scripts/test_pipeline_e2e.py --model equity --generate-sample --quick

      - name: Run UI tests
        run: |
          python scripts/test_ui_integration.py --model equity
```

### Scheduled Testing

Cron job for nightly validation:

```bash
# /etc/cron.d/pipeline-test
0 2 * * * /path/to/venv/bin/python /path/to/scripts/test_pipeline_e2e.py --model equity
```

## Common Workflows

### Development Workflow

```bash
# 1. Make changes to model or ETL
vim models/implemented/equity/model.py

# 2. Generate test data
python scripts/test_pipeline_e2e.py --model equity --generate-sample --quick

# 3. Test specific stage
python scripts/test_pipeline_e2e.py --model equity --stages silver gold

# 4. Test UI components
python scripts/test_ui_integration.py --model equity --components measures
```

### Debugging Failed Tests

```bash
# Run with verbose logging
python scripts/test_pipeline_e2e.py --model equity --verbose

# Test single stage
python scripts/test_pipeline_e2e.py --model equity --stages bronze

# Check test results
cat test_results/pipeline_e2e_equity_*.json | jq .
```

### Performance Testing

```bash
# Benchmark UI queries
python scripts/test_ui_integration.py --model equity --benchmark

# Test with larger dataset
python scripts/test_pipeline_e2e.py --model equity --generate-sample

# Profile specific queries
python -m cProfile scripts/test_ui_integration.py --model equity
```

## Validation Criteria

### Bronze Layer

- ✅ Files exist at expected paths
- ✅ Data is readable (valid Parquet/CSV)
- ✅ Row count > 0
- ✅ Required columns present
- ✅ No nulls in key columns
- ✅ Data types match schema

### Silver Layer

- ✅ All model tables exist
- ✅ Format is Parquet or Delta
- ✅ Row count > 0 for fact tables
- ✅ Schema matches model config
- ✅ Referential integrity maintained
- ✅ No duplicate primary keys

### Gold Layer

- ✅ All measures execute
- ✅ Results are non-empty (or expected empty)
- ✅ Query time < 5 seconds
- ✅ Results match expected ranges
- ✅ No SQL errors

### UI Layer

- ✅ All query patterns work
- ✅ Filters return expected results
- ✅ Charts have plottable data
- ✅ Tables display correctly
- ✅ Interactive controls functional

## Troubleshooting

### Bronze Layer Issues

**Problem**: Bronze files not found

```bash
# Solution: Check path and generate sample data
python scripts/test_pipeline_e2e.py --model equity --generate-sample
```

**Problem**: Bronze data has nulls

```bash
# Solution: Check ETL process
# Validate source data quality
# Add null handling in transformation
```

### Silver Layer Issues

**Problem**: Silver tables don't exist

```bash
# Solution: Rebuild from Bronze
python scripts/rebuild_model.py --model equity
```

**Problem**: Format detection fails

```bash
# Solution: Check for _delta_log directory
ls -la storage/silver/equity/fact_equity_prices/
```

### Gold Layer Issues

**Problem**: Measures fail to calculate

```bash
# Solution: Check measure definitions
# Verify source tables exist
# Test SQL directly in DuckDB
```

**Problem**: Query timeout

```bash
# Solution: Add indexes/partitioning
# Optimize Delta tables
python scripts/optimize_delta.py --model equity
```

### UI Layer Issues

**Problem**: UI queries slow

```bash
# Solution: Run benchmarks to identify bottleneck
python scripts/test_ui_integration.py --model equity --benchmark

# Optimize identified queries
# Consider adding indexes
# Use Delta z-ordering
```

## Best Practices

1. **Run tests before commits** - Catch issues early
2. **Use quick mode in development** - Faster iteration
3. **Full tests in CI/CD** - Comprehensive validation
4. **Benchmark regularly** - Track performance regression
5. **Save test results** - Historical tracking
6. **Test with realistic data** - Edge cases matter
7. **Validate all stages** - Don't skip layers
8. **Monitor query times** - Set performance budgets
9. **Test Delta and Parquet** - Both formats matter
10. **Document test failures** - Help future debugging

## Performance Targets

| Stage | Operation | Target Time | Notes |
|-------|-----------|-------------|-------|
| Bronze | Read 10K rows | < 0.1s | Parquet read |
| Silver | Read 10K rows | < 0.1s | Delta scan |
| Gold | Calculate measure | < 1s | Simple aggregation |
| Gold | Complex measure | < 5s | Window functions |
| UI | Filter query | < 0.1s | With indexes |
| UI | Chart data | < 0.5s | Time series |
| UI | Table display | < 0.2s | Paginated |

## See Also

- [Model Reset/Rebuild Guide](MODEL_RESET_REBUILD_GUIDE.md) - Data management
- [Delta Lake Usage Guide](DELTA_LAKE_USAGE_GUIDE.md) - Delta operations
- [Model Documentation](../configs/models/) - Model schemas
- [Streamlit App](../app/) - UI implementation
