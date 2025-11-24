# BLS API Reference

**Endpoint documentation and series IDs**

---

## Base Configuration

```json
{
  "base_urls": {
    "core": "https://api.bls.gov/publicAPI/v2"
  },
  "auth": {
    "type": "json_body",
    "param_name": "registrationkey"
  }
}
```

---

## API Versions

| Version | URL | Features |
|---------|-----|----------|
| v1 | `/publicAPI/v1/` | Basic queries, no registration |
| v2 | `/publicAPI/v2/` | More features, registration optional |

**de_Funk uses v2** for additional features like calculations.

---

## Endpoints

### 1. Time Series Data (timeseries/data)

**Purpose**: Retrieve time series data for one or more series

**Endpoint**: `POST /publicAPI/v2/timeseries/data/`

**Request Body**:

```json
{
  "seriesid": ["LNS14000000", "CUUR0000SA0"],
  "startyear": "2014",
  "endyear": "2024",
  "registrationkey": "your_key_here",
  "calculations": true,
  "annualaverage": true
}
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| `seriesid` | Yes | Array of series IDs (max 50) |
| `startyear` | Yes | Start year (YYYY) |
| `endyear` | Yes | End year (YYYY) |
| `registrationkey` | No | API key (increases limits) |
| `calculations` | No | Include net/percent changes |
| `annualaverage` | No | Include annual averages |
| `aspects` | No | Include footnotes |

**Response**:

```json
{
  "status": "REQUEST_SUCCEEDED",
  "responseTime": 150,
  "message": [],
  "Results": {
    "series": [
      {
        "seriesID": "LNS14000000",
        "data": [
          {
            "year": "2024",
            "period": "M01",
            "periodName": "January",
            "value": "3.7",
            "footnotes": [{}]
          }
        ]
      }
    ]
  }
}
```

---

### 2. Series Information (timeseries/info)

**Purpose**: Get metadata about a series

**Endpoint**: `GET /publicAPI/v2/timeseries/info?seriesid=LNS14000000`

**Response**:

```json
{
  "status": "REQUEST_SUCCEEDED",
  "Results": {
    "series": {
      "seriesID": "LNS14000000",
      "catalog": {
        "survey_name": "Labor Force Statistics from the Current Population Survey",
        "survey_abbreviation": "LN",
        "seasonality": "Seasonally Adjusted"
      }
    }
  }
}
```

---

## Period Codes

BLS uses period codes for time granularity:

| Code | Meaning | Example |
|------|---------|---------|
| `M01`-`M12` | Monthly | M01 = January |
| `Q01`-`Q04` | Quarterly | Q01 = Q1 |
| `A01` | Annual | A01 = Annual |
| `S01`-`S02` | Semi-annual | S01 = First half |

---

## Common Series IDs

### Employment (Labor Force Statistics - LN)

| Series ID | Description |
|-----------|-------------|
| `LNS14000000` | Unemployment rate, seasonally adjusted |
| `LNS11000000` | Civilian labor force level |
| `LNS12000000` | Employment level |
| `LNS13000000` | Unemployment level |

### Consumer Price Index (CPI - CU)

| Series ID | Description |
|-----------|-------------|
| `CUUR0000SA0` | All items, US city average |
| `CUUR0000SAF1` | Food |
| `CUUR0000SETA01` | New vehicles |
| `CUUR0000SAH1` | Shelter |
| `CUUR0000SETB01` | Gasoline |

### Employment Situation (CES)

| Series ID | Description |
|-----------|-------------|
| `CES0000000001` | Total nonfarm employment |
| `CES0500000001` | Total private employment |
| `CES0500000003` | Average hourly earnings, private |
| `CES0500000008` | Average hourly earnings, production |

### Producer Price Index (PPI - WP)

| Series ID | Description |
|-----------|-------------|
| `WPUFD4` | Final demand |
| `WPUFD49104` | Final demand, goods |
| `WPUFD49116` | Final demand, services |

### JOLTS (JT)

| Series ID | Description |
|-----------|-------------|
| `JTS00000000JOL` | Total job openings |
| `JTS00000000QUR` | Quits rate |
| `JTS00000000HIR` | Hires |
| `JTS00000000TSR` | Total separations rate |

---

## Rate Limits

| Registration | Queries/Day | Years/Query | Series/Query |
|--------------|-------------|-------------|--------------|
| None | 25 | 10 | 25 |
| Registered | 500 | 20 | 50 |

### Rate Limit Response

```json
{
  "status": "REQUEST_FAILED",
  "message": ["Request rate exceeded. Please try again later."]
}
```

---

## Error Responses

### Invalid Series ID

```json
{
  "status": "REQUEST_SUCCEEDED",
  "Results": {
    "series": [
      {
        "seriesID": "INVALID123",
        "data": []
      }
    ]
  }
}
```

### Year Range Error

```json
{
  "status": "REQUEST_FAILED",
  "message": ["The start year must be less than or equal to end year"]
}
```

---

## Configuration File

**File**: `configs/bls_endpoints.json`

```json
{
  "base_urls": {
    "core": "https://api.bls.gov/publicAPI/v2"
  },
  "rate_limit": {
    "calls_per_second": 0.42
  },
  "endpoints": {
    "timeseries": {
      "base": "core",
      "method": "POST",
      "path_template": "/timeseries/data/",
      "response_key": "Results.series"
    }
  },
  "series": {
    "unemployment": "LNS14000000",
    "cpi": "CUUR0000SA0",
    "employment": "CES0000000001",
    "wages": "CES0500000003"
  }
}
```

---

## Usage Example

```python
import requests

url = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
payload = {
    "seriesid": ["LNS14000000"],
    "startyear": "2020",
    "endyear": "2024",
    "registrationkey": "YOUR_KEY"
}

response = requests.post(url, json=payload)
data = response.json()

for series in data["Results"]["series"]:
    for item in series["data"]:
        print(f"{item['year']}-{item['period']}: {item['value']}%")
```

---

## Related Documentation

- [Terms of Use](terms-of-use.md) - Usage terms
- [Facets](facets.md) - Data transformations
- [Bronze Tables](bronze-tables.md) - Output schemas
