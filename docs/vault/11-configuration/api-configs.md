# API Configurations

**API endpoint configuration for data providers**

Files: `configs/*_endpoints.json`
Loader: `config.ConfigLoader` (auto-discovers all API configs)

---

## Overview

de_Funk uses **JSON configuration files** to define API endpoints for external data providers. Each provider has its own config file with endpoints, authentication, and rate limiting.

**Supported Providers**:
- **Alpha Vantage** - Stock market data (prices, fundamentals, technicals)
- **Bureau of Labor Statistics (BLS)** - Economic indicators
- **Chicago Data Portal** - Municipal finance data

---

## Quick Reference

### Configuration Files

| File | Provider | Purpose |
|------|----------|---------|
| `configs/alpha_vantage_endpoints.json` | Alpha Vantage | Stock market data |
| `configs/bls_endpoints.json` | BLS | Economic indicators |
| `configs/chicago_endpoints.json` | Chicago Data Portal | Municipal data |

### Auto-Discovery

```python
from config import ConfigLoader

loader = ConfigLoader()
config = loader.load()

# All API configs auto-discovered
alpha_vantage_cfg = config.apis.get("alpha_vantage", {})
bls_cfg = config.apis.get("bls", {})
chicago_cfg = config.apis.get("chicago", {})
```

---

## Configuration Schema

### Top-Level Structure

All API config files follow this schema:

```json
{
  "credentials": {
    "api_keys": []
  },
  "base_urls": {
    "core": "https://api.example.com"
  },
  "headers": {
    "Authorization": "Bearer ${API_KEY}"
  },
  "rate_limit_per_sec": 5.0,
  "endpoints": {
    "endpoint_name": {
      "base": "core",
      "method": "GET",
      "path_template": "/v1/resource/{param}",
      "required_params": ["param"],
      "default_query": {},
      "response_key": "results",
      "default_path_params": {},
      "pagination_type": "offset"
    }
  }
}
```

---

### Field Reference

#### credentials

**Type**: Object
**Purpose**: API authentication configuration
**Example**:
```json
"credentials": {
  "api_keys": []
}
```

**Notes**:
- Empty array means keys loaded from environment
- Environment variable: `{PROVIDER}_API_KEYS`
- See [Environment Variables](environment-variables.md)

---

#### base_urls

**Type**: Object
**Purpose**: Base URLs for API endpoints
**Example**:
```json
"base_urls": {
  "core": "https://www.alphavantage.co"
}
```

**Notes**:
- Multiple base URLs supported
- Endpoints reference by key (e.g., `"base": "core"`)

---

#### headers

**Type**: Object
**Purpose**: HTTP headers for all requests
**Example**:
```json
"headers": {
  "Content-Type": "application/json"
}
```

---

#### rate_limit_per_sec

**Type**: Number
**Purpose**: Maximum requests per second
**Example**:
```json
"rate_limit_per_sec": 0.083
```

**Provider Defaults**:
- Alpha Vantage Free: 0.083 (5/min)
- Alpha Vantage Premium: 1.25 (75/min)
- BLS: 0.42 (~25/min)
- Chicago: 5.0

**Notes**:
- Provider automatically throttles requests
- Adjust based on API plan tier

---

#### endpoints

**Type**: Object
**Purpose**: Define available API endpoints
**Structure**: `{endpoint_name: endpoint_config}`

---

### Endpoint Configuration

Each endpoint has these fields:

#### base

**Type**: String
**Purpose**: Reference to base URL
**Example**: `"base": "core"`

---

#### method

**Type**: String
**Purpose**: HTTP method
**Values**: `GET`, `POST`, `PUT`, `DELETE`
**Example**: `"method": "GET"`

---

#### path_template

**Type**: String
**Purpose**: URL path with parameter placeholders
**Example**: `"/query"`

---

#### required_params

**Type**: Array of strings
**Purpose**: Required parameters for this endpoint
**Example**: `["function", "symbol"]`

**Validation**:
- Provider validates before making request
- Missing params raise error

---

#### default_query

**Type**: Object
**Purpose**: Default query string parameters
**Example**:
```json
"default_query": {
  "function": "TIME_SERIES_DAILY",
  "outputsize": "full"
}
```

**Notes**:
- Can be overridden at runtime
- Merged with runtime params

---

#### response_key

**Type**: String (or null)
**Purpose**: Key to extract data from response
**Example**: `"response_key": "Time Series (Daily)"`

**Behavior**:
- `"results"` - Extract `response["results"]`
- `null` - Use entire response body

---

## Provider Configurations

### Alpha Vantage (Stock Market Data)

**File**: `configs/alpha_vantage_endpoints.json`

**Endpoints**:
- `time_series_daily` - Daily OHLCV prices
- `time_series_daily_adjusted` - Adjusted daily prices
- `company_overview` - Company fundamentals
- `sma` - Simple Moving Average
- `ema` - Exponential Moving Average
- `rsi` - Relative Strength Index
- `macd` - MACD indicator

**Example Endpoint**:
```json
"time_series_daily": {
  "base": "core",
  "method": "GET",
  "path_template": "/query",
  "required_params": ["symbol"],
  "default_query": {
    "function": "TIME_SERIES_DAILY",
    "outputsize": "full"
  },
  "response_key": "Time Series (Daily)"
}
```

**Usage**:
```python
from datapipelines.providers.alpha_vantage import AlphaVantageProvider

provider = AlphaVantageProvider(config)
data = provider.get_daily_prices(symbol="AAPL")
```

**Rate Limits**:
- Free: 5 requests/minute, 500/day
- Premium: 75 requests/minute
- Configured: 0.083 req/sec (5/min for free tier)

---

### Bureau of Labor Statistics (Economic Data)

**File**: `configs/bls_endpoints.json`

**Endpoints**:
- `timeseries` - Get time series data
- `series_info` - Get series metadata

**Series Codes** (pre-configured):
- `unemployment.national` - `LNS14000000`
- `employment.total_nonfarm` - `CES0000000001`
- `cpi.all_items` - `CUUR0000SA0`
- `ppi.final_demand` - `WPUFD4`
- `wages.avg_hourly_earnings` - `CES0500000003`

**Example Endpoint**:
```json
"timeseries": {
  "base": "core",
  "method": "POST",
  "path_template": "/timeseries/data/",
  "required_params": ["seriesid", "startyear", "endyear"],
  "default_query": {},
  "response_key": "Results.series"
}
```

**Usage**:
```python
from datapipelines.providers.bls import BLSProvider

provider = BLSProvider(config)
data = provider.get_timeseries(
    series_ids=["LNS14000000"],
    start_year=2020,
    end_year=2024
)
```

**Rate Limits**:
- Without key: 25 queries/day
- With key: 500 queries/day
- Configured: 0.42 req/sec (~25/min)

---

### Chicago Data Portal (Municipal Data)

**File**: `configs/chicago_endpoints.json`

**Endpoints**:
- `building_permits` - Building permits issued
- `business_licenses` - Active business licenses
- `unemployment_rates` - Community area unemployment
- `per_capita_income` - Community area income
- `economic_indicators` - Economic time series
- `affordable_rental_housing` - Affordable housing

**Example Endpoint**:
```json
"building_permits": {
  "base": "core",
  "method": "GET",
  "path_template": "/resource/ydr8-5enu.json",
  "required_params": [],
  "default_query": {
    "$limit": 1000,
    "$order": "issue_date DESC"
  },
  "response_key": null,
  "pagination_type": "offset"
}
```

**Socrata Query Parameters**:
- `$limit` - Records per page (max 1000)
- `$offset` - Skip N records (pagination)
- `$order` - Sort order
- `$where` - Filter clause (SQL-like)

**Usage**:
```python
from datapipelines.providers.chicago import ChicagoProvider

provider = ChicagoProvider(config)
data = provider.get_building_permits(
    limit=1000,
    where="issue_date > '2024-01-01'"
)
```

**Rate Limits**:
- Without token: 1,000 requests/day
- With token: Higher limits
- Configured: 5.0 req/sec

---

## Extending API Configurations

### Adding a New Endpoint

1. **Edit config file** (e.g., `configs/alpha_vantage_endpoints.json`):

```json
"endpoints": {
  "new_endpoint": {
    "base": "core",
    "method": "GET",
    "path_template": "/query",
    "required_params": ["symbol"],
    "default_query": {
      "function": "NEW_FUNCTION"
    },
    "response_key": "data"
  }
}
```

2. **Update provider class**:

```python
class AlphaVantageProvider:
    def get_new_data(self, symbol: str):
        return self.call_endpoint(
            'new_endpoint',
            query_params={'symbol': symbol}
        )
```

3. **Test endpoint**:

```python
provider = AlphaVantageProvider(config)
data = provider.get_new_data('AAPL')
```

---

### Adding a New Provider

1. **Create config file**: `configs/newprovider_endpoints.json`

```json
{
  "credentials": {"api_keys": []},
  "base_urls": {"core": "https://api.newprovider.com"},
  "headers": {"X-API-Key": "${API_KEY}"},
  "rate_limit_per_sec": 2.0,
  "endpoints": {
    "get_data": {
      "base": "core",
      "method": "GET",
      "path_template": "/v1/data",
      "required_params": [],
      "default_query": {},
      "response_key": "results"
    }
  }
}
```

2. **Add environment variable** (`.env`):

```bash
NEWPROVIDER_API_KEYS=your_key_here
```

3. **Create provider class**:

```python
# datapipelines/providers/newprovider/provider.py
from datapipelines.base.provider import BaseProvider

class NewProvider(BaseProvider):
    def __init__(self, config):
        super().__init__(config, provider_name="newprovider")

    def get_data(self):
        return self.call_endpoint('get_data')
```

4. **Config auto-discovered**:

```python
from config import ConfigLoader

loader = ConfigLoader()
config = loader.load()

# Auto-discovered!
newprovider_cfg = config.apis.get("newprovider", {})
```

---

## Rate Limiting

### How It Works

Providers automatically throttle requests:

```python
# In BaseProvider
def call_endpoint(self, endpoint_name, **kwargs):
    # Calculate delay based on rate_limit_per_sec
    delay = 1.0 / self.config['rate_limit_per_sec']

    # Wait if needed
    time.sleep(delay)

    # Make request
    response = requests.request(...)
    return response
```

### Adjusting Rate Limits

**Conservative** (avoid rate limit errors):
```json
"rate_limit_per_sec": 0.05
```

**Based on API Plan**:
- Free tier: Use conservative values
- Paid tier: Match API plan limits

---

## Authentication Patterns

### Query Parameter (Alpha Vantage)

```json
"default_query": {
  "apikey": "${API_KEY}"
}
```

### Header Token (Chicago)

```json
"headers": {
  "X-App-Token": "${API_KEY}"
}
```

### POST Body (BLS)

```json
"default_query": {
  "registrationkey": "${API_KEY}"
}
```

### Multiple Keys (Rotation)

```bash
# .env
ALPHA_VANTAGE_API_KEYS=key1,key2,key3
```

Provider rotates through keys automatically.

---

## Pagination Patterns

### Offset-Based (Chicago)

```json
"pagination_type": "offset",
"default_query": {
  "$limit": 1000,
  "$offset": 0
}
```

**Usage**:
```python
# Page 1
data = provider.get(limit=1000, offset=0)

# Page 2
data = provider.get(limit=1000, offset=1000)
```

---

### No Pagination (Alpha Vantage, BLS)

```json
"pagination_type": "none"
```

Alpha Vantage and BLS return all data in single responses.

---

## Troubleshooting

### Config Not Found

**Symptom**: `KeyError: 'alpha_vantage'`

**Solution**:
- Check file exists: `configs/alpha_vantage_endpoints.json`
- Check file is valid JSON
- Check ConfigLoader auto-discovery

---

### Endpoint Not Found

**Symptom**: `KeyError: 'endpoint_name'`

**Solution**:
- Check endpoint exists in config file
- Check spelling matches exactly
- Check `endpoints` section structure

---

### Rate Limit Errors

**Symptom**: `429 Too Many Requests`

**Solutions**:
1. Lower `rate_limit_per_sec`
2. Add multiple API keys
3. Upgrade API plan

---

### Invalid API Key

**Symptom**: `401 Unauthorized`

**Solutions**:
1. Check `.env` has correct variable name
2. Check API key is valid
3. Check header/query param format matches API docs

---

## Related Documentation

- [Environment Variables](environment-variables.md) - API key configuration
- [Providers](../06-pipelines/providers.md) - Provider implementations
- [Ingestors](../06-pipelines/ingestors.md) - Orchestration layer
- [ConfigLoader](config-loader.md) - Configuration system
