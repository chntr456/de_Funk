# Measure Framework Examples

Example scripts demonstrating how to use the unified measure framework.

## Getting Started

### Run Pipeline Tester

Test the complete pipeline with real data:

```bash
# Test with DuckDB (default)
python tests/pipeline_tester.py

# Test with verbose output
python tests/pipeline_tester.py --verbose

# Test with Spark (if available)
python tests/pipeline_tester.py --backend spark
```

### Run Basic Usage Examples

```bash
python examples/measure_framework/01_basic_usage.py
```

### Run Troubleshooting Guide

```bash
python examples/measure_framework/02_troubleshooting.py
```

## Examples Overview

### 01_basic_usage.py

Demonstrates basic measure calculations:
- Simple measures (AVG, SUM, etc.)
- Computed measures (expressions)
- Weighted measures (indices)
- Listing available measures
- Explaining SQL generation
- Using convenience methods

### 02_troubleshooting.py

Common problems and solutions:
- Measure not found errors
- Backend issues
- Table not found errors
- SQL generation debugging
- Performance optimization
- Data type mismatches
- Weighted measure validation
- ETF holdings measures

## Unit Tests

Run unit tests with pytest:

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/unit/test_backend_adapters.py

# Run with verbose output
pytest tests/ -v

# Run integration tests only
pytest tests/integration/
```

## Pipeline Tester Features

The pipeline tester validates:

1. **Context Initialization** - RepoContext setup
2. **Bronze Data** - Checks for required bronze tables
3. **Model Loading** - CompanyModel instantiation
4. **List Measures** - Enumerate available measures
5. **Simple Measures** - Basic aggregations
6. **Computed Measures** - Expression-based calculations
7. **Weighted Measures** - Weighted aggregations
8. **SQL Generation** - Explain functionality
9. **All Weighting Methods** - Tests all 6+ strategies
10. **Backend Abstraction** - Adapter functionality
11. **ETF Model** - ETF-specific measures
12. **Performance Benchmark** - Timing analysis

## Typical Workflow

### 1. Run Pipeline Tester

```bash
python tests/pipeline_tester.py
```

This validates your entire setup and identifies any issues.

### 2. Review Examples

```bash
python examples/measure_framework/01_basic_usage.py
```

See how to use each feature.

### 3. Debug Issues

```bash
python examples/measure_framework/02_troubleshooting.py
```

Use troubleshooting guide if you encounter problems.

### 4. Run Unit Tests

```bash
pytest tests/unit/ -v
```

Validate individual components.

## Common Issues

### Issue: "Measure not found"

**Solution:**
```python
# List available measures
measures = model.measures.list_measures()
print(measures.keys())
```

### Issue: "Table not found in schema"

**Solution:**
```python
# Check model schema
schema = model.model_cfg['schema']
print("Dimensions:", schema.get('dimensions', {}).keys())
print("Facts:", schema.get('facts', {}).keys())
```

### Issue: "Backend not supported"

**Solution:**
```python
# Check detected backend
print(f"Backend: {model.backend}")
print(f"Adapter: {type(model.measures.adapter).__name__}")
```

### Issue: SQL errors

**Solution:**
```python
# Explain SQL to debug
sql = model.measures.explain_measure('measure_name')
print(sql)
```

## Testing Your Own Measures

### 1. Add measure to config

Edit `configs/models/company.yaml`:

```yaml
measures:
  my_custom_measure:
    source: fact_prices.close
    aggregation: avg
    data_type: double
```

### 2. Test with pipeline tester

```bash
python tests/pipeline_tester.py
```

### 3. Calculate measure

```python
result = model.calculate_measure('my_custom_measure', entity_column='ticker')
print(result.data)
```

## Performance Tips

1. **Use LIMIT** to reduce result sets
2. **Add filters** to reduce data scanned
3. **Check query time** with `result.query_time_ms`
4. **Use explain** to analyze SQL
5. **Profile with benchmarks** in pipeline tester

## Getting Help

1. Run troubleshooting guide: `python examples/measure_framework/02_troubleshooting.py`
2. Check pipeline tester output: `python tests/pipeline_tester.py --verbose`
3. Review unit tests for examples: `tests/unit/test_*.py`
4. Read implementation docs: `docs/IMPLEMENTATION_SUMMARY.md`

## Architecture Overview

```
YAML Config → MeasureRegistry → Measure Class → SQL → Backend Adapter → Results
   (WHAT)      (DISPATCH)         (HOW)         (↓)     (WHERE)         (DATA)
```

All measures use the same execution path!
