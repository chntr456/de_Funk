# API Configurations

**API endpoint configuration for data providers**

Files: `configs/*_endpoints.json`
Loader: `config.ConfigLoader` (auto-discovers all API configs)

---

## Overview

de_Funk uses **JSON configuration files** to define API endpoints for external data providers. Each provider has its own config file with endpoints, authentication, and rate limiting.

**Supported Providers**:
- **Polygon.io** - Stock market data (prices, companies, news)
- **Bureau of Labor Statistics (BLS)** - Economic indicators
- **Chicago Data Portal** - Municipal finance data

---

## Quick Reference

### Configuration Files

| File | Provider | Purpose |
|------|----------|---------|
| `configs/polygon_endpoints.json` | Polygon.io | Stock market data |
| `configs/bls_endpoints.json` | BLS | Economic indicators |
| `configs/chicago_endpoints.json` | Chicago Data Portal | Municipal data |

### Auto-Discovery

```python
from config import ConfigLoader

loader = ConfigLoader()
config = loader.load()

# All API configs auto-discovered
polygon_cfg = config.apis.get("polygon", {})
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
  "core": "https://api.polygon.io",
  "reference": "https://reference.polygon.io"
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
  "Authorization": "Bearer ${API_KEY}",
  "Content-Type": "application/json"
}
```

**Variable Substitution**:
- `${API_KEY}` - Replaced with current API key
- Rotation handled by provider

---

#### rate_limit_per_sec

**Type**: Number
**Purpose**: Maximum requests per second
**Example**:
```json
"rate_limit_per_sec": 1.0
```

**Provider Defaults**:
- Polygon: 1.0 (60/min on free tier, but conservative)
- BLS: 0.42 (~25/min on free tier)
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
**Example**: `"/v3/reference/tickers/{ticker}"`

**Placeholders**:
- `{param}` - Replaced with value from `path_params`
- Use `required_params` to validate

---

#### required_params

**Type**: Array of strings
**Purpose**: Required parameters for this endpoint
**Example**: `["ticker", "date"]`

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
  "limit": 1000,
  "adjusted": "true"
}
```

**Notes**:
- Can be overridden at runtime
- Merged with runtime params

---

#### response_key

**Type**: String (or null)
**Purpose**: Key to extract data from response
**Example**: `"response_key": "results"`

**Behavior**:
- `"results"` - Extract `response["results"]`
- `null` - Use entire response body

---

#### default_path_params

**Type**: Object
**Purpose**: Default values for path parameters
**Example**:
```json
"default_path_params": {
  "version": "v3"
}
```

---

#### pagination_type

**Type**: String (optional)
**Purpose**: Pagination strategy
**Values**: `"offset"`, `"cursor"`, `"page"`, `"none"`
**Example**: `"pagination_type": "offset"`

---

## Provider Configurations

### Polygon.io (Stock Market Data)

**File**: `configs/polygon_endpoints.json`

**Endpoints**:
- `ref_all_tickers` - List all tickers
- `ref_ticker` - Single ticker details
- `exchanges` - Stock exchanges
- `prices_daily_grouped` - Daily prices for all tickers
- `news_by_date` - News articles by date range

**Example Endpoint**:
```json
"prices_daily_grouped": {
  "base": "core",
  "method": "GET",
  "path_template": "/v2/aggs/grouped/locale/us/market/stocks/{date}",
  "required_params": ["date"],
  "default_query": {
    "adjusted": "true"
  },
  "response_key": "results"
}
```

**Usage**:
```python
from datapipelines.providers.polygon import PolygonProvider

provider = PolygonProvider(config)
data = provider.get_daily_prices(date="2024-01-15")
```

**Rate Limits**:
- Free: 5 requests/minute
- Basic: 100 requests/minute
- Configured: 1.0 req/sec (conservative for free tier)

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

1. **Edit config file** (e.g., `configs/polygon_endpoints.json`):

```json
"endpoints": {
  "new_endpoint": {
    "base": "core",
    "method": "GET",
    "path_template": "/v3/new/resource/{id}",
    "required_params": ["id"],
    "default_query": {
      "limit": 100
    },
    "response_key": "data"
  }
}
```

2. **Update provider class**:

```python
class PolygonProvider:
    def get_new_resource(self, resource_id: str):
        return self.call_endpoint(
            'new_endpoint',
            path_params={'id': resource_id}
        )
```

3. **Test endpoint**:

```python
provider = PolygonProvider(config)
data = provider.get_new_resource('test123')
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
"rate_limit_per_sec": 0.5
```

**Aggressive** (maximize throughput):
```json
"rate_limit_per_sec": 5.0
```

**Based on API Plan**:
- Free tier: Use conservative values
- Paid tier: Match API plan limits

---

## Authentication Patterns

### Bearer Token (Polygon)

```json
"headers": {
  "Authorization": "Bearer ${API_KEY}"
}
```

### Header Token (Chicago)

```json
"headers": {
  "X-App-Token": "${API_KEY}"
}
```

### Query Parameter (BLS)

```json
"default_query": {
  "registrationkey": "${API_KEY}"
}
```

### Multiple Keys (Rotation)

```bash
# .env
POLYGON_API_KEYS=key1,key2,key3
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

### Cursor-Based (Polygon)

```json
"pagination_type": "cursor",
"response_key": "results",
"cursor_key": "next_url"
```

**Usage**:
```python
cursor = None
while True:
    data = provider.get(cursor=cursor)
    if not data['next_url']:
        break
    cursor = data['next_url']
```

---

### No Pagination (BLS)

```json
"pagination_type": "none"
```

BLS returns all data for requested time period in single response.

---

## Troubleshooting

### Config Not Found

**Symptom**: `KeyError: 'polygon'`

**Solution**:
- Check file exists: `configs/polygon_endpoints.json`
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
3. Check header format matches API docs

---

## Related Documentation

- [Environment Variables](environment-variables.md) - API key configuration
- [Providers](../04-data-pipelines/providers.md) - Provider implementations
- [Ingestors](../04-data-pipelines/ingestors.md) - Orchestration layer
- [ConfigLoader](config-loader.md) - Configuration system
