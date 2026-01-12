# Bureau of Labor Statistics Pipeline Summary

**Provider ID:** `bls`
**Status:** Active (needs rebuild)
**API Type:** REST (POST with JSON body)
**Base URL:** `https://api.bls.gov/publicAPI/v2`

---

## Overview

The Bureau of Labor Statistics (BLS) provides official U.S. government economic data including unemployment rates, employment statistics, consumer price index (CPI), producer price index (PPI), productivity metrics, and wage data.

## Rate Limits

| Tier | Daily Limit | Years per Query | Features |
|------|-------------|-----------------|----------|
| Unregistered | 25 queries | 10 years | Basic data |
| v1 Registered | 500 queries | 10 years | Basic data |
| v2 Registered | 500 queries | 20 years | Net/percent calculations, annual averages |

**Configured Rate:** 0.42 req/sec (conservative)

## Authentication

- **Method:** Registration key in POST body (`registrationkey` field)
- **Environment Variable:** `BLS_API_KEYS`
- **Registration:** https://data.bls.gov/registrationEngine/

---

## Endpoints

| Endpoint ID | Description | Bronze Table | Status |
|-------------|-------------|--------------|--------|
| `timeseries` | Time series data by series ID | `bls_timeseries` | Active |
| `series_info` | Series metadata | `bls_series_info` | Available |

### Key Series IDs

| Series ID | Description | Category |
|-----------|-------------|----------|
| `LNS14000000` | Unemployment Rate | Labor |
| `CES0000000001` | Total Nonfarm Employment | Employment |
| `CUUR0000SA0` | Consumer Price Index (CPI) | Prices |
| `WPUFD4` | Producer Price Index (PPI) | Prices |
| `PRS85006092` | Labor Productivity | Productivity |
| `CES0500000003` | Average Hourly Earnings | Wages |
| `JTS00000000JOL` | Job Openings (JOLTS) | Labor |
| `JTS00000000QUR` | Quits Rate (JOLTS) | Labor |

---

## Bronze Tables

| Table | Source | Partitions | Key Fields |
|-------|--------|------------|------------|
| `bls_timeseries` | timeseries | `series_id`, `year` | series_id, year, period, value, footnotes |
| `bls_series_info` | series_info | - | series_id, title, survey_name, frequency |

---

## Usage

### Pipeline Configuration
In `configs/pipelines/run_config.json`:
```json
{
  "providers": {
    "bls": {
      "enabled": true,
      "rate_limit_per_sec": 0.42
    }
  }
}
```

### Running Ingestion
```bash
# Ingest unemployment and CPI data
python -m scripts.ingest.run_bls_ingestion --series unemployment cpi --years 5

# Full macro indicator refresh
python -m scripts.ingest.run_bls_ingestion --all-series --years 10
```

### Code Example
```python
from datapipelines.providers.bls.bls_ingestor import BLSIngestor
from datapipelines.providers.bls.facets.unemployment_facet import UnemploymentFacet

ingestor = BLSIngestor(ctx.bls_cfg, ctx.storage_cfg, ctx.spark)
facet = UnemploymentFacet(ctx.spark, start_year="2020", end_year="2023")
batches = ingestor._fetch_calls(facet.calls())
df = facet.normalize(batches)
```

### API Request Example
```python
# BLS uses POST with JSON body
import requests

payload = {
    "seriesid": ["LNS14000000", "CUUR0000SA0"],
    "startyear": "2020",
    "endyear": "2024",
    "registrationkey": "YOUR_API_KEY"
}

response = requests.post(
    "https://api.bls.gov/publicAPI/v2/timeseries/data/",
    json=payload
)
```

---

## Known Issues & Quirks

1. **POST for Timeseries**: Main data endpoint requires POST with JSON body (not GET)
2. **Series ID Format**: IDs are cryptic strings - maintain a lookup table
3. **Monthly Release Schedule**: Most data released on specific days each month
4. **Seasonal Adjustment**: Many series have SA (seasonally adjusted) and NSA variants
5. **Revision Lag**: Initial releases are revised in subsequent months
6. **No Pagination**: Returns complete time series in single response

---

## Models Fed

- `macro` - Economic indicators and time series

---

## Recommended Cadence

| Data Type | Frequency | Notes |
|-----------|-----------|-------|
| Monthly indicators | Weekly | Data released monthly, check for revisions |
| Annual data | Monthly | Updated less frequently |

---

## Data Release Schedule

| Series | Release Day | Notes |
|--------|-------------|-------|
| Employment Situation | First Friday | Includes unemployment rate |
| CPI | Mid-month | ~2 weeks after reference month |
| PPI | Mid-month | ~2 weeks after reference month |
| JOLTS | ~40 days after | Job openings and turnover |
