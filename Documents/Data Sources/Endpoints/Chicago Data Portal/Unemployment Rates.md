---
type: api-endpoint
provider: Chicago Data Portal
endpoint_id: unemployment_rates

# API Configuration
endpoint_pattern: /resource/ane4-dwhs.json
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
subject_entity_tags: [municipal, labor]
data_tags: [time-series, unemployment, community-area]
status: active
update_cadence: monthly
last_verified:
last_reviewed:
notes: "Monthly unemployment rates by Chicago community area"

# Storage Configuration
bronze: chicago_unemployment
partitions: []
write_strategy: upsert
key_columns: [date, community_area]
date_column: date

# Schema
schema:
  - [date, date, date, false, "Report date", {transform: "to_date(yyyy-MM-dd)"}]
  - [community_area, string, community_area, false, "Chicago community area name"]
  - [community_area_number, int, community_area_number, true, "Community area code", {coerce: long}]
  - [unemployment_rate, double, unemployment_rate, true, "Unemployment rate %", {coerce: double}]
---

## Description

Monthly unemployment rates by Chicago community area. Provides granular local labor market data.

## Homelab Usage

```bash
python -m scripts.ingest.run_bronze_ingestion --provider chicago --endpoints unemployment_rates
```
