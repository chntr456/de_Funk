---
type: api-endpoint
provider: Bureau of Labor Statistics
endpoint_id: timeseries

# API Configuration
endpoint_pattern: /timeseries/data/
method: POST
format: json
auth: inherit
response_key: Results.series

# Query Parameters (sent in POST body)
default_query: {}
required_params: [seriesid, startyear, endyear]

# Pagination
pagination_type: none
bulk_download: false

# Metadata
domain: economic
legal_entity_type: federal
subject_entity_tags: [labor, economic]
data_tags: [time-series, monthly, economic-indicators]
status: active
update_cadence: monthly
last_verified:
last_reviewed:
notes: "POST request with JSON body containing series IDs and date range"

# Bronze Layer Configuration
bronze:
  table: bls/timeseries
  partitions: [series_id]
  write_strategy: upsert
  key_columns: [series_id, year, period]
  date_column: null
  comment: "BLS time series data - partitioned by series ID"
---

## Description

Get time series data for specified BLS series IDs. This is the primary endpoint for retrieving economic indicator data from BLS.

**Request Format**: POST with JSON body (unlike typical REST GET)

## Schema

```yaml
# Format: [field_name, type, source_field, nullable, description, {options}]
schema:
  # Identifiers
  - [series_id, string, seriesID, false, "BLS series identifier"]
  - [year, string, year, false, "Data year"]
  - [period, string, period, false, "Period code (M01-M12 for monthly)"]
  - [period_name, string, periodName, true, "Period name (January, etc.)"]

  # Value
  - [value, double, value, false, "Reported value", {coerce: double}]

  # Optional calculations (v2 API with registered key)
  - [pct_change_1m, double, calculations.pct_changes.1, true, "1-month percent change", {coerce: double}]
  - [pct_change_3m, double, calculations.pct_changes.3, true, "3-month percent change", {coerce: double}]
  - [pct_change_6m, double, calculations.pct_changes.6, true, "6-month percent change", {coerce: double}]
  - [pct_change_12m, double, calculations.pct_changes.12, true, "12-month percent change", {coerce: double}]
  - [net_change_1m, double, calculations.net_changes.1, true, "1-month net change", {coerce: double}]
  - [net_change_12m, double, calculations.net_changes.12, true, "12-month net change", {coerce: double}]

  # Footnotes
  - [footnotes, string, footnotes, true, "Data footnotes/qualifiers"]
```

## Request Body Example

```json
{
  "seriesid": ["LNS14000000", "CES0000000001"],
  "startyear": "2020",
  "endyear": "2023",
  "registrationkey": "YOUR_API_KEY",
  "calculations": true,
  "annualaverage": true
}
```

## Homelab Usage

```bash
# Ingest unemployment data
python -m scripts.ingest.run_bls_ingestion --series LNS14000000 --start-year 2020 --end-year 2024
```

## Known Quirks

1. **POST method**: Unusual for data retrieval
2. **Array of series**: Can request multiple series in one call
3. **Period codes**: M01-M12 for monthly, Q01-Q04 for quarterly, A01 for annual
4. **Calculations**: Only available with v2 API and registered key
5. **Annual averages**: Set `annualaverage: true` to include A01 period
