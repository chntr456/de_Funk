# Testing Guide

**Comprehensive testing documentation for de_Funk**

---

## Overview

de_Funk uses pytest for testing with a focus on both unit tests and integration tests across both backend systems (DuckDB and Spark).

---

## Documents

| Document | Description |
|----------|-------------|
| [Testing Guide](testing-guide.md) | Comprehensive testing overview |
| [Backend Testing](backend-testing.md) | DuckDB/Spark backend tests |
| [Pipeline Testing](pipeline-testing.md) | Data pipeline tests |

---

## Test Organization

```
tests/
├── conftest.py              # Pytest configuration & fixtures
├── fixtures/                # Test data generators
│   └── sample_data_generator.py
├── unit/                    # Unit tests
│   ├── test_measure_framework.py
│   ├── test_backend_adapters.py
│   └── test_weighting_strategies.py
└── integration/             # Integration tests
    └── test_measure_pipeline.py
```

---

## Running Tests

### All Tests

```bash
pytest
```

### Unit Tests Only

```bash
pytest tests/unit/
```

### Integration Tests Only

```bash
pytest tests/integration/
```

### Specific Test File

```bash
pytest tests/unit/test_measure_framework.py -v
```

### Backend Compatibility

```bash
bash scripts/test/validation/run_backend_tests.sh
```

---

## Test Categories

### Unit Tests

Test individual components in isolation:

- Measure framework calculations
- Backend adapter behavior
- Weighting strategies
- Filter engine logic

### Integration Tests

Test component interactions:

- Full measure pipeline
- Model building
- Cross-model queries
- Filter application

### Validation Tests

Located in `scripts/test/validation/`:

- Backend compatibility
- Model build verification
- Data integrity checks

---

## Test Scripts

| Script | Purpose |
|--------|---------|
| `scripts/test/test_all_models.py` | Test all model implementations |
| `scripts/test/test_alpha_vantage_api.py` | Test API connectivity |
| `scripts/test/test_duckdb_setup.py` | Verify DuckDB configuration |
| `scripts/test/validation/run_backend_tests.sh` | Backend compatibility |

---

## Fixtures

### Sample Data Generator

Located at `tests/fixtures/sample_data_generator.py`:

```python
from tests.fixtures.sample_data_generator import generate_price_data

# Generate test price data
prices_df = generate_price_data(
    tickers=["AAPL", "MSFT"],
    start_date="2024-01-01",
    end_date="2024-12-31"
)
```

### Available Fixtures

| Fixture | Data Type |
|---------|-----------|
| `generate_price_data()` | Daily OHLCV prices |
| `generate_company_data()` | Company reference |
| `generate_calendar_data()` | Calendar dimension |

---

## Best Practices

1. **Test both backends**: Verify DuckDB and Spark compatibility
2. **Use fixtures**: Leverage existing test data generators
3. **Test measures**: Verify simple, computed, and weighted measures
4. **Test cross-model**: Verify model dependencies work
5. **Test filters**: Ensure filters work across backends
6. **Use in-memory DB**: Faster tests with DuckDB in-memory

---

## Related Documentation

- [Scripts Reference](../08-scripts-reference/) - Test scripts
- [Core Framework](../01-core-framework/) - Component documentation
- [Troubleshooting](../12-troubleshooting/) - Debug resources
