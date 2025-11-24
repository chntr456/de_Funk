# Configuration

**Centralized configuration system for de_Funk**

---

## Overview

de_Funk uses a centralized, type-safe configuration system that eliminates scattered configuration loading and provides clear precedence rules.

---

## Documents

| Document | Description |
|----------|-------------|
| [Config Loader](config-loader.md) | ConfigLoader class reference |
| [Environment Variables](environment-variables.md) | Environment configuration |
| [API Configs](api-configs.md) | API endpoint configuration |

---

## Configuration Precedence

Configuration sources in order of priority (highest to lowest):

1. **Explicit parameters** - Passed directly to `loader.load()`
2. **Environment variables** - From `.env` file or system env
3. **Configuration files** - JSON files in `configs/` directory
4. **Default values** - Defined in `config/constants.py`

---

## ConfigLoader Usage

```python
from config import ConfigLoader

# Basic usage
loader = ConfigLoader()
config = loader.load()

# Access typed configuration
print(f"Connection type: {config.connection.type}")
print(f"Repo root: {config.repo_root}")

# Override connection type
config = loader.load(connection_type="duckdb")

# Access API configs
alpha_vantage_cfg = config.apis.get("alpha_vantage", {})
```

---

## Configuration Files

### Storage Configuration

**File**: `configs/storage.json`

```json
{
  "bronze_root": "storage/bronze",
  "silver_root": "storage/silver",
  "tables": {
    "securities_reference": {
      "path": "alpha_vantage/securities_reference",
      "partition_by": ["snapshot_dt", "asset_type"]
    }
  }
}
```

### API Endpoints

**Files**: `configs/*_endpoints.json`

```json
{
  "base_url": "https://www.alphavantage.co",
  "endpoints": {
    "time_series_daily": {
      "path": "/query",
      "params": {"function": "TIME_SERIES_DAILY"}
    }
  }
}
```

---

## Environment Variables

Set in `.env` file:

```bash
# API Keys (required for data ingestion)
ALPHA_VANTAGE_API_KEYS=your_key_here
BLS_API_KEYS=your_key_here
CHICAGO_API_KEYS=your_key_here

# Connection type
CONNECTION_TYPE=duckdb

# DuckDB configuration
DUCKDB_DATABASE_PATH=storage/duckdb/analytics.db
DUCKDB_MEMORY_LIMIT=8GB
DUCKDB_THREADS=8

# Spark configuration (when using Spark)
SPARK_DRIVER_MEMORY=8g
SPARK_EXECUTOR_MEMORY=8g
```

---

## Model Configuration (v2.0)

Models use modular YAML files:

```
configs/models/{model}/
├── model.yaml      # Metadata, dependencies
├── schema.yaml     # Dimensions, facts
├── graph.yaml      # Nodes, edges, paths
└── measures.yaml   # Measure definitions
```

### Inheritance

```yaml
# model.yaml
model: stocks
inherits_from: _base.securities

# schema.yaml
extends: _base.securities.schema
dimensions:
  dim_stock:
    extends: _base.securities._dim_security
```

---

## Type-Safe Configuration

All configuration uses dataclasses:

```python
@dataclass
class AppConfig:
    repo_root: Path
    connection: ConnectionConfig
    storage: Dict
    apis: Dict
    log_level: str

@dataclass
class ConnectionConfig:
    type: str  # "spark" or "duckdb"
    spark: SparkConfig
    duckdb: DuckDBConfig
```

---

## Related Documentation

- [Data Providers](../03-data-providers/) - API documentation
- [Core Framework](../01-core-framework/) - RepoContext usage
- [Scripts Reference](../08-scripts-reference/) - Configuration scripts
