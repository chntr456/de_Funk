# Data Providers

**API integrations and data sources for de_Funk**

---

## Overview

de_Funk integrates with three external data providers to ingest financial and economic data:

| Provider | Data Type | Status | Terms |
|----------|-----------|--------|-------|
| [Alpha Vantage](alpha-vantage/) | Securities (stocks, options, ETFs) | Active | [No commercial use](alpha-vantage/terms-of-use.md) |
| [BLS](bls/) | Economic indicators | Active | [Public domain](bls/terms-of-use.md) |
| [Chicago](chicago/) | Municipal data | Active | [Open data](chicago/terms-of-use.md) |

---

## Provider Comparison

| Feature | Alpha Vantage | BLS | Chicago |
|---------|---------------|-----|---------|
| **Rate Limit (Free)** | 5 calls/min | 25 queries/day | 1000 requests/day |
| **Rate Limit (Premium)** | 75 calls/min | 500 queries/day | 5 requests/sec |
| **Auth Type** | API key (query param) | Registration key (optional) | App token (optional) |
| **Response Format** | JSON (nested) | JSON (nested) | JSON (array) |
| **Pagination** | None | None | Offset-based |
| **Commercial Use** | No (free tier) | Yes | Yes |

---

## In This Section

### Alpha Vantage
- [Overview](alpha-vantage/overview.md) - Provider capabilities
- [Terms of Use](alpha-vantage/terms-of-use.md) - Usage restrictions
- [API Reference](alpha-vantage/api-reference.md) - Endpoints and parameters
- [Rate Limits](alpha-vantage/rate-limits.md) - Throttling strategies
- [Facets](alpha-vantage/facets.md) - Data transformations
- [Bronze Tables](alpha-vantage/bronze-tables.md) - Output schemas

### BLS (Bureau of Labor Statistics)
- [Overview](bls/overview.md) - Provider capabilities
- [Terms of Use](bls/terms-of-use.md) - Government data terms
- [API Reference](bls/api-reference.md) - Series IDs and endpoints
- [Facets](bls/facets.md) - Data transformations
- [Bronze Tables](bls/bronze-tables.md) - Output schemas

### Chicago Data Portal
- [Overview](chicago/overview.md) - Provider capabilities
- [Terms of Use](chicago/terms-of-use.md) - Open data terms
- [API Reference](chicago/api-reference.md) - Socrata endpoints
- [Facets](chicago/facets.md) - Data transformations
- [Bronze Tables](chicago/bronze-tables.md) - Output schemas

### Development
- [Adding Providers](adding-providers.md) - How to add new data sources

---

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Alpha Vantage  │     │      BLS        │     │    Chicago      │
│    (REST API)   │     │   (REST API)    │     │  (Socrata API)  │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                        PROVIDER LAYER                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │  Registry   │  │ HTTP Client │  │      Rate Limiter       │  │
│  │ (endpoints) │  │ (requests)  │  │ (token bucket/backoff)  │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                         FACET LAYER                              │
│  ┌─────────────────┐  ┌───────────────┐  ┌───────────────────┐  │
│  │SecuritiesRef    │  │Unemployment   │  │UnemploymentRates  │  │
│  │SecuritiesPrices │  │CPI            │  │BuildingPermits    │  │
│  └─────────────────┘  └───────────────┘  └───────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                       BRONZE LAYER                               │
│  securities_reference    bls_unemployment    chicago_unemployment│
│  securities_prices_daily bls_cpi             chicago_permits     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Provider Interface Pattern

All providers follow a consistent pattern:

```python
# 1. Registry loads endpoint configuration
registry = AlphaVantageRegistry(config_path)

# 2. Facet generates API calls
facet = SecuritiesPricesFacetAV(spark, tickers=['AAPL'])
calls = list(facet.calls())

# 3. Ingestor executes calls with rate limiting
ingestor = AlphaVantageIngestor(config, storage, spark)
raw_data = ingestor._fetch_calls(calls)

# 4. Facet normalizes to DataFrame
df = facet.normalize(raw_data)

# 5. Write to Bronze (partitions from storage.json - single source of truth)
sink.smart_write(df, 'securities_prices_daily')  # Reads partitions from configs/storage.json
```

---

## Configuration Files

| Provider | Config File | Location |
|----------|-------------|----------|
| Alpha Vantage | `alpha_vantage_endpoints.json` | `configs/` |
| BLS | `bls_endpoints.json` | `configs/` |
| Chicago | `chicago_endpoints.json` | `configs/` |

---

## API Keys

Set in `.env` file:

```bash
# Alpha Vantage (required for securities data)
ALPHA_VANTAGE_API_KEYS=your_key_here

# BLS (optional - increases rate limits)
BLS_API_KEYS=your_key_here

# Chicago (optional - increases rate limits)
CHICAGO_API_KEYS=your_app_token_here
```

---

## Related Documentation

- [Pipelines](../06-pipelines/README.md) - ETL orchestration
- [Bronze Layer](../06-pipelines/bronze-layer.md) - Raw data storage
- [Configuration](../11-configuration/README.md) - Config system
