# Troubleshooting Guide

**Common issues and solutions for de_Funk**

---

## Overview

This guide covers common issues encountered when working with de_Funk and their solutions.

---

## Quick Diagnostics

```bash
# Check Bronze data
python -m scripts.diagnose_bronze_data

# Check Silver data
python -m scripts.diagnose_silver_data

# Test API connectivity
python -m scripts.test.test_alpha_vantage_api

# Test DuckDB setup
python -m scripts.test.test_duckdb_setup
```

---

## Common Issues

### API Key Errors

**Symptom**: `401 Unauthorized` or missing API key errors

**Solution**:
```bash
# Copy example env file
cp .env.example .env

# Edit .env and add your API keys
nano .env
```

**Required Keys**:
```bash
ALPHA_VANTAGE_API_KEYS=your_key_here
BLS_API_KEYS=your_key_here       # Optional
CHICAGO_API_KEYS=your_key_here   # Optional
```

---

### Model Build Failures

**Symptom**: Model fails to build or shows dependency errors

**Diagnosis**:
```bash
python -m scripts.test.test_all_models
```

**Solution**:
```bash
# Build models in dependency order
# 1. Core first
python -m scripts.build.rebuild_model --model core

# 2. Then tier 1 models
python -m scripts.build.rebuild_model --model company
python -m scripts.build.rebuild_model --model macro

# 3. Then dependent models
python -m scripts.build.rebuild_model --model stocks
```

---

### Missing Bronze Data

**Symptom**: No data in `storage/bronze/`

**Diagnosis**:
```bash
ls -R storage/bronze/
```

**Solution**:
```bash
# Run full pipeline to ingest data
python -m scripts.ingest.run_full_pipeline --top-n 100

# Verify data exists
python -m scripts.diagnose_bronze_data
```

---

### Missing Silver Data

**Symptom**: No data in `storage/silver/`

**Solution**:
```bash
# Build all Silver layer models
python -m scripts.build.build_all_models

# Or rebuild specific model
python -m scripts.build.rebuild_model --model stocks
```

---

### DuckDB Connection Issues

**Symptom**: Cannot connect to DuckDB

**Diagnosis**:
```bash
python -m scripts.test.test_duckdb_setup
```

**Common Causes**:
- Database file locked by another process
- Corrupted database file
- Memory limit exceeded

**Solution**:
```bash
# Check for locks
lsof storage/duckdb/analytics.db

# Reset database
rm storage/duckdb/analytics.db
python -m scripts.build.build_all_models
```

---

### Rate Limit Errors

**Symptom**: `429 Too Many Requests` from API

**Solution**:
```bash
# Wait for rate limit reset
# Alpha Vantage: 5 calls/min (free), 75 calls/min (premium)

# Use smaller batch sizes
python -m scripts.ingest.run_full_pipeline --top-n 50
```

---

### Measure Not Found

**Symptom**: `Measure 'avg_close' not defined in model 'stocks'`

**Solution**:
1. Check measure exists in YAML: `configs/models/stocks/measures.yaml`
2. Verify measure name spelling
3. Check model is loaded correctly

```python
# List available measures
model = registry.get_model("stocks")
measures = model.list_measures()
print(measures.keys())
```

---

### Cross-Model Reference Failed

**Symptom**: `Cross-model reference 'core.dim_calendar' failed`

**Causes**:
- Dependency model not built
- Session not injected
- Model not in `depends_on`

**Solution**:
1. Check `depends_on` in model YAML
2. Build dependency models first
3. Use UniversalSession for cross-model queries

---

### Import Errors

**Symptom**: `ModuleNotFoundError: No module named 'core'`

**Solution**:
```bash
# Always use python -m syntax
python -m scripts.build.build_all_models  # Correct

# NOT
python scripts/build/build_all_models.py  # Wrong
```

---

### Filter Not Working

**Symptom**: Filters don't seem to apply

**Diagnosis**:
```python
# Check filter syntax
filters = [{"column": "ticker", "operator": "eq", "value": "AAPL"}]

# Verify filter application
result = model.calculate_measure("avg_close", filters=filters)
print(f"Rows: {len(result)}")
```

**Common Issues**:
- Wrong column name
- Incorrect operator syntax
- Data type mismatch

---

## Performance Issues

### Slow Queries

**Solutions**:
1. **Check partitioning**: Ensure data is properly partitioned
2. **Push filters early**: Apply filters in SQL, not Python
3. **Limit results**: Use `LIMIT` clause
4. **Use appropriate backend**: Choose backend based on data size

### Memory Errors

**Solutions**:
```bash
# Increase DuckDB memory limit
export DUCKDB_MEMORY_LIMIT=16GB

# Or in .env
DUCKDB_MEMORY_LIMIT=16GB
```

---

## Debug Resources

| Script | Purpose |
|--------|---------|
| `scripts/diagnose_bronze_data.py` | Check Bronze data |
| `scripts/diagnose_silver_data.py` | Check Silver data |
| `scripts/debug/check_parquet_path.py` | Verify Parquet paths |
| `scripts/debug/diagnose_view_data.py` | Debug view data |

---

## Reset and Rebuild

### Complete Reset

```bash
# 1. Clear all data
python -m scripts.maintenance.clear_and_refresh

# 2. Re-ingest
python -m scripts.ingest.run_full_pipeline --top-n 100

# 3. Rebuild models
python -m scripts.build.build_all_models

# 4. Verify
python -m scripts.diagnose_silver_data
```

### Reset Specific Model

```bash
python -m scripts.maintenance.reset_model --model stocks
python -m scripts.build.rebuild_model --model stocks
```

---

## Getting Help

- **Documentation**: Check this vault's sections
- **Examples**: See `scripts/examples/` for working code
- **Tests**: Run `pytest tests/` to verify setup
- **GitHub**: Report issues at https://github.com/anthropics/claude-code/issues

---

## Related Documentation

- [Testing Guide](../10-testing-guide/) - Test scripts
- [Scripts Reference](../08-scripts-reference/) - All scripts
- [Configuration](../11-configuration/) - Setup help
