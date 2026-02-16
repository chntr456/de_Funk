---
type: domain-model-table
table: dim_ward
table_type: dimension
from: bronze.chicago_wards
primary_key: [ward_id]
unique_key: [ward_number]

schema:
  - [ward_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT('CHICAGO_WARD_', ward_number)))"}]
  - [ward_number, integer, false, "Ward number (1-50)", {derived: "CAST(ward AS INT)"}]
  - [alderman, string, true, "Current alderman name"]
  - [centroid_lat, double, true, "Centroid latitude"]
  - [centroid_lon, double, true, "Centroid longitude"]
  - [area_sqmi, double, true, "Area in square miles"]
  - [geom_wkt, string, true, "Boundary geometry as WKT"]
  - [location_id, integer, true, "FK to geospatial.dim_location", {fk: geospatial.dim_location.location_id}]

measures:
  - [ward_count, count_distinct, ward_id, "Number of wards", {format: "#,##0"}]
---

## Ward Dimension

Chicago's 50 city wards — political districts that change with redistricting every 10 years.
