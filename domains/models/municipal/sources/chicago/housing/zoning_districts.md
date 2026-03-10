---
type: domain-model-source
source: zoning_districts
extends: _base.geography.geo_spatial
maps_to: dim_zoning_district
from: bronze.chicago_zoning_districts
domain_source: "'chicago'"

aliases:
  - [boundary_id, "ABS(HASH(CONCAT('ZONING_DISTRICT', '_', zone_class)))"]
  - [boundary_type, "'ZONING_DISTRICT'"]
  - [boundary_code, zone_class]
  - [boundary_name, zone_type]
  - [parent_boundary_id, "null"]
  - [centroid_lat, "null"]
  - [centroid_lon, "null"]
  - [geom_wkt, the_geom]
  - [area_sqmi, TBD]
  - [population, "null"]
---

## Zoning Districts
Zoning classification boundaries (residential, commercial, manufacturing, planned development).
