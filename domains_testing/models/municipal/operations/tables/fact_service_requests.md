---
type: domain-model-table
table: fact_service_requests
extends: _base.operations.service_request._fact_service_requests
table_type: fact
from: bronze.chicago_311_requests
primary_key: [request_id]
partition_by: [year]

schema:
  - [request_id, string, false, "PK", {derived: "sr_number"}]
  - [request_type_id, integer, true, "FK to dim_request_type", {fk: dim_request_type.request_type_id, derived: "ABS(HASH(COALESCE(sr_type, 'UNKNOWN')))"}]
  - [status_id, integer, true, "FK to dim_status", {fk: dim_status.status_id, derived: "ABS(HASH(COALESCE(status, 'UNKNOWN')))"}]
  - [created_date, timestamp, true, "Request created"]
  - [closed_date, timestamp, true, "Request closed"]
  - [year, integer, true, "Year created", {derived: "YEAR(created_date)"}]
  - [street_address, string, true, "Street address"]
  - [zip_code, string, true, "ZIP code"]
  - [ward, integer, true, "City ward"]
  - [community_area, integer, true, "Community area"]
  - [latitude, double, true, "Latitude"]
  - [longitude, double, true, "Longitude"]
  - [is_legacy, boolean, true, "From old 311 system", {derived: "legacy_record"}]
  - [days_to_close, integer, true, "Days to close", {derived: "DATEDIFF('day', created_date, closed_date)"}]

measures:
  - [request_count, count, request_id, "Total requests", {format: "#,##0"}]
  - [avg_days_to_close, avg, days_to_close, "Avg days to close", {format: "#,##0.1"}]
---

## Service Requests Fact Table

311 service requests since 12/18/2018.
