# Testing Guide

**Testing strategies and best practices**

Source: See `/TESTING_GUIDE.md` for comprehensive guide
Files: `tests/`

---

## Overview

de_Funk uses **pytest** for unit and integration testing with support for both DuckDB and Spark backends.

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

**All Tests**:
```bash
pytest tests/
```

**Unit Tests Only**:
```bash
pytest tests/unit/
```

**Integration Tests**:
```bash
pytest tests/integration/
```

**Backend Tests**:
```bash
bash scripts/run_backend_tests.sh
```

**Specific Test**:
```bash
pytest tests/unit/test_measure_framework.py::test_simple_measure
```

---

## Test Scripts

| Script | Purpose |
|--------|---------|
| `run_backend_tests.sh` | Test DuckDB vs Spark compatibility |
| `test_all_models.py` | Validate all model configs |
| `test_domain_model_integration_duckdb.py` | DuckDB integration tests |
| `test_pipeline_e2e.py` | End-to-end pipeline test |
| `test_ui_integration.py` | UI integration tests |

---

## Best Practices

1. **Test both backends** (DuckDB and Spark)
2. **Use fixtures** for sample data
3. **Test measure calculations** (verify accuracy)
4. **Test cross-model queries**
5. **Use in-memory databases** for speed

---

## Related Documentation

- [Backend Testing](backend-testing.md) - Backend compatibility tests
- [Pipeline Testing](pipeline-testing.md) - Pipeline validation
- `/TESTING_GUIDE.md` - Comprehensive testing guide
