# Chicago Data Portal API Reference

**Socrata Open Data API endpoints and queries**

---

## Base Configuration

```json
{
  "base_urls": {
    "core": "https://data.cityofchicago.org"
  },
  "auth": {
    "type": "header",
    "header_name": "X-App-Token"
  }
}
```

---

## API Overview

The Chicago Data Portal uses the **Socrata Open Data API (SODA)**.

### Base URL Pattern

```
https://data.cityofchicago.org/resource/{dataset-id}.json
```

### Authentication

| Method | Header | Limits |
|--------|--------|--------|
| None | - | 1,000 requests/day |
| App Token | `X-App-Token: your_token` | Higher limits |

---

## Endpoints (Datasets)

### 1. Unemployment Rates by Community Area

**Dataset ID**: `ane4-dwhs`

**Endpoint**: `GET /resource/ane4-dwhs.json`

**Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `geography` | string | Community area name |
| `geography_type` | string | Geographic type |
| `year` | number | Year |
| `month` | number | Month |
| `unemployment_rate` | number | Unemployment rate (%) |
| `labor_force` | number | Labor force count |
| `employed` | number | Employed count |
| `unemployed` | number | Unemployed count |

**Example Request**:
```
https://data.cityofchicago.org/resource/ane4-dwhs.json?$limit=1000&$where=year=2024
```

---

### 2. Building Permits

**Dataset ID**: `ydr8-5enu`

**Endpoint**: `GET /resource/ydr8-5enu.json`

**Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Permit ID |
| `permit_` | string | Permit number |
| `permit_type` | string | Type of permit |
| `issue_date` | datetime | Date issued |
| `application_start_date` | datetime | Application date |
| `total_fee` | number | Fee amount |
| `street_number` | string | Address number |
| `street_direction` | string | Street direction |
| `street_name` | string | Street name |
| `work_description` | string | Work description |
| `community_area` | string | Community area number |
| `latitude` | number | Latitude |
| `longitude` | number | Longitude |

**Example Request**:
```
https://data.cityofchicago.org/resource/ydr8-5enu.json?$limit=1000&$where=issue_date>'2024-01-01'
```

---

### 3. Business Licenses

**Dataset ID**: `r5kz-chrr`

**Endpoint**: `GET /resource/r5kz-chrr.json`

**Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `license_id` | string | License ID |
| `account_number` | string | Business account |
| `legal_name` | string | Business legal name |
| `doing_business_as_name` | string | DBA name |
| `license_description` | string | License type |
| `license_start_date` | datetime | Start date |
| `expiration_date` | datetime | Expiration date |
| `address` | string | Business address |
| `city` | string | City |
| `state` | string | State |
| `zip_code` | string | ZIP code |
| `latitude` | number | Latitude |
| `longitude` | number | Longitude |

---

### 4. Per Capita Income

**Dataset ID**: `qpxx-qyaw`

**Endpoint**: `GET /resource/qpxx-qyaw.json`

**Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `community_area` | string | Community area number |
| `community_area_name` | string | Area name |
| `per_capita_income` | number | Income per person |
| `below_poverty_level` | number | Poverty percentage |
| `unemployment` | number | Unemployment rate |

---

### 5. Economic Indicators

**Dataset ID**: `nej5-8p3s`

**Endpoint**: `GET /resource/nej5-8p3s.json`

**Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `date` | datetime | Data date |
| `indicator` | string | Indicator name |
| `value` | number | Indicator value |

---

## SoQL Query Language

Socrata uses SoQL (Socrata Query Language), similar to SQL.

### Query Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `$select` | Columns to return | `$select=permit_type,issue_date` |
| `$where` | Filter condition | `$where=year=2024` |
| `$order` | Sort order | `$order=issue_date DESC` |
| `$limit` | Max rows | `$limit=1000` |
| `$offset` | Skip rows | `$offset=1000` |
| `$group` | Group by | `$group=community_area` |
| `$having` | Group filter | `$having=count(*)>10` |

### Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `=` | Equals | `year=2024` |
| `!=` | Not equals | `status!='Closed'` |
| `>`, `<` | Comparison | `total_fee>1000` |
| `>=`, `<=` | Comparison | `issue_date>='2024-01-01'` |
| `AND`, `OR` | Logical | `year=2024 AND month=1` |
| `IN` | In list | `permit_type IN ('PERMIT','EASY PERMIT')` |
| `LIKE` | Pattern match | `street_name LIKE '%MICHIGAN%'` |
| `IS NULL` | Null check | `latitude IS NOT NULL` |

### Functions

| Function | Description | Example |
|----------|-------------|---------|
| `count(*)` | Row count | `$select=count(*)` |
| `sum(col)` | Sum | `$select=sum(total_fee)` |
| `avg(col)` | Average | `$select=avg(unemployment_rate)` |
| `max(col)` | Maximum | `$select=max(issue_date)` |
| `date_trunc_y(col)` | Truncate to year | `$select=date_trunc_y(issue_date)` |

---

## Pagination

Large datasets require pagination:

```python
offset = 0
limit = 1000
all_data = []

while True:
    url = f"https://data.cityofchicago.org/resource/ydr8-5enu.json?$limit={limit}&$offset={offset}"
    response = requests.get(url)
    data = response.json()

    if len(data) == 0:
        break

    all_data.extend(data)
    offset += limit
```

---

## Rate Limits

| Authentication | Limit |
|----------------|-------|
| No token | 1,000 requests/day |
| With app token | 5 requests/second |

### Rate Limit Response

HTTP 429 with:
```json
{
  "error": true,
  "message": "Rate limit exceeded"
}
```

---

## Configuration File

**File**: `configs/chicago_endpoints.json`

```json
{
  "base_urls": {
    "core": "https://data.cityofchicago.org"
  },
  "rate_limit": {
    "calls_per_second": 5.0
  },
  "endpoints": {
    "unemployment_rates": {
      "base": "core",
      "method": "GET",
      "path_template": "/resource/ane4-dwhs.json",
      "default_query": {
        "$limit": 1000,
        "$order": "date DESC"
      }
    },
    "building_permits": {
      "base": "core",
      "method": "GET",
      "path_template": "/resource/ydr8-5enu.json",
      "default_query": {
        "$limit": 1000,
        "$order": "issue_date DESC"
      }
    },
    "business_licenses": {
      "base": "core",
      "method": "GET",
      "path_template": "/resource/r5kz-chrr.json",
      "default_query": {
        "$limit": 1000
      }
    }
  }
}
```

---

## Usage Example

```python
import requests

# With app token
headers = {"X-App-Token": "YOUR_APP_TOKEN"}

# Get recent permits
url = "https://data.cityofchicago.org/resource/ydr8-5enu.json"
params = {
    "$where": "issue_date >= '2024-01-01'",
    "$order": "issue_date DESC",
    "$limit": 100
}

response = requests.get(url, headers=headers, params=params)
permits = response.json()

for permit in permits:
    print(f"{permit['permit_']} - {permit['permit_type']} - ${permit.get('total_fee', 0)}")
```

---

## Related Documentation

- [Terms of Use](terms-of-use.md) - Open data terms
- [Facets](facets.md) - Data transformations
- [Bronze Tables](bronze-tables.md) - Output schemas
