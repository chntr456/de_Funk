---
type: api-endpoint
provider:                               # Must match a provider note (e.g., "Alpha Vantage")
endpoint_id:                            # Unique code identifier (e.g., "company_overview")

# API Configuration
endpoint_pattern:                       # URL path template (e.g., "/resource/{view_id}.json")
method: GET                             # HTTP method
format: json                            # json | csv | xml | geojson
auth: inherit                           # inherit | none | api-key | basic
response_key:                           # JSON key containing data (null = entire response)

# Query Parameters
default_query: {}                       # Default query params (e.g., {function: OVERVIEW})
required_params: []                     # Required parameters (e.g., [symbol])

# Pagination
pagination_type: none                   # none | offset | cursor | page
multiple_endpoints: false               # Whether multiple sources required for full data
bulk_download: false                    # Whether bulk downloads are available

# Metadata
domain:                                 # finance | securities | geospatial | housing | etc.
legal_entity_type:                      # municipal | county | federal | vendor
subject_entity_tags: []                 # Who is the data about [corporate, municipal, property]
data_tags: []                           # Descriptive tags [time-series, public, daily, reference]
status: active                          # active | flaky | deprecated
update_cadence: irregular               # daily | weekly | monthly | quarterly | annual | irregular
last_verified:
last_reviewed:
notes:

# ============================================
# BRONZE LAYER CONFIGURATION
# (Replaces storage.json entries for this endpoint)
# ============================================
bronze:
  table:                                # Bronze table name (e.g., "company_reference")
  partitions: []                        # Partition columns (e.g., [asset_type])
  write_strategy: upsert                # upsert | append | overwrite
  key_columns: []                       # Primary key columns for upsert (e.g., [ticker])
  date_column:                          # Date column for incremental loads
  comment:                              # Description of this bronze table
---

## Description

What data this endpoint returns.

## Schema

```yaml
# Format: [field_name, type, source_field, nullable, description]
# Types: string | long | double | boolean | date | timestamp
# Source: API field name or "_generated" for computed fields
schema:
  - [example_field, string, ExampleField, false, "Description of field"]
```

## Request Notes

Query params, limits, filters, authentication details.

## Homelab Usage

Cron jobs, ingest scripts, storage paths, recommended refresh cadence.

## Known Quirks

Downtime patterns, format changes, schema drift, error handling notes.
