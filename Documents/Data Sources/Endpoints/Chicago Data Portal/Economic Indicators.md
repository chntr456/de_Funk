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

# Storage Configuration
bronze: chicago_economic_indicators
partitions: []
write_strategy: upsert
key_columns: [date, indicator]
date_column: date

# Schema
schema:
  - [date, date, date, false, "Indicator date", {transform: "to_date(yyyy-MM-dd)"}]
  - [indicator, string, indicator, false, "Indicator name"]
  - [value, double, value, true, "Indicator value", {coerce: double}]
---

## Description

Chicago economic indicators time series data from the City of Chicago Data Portal.

## Homelab Usage

```bash
python -m scripts.ingest.run_bronze_ingestion --provider chicago --endpoints economic_indicators
```
