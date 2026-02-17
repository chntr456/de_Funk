---
type: domain-model-table
table: dim_county
table_type: dimension
primary_key: [county_id]
unique_key: [county_fips]

schema:
  - [county_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT('COUNTY_', county_fips)))"}]
  - [state_id, integer, false, "FK to dim_state", {fk: dim_state.state_id}]
  - [county_fips, string, false, "Full FIPS code (5 digits)"]
  - [county_name, string, false, "County name"]
  - [state_fips, string, false, "State FIPS"]
  - [latitude, double, true, "Centroid latitude"]
  - [longitude, double, true, "Centroid longitude"]
  - [population, long, true, "Population estimate"]
  - [land_area_sqmi, double, true, "Land area"]

measures:
  - [county_count, count_distinct, county_id, "Number of counties", {format: "#,##0"}]
---

## County Dimension

US counties (3,143) from FIPS codes.
