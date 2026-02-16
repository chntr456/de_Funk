---
type: domain-model-table
table: dim_community_area
extends: _base.geography.geo_spatial._dim_boundary
table_type: dimension
from: bronze.chicago_community_areas
primary_key: [community_area_id]
unique_key: [area_number]

schema:
  - [community_area_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT('CHICAGO_CA_', area_number)))"}]
  - [area_number, integer, false, "Community area number (1-77)", {derived: "CAST(area_numbe AS INT)"}]
  - [community_name, string, false, "Community area name", {derived: "community"}]
  - [centroid_lat, double, true, "Centroid latitude"]
  - [centroid_lon, double, true, "Centroid longitude"]
  - [area_sqmi, double, true, "Area in square miles"]
  - [geom_wkt, string, true, "Boundary geometry as WKT"]
  - [location_id, integer, true, "FK to geospatial.dim_location", {fk: geospatial.dim_location.location_id}]

measures:
  - [community_area_count, count_distinct, community_area_id, "Number of community areas", {format: "#,##0"}]
  - [total_area_sqmi, sum, area_sqmi, "Total area in square miles", {format: "#,##0.0"}]
---

## Community Area Dimension

Chicago's 77 community areas — stable boundaries since the 1920s, ideal for longitudinal analysis.
