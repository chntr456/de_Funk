# Cook County Data Portal Pipeline Summary

**Provider ID:** `cook_county`
**Status:** Active
**API Type:** Socrata Open Data API (SODA)
**Base URL:** `https://datacatalog.cookcountyil.gov`

---

## Overview

Cook County Assessor's Office open data portal powered by Socrata. Provides access to property assessment data, parcel characteristics, sales history, appeals, permits, and geospatial boundaries. Primary source for Cook County (Illinois) property tax and assessment data covering ~1.8 million parcels.

## Rate Limits

| Tier | Requests | Notes |
|------|----------|-------|
| No token | 1/sec | Heavily throttled, not recommended |
| App token | ~5/sec | Standard for bulk downloads |

**Configured Rate:** 5.0 req/sec (with app token)

## Authentication

- **Method:** `X-App-Token` header
- **Environment Variable:** `COOK_COUNTY_API_KEYS`
- **Registration:** https://datacatalog.cookcountyil.gov (create account for app token)
- **Note:** API works without token but at reduced rate (1 req/sec)

---

## Active Endpoints (Dev Profile)

| Endpoint ID | Dataset ID | Domain | Bronze Table | Records (approx) |
|-------------|------------|--------|--------------|------------------|
| `parcel_sales` | `wvhk-k5uv` | Finance | `cook_county_parcel_sales` | 2.5M+ |
| `assessed_values` | `uzyt-m557` | Finance | `cook_county_assessed_values` | 20M+ |
| `parcel_universe` | `tx2p-k2g9` | Geospatial | `cook_county_parcel_universe` | 1.8M+ |
| `residential_characteristics` | `bcnq-qi2z` | Housing | `cook_county_residential_chars` | 1.5M+ |

## All Available Endpoints

### Finance
| Endpoint ID | Dataset ID | Description | Status |
|-------------|------------|-------------|--------|
| `parcel_sales` | `wvhk-k5uv` | Property sales 1999-present | Active |
| `assessed_values` | `uzyt-m557` | Annual assessed values | Active |
| `tax_exempt_parcels` | `4i5r-5quw` | Tax-exempt properties | Available |

### Housing
| Endpoint ID | Dataset ID | Description | Status |
|-------------|------------|-------------|--------|
| `residential_characteristics` | `bcnq-qi2z` | Single/multi-family characteristics | Active |
| `condo_characteristics` | `8c7e-zxxx` | Condominium unit details | Available |
| `commercial_valuation` | `4i5r-5quw` | Commercial property data | Available |

### Geospatial
| Endpoint ID | Dataset ID | Description | Status |
|-------------|------------|-------------|--------|
| `parcel_universe` | `tx2p-k2g9` | All parcels with base info | Active |
| `neighborhood_boundaries` | `pcdw-pxtg` | Assessor neighborhood boundaries | Available |
| `parcel_addresses` | `3723-97qp` | Parcel address lookups | Available |
| `parcel_proximity` | `xxx-xxxx` | Proximity to amenities | Available |

### Regulatory
| Endpoint ID | Dataset ID | Description | Status |
|-------------|------------|-------------|--------|
| `appeals` | `y7vc-dvez` | Assessment appeals filed | Available |
| `bor_appeal_decisions` | `7pny-nedm` | Board of Review decisions | Available |
| `permits` | `xxxx-xxxx` | Building permits | Available |

---

## Bronze Tables

| Table | Source Endpoint | Partitions | Key Fields |
|-------|-----------------|------------|------------|
| `cook_county_parcel_sales` | parcel_sales | `year` | pin, sale_date, sale_price, deed_type |
| `cook_county_assessed_values` | assessed_values | `year` | pin, year, mailed_bldg, mailed_land, mailed_tot |
| `cook_county_parcel_universe` | parcel_universe | - | pin, class, township_code, nbhd_code |
| `cook_county_residential_chars` | residential_characteristics | `year` | pin, year, bldg_sf, land_sf, age, rooms |

---

## Usage

### Pipeline Configuration
In `configs/pipelines/run_config.json`:
```json
{
  "providers": {
    "cook_county": {
      "enabled": true,
      "rate_limit_per_sec": 5.0,
      "endpoints": [
        "parcel_sales",
        "assessed_values",
        "parcel_universe",
        "residential_characteristics"
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
  --provider cook_county \
  --endpoints parcel_sales \
  --max-records 100000

# All active endpoints
python -m scripts.ingest.run_bronze_ingestion \
  --provider cook_county \
  --max-records 50000
```

### Code Example
```python
from datapipelines.providers.cook_county import create_cook_county_provider
from pathlib import Path

# Create provider
provider = create_cook_county_provider(
    api_cfg, storage_cfg, spark,
    docs_path=Path("Documents")
)

# Ingest single endpoint
result = provider.ingest_endpoint("parcel_sales", max_records=50000)
print(f"Ingested {result.record_count} records")

# Ingest all active endpoints
results = provider.ingest_all(max_records_per_endpoint=50000)
for eid, result in results.items():
    print(f"{eid}: {'OK' if result.success else 'FAIL'} - {result.record_count} records")
```

### Query with SoQL Filters
```python
# Filter by year
result = provider.fetch_dataset(
    "parcel_sales",
    query_params={
        "$where": "year >= 2020",
        "$order": "sale_date DESC"
    },
    max_records=10000
)

# Filter by township
result = provider.fetch_dataset(
    "assessed_values",
    query_params={
        "$where": "township_code = '70'"  # Chicago
    }
)
```

### Query by PIN
```python
# Fetch data for specific parcels
result = provider.fetch_parcel_data(
    pins=["12345678901234", "12345678901235"],
    year=2023
)
```

---

## PIN (Parcel Index Number) Format

Cook County uses a 14-digit PIN to uniquely identify each parcel:

```
XX-XX-XXX-XXX-XXXX
 |  |   |   |   |
 |  |   |   |   +-- Parcel suffix
 |  |   |   +------ Block number
 |  |   +---------- Section number
 |  +-------------- Township
 +----------------- Volume
```

**Important:** Always zero-pad PINs to 14 digits. Downloads may strip leading zeros.

```python
# Correct PIN handling
pin = "12345678901234"  # Always 14 digits
pin_formatted = pin.zfill(14)  # Ensure zero-padding
```

---

## Known Issues & Quirks

1. **PIN Zero-Padding**: PINs must be zero-padded to 14 digits; downloads may strip leading zeros
2. **Default 1000 Row Limit**: Always specify `$limit` for bulk downloads
3. **Type Conversion**: All values returned as strings - provider casts to schema types
4. **Float-as-String for Integers**: Year values may come as "2025.0" - requires double→int cast
5. **Monthly Updates**: Most datasets updated monthly with lag
6. **Year-Based Partitioning**: Many datasets partitioned by assessment year
7. **Class Code Changes**: Property class codes can change across time
8. **Incomplete Current Year**: Current year data incomplete until assessment roll certified

---

## Property Classes

Common property class codes:

| Class | Description |
|-------|-------------|
| 2-XX | Residential (single-family, multi-family) |
| 3-XX | Multi-family (7+ units) |
| 5-XX | Commercial |
| 6-XX | Industrial |
| 7-XX | Vacant land |
| 8-XX | Tax-exempt |

Full class code reference: [Cook County Class Codes PDF](https://prodassets.cookcountyassessor.com/s3fs-public/form_documents/classcode.pdf)

---

## Models Fed

- (No Silver models currently - property data available in Bronze)

---

## Recommended Cadence

| Data Type | Frequency | Notes |
|-----------|-----------|-------|
| Parcel Sales | Monthly | Sales reported on lag |
| Assessed Values | Quarterly | Major updates during triennial reassessment |
| Characteristics | Quarterly | Updated as parcels resurveyed |
| Appeals | Monthly | Updated as appeals filed/decided |

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

---

## Geographic Coverage

Cook County, Illinois includes:
- **City of Chicago** (major portion)
- **130+ suburban municipalities**
- **~1.8 million parcels**
- **5.2 million residents** (2nd most populous US county)
