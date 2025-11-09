---
title: "BLS Integration"
tags: [economics/bls, component/data-pipeline, source/bls, concept/api]
aliases: ["BLS Integration", "BLS API", "Bureau of Labor Statistics"]
---

# BLS Integration

---

The Bureau of Labor Statistics (BLS) provides official economic statistics for the United States through a public API, serving as the data source for the Macro model.

**Provider:** U.S. Bureau of Labor Statistics
**Documentation:** https://www.bls.gov/developers/
**API Version:** v2
**Data Coverage:** National economic indicators, 1940s-present

---

## Purpose

---

BLS serves as the authoritative source for:
- Unemployment rates
- Consumer Price Index (inflation)
- Employment statistics
- Wage and earnings data
- Economic series metadata

---

## API Endpoints

---

### 1. Time Series Data

**Endpoint:** `POST /publicAPI/v2/timeseries/data/`

**Purpose:** Retrieve time series data for one or more series

**Request:**
```json
{
  "seriesid": ["LNS14000000", "CUUR0000SA0"],
  "startyear": "2020",
  "endyear": "2024",
  "registrationkey": "your_api_key_here"
}
```

**Response:**
```json
{
  "status": "REQUEST_SUCCEEDED",
  "responseTime": 89,
  "Results": {
    "series": [
      {
        "seriesID": "LNS14000000",
        "data": [
          {
            "year": "2024",
            "period": "M11",
            "periodName": "November",
            "value": "3.7",
            "footnotes": []
          }
        ]
      }
    ]
  }
}
```

**Bronze Tables:**
- `bronze.bls_unemployment` (LNS14000000)
- `bronze.bls_cpi` (CUUR0000SA0)
- `bronze.bls_employment` (CES0000000001)
- `bronze.bls_wages` (CES0500000003)

---

### 2. Series Catalog

**Endpoint:** `POST /publicAPI/v2/timeseries/data/`

**Purpose:** Get series metadata

**Request:**
```json
{
  "seriesid": ["LNS14000000"],
  "catalog": true,
  "registrationkey": "your_api_key_here"
}
```

**Response:**
```json
{
  "Results": {
    "series": [
      {
        "seriesID": "LNS14000000",
        "catalog": {
          "series_title": "Unemployment Rate - Civilian Labor Force",
          "series_id": "LNS14000000",
          "seasonally_adj": "Seasonally Adjusted",
          "survey_name": "Current Population Survey"
        }
      }
    ]
  }
}
```

---

## BLS Series Configuration

---

### Unemployment Series

**Series ID:** `LNS14000000`
**Name:** Unemployment Rate - Civilian Labor Force (Seasonally Adjusted)
**Survey:** Current Population Survey (CPS)
**Frequency:** Monthly
**Units:** Percent
**Start Date:** 1948-01-01

**Bronze Table:** `bronze.bls_unemployment`

---

### CPI Series

**Series ID:** `CUUR0000SA0`
**Name:** Consumer Price Index - All Urban Consumers, U.S. city average, All items
**Survey:** Consumer Price Index (CPI)
**Frequency:** Monthly
**Units:** Index (1982-84=100)
**Start Date:** 1947-01-01

**Bronze Table:** `bronze.bls_cpi`

---

### Employment Series

**Series ID:** `CES0000000001`
**Name:** Total Nonfarm Employment (Seasonally Adjusted)
**Survey:** Current Employment Statistics (CES)
**Frequency:** Monthly
**Units:** Thousands of jobs
**Start Date:** 1939-01-01

**Bronze Table:** `bronze.bls_employment`

---

### Wages Series

**Series ID:** `CES0500000003`
**Name:** Average Hourly Earnings - Total Private (Seasonally Adjusted)
**Survey:** Current Employment Statistics (CES)
**Frequency:** Monthly
**Units:** U.S. dollars
**Start Date:** 2006-01-01

**Bronze Table:** `bronze.bls_wages`

---

## Data Pipeline

---

### Bronze Layer (Raw Ingestion)

**Location:** `storage/bronze/bls/`

**Tables:**
- `bls_unemployment` - Raw unemployment data
- `bls_cpi` - Raw CPI data
- `bls_employment` - Raw employment data
- `bls_wages` - Raw wage data

**Format:** Parquet (partitioned by year)

**Update Frequency:**
- All series: Monthly (first Friday of month)
- Revisions: Continuous for recent 2-3 months

---

### Silver Layer (Dimensional Model)

**Location:** `storage/silver/macro/`

**Transformation:** Bronze → Silver via Macro model graph

**Process:**
1. Read from Bronze BLS tables
2. Apply economic facet normalization ([[Facets/Economics]])
3. Build dimensional schema ([[Economic Series Dimension]], fact tables)
4. Write to Silver storage

See [[Macro Model Overview]] for complete schema.

---

## Authentication

---

**API Key Required:** Optional (recommended for higher limits)

**Without API Key:**
- 25 queries per day
- 10 years per query
- 1 series per query

**With API Key (Free Registration):**
- 500 queries per day
- 20 years per query
- 50 series per query

**Configuration:**
```bash
# Environment variable
export BLS_API_KEY="your_api_key_here"

# Or in config file
# configs/providers/bls.yaml
api_key: ${BLS_API_KEY}
```

**Registration:** https://data.bls.gov/registrationEngine/

---

## Facet Normalization

---

### Economics Facet

**Purpose:** Normalize BLS API response to canonical schema

**Mapping:**
```yaml
from: bls.timeseries
to: bronze.bls_{series}
fields:
  seriesID → series_id
  year → year
  period → period (M01-M12)
  periodName → period_name
  value → value (cast to double)
  # Derive date from year + period
  {year, period} → date (first day of month)
```

**Period Code Conversion:**
```python
# BLS uses M01, M02, ..., M12
# Convert to date: year=2024, period=M11 → 2024-11-01
def period_to_date(year: int, period: str) -> date:
    month = int(period[1:])  # Extract month from "M11"
    return date(year, month, 1)
```

See [[Facets/Economics]] for detailed normalization logic.

---

## Provider Implementation

---

**Location:** `models/providers/bls_provider.py`

**Key Classes:**
- `BLSProvider` - Main API client
- `BLSIngestor` - Bronze layer ingestion
- `EconomicsFacet` - BLS data normalization

**Example:**
```python
from models.providers.bls_provider import BLSProvider

# Initialize provider
provider = BLSProvider(api_key=os.getenv('BLS_API_KEY'))

# Fetch unemployment data
unemployment = provider.get_series(
    series_id='LNS14000000',
    start_year=2020,
    end_year=2024
)

# Fetch multiple series
multi_series = provider.get_multiple_series(
    series_ids=['LNS14000000', 'CUUR0000SA0'],
    start_year=2020,
    end_year=2024
)
```

---

## Usage Examples

---

### Manual Ingestion

```python
from models.providers.bls_provider import BLSProvider
from models.ingestors.bronze_writer import BronzeWriter

# Initialize
provider = BLSProvider(api_key=os.getenv('BLS_API_KEY'))
writer = BronzeWriter(storage_root='storage/bronze/bls')

# Ingest unemployment data
series_config = {
    'unemployment': 'LNS14000000',
    'cpi': 'CUUR0000SA0',
    'employment': 'CES0000000001',
    'wages': 'CES0500000003'
}

for name, series_id in series_config.items():
    data = provider.get_series(
        series_id=series_id,
        start_year=2010,
        end_year=2024
    )

    writer.write_economic_data(data, series_name=name)

print("Ingestion complete!")
```

### Backfill Historical Data

```python
# Backfill all available history
for name, series_id in series_config.items():
    data = provider.get_series(
        series_id=series_id,
        start_year=1948,  # Earliest available for unemployment
        end_year=2024
    )

    writer.write_economic_data(data, series_name=name, mode='overwrite')
```

### Update Recent Data

```python
from datetime import datetime

# Update last 2 years (captures revisions)
current_year = datetime.now().year
start_year = current_year - 2

for name, series_id in series_config.items():
    data = provider.get_series(
        series_id=series_id,
        start_year=start_year,
        end_year=current_year
    )

    writer.write_economic_data(data, series_name=name, mode='append')
```

---

## Data Quality

---

### Coverage

- **Time Range:** 1940s to present (varies by series)
- **Frequency:** Monthly for all tracked series
- **Revisions:** Common for recent 2-3 months
- **Reliability:** Government official statistics

### Release Schedule

**First Friday of Each Month (~8:30 AM ET):**
- Employment Situation (unemployment + employment + wages)
- CPI typically mid-month (2nd or 3rd week)

### Known Issues

- **Revisions:** Data subject to revision for 2-3 months
- **Seasonal adjustment:** Can change with annual recalculations
- **Missing periods:** Some series have gaps (strikes, COVID)
- **API limits:** Rate limiting without registration

---

## Cost Considerations

---

**Free Tier (No Registration):**
- 25 API calls/day
- 10 years per query
- 1 series per query

**Free Tier (With Registration):**
- 500 API calls/day
- 20 years per query
- 50 series per query

**Recommendation:**
- Register for free API key
- Sufficient for daily updates (4 series)
- Batch historical backfills efficiently

---

## Related Documentation

---

### Model Documentation
- [[Macro Model Overview]] - Data consumer
- [[Unemployment Facts]] - Unemployment schema
- [[CPI Facts]] - CPI schema
- [[Employment Facts]] - Employment schema
- [[Wages Facts]] - Wages schema

### Architecture Documentation
- [[Data Pipeline/Overview]] - Ingestion architecture
- [[Providers]] - Provider framework
- [[Facets/Economics]] - Economic normalization
- [[Bronze Storage]] - Raw data storage

### External Resources
- [BLS Developers Home](https://www.bls.gov/developers/)
- [API Documentation](https://www.bls.gov/developers/api_signature_v2.htm)
- [Series ID Formats](https://www.bls.gov/help/hlpforma.htm)
- [Data Finder](https://www.bls.gov/data/)

---

**Tags:** #economics/bls #component/data-pipeline #source/bls #concept/api

**Last Updated:** 2024-11-08
**Provider:** Bureau of Labor Statistics
**API Version:** v2
