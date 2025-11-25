# Providers

**API client implementations for data sources**

Files: `datapipelines/providers/`
Related: [Pipeline Architecture](pipeline-architecture.md)

---

## Overview

**Providers** are API-specific clients that handle HTTP requests, authentication, rate limiting, and error handling for external data sources.

**Design Pattern**: One provider per data source API

---

## Implemented Providers

### Alpha Vantage Provider

**File**: `datapipelines/providers/alpha_vantage/`

**API**: Alpha Vantage (Stock market data)

**Features**:
- Multi-key rotation for rate limit management
- Retry logic with exponential backoff
- Endpoint configuration from `alpha_vantage_endpoints.json`

**Endpoints**:
- Daily prices (OHLCV)
- Ticker reference data with CIK
- Company overview/fundamentals
- Technical indicators

**Example**:
```python
from datapipelines.providers.alpha_vantage.client import AlphaVantageClient

client = AlphaVantageClient(api_keys=['key1', 'key2', 'key3'])

# Fetch daily prices
prices = client.get_daily_prices(
    ticker='AAPL',
    from_date='2024-01-01',
    to_date='2024-12-31'
)
```

---

### BLS Provider

**File**: `datapipelines/providers/bls/`

**API**: Bureau of Labor Statistics

**Features**:
- Series ID-based requests
- Annual vs monthly data handling
- Configurable time ranges

**Endpoints**:
- Unemployment rates
- Consumer Price Index (CPI)
- Producer Price Index (PPI)

---

### Chicago Provider

**File**: `datapipelines/providers/chicago/`

**API**: Chicago Data Portal (Socrata)

**Features**:
- SoQL query support
- Pagination handling
- Resource-based endpoints

**Endpoints**:
- Local unemployment
- Building permits
- Business licenses

---

## Provider Interface

All providers implement:

```python
class BaseProvider:
    def __init__(self, api_keys):
        self.api_keys = api_keys
        self.client = HttpClient(api_keys)

    def fetch(self, endpoint, params):
        """Fetch data from endpoint with params."""
        response = self.client.get(endpoint, params=params)
        return response.json()

    def fetch_batch(self, call_specs):
        """Fetch multiple calls efficiently."""
        return [self.fetch(spec['endpoint'], spec['params'])
                for spec in call_specs]
```

---

## HTTP Client

**File**: `datapipelines/base/http_client.py`

**Features**:
- API key rotation
- Rate limiting
- Retry logic
- Request logging

**Example**:
```python
from datapipelines.base.http_client import HttpClient

client = HttpClient(
    api_keys=['key1', 'key2'],
    rate_limit={'calls': 5, 'period': 60}  # 5 calls per 60 seconds
)

response = client.get('https://api.example.com/data', params={'ticker': 'AAPL'})
```

---

## API Key Management

**File**: `datapipelines/base/key_pool.py`

**Strategy**: Round-robin key rotation to distribute load

```python
class KeyPool:
    def __init__(self, keys):
        self.keys = keys
        self.current_index = 0

    def get_next_key(self):
        key = self.keys[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.keys)
        return key
```

**Usage**:
```bash
# .env file
ALPHA_VANTAGE_API_KEYS=key1,key2,key3
```

---

## Rate Limiting

**Configuration**: `configs/*_endpoints.json`

```json
{
  "base_url": "https://www.alphavantage.co",
  "rate_limit": {
    "calls": 5,
    "period": 60
  }
}
```

**Implementation**: Token bucket algorithm with sleep delays

---

## Error Handling

**Transient Errors** (retry):
- 429 Too Many Requests
- 500 Internal Server Error
- Network timeouts

**Permanent Errors** (fail):
- 401 Unauthorized (bad API key)
- 404 Not Found
- 400 Bad Request

**Retry Strategy**:
```python
max_retries = 3
backoff_factor = 2  # 2^n seconds

for attempt in range(max_retries):
    try:
        return self.fetch(endpoint, params)
    except TransientError:
        if attempt < max_retries - 1:
            time.sleep(backoff_factor ** attempt)
        else:
            raise
```

---

## Adding New Providers

To add a new data source:

1. **Create provider directory**: `datapipelines/providers/new_provider/`
2. **Implement client**: `client.py` with API-specific logic
3. **Create endpoint config**: `configs/new_provider_endpoints.json`
4. **Add API keys**: `.env` file
5. **Create facets**: `datapipelines/facets/new_provider/`
6. **Create ingestor**: `datapipelines/ingestors/new_provider_ingestor.py`

**Example Structure**:
```
datapipelines/providers/new_provider/
├── __init__.py
├── client.py           # NewProviderClient
└── facets/
    ├── data_facet.py
    └── reference_facet.py
```

---

## Related Documentation

- [Ingestors](ingestors.md) - Orchestration layer
- [Facet System](facet-system.md) - Data normalization
- [Pipeline Architecture](pipeline-architecture.md) - Overall design
- [Configuration](../11-configuration/api-configs.md) - API key setup
