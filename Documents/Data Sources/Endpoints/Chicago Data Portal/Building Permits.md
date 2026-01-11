---
type: api-endpoint
provider: Chicago Data Portal
endpoint_id: building_permits

# API Configuration
endpoint_pattern: /resource/ydr8-5enu.json
method: GET
format: json
auth: inherit
response_key: null

# Query Parameters
default_query:
  $limit: 1000
  $order: issue_date DESC
required_params: []

# Pagination
pagination_type: offset
bulk_download: true

# Metadata
domain: housing
legal_entity_type: municipal
subject_entity_tags: [municipal, property]
data_tags: [time-series, permits, construction]
status: active
update_cadence: daily
last_verified:
last_reviewed:
notes: "Building permits issued by the City of Chicago"

# Bronze Layer Configuration
bronze:
  table: chicago_building_permits
  partitions: []
  write_strategy: upsert
  key_columns: [permit_number]
  date_column: issue_date
  comment: "Chicago building permits"
---

## Description

Building permits issued by the City of Chicago. Updated daily as new permits are issued.

## Schema

```yaml
# Format: [field_name, type, source_field, nullable, description, {options}]
schema:
  - [permit_number, string, permit_, false, "Permit ID"]
  - [permit_type, string, permit_type, true, "Type of permit"]
  - [issue_date, date, issue_date, true, "Date permit issued", {transform: "to_date(yyyy-MM-dd)"}]
  - [work_description, string, work_description, true, "Description of work"]
  - [total_fee, double, total_fee, true, "Total permit fee", {coerce: double}]
  - [community_area, string, community_area, true, "Community area"]
  - [street_direction, string, street_direction, true, "Street direction"]
  - [street_name, string, street_name, true, "Street name"]
  - [street_number, string, street_number, true, "Street number"]
```

## Homelab Usage

```bash
python -m scripts.ingest.run_chicago_ingestion --endpoint building_permits
```
