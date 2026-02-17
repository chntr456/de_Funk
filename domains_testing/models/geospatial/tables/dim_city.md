---
type: domain-model-table
table: dim_city
table_type: dimension
primary_key: [city_id]
unique_key: [city_code]

schema:
  - [city_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT('CITY_', city_code)))"}]
  - [state_id, integer, true, "FK to dim_state", {fk: dim_state.state_id}]
  - [county_id, integer, true, "FK to dim_county", {fk: dim_county.county_id}]
  - [city_code, string, false, "Unique city identifier"]
  - [city_name, string, false, "City name"]
  - [state_abbr, string, true, "State abbreviation"]
  - [latitude, double, true, "Centroid latitude"]
  - [longitude, double, true, "Centroid longitude"]
  - [population, long, true, "Population estimate"]
  - [timezone, string, true, "IANA timezone"]

measures:
  - [city_count, count_distinct, city_id, "Number of cities", {format: "#,##0"}]
---

## City Dimension

US cities with state and county linkage.
