---
type: domain-model-source
source: neighborhoods
extends: _base.geography.geo_spatial
maps_to: dim_neighborhood
from: bronze.cook_county_neighborhoods

aliases:
  - [boundary_id, "ABS(HASH(CONCAT('NEIGHBORHOOD', '_', nbhd_code)))"]
  - [boundary_type, "'NEIGHBORHOOD'"]
  - [boundary_code, nbhd_code]
  - [boundary_name, nbhd_name]
  - [parent_boundary_id, TBD]
  - [centroid_lat, TBD]
  - [centroid_lon, TBD]
  - [geom_wkt, the_geom]
  - [area_sqmi, TBD]
  - [population, "null"]
---

## Neighborhoods
~200 assessor-defined neighborhood boundaries used for property valuation.
