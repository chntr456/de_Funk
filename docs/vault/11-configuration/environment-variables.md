# Environment Variables

**Environment-based configuration for de_Funk**

Source: `.env.example`
Loader: `utils/env_loader.py` (deprecated, use `config.ConfigLoader`)

---

## Overview

de_Funk uses **environment variables** for sensitive configuration (API keys) and runtime settings. Variables are loaded from a `.env` file at the repository root.

**Configuration Precedence**:
1. Environment variables (`.env` or system)
2. Configuration files (`configs/*.json`)
3. Default values (`config/constants.py`)

---

## Quick Reference

### Required Variables

```bash
# API Keys (required for data ingestion)
ALPHA_VANTAGE_API_KEYS=your_key_here
BLS_API_KEYS=your_key_here
CHICAGO_API_KEYS=your_key_here
```

### Optional Variables

```bash
# Connection type (default: duckdb)
CONNECTION_TYPE=duckdb

# Logging level (default: INFO)
LOG_LEVEL=DEBUG

# DuckDB settings
DUCKDB_DATABASE_PATH=storage/duckdb/analytics.db
DUCKDB_MEMORY_LIMIT=8GB
DUCKDB_THREADS=8

# Spark settings
SPARK_DRIVER_MEMORY=8g
SPARK_EXECUTOR_MEMORY=8g
SPARK_SHUFFLE_PARTITIONS=400
```

---

## Setup Instructions

### 1. Copy Template

```bash
cp .env.example .env
```

### 2. Add API Keys

Edit `.env` and replace placeholder values:

```bash
# Alpha Vantage - Get from: https://www.alphavantage.co/support/#api-key
ALPHA_VANTAGE_API_KEYS=your_key_here

# BLS - Register at: https://data.bls.gov/registrationEngine/
BLS_API_KEYS=blskey123abc

# Chicago Data Portal - Get from: https://data.cityofchicago.org/profile/app_tokens
CHICAGO_API_KEYS=apptoken123
```

### 3. Never Commit `.env`

**IMPORTANT**: `.env` is in `.gitignore` - never commit it!

---

## Variable Reference

### API Keys

#### ALPHA_VANTAGE_API_KEYS

**Purpose**: Alpha Vantage API authentication
**Format**: Comma-separated list of API keys
**Required**: Yes (for stock market data ingestion)
**Example**:
```bash
# Single key
ALPHA_VANTAGE_API_KEYS=your_api_key

# Multiple keys (for rate limit rotation)
ALPHA_VANTAGE_API_KEYS=key1,key2,key3
```

**Get Key**: https://www.alphavantage.co/support/#api-key

**Rate Limits**:
- Free tier: 5 requests/minute, 500 requests/day
- Premium: 75 requests/minute (varies by plan)

---

#### BLS_API_KEYS

**Purpose**: Bureau of Labor Statistics API authentication
**Format**: Comma-separated list of API keys
**Required**: No (but recommended for higher limits)
**Example**:
```bash
BLS_API_KEYS=abc123xyz789def456
```

**Get Key**: https://data.bls.gov/registrationEngine/

**Rate Limits**:
- Without key: 25 queries/day, 10 years/query
- With key (v1): 500 queries/day, 10 years/query
- With key (v2): 500 queries/day, 20 years/query

---

#### CHICAGO_API_KEYS

**Purpose**: Chicago Data Portal (Socrata) API authentication
**Format**: Comma-separated list of app tokens
**Required**: No (but recommended for higher limits)
**Example**:
```bash
CHICAGO_API_KEYS=apptoken123abc
```

**Get Token**: https://data.cityofchicago.org/profile/app_tokens

**Rate Limits**:
- Without token: 1,000 requests/day
- With token: Higher limits (varies by plan)

---

### Connection Configuration

#### CONNECTION_TYPE

**Purpose**: Specify database backend
**Values**: `duckdb`, `spark`
**Default**: `duckdb`
**Example**:
```bash
CONNECTION_TYPE=duckdb
```

**Notes**:
- DuckDB: in-process analytics database
- Spark: distributed processing for large datasets
- Precedence: env var > storage.json > default

---

### DuckDB Configuration

#### DUCKDB_DATABASE_PATH

**Purpose**: Path to DuckDB database file
**Format**: Relative or absolute path
**Default**: `storage/duckdb/analytics.db`
**Example**:
```bash
DUCKDB_DATABASE_PATH=/mnt/data/analytics.db
```

---

#### DUCKDB_MEMORY_LIMIT

**Purpose**: Maximum memory for DuckDB queries
**Format**: Size with unit (GB, MB)
**Default**: System dependent
**Example**:
```bash
DUCKDB_MEMORY_LIMIT=16GB
```

**Recommendations**:
- Development: 4-8GB
- Production: 50-75% of available RAM

---

#### DUCKDB_THREADS

**Purpose**: Number of threads for parallel processing
**Format**: Integer
**Default**: Number of CPU cores
**Example**:
```bash
DUCKDB_THREADS=16
```

---

### Spark Configuration

#### SPARK_DRIVER_MEMORY

**Purpose**: Memory allocated to Spark driver
**Format**: Size with unit (g, m)
**Default**: `4g`
**Example**:
```bash
SPARK_DRIVER_MEMORY=8g
```

---

#### SPARK_EXECUTOR_MEMORY

**Purpose**: Memory allocated to each Spark executor
**Format**: Size with unit (g, m)
**Default**: `4g`
**Example**:
```bash
SPARK_EXECUTOR_MEMORY=16g
```

---

#### SPARK_SHUFFLE_PARTITIONS

**Purpose**: Number of partitions for shuffle operations
**Format**: Integer
**Default**: `200`
**Example**:
```bash
SPARK_SHUFFLE_PARTITIONS=800
```

**Recommendations**:
- Small datasets (<10GB): 100-200
- Medium datasets (10-100GB): 400-800
- Large datasets (>100GB): 1000+

---

#### SPARK_TIMEZONE

**Purpose**: Timezone for Spark SQL operations
**Format**: IANA timezone string
**Default**: `UTC`
**Example**:
```bash
SPARK_TIMEZONE=America/Chicago
```

---

### Logging Configuration

#### LOG_LEVEL

**Purpose**: Control logging verbosity
**Values**: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
**Default**: `INFO`
**Example**:
```bash
LOG_LEVEL=DEBUG
```

**Use Cases**:
- `DEBUG`: Development and troubleshooting
- `INFO`: Normal operation (default)
- `WARNING`: Production environments
- `ERROR`: Minimal logging

---

## Loading Environment Variables

### New Config System (Recommended)

```python
from config import ConfigLoader

# ConfigLoader automatically loads .env
loader = ConfigLoader()
config = loader.load()

# Access configuration
print(config.connection.type)  # From CONNECTION_TYPE
print(config.log_level)         # From LOG_LEVEL
```

### Legacy System (Deprecated)

```python
from utils.env_loader import load_dotenv, get_alpha_vantage_api_keys

# Manually load .env
load_dotenv()

# Get API keys
av_keys = get_alpha_vantage_api_keys()
```

---

## Multiple API Keys (Rate Limit Rotation)

de_Funk supports **multiple API keys** for the same provider to work around rate limits:

**Example**:
```bash
ALPHA_VANTAGE_API_KEYS=key1,key2,key3
```

**How It Works**:
1. Provider rotates through keys on each request
2. If one key hits rate limit, next key is used
3. Errors are logged but don't stop pipeline

**Implementation**:
```python
# In provider code
from utils.env_loader import get_api_keys

api_keys = get_api_keys('ALPHA_VANTAGE_API_KEYS')
# Returns: ['key1', 'key2', 'key3']

# Rotate on each request
current_key = api_keys[request_count % len(api_keys)]
```

---

## Security Best Practices

### 1. Never Commit .env

**Check `.gitignore`**:
```bash
# .gitignore
.env
.env.*
!.env.example
```

### 2. Use Strong API Keys

- Rotate keys periodically
- Use separate keys for dev/prod
- Revoke keys if compromised

### 3. Restrict Access

```bash
# Set restrictive permissions
chmod 600 .env
```

### 4. Use Different Keys Per Environment

```bash
# Development
ALPHA_VANTAGE_API_KEYS=dev_key_here

# Production
ALPHA_VANTAGE_API_KEYS=prod_key_here
```

---

## Troubleshooting

### .env Not Loading

**Symptom**: Environment variables not set

**Solutions**:

1. **Check .env location**:
   ```bash
   ls -la .env  # Must be at repo root
   ```

2. **Check syntax**:
   ```bash
   # Valid
   KEY=value

   # Invalid
   KEY = value  # No spaces around =
   export KEY=value  # No export keyword
   ```

3. **Explicit load**:
   ```python
   from utils.env_loader import load_dotenv
   load_dotenv()  # Force load
   ```

---

### API Key Not Found

**Symptom**: `Warning: ALPHA_VANTAGE_API_KEYS not set`

**Solutions**:

1. **Check key name** (must be exact):
   ```bash
   # Correct
   ALPHA_VANTAGE_API_KEYS=abc123

   # Wrong
   ALPHA_VANTAGE_API_KEY=abc123  # Missing 'S'
   ```

2. **Check quotes** (optional but must match):
   ```bash
   # All valid
   KEY=value
   KEY="value"
   KEY='value'

   # Invalid
   KEY="value'  # Mismatched quotes
   ```

---

### Rate Limit Errors

**Symptom**: `429 Too Many Requests`

**Solutions**:

1. **Add multiple keys**:
   ```bash
   ALPHA_VANTAGE_API_KEYS=key1,key2,key3
   ```

2. **Reduce request rate**:
   - Edit `configs/alpha_vantage_endpoints.json`
   - Lower `rate_limit_per_sec` value

3. **Upgrade API plan**:
   - Free tier: 5 req/min
   - Premium: 75 req/min

---

## Related Documentation

- [ConfigLoader](config-loader.md) - Centralized configuration system
- [API Configs](api-configs.md) - API endpoint configuration
- [Providers](../06-pipelines/providers.md) - API client implementations
- `/QUICKSTART.md` - Getting started guide
