---
type: domain-model-source
source: community_areas
extends: _base.geography.geo_spatial
maps_to: dim_community_area
from: bronze.chicago_community_areas

aliases:
  - [boundary_type, "'COMMUNITY_AREA'"]
  - [boundary_code, "CAST(area_numbe AS STRING)"]
  - [boundary_name, community]
  - [parent_boundary_id, "null"]
  - [centroid_lat, TBD]
  - [centroid_lon, TBD]
  - [geom_wkt, the_geom]
  - [area_sqmi, shape_area]
  - [population, "null"]
---

## Community Areas
77 community area boundaries. Static reference.
