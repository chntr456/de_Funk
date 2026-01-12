# Chicago Data Portal Pipeline Summary

**Provider ID:** `chicago`
**Status:** Active
**API Type:** Socrata Open Data API (SODA)
**Base URL:** `https://data.cityofchicago.org`

---

## Overview

City of Chicago open data portal powered by Socrata. Provides access to municipal datasets including crime statistics, building permits, business licenses, city finances, transportation data, and geospatial boundaries. Data updated at varying cadences from daily to annually.

## Rate Limits

| Tier | Requests | Notes |
|------|----------|-------|
| No token | 1/sec | Heavily throttled, not recommended |
| App token | ~5/sec | Standard for bulk downloads |

**Configured Rate:** 5.0 req/sec (with app token)

## Authentication

- **Method:** `X-App-Token` header
- **Environment Variable:** `CHICAGO_API_KEYS`
- **Registration:** https://data.cityofchicago.org (create account for app token)
- **Note:** API works without token but at reduced rate (1 req/sec)

---

## Active Endpoints (Dev Profile)

| Endpoint ID | Dataset ID | Domain | Bronze Table | Records (approx) |
|-------------|------------|--------|--------------|------------------|
| `crimes` | `ijzp-q8t2` | Public Safety | `chicago_crimes` | 8M+ |
| `building_permits` | `ydr8-5enu` | Housing | `chicago_building_permits` | 700K+ |
| `business_licenses` | `r5kz-chrr` | Regulatory | `chicago_business_licenses` | 1M+ |
| `food_inspections` | `4ijn-s7e5` | Regulatory | `chicago_food_inspections` | 250K+ |
| `cta_l_ridership_daily` | `t2rn-p8d7` | Transportation | `chicago_cta_l_ridership` | 1.2M+ |
| `cta_bus_ridership_daily` | `jyb9-n7fm` | Transportation | `chicago_cta_bus_ridership` | 1.5M+ |

## All Available Endpoints

### Public Safety
| Endpoint ID | Dataset ID | Description | Status |
|-------------|------------|-------------|--------|
| `crimes` | `ijzp-q8t2` | Crime incidents 2001-present | Active |
| `arrests` | `dpt3-jri9` | Arrests 2014-present | Available |
| `police_beats` | `aerh-rz74` | Police beat boundaries | Available |
| `police_stations` | `z8bn-74gv` | Police station locations | Available |
| `iucr_codes` | `c7ck-438e` | Crime classification codes | Available |

### Finance
| Endpoint ID | Dataset ID | Description | Status |
|-------------|------------|-------------|--------|
| `budget_appropriations` | `[varies by year]` | Annual budget data | Available* |
| `contracts` | `rsxa-ify5` | City contracts | Available |
| `payments` | `s4vu-giwb` | Vendor payments | Available |
| `positions_salaries` | `xzkq-xp2w` | Budget positions | Available |
| `budget_revenue` | `[varies by year]` | Revenue projections | Available* |

*Note: Budget endpoints require iterating through yearly view IDs

### Transportation
| Endpoint ID | Dataset ID | Description | Status |
|-------------|------------|-------------|--------|
| `cta_l_ridership_daily` | `t2rn-p8d7` | Daily L station entries | Active |
| `cta_bus_ridership_daily` | `jyb9-n7fm` | Daily bus route ridership | Active |
| `cta_l_stops` | `8pix-ypme` | L station locations | Available |
| `cta_bus_stops` | `hvnx-qtky` | Bus stop locations | Available |
| `traffic_congestion` | `t2qc-9pjd` | Traffic congestion estimates | Available |

### Regulatory
| Endpoint ID | Dataset ID | Description | Status |
|-------------|------------|-------------|--------|
| `food_inspections` | `4ijn-s7e5` | Restaurant inspections | Active |
| `business_licenses` | `r5kz-chrr` | Business licenses | Active |
| `building_violations` | `22u3-xenr` | Building code violations | Available |
| `ordinance_violations` | `awqx-tuwv` | Ordinance violations | Available |

### Housing
| Endpoint ID | Dataset ID | Description | Status |
|-------------|------------|-------------|--------|
| `building_permits` | `ydr8-5enu` | Building permits | Active |
| `zoning_districts` | `fk7b-2fkv` | Zoning boundaries | Available |

### Economic
| Endpoint ID | Dataset ID | Description | Status |
|-------------|------------|-------------|--------|
| `economic_indicators` | `kn9c-c2s2` | Economic health indicators | Available |
| `unemployment` | `iqnk-2tcu` | Unemployment by community area | Available |
| `per_capita_income` | `kn9c-c2s2` | Per capita income data | Available |

### Operational
| Endpoint ID | Dataset ID | Description | Status |
|-------------|------------|-------------|--------|
| `311_requests` | `v6vf-nfxy` | 311 service requests | Available |

### Geospatial
| Endpoint ID | Dataset ID | Description | Status |
|-------------|------------|-------------|--------|
| `boundaries_wards` | `sp34-6z76` | Ward boundaries | Available |
| `boundaries_community` | `cauq-8yn6` | Community area boundaries | Available |

---

## Bronze Tables

| Table | Source Endpoint | Partitions | Key Fields |
|-------|-----------------|------------|------------|
| `chicago_crimes` | crimes | `year` | id, case_number, date, primary_type, arrest |
| `chicago_building_permits` | building_permits | `year` | permit_number, issue_date, work_type |
| `chicago_business_licenses` | business_licenses | `year` | license_id, account_number, business_activity |
| `chicago_food_inspections` | food_inspections | `year` | inspection_id, dba_name, results, violations |
| `chicago_cta_l_ridership` | cta_l_ridership_daily | `year` | station_id, date, rides |
| `chicago_cta_bus_ridership` | cta_bus_ridership_daily | `year` | route, date, rides |

---

## Usage

### Pipeline Configuration
In `configs/pipelines/run_config.json`:
```json
{
  "providers": {
    "chicago": {
      "enabled": true,
      "rate_limit_per_sec": 5.0,
      "endpoints": [
        "crimes",
        "building_permits",
        "business_licenses",
        "food_inspections",
        "cta_l_ridership_daily",
        "cta_bus_ridership_daily"
      ]
    }
  }
}
```

### Running Ingestion
```bash
# Via test pipeline (with dev profile)
./scripts/test/test_pipeline.sh --profile dev

# Direct ingestion (single endpoint)
python -m scripts.ingest.run_bronze_ingestion \
  --provider chicago \
  --endpoints crimes \
  --max-records 100000

# All active endpoints
python -m scripts.ingest.run_bronze_ingestion \
  --provider chicago \
  --max-records 50000
```

### Code Example
```python
from datapipelines.providers.chicago import create_chicago_provider
from pathlib import Path

# Create provider
provider = create_chicago_provider(
    api_cfg, storage_cfg, spark,
    docs_path=Path("Documents")
)

# Ingest single endpoint
result = provider.ingest_endpoint("crimes", max_records=10000)
print(f"Ingested {result.record_count} records")

# Ingest all active endpoints
results = provider.ingest_all(max_records_per_endpoint=50000)
for eid, result in results.items():
    print(f"{eid}: {'OK' if result.success else 'FAIL'} - {result.record_count} records")
```

### Query with SoQL Filters
```python
# Filter by date
result = provider.fetch_dataset(
    "crimes",
    query_params={
        "$where": "date > '2024-01-01'",
        "$order": "date DESC"
    },
    max_records=5000
)

# Filter by type
result = provider.fetch_dataset(
    "crimes",
    query_params={
        "$where": "primary_type = 'THEFT'"
    }
)
```

---

## Known Issues & Quirks

1. **Default 1000 Row Limit**: Always specify `$limit` for bulk downloads
2. **Type Conversion**: All values returned as strings - provider casts to schema types
3. **Date Formats**: ISO 8601 format (`YYYY-MM-DDTHH:MM:SS`)
4. **Null Handling**: Null fields omitted from JSON (not explicit null)
5. **Floating Point Timestamps**: Some date fields return as floating point epoch
6. **Schema Changes**: Field names occasionally change - verify with `$describe`
7. **Block-Level Location**: Crime data shows block-level only (privacy)

---

## Models Fed

- `city_finance` - Municipal finance analysis

---

## Recommended Cadence

| Data Type | Frequency | Notes |
|-----------|-----------|-------|
| Crimes | Daily | Updated daily (minus 7-day lag) |
| Building Permits | Daily | Real-time updates |
| Business Licenses | Weekly | Less frequent changes |
| Food Inspections | Daily | Updated as inspections occur |
| CTA Ridership | Daily | Previous day's data |

---

## Pagination

The Socrata API uses offset-based pagination:

```
?$limit=50000&$offset=0      # First 50,000 records
?$limit=50000&$offset=50000  # Next 50,000 records
...
```

Maximum `$limit` per request: **50,000 records**

The provider automatically handles pagination for bulk downloads.
