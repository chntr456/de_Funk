---
type: api-provider
provider_id: chicago
provider: Chicago Data Portal

# API Configuration
api_type: soda
base_url: https://data.cityofchicago.org
homepage: https://data.cityofchicago.org

# Authentication
auth_model: api-key
env_api_key: CHICAGO_API_KEYS

# Rate Limiting
rate_limit_per_sec: 5.0
rate_limit_comment: "SODA API generally allows 5 req/sec with app token. Without token: 1 req/sec throttled."

# Default Headers (API key passed as X-App-Token header)
default_headers:
  X-App-Token: "${API_KEY}"

# Provider-specific settings
provider_settings:
  default_limit: 50000
  max_limit: 1000000
  default_limit_comment: "SODA default is 1000 rows. Set $limit for bulk downloads."

# Models Fed (Silver layer)
models:
  - city_finance

# Metadata
category: public
legal_entity_type: municipal
data_domains: [finance, public-safety, transportation, housing, regulatory]
data_tags: [public, time-series, reference, municipal, geospatial]
status: active
bulk_download: true
last_verified:
last_reviewed:
notes: "City of Chicago open data - Socrata platform (SODA API)"
---

## Description

City of Chicago open data portal powered by Socrata. Provides access to municipal datasets including crime statistics, building permits, business licenses, city finances, transportation data, and geospatial boundaries. Data updated at varying cadences from daily to annually depending on dataset.

## API Notes

- **Socrata Open Data API (SODA)**: RESTful API with SoQL query language
- **Base URL Structure**: `https://data.cityofchicago.org/resource/{dataset-id}.json`
- **Alternative endpoint**: `/api/v3/views/{dataset-id}/query.json` (newer v3 API)
- **Authentication**: App token passed via `X-App-Token` header or `$$app_token` query param
- **Response Format**: JSON (default), CSV, GeoJSON available

### Query Parameters (SoQL)

| Parameter | Description | Example |
|-----------|-------------|---------|
| `$select` | Fields to return | `$select=case_number,date,primary_type` |
| `$where` | Filter conditions | `$where=date > '2024-01-01'` |
| `$order` | Sort order | `$order=date DESC` |
| `$limit` | Max rows | `$limit=50000` |
| `$offset` | Pagination offset | `$offset=50000` |
| `$q` | Full-text search | `$q=theft` |

### Rate Limits

| Tier | Requests | Notes |
|------|----------|-------|
| No token | 1/sec, throttled | Not recommended |
| App token | ~5/sec | Standard for bulk downloads |

## Homelab Usage Notes

```bash
# Ingest Chicago endpoints
python -m scripts.ingest.run_bronze_ingestion --provider chicago --endpoints crimes

# Bulk download with pagination
# Use $limit=50000 and $offset for large datasets
```

- **Bulk Strategy**: Use pagination with `$limit` and `$offset` for datasets >50K rows
- **Incremental**: Filter by date column for incremental loads
- **Geospatial**: Some datasets include lat/lon or GeoJSON; can request `.geojson` format

## Known Quirks

1. **Default 1000 row limit**: Always specify `$limit` for bulk downloads
2. **Date formats**: ISO 8601 format (`YYYY-MM-DDTHH:MM:SS`)
3. **Null handling**: Null fields omitted from JSON response (not explicit null)
4. **Floating point timestamps**: Some date fields return as floating point epoch
5. **Throttling**: Without app token, requests are heavily throttled
6. **Schema changes**: Field names occasionally change; check `$describe` endpoint