# BLS Overview

**Bureau of Labor Statistics - Official U.S. economic indicators**

---

## Summary

| Property | Value |
|----------|-------|
| **Provider** | Bureau of Labor Statistics (BLS) |
| **Website** | https://www.bls.gov |
| **Data Types** | Employment, Inflation, Wages, Productivity |
| **Status** | Active |
| **Cost** | Free (government data) |

---

## Capabilities

### Data Available

| Category | Series ID | Description | Frequency |
|----------|-----------|-------------|-----------|
| **Unemployment** | LNS14000000 | National unemployment rate | Monthly |
| **Employment** | CES0000000001 | Total nonfarm employment | Monthly |
| **CPI** | CUUR0000SA0 | Consumer Price Index (all items) | Monthly |
| **PPI** | WPUFD4 | Producer Price Index | Monthly |
| **Wages** | CES0500000003 | Average hourly earnings | Monthly |
| **Productivity** | PRS85006092 | Labor productivity | Quarterly |
| **Job Openings** | JTS00000000JOL | JOLTS job openings | Monthly |
| **Quits** | JTS00000000QUR | JOLTS quit rate | Monthly |

### Key Features

- **Official Data**: U.S. government authoritative source
- **Historical Depth**: Decades of time series data
- **No Cost**: Free public domain data
- **Seasonal Adjustment**: Both adjusted and unadjusted series
- **Revision Tracking**: Data revised as better info available

---

## de_Funk Integration

### Bronze Tables Generated

| Table | Series | Partitions |
|-------|--------|------------|
| `bls_unemployment` | LNS14000000 | year |
| `bls_cpi` | CUUR0000SA0 | year |
| `bls_employment` | CES0000000001 | year |
| `bls_wages` | CES0500000003 | year |

### Facets Implemented

| Facet | Purpose | Output |
|-------|---------|--------|
| `UnemploymentFacet` | Monthly unemployment rates | bls_unemployment |
| `CPIFacet` | Consumer Price Index | bls_cpi |

### Pipeline Flow

```
BLS API
    ↓
BLSIngestor
    ↓
┌─────────────────────┬─────────────────────┐
│ UnemploymentFacet   │ CPIFacet            │
│ (LNS14000000)       │ (CUUR0000SA0)       │
└─────────┬───────────┴───────────┬─────────┘
          ↓                       ↓
    bls_unemployment           bls_cpi
        (Bronze)               (Bronze)
```

---

## Data Quality

### Strengths
- Official government source
- Long historical coverage
- Consistent methodology
- Well-documented revisions

### Limitations
- Monthly/quarterly frequency only
- Data released with lag
- Some series discontinued
- Seasonal adjustments may change

---

## In This Section

| Document | Purpose |
|----------|---------|
| [Terms of Use](terms-of-use.md) | Public domain, no alteration intent |
| [API Reference](api-reference.md) | Series IDs and endpoints |
| [Facets](facets.md) | Data transformations |
| [Bronze Tables](bronze-tables.md) | Output schemas |

---

## Quick Start

### Get API Key (Optional but Recommended)

1. Visit https://data.bls.gov/registrationEngine/
2. Register for free API key
3. Add to `.env`:

```bash
BLS_API_KEYS=your_key_here
```

### Run Ingestion

```bash
# Ingest economic indicators
python -m scripts.ingest.run_full_pipeline
```

---

## Series ID Reference

### Understanding Series IDs

BLS series IDs encode information about the data:

```
LNS14000000
│││││││││││
│││││││││└─ Seasonally adjusted (0=no, 1=yes)
││││││││└── [Reserved]
│││││││└─── [Reserved]
││││││└──── [Reserved]
│││││└───── Category code
││││└────── Age group
│││└─────── Sex
││└──────── Race
│└───────── Employment status
└────────── Survey (LN=Labor Force Statistics)
```

### Common Series

| Series ID | Description |
|-----------|-------------|
| `LNS14000000` | Unemployment rate, seasonally adjusted |
| `LNS14000001` | Unemployment rate, men 16+ |
| `LNS14000002` | Unemployment rate, women 16+ |
| `CUUR0000SA0` | CPI-U, all items, US city average |
| `CUUR0000SETA01` | CPI-U, new vehicles |
| `CES0000000001` | Total nonfarm employment |

---

## Related Documentation

- [Data Providers Overview](../README.md)
- [Macro Model](../../04-implemented-models/macro/)
- [Pipelines](../../06-pipelines/README.md)
