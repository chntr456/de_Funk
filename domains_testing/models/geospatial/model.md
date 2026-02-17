---
type: domain-model
model: geospatial
version: 3.0
description: "Geographic and location dimensions - foundation for spatial analysis"
extends: _base.geography.geo_spatial
depends_on: []

storage:
  format: delta
  silver:
    root: storage/silver/geospatial/

graph:
  edges:
    - [county_to_state, dim_county, dim_state, [state_id=state_id], many_to_one, null]
    - [city_to_state, dim_city, dim_state, [state_id=state_id], many_to_one, null]
    - [city_to_county, dim_city, dim_county, [county_id=county_id], many_to_one, null]

build:
  partitions: []
  sort_by: [location_id]
  optimize: true
  phases:
    1: { tables: [dim_location, dim_state] }
    2: { tables: [dim_county] }
    3: { tables: [dim_city] }

metadata:
  domain: geospatial
  owner: data_engineering
status: active
---

## Geospatial Model

Foundation geographic dimensions (US states, counties, cities).
Other models link TO geospatial via location FKs.
