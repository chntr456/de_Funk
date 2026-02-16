---
type: domain-model-table
table: dim_facility
table_type: dimension
from: bronze.chicago_food_inspections
transform: aggregate
group_by: [license_]
primary_key: [facility_id]

schema:
  - [facility_id, integer, false, "PK", {derived: "ABS(HASH(CAST(license_ AS STRING)))"}]
  - [facility_name, string, true, "Business name", {derived: "FIRST(dba_name)"}]
  - [facility_type, string, true, "Facility type", {derived: "FIRST(facility_type)"}]
  - [risk_level, string, true, "Risk level", {derived: "FIRST(risk)"}]
  - [address, string, true, "Address", {derived: "FIRST(address)"}]
  - [ward, integer, true, "Ward", {derived: "FIRST(CAST(ward AS INT))"}]
  - [community_area, integer, true, "Community area"]
  - [latitude, double, true, "Latitude"]
  - [longitude, double, true, "Longitude"]

measures:
  - [facility_count, count_distinct, facility_id, "Facilities", {format: "#,##0"}]
---

## Facility Dimension

Food establishments aggregated by license number.
