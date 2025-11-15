# Configuration Management

## Overview

de_Funk uses a centralized configuration system that provides:

- **Type-safe configuration** using dataclasses
- **Clear precedence rules** for configuration sources
- **Validation** of all configuration values
- **No hardcoded values** scattered throughout the codebase
- **Explicit initialization** (no auto-load side effects)

## Quick Start

### Basic Usage

```python
from config import ConfigLoader

# Auto-discover repo root and load all configuration
loader = ConfigLoader()
config = loader.load()

# Access typed configuration
print(f"Connection type: {config.connection.type}")
print(f"Repo root: {config.repo_root}")
print(f"Log level: {config.log_level}")

# Access API configurations
polygon_api = config.apis.get("polygon")
if polygon_api:
    print(f"Polygon API keys: {len(polygon_api.api_keys)}")
```

### Using with RepoContext (Backward Compatible)

```python
from core.context import RepoContext

# RepoContext now uses ConfigLoader internally
ctx = RepoContext.from_repo_root(connection_type="duckdb")

# Access the new typed config
if ctx.config:
    print(f"Models directory: {ctx.config.models_dir}")
```

## Configuration Sources and Precedence

Configuration is loaded from multiple sources with clear precedence:

1. **Explicit parameters** (highest priority)
2. **Environment variables** (from `.env` file or system)
3. **Configuration files** (`configs/*.json`)
4. **Default values** (lowest priority)

### Example Precedence

```python
# storage.json has: "connection": {"type": "spark"}
# .env has: CONNECTION_TYPE=duckdb
# Code:
config = loader.load(connection_type="duckdb")  # Uses 'duckdb' (explicit param wins)

config = loader.load()  # Uses 'duckdb' (env var wins over config file)
```

## Configuration Files

### Required Files

All configuration files are located in `configs/` directory:

#### `storage.json`
```json
{
  "connection": {
    "type": "duckdb"
  },
  "bronze_root": "storage/bronze",
  "silver_root": "storage/silver",
  "tables": {
    "polygon_daily_prices": {
      "path": "polygon/daily_prices",
      "partition_by": ["dt"]
    }
  }
}
```

#### `polygon_endpoints.json`
```json
{
  "base_url": "https://api.polygon.io",
  "rate_limit": {
    "calls": 5,
    "period": 60
  },
  "endpoints": {
    "ref_all_tickers": {
      "path": "/v3/reference/tickers",
      "method": "GET"
    }
  }
}
```

### Optional Files

- `bls_endpoints.json` - Bureau of Labor Statistics API configuration
- `chicago_endpoints.json` - Chicago Data Portal API configuration

### Model Configurations

Model configurations are YAML files in `configs/models/`:

- `core.yaml` - Calendar dimensions
- `company.yaml` - Company domain model
- `equity.yaml` - Equity data
- `macro.yaml` - Macroeconomic indicators
- etc.

## Environment Variables

### Required Variables

Set these in `.env` file (copy from `.env.example`):

```bash
# API Keys (required for data ingestion)
POLYGON_API_KEYS=your_key_here
BLS_API_KEYS=your_key_here
CHICAGO_API_KEYS=your_key_here
```

### Optional Variables

#### Connection Configuration
```bash
# Override connection type (default: duckdb)
CONNECTION_TYPE=spark

# Logging level (default: INFO)
LOG_LEVEL=DEBUG
```

#### Spark Configuration (when using Spark)
```bash
SPARK_DRIVER_MEMORY=8g
SPARK_EXECUTOR_MEMORY=8g
SPARK_SHUFFLE_PARTITIONS=200
SPARK_TIMEZONE=UTC
SPARK_LEGACY_TIME_PARSER=true
```

#### DuckDB Configuration (when using DuckDB)
```bash
DUCKDB_PATH=storage/duckdb/analytics.db
DUCKDB_MEMORY_LIMIT=8GB
DUCKDB_THREADS=8
```

## Configuration Objects

### AppConfig

Main configuration object containing all settings:

```python
@dataclass
class AppConfig:
    repo_root: Path
    connection: ConnectionConfig
    storage: StorageConfig
    apis: Dict[str, APIConfig]
    log_level: str
    env_loaded: bool
```

**Properties:**
- `models_dir` - Path to model configurations
- `configs_dir` - Path to config files

### ConnectionConfig

Database connection configuration:

```python
@dataclass
class ConnectionConfig:
    type: str  # "spark" or "duckdb"
    spark: Optional[SparkConfig] = None
    duckdb: Optional[DuckDBConfig] = None
```

### SparkConfig

Spark-specific configuration:

```python
@dataclass
class SparkConfig:
    driver_memory: str = "4g"
    executor_memory: str = "4g"
    shuffle_partitions: int = 200
    timezone: str = "UTC"
    legacy_time_parser: bool = True
    additional_config: Dict[str, Any] = field(default_factory=dict)
```

**Methods:**
- `to_spark_conf_dict()` - Convert to Spark configuration dictionary

### DuckDBConfig

DuckDB-specific configuration:

```python
@dataclass
class DuckDBConfig:
    database_path: Path
    memory_limit: str = "4GB"
    threads: int = 4
    read_only: bool = False
    additional_config: Dict[str, Any] = field(default_factory=dict)
```

**Methods:**
- `to_connection_params()` - Convert to DuckDB connection parameters

### StorageConfig

Storage layer configuration:

```python
@dataclass
class StorageConfig:
    bronze_root: Path
    silver_root: Path
    tables: Dict[str, Dict[str, Any]]
```

### APIConfig

API provider configuration:

```python
@dataclass
class APIConfig:
    name: str
    base_url: str
    endpoints: Dict[str, Any]
    api_keys: List[str]
    rate_limit_calls: int = 5
    rate_limit_period: int = 60
    headers: Dict[str, str]
    timeout: int = 30
```

## Advanced Usage

### Custom Configuration Loading

```python
from config import ConfigLoader
from pathlib import Path

# Explicit repo root
loader = ConfigLoader(repo_root="/path/to/repo")

# Skip .env loading (use system env vars only)
config = loader.load(load_env=False)

# Override connection type
config = loader.load(connection_type="spark")
```

### Accessing Specific Configurations

```python
# Get Spark configuration for creating session
if config.connection.type == "spark":
    spark_conf = config.connection.spark.to_spark_conf_dict()
    # Use with SparkSession.builder

# Get DuckDB connection parameters
if config.connection.type == "duckdb":
    db_params = config.connection.duckdb.to_connection_params()
    # Use with duckdb.connect()

# Access API configurations
for api_name, api_config in config.apis.items():
    print(f"{api_name}: {api_config.base_url}")
    print(f"  Keys loaded: {len(api_config.api_keys)}")
```

### Using with Spark Sessions

```python
from orchestration.common.spark_session import get_spark

# New way (with SparkConfig)
spark = get_spark("MyApp", spark_config=config.connection.spark)

# Old way (still supported)
spark = get_spark("MyApp", config={"spark.driver.memory": "8g"})
```

## Migration Guide

### From Direct JSON Loading

**Before:**
```python
import json
from pathlib import Path

polygon_cfg = json.loads((root / "configs" / "polygon_endpoints.json").read_text())
```

**After:**
```python
from config import ConfigLoader

config = ConfigLoader().load()
polygon_api = config.apis["polygon"]
```

### From utils.env_loader

**Before:**
```python
from utils.env_loader import get_polygon_api_keys, inject_credentials_into_config

api_keys = get_polygon_api_keys()
polygon_cfg = inject_credentials_into_config(polygon_cfg, 'polygon')
```

**After:**
```python
from config import ConfigLoader

config = ConfigLoader().load()
api_keys = config.apis["polygon"].api_keys
# Credentials already injected!
```

### From RepoContext

**Before:**
```python
from core.context import RepoContext

ctx = RepoContext.from_repo_root()
polygon_cfg = ctx.polygon_cfg  # dict
storage = ctx.storage  # dict
```

**After:**
```python
from core.context import RepoContext

ctx = RepoContext.from_repo_root()
# Still works! But now uses ConfigLoader internally

# Access typed config for new features
config = ctx.config
polygon_api = config.apis["polygon"]  # APIConfig object
storage = config.storage  # StorageConfig object
```

## Troubleshooting

### Configuration file not found

**Error:** `ValueError: Configuration file not found: /path/to/configs/storage.json`

**Solution:** Ensure you're running from within the repository or provide explicit `repo_root`:
```python
loader = ConfigLoader(repo_root="/path/to/de_Funk")
```

### No API keys loaded

**Warning:** `No API keys found for polygon`

**Solution:**
1. Check `.env` file exists in repo root
2. Verify `POLYGON_API_KEYS=your_key` is set
3. Ensure no spaces around `=`
4. For multiple keys: `POLYGON_API_KEYS=key1,key2,key3`

### Invalid connection type

**Error:** `ValueError: Invalid connection type: mysql. Must be 'spark' or 'duckdb'.`

**Solution:** Only `spark` and `duckdb` are supported. Check:
1. `storage.json` has valid `connection.type`
2. `CONNECTION_TYPE` env var is not set to invalid value
3. Explicit parameter uses valid type

### Import errors

**Error:** `ModuleNotFoundError: No module named 'config'`

**Solution:** The `config` module should be in the repo root. Ensure:
1. `config/__init__.py` exists
2. Python path includes repo root
3. Not running from subdirectory without proper imports

## Best Practices

### 1. Use ConfigLoader for New Code

```python
# Good
from config import ConfigLoader
config = ConfigLoader().load()

# Avoid (unless maintaining legacy code)
import json
config = json.loads(file.read_text())
```

### 2. Don't Hardcode Configuration

```python
# Bad
spark = SparkSession.builder.config("spark.driver.memory", "4g")

# Good
from config import ConfigLoader
config = ConfigLoader().load()
spark = get_spark("App", spark_config=config.connection.spark)
```

### 3. Use Type-Safe Access

```python
# Good - typed, validated
if config.connection.type == "duckdb":
    db_path = config.connection.duckdb.database_path

# Avoid - untyped, error-prone
if storage["connection"]["type"] == "duckdb":
    db_path = storage.get("duckdb_path", "default.db")
```

### 4. Set Defaults in .env.example

Document all configuration options in `.env.example` with:
- Comments explaining the option
- Example values
- Links to documentation
- Recommended defaults

### 5. Validate Early

Let ConfigLoader validate configuration at startup:

```python
# At application startup
try:
    config = ConfigLoader().load()
except ValueError as e:
    logger.error(f"Invalid configuration: {e}")
    sys.exit(1)
```

## See Also

- [Architecture Overview](architecture.md)
- [API Documentation](api.md)
- [Environment Setup](setup.md)
