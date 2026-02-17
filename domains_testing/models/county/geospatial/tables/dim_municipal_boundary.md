---
type: domain-model-table
table: dim_municipal_boundary
extends: _base.geography.geo_spatial._dim_boundary
table_type: dimension
from: bronze.cook_county_municipalities
primary_key: [municipality_id]

schema:
  - [municipality_id, string, false, "PK"]
  - [municipality_name, string, true, "City/village name"]
  - [municipality_type, string, true, "city, village, town, unincorporated"]
  - [township_code, string, true, "Primary township"]
  - [area_sqmi, double, true, "Area in square miles"]
  - [is_chicago, boolean, true, "Is City of Chicago", {derived: "municipality_name = 'Chicago'"}]
  - [geometry, string, true, "Municipality boundary WKT"]

measures:
  - [municipality_count, count_distinct, municipality_id, "Number of municipalities", {format: "#,##0"}]
---

## Municipality Dimension

130+ municipalities within Cook County (cities, villages, unincorporated areas).
