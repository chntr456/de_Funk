---
type: domain-model-table
table: dim_police_district
table_type: dimension
from: bronze.chicago_police_districts
primary_key: [district_id]
unique_key: [district_number]

schema:
  - [district_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT('CHICAGO_DIST_', dist_num)))"}]
  - [district_number, string, false, "District number", {derived: "dist_num"}]
  - [district_name, string, true, "District name", {derived: "dist_label"}]
  - [centroid_lat, double, true, "Centroid latitude"]
  - [centroid_lon, double, true, "Centroid longitude"]
  - [area_sqmi, double, true, "Area in square miles"]
  - [geom_wkt, string, true, "Boundary geometry as WKT"]
  - [location_id, integer, true, "FK to geospatial.dim_location", {fk: geospatial.dim_location.location_id}]

measures:
  - [district_count, count_distinct, district_id, "Number of police districts", {format: "#,##0"}]
---

## Police District Dimension

Chicago's 22 police administrative districts.
