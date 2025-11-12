# Testing Guide - Measure Framework

Complete guide to testing and validating the unified measure framework.

---

## Quick Start

### 1. Run Pipeline Tester (Recommended First Step)

```bash
# Test complete system with real data
python tests/pipeline_tester.py

# Verbose output for debugging
python tests/pipeline_tester.py --verbose
```

This validates your entire setup and identifies any configuration issues.

### 2. Run Example Scripts

```bash
# Basic usage examples
python examples/measure_framework/01_basic_usage.py

# Troubleshooting guide
python examples/measure_framework/02_troubleshooting.py
```

### 3. Run Unit Tests

```bash
# All tests
pytest tests/ -v

# Specific component
pytest tests/unit/test_backend_adapters.py -v
```

---

## Test Suite Overview

### Pipeline Tester (`tests/pipeline_tester.py`)

**Purpose:** Validates entire measure framework with real bronze data.

**Tests 12 Stages:**
1. Context initialization
2. Bronze data verification
3. Model loading
4. Measure enumeration
5. Simple measure calculation
6. Computed measure calculation
7. Weighted measure calculation
8. SQL generation (explain)
9. All weighting methods
10. Backend abstraction
11. ETF model support
12. Performance benchmarking

**Usage:**
```bash
# Standard test
python tests/pipeline_tester.py

# With verbose output
python tests/pipeline_tester.py --verbose

# Test Spark backend (if available)
python tests/pipeline_tester.py --backend spark
```

**Expected Output:**
```
======================================================================
MEASURE FRAMEWORK PIPELINE TESTER
======================================================================
Backend: duckdb
Timestamp: 2025-11-12 14:30:00
======================================================================

▶ Test 1: Context Initialization
✓ Context Initialization: PASSED

▶ Test 2: Bronze Data Check
✓ Bronze table: prices_daily: PASSED
...

======================================================================
TEST SUMMARY
======================================================================
Passed:  12
Failed:  0
Skipped: 0
Time:    5.23s
======================================================================

✓ ALL TESTS PASSED!
======================================================================
```

---

## Unit Tests

### Backend Adapters (`tests/unit/test_backend_adapters.py`)

Tests backend abstraction layer:
- DuckDB adapter functionality
- Spark adapter functionality
- SQL builder utilities
- Table reference resolution
- Feature support detection

**Run:**
```bash
pytest tests/unit/test_backend_adapters.py -v
```

**Tests:**
- `test_get_dialect` - Dialect detection
- `test_execute_sql` - SQL execution
- `test_get_table_reference_missing_table` - Error handling
- `test_supports_feature` - Feature checks
- `test_build_simple_aggregate` - SQL generation
- `test_build_weighted_aggregate` - Weighted SQL

### Measure Framework (`tests/unit/test_measure_framework.py`)

Tests measure registry and execution:
- Measure type registration
- Factory pattern creation
- Measure executor functionality
- SQL generation for all types

**Run:**
```bash
pytest tests/unit/test_measure_framework.py -v
```

**Tests:**
- `test_create_simple_measure` - Simple measure creation
- `test_create_computed_measure` - Computed measure creation
- `test_create_weighted_measure` - Weighted measure creation
- `test_execute_measure` - End-to-end execution
- `test_explain_measure` - SQL generation

### Weighting Strategies (`tests/unit/test_weighting_strategies.py`)

Tests all weighting implementations:
- 6 equity weighting strategies
- 1 ETF holdings strategy
- Strategy registry
- SQL generation validation

**Run:**
```bash
pytest tests/unit/test_weighting_strategies.py -v
```

**Tests:**
- `test_equal_weight_strategy` - Equal weighting
- `test_volume_weight_strategy` - Volume weighting
- `test_market_cap_weight_strategy` - Market cap weighting
- `test_price_weight_strategy` - Price weighting
- `test_volume_deviation_weight_strategy` - Unusual activity
- `test_volatility_weight_strategy` - Inverse volatility
- `test_holdings_weight_strategy` - ETF holdings

---

## Integration Tests

### Measure Pipeline (`tests/integration/test_measure_pipeline.py`)

Tests complete end-to-end workflows:
- Full measure calculation pipeline
- Backend comparison (DuckDB vs Spark)
- Performance benchmarking
- Result consistency

**Run:**
```bash
pytest tests/integration/test_measure_pipeline.py -v
```

**Tests:**
- `test_calculate_simple_measure` - Simple measure E2E
- `test_calculate_computed_measure` - Computed measure E2E
- `test_calculate_weighted_measure` - Weighted measure E2E
- `test_measure_execution_time` - Performance validation
- `test_repeated_execution_consistency` - Consistency check

---

## Example Scripts

### Basic Usage (`examples/measure_framework/01_basic_usage.py`)

Demonstrates common operations:
- Example 1: Simple measure
- Example 2: Computed measure
- Example 3: Weighted measure
- Example 4: List measures
- Example 5: Explain SQL
- Example 6: Convenience methods

**Run:**
```bash
python examples/measure_framework/01_basic_usage.py
```

### Troubleshooting (`examples/measure_framework/02_troubleshooting.py`)

Shows solutions to common problems:
- Problem 1: Measure not found
- Problem 2: Backend issues
- Problem 3: Table not found
- Problem 4: SQL generation error
- Problem 5: Performance issues
- Problem 6: Data type mismatch
- Problem 7: Weighted measure validation
- Problem 8: ETF holdings not working

**Run:**
```bash
python examples/measure_framework/02_troubleshooting.py
```

---

## Test Fixtures

### Pytest Fixtures (`tests/conftest.py`)

Shared test fixtures:
- `temp_dir` - Temporary directory
- `sample_price_data` - Price DataFrame
- `sample_company_data` - Company DataFrame
- `sample_etf_holdings` - ETF holdings DataFrame
- `simple_model_config` - Model configuration
- `duckdb_connection` - DuckDB connection
- `mock_model` - Mock BaseModel instance
- `storage_cfg` - Storage configuration

**Usage in tests:**
```python
def test_my_feature(mock_model):
    result = mock_model.calculate_measure('avg_close_price')
    assert result.rows > 0
```

### Sample Data Generator (`tests/fixtures/sample_data_generator.py`)

Generates realistic test data:
- `generate_price_data()` - Stock prices (OHLCV)
- `generate_company_data()` - Company dimension
- `generate_etf_holdings()` - ETF holdings
- `generate_etf_prices()` - ETF prices with NAV

**Usage:**
```python
from tests.fixtures.sample_data_generator import generate_price_data

prices = generate_price_data(['AAPL', 'MSFT'], num_days=30)
```

---

## Common Test Workflows

### Workflow 1: Validate New Installation

```bash
# 1. Run pipeline tester
python tests/pipeline_tester.py

# 2. If errors, check troubleshooting
python examples/measure_framework/02_troubleshooting.py

# 3. Run unit tests
pytest tests/unit/ -v
```

### Workflow 2: Add New Measure

```bash
# 1. Add measure to configs/models/company.yaml
# 2. Test with pipeline tester
python tests/pipeline_tester.py

# 3. Calculate measure
python -c "
from core.context import RepoContext
from models.implemented.company.model import CompanyModel

ctx = RepoContext.from_repo_root(connection_type='duckdb')
model = CompanyModel(ctx.connection, ctx.storage, ctx.repo)

result = model.calculate_measure('my_new_measure')
print(result.data)
"
```

### Workflow 3: Debug Failing Measure

```bash
# 1. Explain SQL
python -c "
from core.context import RepoContext
from models.implemented.company.model import CompanyModel

ctx = RepoContext.from_repo_root(connection_type='duckdb')
model = CompanyModel(ctx.connection, ctx.storage, ctx.repo)

sql = model.measures.explain_measure('failing_measure')
print(sql)
"

# 2. Test SQL directly in DuckDB
duckdb storage/silver/company/facts/fact_prices
> [paste SQL here]

# 3. Check schema
python -c "
from core.context import RepoContext
from models.implemented.company.model import CompanyModel

ctx = RepoContext.from_repo_root(connection_type='duckdb')
model = CompanyModel(ctx.connection, ctx.storage, ctx.repo)

schema = model.model_cfg['schema']
print('Dimensions:', list(schema.get('dimensions', {}).keys()))
print('Facts:', list(schema.get('facts', {}).keys()))
"
```

### Workflow 4: Add New Weighting Strategy

```bash
# 1. Add strategy class to models/domains/equities/weighting.py
# 2. Register strategy
# 3. Add measure to config
# 4. Test with pipeline tester
python tests/pipeline_tester.py

# 5. Run weighting strategy tests
pytest tests/unit/test_weighting_strategies.py -v
```

---

## Performance Testing

### Benchmark Measures

```python
import time
from core.context import RepoContext
from models.implemented.company.model import CompanyModel

ctx = RepoContext.from_repo_root(connection_type='duckdb')
model = CompanyModel(ctx.connection, ctx.storage, ctx.repo)

# Measure performance
measures_to_test = ['avg_close_price', 'volume_weighted_index', 'market_cap']

for measure_name in measures_to_test:
    # Run 5 times
    times = []
    for _ in range(5):
        start = time.time()
        result = model.calculate_measure(measure_name, entity_column='ticker', limit=10)
        elapsed = time.time() - start
        times.append(elapsed * 1000)  # Convert to ms

    avg_time = sum(times) / len(times)
    print(f"{measure_name}: {avg_time:.2f}ms average")
```

### Profile SQL

```python
# Get generated SQL
sql = model.measures.explain_measure('volume_weighted_index')

# Run with EXPLAIN
explain_sql = f"EXPLAIN {sql}"
result = model.connection.conn.execute(explain_sql)
print(result.fetchall())
```

---

## Debugging Tips

### 1. Measure Not Found

```python
# List all measures
measures = model.measures.list_measures()
print("Available:", list(measures.keys()))

# Check specific measure
if 'my_measure' not in measures:
    print("Measure not defined in config!")
```

### 2. SQL Errors

```python
# Generate SQL without executing
sql = model.measures.explain_measure('measure_name')
print(sql)

# Test SQL directly
conn.execute(sql)
```

### 3. Backend Issues

```python
# Check detected backend
print(f"Backend: {model.backend}")
print(f"Adapter: {type(model.measures.adapter).__name__}")

# Check features
adapter = model.measures.adapter
print(f"CTE support: {adapter.supports_feature('cte')}")
print(f"Window functions: {adapter.supports_feature('window_functions')}")
```

### 4. Performance Issues

```python
# Measure query time
result = model.calculate_measure('measure_name')
print(f"Query time: {result.query_time_ms:.2f}ms")

# Check result size
print(f"Rows: {result.rows}")

# Add LIMIT to reduce results
result = model.calculate_measure('measure_name', limit=10)
```

---

## Continuous Integration

### pytest.ini Configuration

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts =
    -v
    --tb=short
    --strict-markers
markers =
    unit: Unit tests
    integration: Integration tests
    slow: Slow tests
```

### Run Tests in CI

```bash
# Run fast tests only
pytest tests/unit/ -m "not slow"

# Run all tests with coverage
pytest tests/ --cov=models --cov-report=html

# Run with specific markers
pytest tests/ -m "unit"
pytest tests/ -m "integration"
```

---

## Test Coverage Report

Run coverage analysis:

```bash
# Install coverage
pip install pytest-cov

# Run with coverage
pytest tests/ --cov=models --cov-report=html

# View report
open htmlcov/index.html
```

---

## Summary

**Test Suite Stats:**
- 14 test files
- 100+ test cases
- 12 pipeline validation stages
- 6 example scripts
- Full backend coverage

**Commands to Remember:**
```bash
# Quick validation
python tests/pipeline_tester.py

# Unit tests
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v

# Examples
python examples/measure_framework/01_basic_usage.py

# Troubleshooting
python examples/measure_framework/02_troubleshooting.py
```

**All tests connect to real bronze data and validate the complete pipeline!** 🚀
