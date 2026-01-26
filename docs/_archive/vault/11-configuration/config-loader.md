# ConfigLoader Reference

**Centralized configuration management system**

File: `config/loader.py`
Related: See `/CLAUDE.md` for complete configuration system overview

---

## Overview

ConfigLoader provides type-safe, validated configuration loading with clear precedence rules. Introduced in November 2025 to replace scattered configuration logic.

**Key Features:**
- Single entry point for all configuration
- Type-safe dataclass models
- Clear precedence (env vars > params > files > defaults)
- Auto-discovery of repository root and API configs

---

## Quick Reference

```python
from config import ConfigLoader

# Basic usage
loader = ConfigLoader()
config = loader.load()

# Override connection
config = loader.load(connection_type="duckdb")

# Access config
print(config.connection.type)      # 'duckdb'
print(config.repo_root)             # Path('/home/user/de_Funk')
print(config.models_dir)            # Path('configs/models')

# API configs (auto-discovered)
alpha_vantage_cfg = config.apis.get("alpha_vantage", {})
```

---

## Configuration Precedence

1. **Explicit parameters** - `loader.load(connection_type="duckdb")`
2. **Environment variables** - `CONNECTION_TYPE=duckdb` in `.env`
3. **Config files** - `configs/storage.json`
4. **Defaults** - `config/constants.py`

---

## Configuration Models

### AppConfig
```python
@dataclass
class AppConfig:
    repo_root: Path
    connection: ConnectionConfig
    storage: Dict
    apis: Dict
    log_level: str
    models_dir: Path
    bronze_dir: Path
    silver_dir: Path
```

### ConnectionConfig
```python
@dataclass
class ConnectionConfig:
    type: str  # 'duckdb' or 'spark'
    spark: SparkConfig
    duckdb: DuckDBConfig
```

---

## Environment Variables

Set in `.env` file (copy from `.env.example`):

```bash
# Connection
CONNECTION_TYPE=duckdb

# API Keys
ALPHA_VANTAGE_API_KEYS=your_key_here
BLS_API_KEYS=your_key_here

# DuckDB
DUCKDB_DATABASE_PATH=storage/duckdb/analytics.db
DUCKDB_MEMORY_LIMIT=8GB

# Spark (if using)
SPARK_DRIVER_MEMORY=8g
SPARK_EXECUTOR_MEMORY=8g
```

---

## Related Documentation

- [CLAUDE.md - Configuration System](/CLAUDE.md#configuration-management-system) - Complete overview
- [Environment Variables](environment-variables.md) - Detailed env var reference
- [API Configs](api-configs.md) - API configuration format
