---
type: api-endpoint
provider: Chicago Data Portal
endpoint_id: per_capita_income

# API Configuration
endpoint_pattern: /resource/qpxx-qyaw.json
method: GET
format: json
auth: inherit
response_key: null

# Query Parameters
default_query:
  $limit: 1000
  $order: community_area_number
required_params: []

# Pagination
pagination_type: offset
bulk_download: true

# Metadata
domain: economic
legal_entity_type: municipal
subject_entity_tags: [municipal, demographic]
data_tags: [reference, income, community-area]
status: active
update_cadence: irregular
last_verified:
last_reviewed:
notes: "Per capita income by Chicago community area (Census-based)"

# Bronze Layer Configuration
bronze:
  table: chicago_per_capita_income
  partitions: []
  write_strategy: overwrite
  key_columns: [community_area_number]
  date_column: null
  comment: "Chicago per capita income by community area"
---

## Description

Per capita income by Chicago community area. Based on Census data, updated irregularly.

## Schema

```yaml
# Format: [field_name, type, source_field, nullable, description, {options}]
schema:
  - [community_area_number, int, community_area_number, false, "Community area code", {coerce: long}]
  - [community_area_name, string, community_area_name, false, "Community area name"]
  - [per_capita_income, double, per_capita_income, true, "Per capita income USD", {coerce: double}]
  - [percent_households_below_poverty, double, percent_households_below_poverty, true, "Poverty rate %", {coerce: double}]
  - [percent_aged_16_unemployed, double, percent_aged_16_unemployed, true, "Age 16+ unemployment %", {coerce: double}]
  - [percent_aged_25_without_high_school_diploma, double, percent_aged_25_without_high_school_diploma, true, "No HS diploma %", {coerce: double}]
  - [percent_aged_under_18_or_over_64, double, percent_aged_under_18_or_over_64, true, "Dependent age %", {coerce: double}]
  - [hardship_index, double, hardship_index, true, "Composite hardship index", {coerce: double}]
```

## Homelab Usage

```bash
python -m scripts.ingest.run_chicago_ingestion --endpoint per_capita_income
```
