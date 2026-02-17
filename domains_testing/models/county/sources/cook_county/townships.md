---
type: domain-model-source
source: townships
extends: _base.geography.geo_spatial
maps_to: dim_township
from: bronze.cook_county_townships

aliases:
  - [boundary_type, "'TOWNSHIP'"]
  - [boundary_code, township_code]
  - [boundary_name, township_name]
  - [parent_boundary_id, "null"]
  - [centroid_lat, TBD]
  - [centroid_lon, TBD]
  - [geom_wkt, the_geom]
  - [area_sqmi, TBD]
  - [population, "null"]
---

## Townships
38 township boundaries within Cook County.
