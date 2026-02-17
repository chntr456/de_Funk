---
type: domain-model-source
source: police_beats
extends: _base.geography.geo_spatial
maps_to: dim_patrol_area
from: bronze.chicago_police_beats

aliases:
  - [boundary_type, "'PATROL_AREA'"]
  - [boundary_code, "CAST(beat_num AS STRING)"]
  - [boundary_name, "CONCAT('Beat ', CAST(beat_num AS STRING))"]
  - [parent_boundary_id, "ABS(HASH(CONCAT('PATROL_DISTRICT_', CAST(district AS STRING))))"]
  - [centroid_lat, TBD]
  - [centroid_lon, TBD]
  - [geom_wkt, the_geom]
  - [area_sqmi, shape_area]
  - [population, "null"]
---

## Police Beats
~280 patrol area boundaries with district hierarchy.
