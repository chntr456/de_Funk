---
type: api-endpoint
provider: Chicago Data Portal
endpoint_id: economic_indicators

# API Configuration
endpoint_pattern: /resource/nej5-8p3s.json
method: GET
format: json
auth: inherit
response_key: null

# Query Parameters
default_query:
  $limit: 1000
  $order: date DESC
required_params: []

# Pagination
pagination_type: offset
bulk_download: true

# Metadata
domain: economic
legal_entity_type: municipal
subject_entity_tags: [municipal]
data_tags: [time-series, economic-indicators, city]
status: active
update_cadence: monthly
last_verified:
last_reviewed:
notes: "Chicago economic indicators time series"

# Bronze Layer Configuration
bronze:
  table: chicago_economic_indicators
  partitions: []
  write_strategy: upsert
  key_columns: [date, indicator]
  date_column: date
  comment: "Chicago economic indicators from Data Portal"
---

## Description

Chicago economic indicators time series data from the City of Chicago Data Portal.

## Schema

```yaml
# Format: [field_name, type, source_field, nullable, description, {options}]
schema:
  - [date, date, date, false, "Indicator date", {transform: "to_date(yyyy-MM-dd)"}]
  - [indicator, string, indicator, false, "Indicator name"]
  - [value, double, value, true, "Indicator value", {coerce: double}]
```

## Homelab Usage

```bash
python -m scripts.ingest.run_chicago_ingestion --endpoint economic_indicators
```
