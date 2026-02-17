---
type: domain-model
model: county_geospatial
version: 3.0
description: "County geospatial boundaries and hierarchies"
extends: [_base.geography.geo_spatial]
depends_on: []

storage:
  format: delta
  sources_from: sources/{entity}/
  silver:
    root: storage/silver/county/{entity}/geospatial/

graph:
  edges:
    - [municipality_to_township, dim_municipal_boundary, dim_township, [township_code=township_code], many_to_one, null]
    - [neighborhood_to_township, dim_neighborhood, dim_township, [township_code=township_code], many_to_one, null]

build:
  partitions: []
  optimize: true
  phases:
    1: { tables: [dim_township] }
    2: { tables: [dim_municipal_boundary, dim_neighborhood] }

measures:
  simple:
    - [township_count, count_distinct, dim_township.township_code, "Number of townships", {format: "#,##0"}]
    - [municipality_count, count_distinct, dim_municipal_boundary.municipality_id, "Number of municipalities", {format: "#,##0"}]
    - [total_area_sqmi, sum, dim_township.area_sqmi, "Total area in square miles", {format: "#,##0.0"}]

metadata:
  domain: county
  subdomain: geospatial
status: active
---

## County Geospatial Model

Geographic boundaries and hierarchies for a county.

### Geographic Units

| Unit | Count | Description |
|------|-------|-------------|
| Townships | 38 | Property tax administration units |
| Municipalities | 130+ | Cities, villages, towns |
| Neighborhoods | ~200 | Assessor valuation areas |
