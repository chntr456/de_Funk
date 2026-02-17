---
type: domain-model-source
source: police_districts
extends: _base.geography.geo_spatial
maps_to: dim_patrol_district
from: bronze.chicago_police_districts

aliases:
  - [boundary_id, "ABS(HASH(CONCAT('PATROL_DISTRICT', '_', CAST(dist_num AS STRING))))"]
  - [boundary_type, "'PATROL_DISTRICT'"]
  - [boundary_code, "CAST(dist_num AS STRING)"]
  - [boundary_name, "CONCAT('District ', CAST(dist_num AS STRING))"]
  - [parent_boundary_id, "null"]
  - [centroid_lat, TBD]
  - [centroid_lon, TBD]
  - [geom_wkt, the_geom]
  - [area_sqmi, shape_area]
  - [population, "null"]
---

## Police Districts
22 patrol district boundaries.
