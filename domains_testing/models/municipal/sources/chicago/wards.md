---
type: domain-model-source
source: wards
extends: _base.geography.geo_spatial
maps_to: dim_ward
from: bronze.chicago_wards

aliases:
  - [domain_source, "'chicago'"]
  - [boundary_id, "ABS(HASH(CONCAT('WARD', '_', CAST(ward AS STRING))))"]
  - [boundary_type, "'WARD'"]
  - [boundary_code, "CAST(ward AS STRING)"]
  - [boundary_name, "CONCAT('Ward ', CAST(ward AS STRING))"]
  - [parent_boundary_id, "null"]
  - [centroid_lat, TBD]
  - [centroid_lon, TBD]
  - [geom_wkt, the_geom]
  - [area_sqmi, shape_area]
  - [population, "null"]
---

## Wards
50 ward boundaries. Updated on redistricting cycles.
