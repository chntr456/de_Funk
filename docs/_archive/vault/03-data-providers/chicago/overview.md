# Chicago Data Portal Overview

**Municipal open data for the City of Chicago**

---

## Summary

| Property | Value |
|----------|-------|
| **Provider** | City of Chicago |
| **Website** | https://data.cityofchicago.org |
| **Platform** | Socrata Open Data API |
| **Data Types** | Permits, Licenses, Economic, Demographics |
| **Status** | Active |
| **Cost** | Free (open data) |

---

## Capabilities

### Data Available

| Dataset | Dataset ID | Description | Update Frequency |
|---------|------------|-------------|------------------|
| **Unemployment Rates** | ane4-dwhs | Unemployment by community area | Monthly |
| **Building Permits** | ydr8-5enu | Building permits issued | Daily |
| **Business Licenses** | r5kz-chrr | Active business licenses | Daily |
| **Per Capita Income** | qpxx-qyaw | Income by community area | Annual |
| **Economic Indicators** | nej5-8p3s | City economic metrics | Monthly |
| **Affordable Housing** | s6ha-ppgi | Affordable rental developments | Quarterly |

### Key Features

- **Socrata API**: Standard REST API with SoQL queries
- **Real-time Updates**: Many datasets updated daily
- **Geographic Data**: Latitude/longitude for permits
- **Community Areas**: 77 Chicago neighborhoods
- **Historical Data**: Years of historical records

---

## de_Funk Integration

### Bronze Tables Generated

| Table | Dataset | Partitions |
|-------|---------|------------|
| `chicago_unemployment` | ane4-dwhs | date |
| `chicago_building_permits` | ydr8-5enu | issue_date |
| `chicago_business_licenses` | r5kz-chrr | start_date |
| `chicago_economic_indicators` | nej5-8p3s | date |

### Facets Implemented

| Facet | Purpose | Output |
|-------|---------|--------|
| `UnemploymentRatesFacet` | Local unemployment | chicago_unemployment |
| `BuildingPermitsFacet` | Permit records | chicago_building_permits |

### Pipeline Flow

```
Chicago Data Portal (Socrata API)
    ↓
ChicagoIngestor
    ↓
┌─────────────────────────┬─────────────────────────┐
│ UnemploymentRatesFacet  │ BuildingPermitsFacet    │
│ (ane4-dwhs)             │ (ydr8-5enu)             │
└───────────┬─────────────┴───────────┬─────────────┘
            ↓                         ↓
    chicago_unemployment      chicago_building_permits
          (Bronze)                  (Bronze)
```

---

## Data Quality

### Strengths
- Official city data
- Regular updates
- Good historical coverage
- Geographic coordinates

### Limitations
- Chicago-specific only
- Some data user-reported
- Quality varies by dataset
- May have reporting delays

---

## In This Section

| Document | Purpose |
|----------|---------|
| [Terms of Use](terms-of-use.md) | Open data terms, no alteration |
| [API Reference](api-reference.md) | Socrata endpoints |
| [Facets](facets.md) | Data transformations |
| [Bronze Tables](bronze-tables.md) | Output schemas |

---

## Quick Start

### Get App Token (Optional but Recommended)

1. Create account at https://data.cityofchicago.org
2. Go to profile → App Tokens
3. Create new token
4. Add to `.env`:

```bash
CHICAGO_API_KEYS=your_app_token_here
```

### Run Ingestion

```bash
# Ingest Chicago municipal data
python -m scripts.ingest.run_full_pipeline
```

---

## Community Areas

Chicago is divided into 77 community areas for statistical purposes:

| Area # | Name | Example Data |
|--------|------|--------------|
| 1 | Rogers Park | Unemployment, permits |
| 8 | Near North Side | High permit volume |
| 32 | Loop | Business licenses |
| 44 | Chatham | Residential permits |
| 76 | O'Hare | Commercial activity |

---

## Related Documentation

- [Data Providers Overview](../README.md)
- [City Finance Model](../../04-implemented-models/city-finance/)
- [Pipelines](../../06-pipelines/README.md)
