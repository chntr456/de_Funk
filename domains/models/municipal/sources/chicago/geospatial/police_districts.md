---
type: domain-model-source
source: police_districts
extends: _base.geography.geo_spatial
maps_to: dim_patrol_district
from: bronze.chicago_police_beats
domain_source: "'chicago'"

aliases:
  - [boundary_id, "ABS(HASH(CONCAT('PATROL_DISTRICT', '_', CAST(district AS STRING))))"]
  - [boundary_type, "'PATROL_DISTRICT'"]
  - [boundary_code, "CAST(district AS STRING)"]
  - [boundary_name, "CONCAT('District ', CAST(district AS STRING))"]
  - [parent_boundary_id, "null"]
  - [centroid_lat, "null"]
  - [centroid_lon, "null"]
  - [geom_wkt, the_geom]
  - [sector, sector]
  - [beat, beat]
  - [beat_num, beat_num]
---

## Police Districts
22 patrol district boundaries.
