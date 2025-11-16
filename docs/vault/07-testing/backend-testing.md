# Backend Testing

**Testing DuckDB and Spark backend compatibility**

Script: `scripts/run_backend_tests.sh`

---

## Overview

Backend testing ensures that **queries, measures, and joins work identically** on both DuckDB and Spark backends.

---

## Test Strategy

**Pattern**: Run same test on both backends, compare results

```python
@pytest.mark.parametrize("backend", ["duckdb", "spark"])
def test_measure_calculation(backend):
    session = UniversalSession(backend=backend)
    result = session.calculate_measure('avg_close_price')

    assert result.rows > 0
    assert 'measure_value' in result.data.columns
```

---

## Backend Comparison Tests

**Purpose**: Verify identical results across backends

```python
def test_backend_consistency():
    duckdb_session = UniversalSession(backend='duckdb')
    spark_session = UniversalSession(backend='spark')

    duckdb_result = duckdb_session.query("SELECT AVG(close) FROM equity.fact_equity_prices")
    spark_result = spark_session.query("SELECT AVG(close) FROM equity.fact_equity_prices")

    assert_dataframes_equal(duckdb_result.data, spark_result.data)
```

---

## Common Issues

**Floating Point Precision**:
```python
# Use approximate equality
assert abs(duckdb_value - spark_value) < 0.0001
```

**Date Handling**:
```python
# Normalize date formats before comparing
duckdb_dates = pd.to_datetime(duckdb_df['date'])
spark_dates = pd.to_datetime(spark_df['date'])
```

---

## Running Backend Tests

```bash
bash scripts/run_backend_tests.sh
```

---

## Related Documentation

- [Connection System](../01-core-components/connection-system.md) - Backend adapters
- [Testing Guide](testing-guide.md) - General testing
