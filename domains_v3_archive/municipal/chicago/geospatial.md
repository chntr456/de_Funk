---
type: domain-model
model: chicago_geospatial
version: 3.0
description: "Chicago geographic boundaries and hierarchies"
tags: [geospatial, chicago, municipal, geography]

# Dependencies
depends_on:
  - geospatial  # Foundation geospatial model

# Storage
storage:
  root: storage/silver/chicago/geospatial
  format: delta

# Build
build:
  partitions: []
  sort_by: [area_number, ward_number, district_id, beat_id]
  optimize: true

# Sources
sources:
  community_areas:
    bronze_table: chicago_community_areas
    description: "77 Chicago community area boundaries"

  wards:
    bronze_table: chicago_wards
    description: "50 Chicago ward boundaries"

  police_beats:
    bronze_table: chicago_police_beats
    description: "Police beat boundaries"

  police_districts:
    bronze_table: chicago_police_districts
    description: "Police district boundaries"

# Tables - v3.0 format with integer surrogate keys
tables:
  dim_community_area:
    type: dimension
    description: "Chicago community areas (77 neighborhoods)"
    primary_key: [community_area_id]

    # Schema: [column, type, nullable, description, {options}]
    schema:
      # Keys - integer surrogate
      - [community_area_id, integer, false, "PK - Integer surrogate", {derived: "ABS(HASH(CONCAT('CHICAGO_CA_', area_number)))"}]

      # Natural key
      - [area_number, integer, false, "Community area number (1-77)", {unique: true}]
      - [community_name, string, false, "Community area name"]

      # Geographic
      - [centroid_lat, double, true, "Centroid latitude"]
      - [centroid_lon, double, true, "Centroid longitude"]
      - [area_sqmi, double, true, "Area in square miles"]
      - [geom_wkt, string, true, "Boundary geometry as WKT"]

      # FK to foundation geospatial
      - [location_id, integer, true, "FK to geospatial.dim_location", {fk: geospatial.dim_location.location_id}]

    measures:
      - [community_area_count, count_distinct, community_area_id, "Number of community areas", {format: "#,##0"}]
      - [total_area_sqmi, sum, area_sqmi, "Total area in square miles", {format: "#,##0.0"}]

  dim_ward:
    type: dimension
    description: "Chicago city wards (50 political districts)"
    primary_key: [ward_id]

    schema:
      - [ward_id, integer, false, "PK - Integer surrogate", {derived: "ABS(HASH(CONCAT('CHICAGO_WARD_', ward_number)))"}]
      - [ward_number, integer, false, "Ward number (1-50)", {unique: true}]
      - [alderman, string, true, "Current alderman name"]
      - [centroid_lat, double, true, "Centroid latitude"]
      - [centroid_lon, double, true, "Centroid longitude"]
      - [area_sqmi, double, true, "Area in square miles"]
      - [geom_wkt, string, true, "Boundary geometry as WKT"]
      - [location_id, integer, true, "FK to geospatial.dim_location", {fk: geospatial.dim_location.location_id}]

    measures:
      - [ward_count, count_distinct, ward_id, "Number of wards", {format: "#,##0"}]

  dim_police_district:
    type: dimension
    description: "Chicago police districts (22 administrative areas)"
    primary_key: [district_id]

    schema:
      - [district_id, integer, false, "PK - Integer surrogate", {derived: "ABS(HASH(CONCAT('CHICAGO_DIST_', district_number)))"}]
      - [district_number, string, false, "District number", {unique: true}]
      - [district_name, string, true, "District name"]
      - [centroid_lat, double, true, "Centroid latitude"]
      - [centroid_lon, double, true, "Centroid longitude"]
      - [area_sqmi, double, true, "Area in square miles"]
      - [geom_wkt, string, true, "Boundary geometry as WKT"]
      - [location_id, integer, true, "FK to geospatial.dim_location", {fk: geospatial.dim_location.location_id}]

    measures:
      - [district_count, count_distinct, district_id, "Number of police districts", {format: "#,##0"}]

  dim_police_beat:
    type: dimension
    description: "Chicago police beats (patrol sub-areas)"
    primary_key: [beat_id]

    schema:
      - [beat_id, integer, false, "PK - Integer surrogate", {derived: "ABS(HASH(CONCAT('CHICAGO_BEAT_', beat_number)))"}]
      - [beat_number, string, false, "Beat number", {unique: true}]
      - [district_id, integer, false, "FK to dim_police_district", {fk: dim_police_district.district_id}]
      - [district_number, string, false, "Parent district number"]
      - [centroid_lat, double, true, "Centroid latitude"]
      - [centroid_lon, double, true, "Centroid longitude"]
      - [geom_wkt, string, true, "Boundary geometry as WKT"]
      - [location_id, integer, true, "FK to geospatial.dim_location", {fk: geospatial.dim_location.location_id}]

    measures:
      - [beat_count, count_distinct, beat_id, "Number of police beats", {format: "#,##0"}]

# Graph
graph:
  nodes:
    dim_community_area:
      from: bronze.chicago_community_areas
      type: dimension
      derive:
        community_area_id: "ABS(HASH(CONCAT('CHICAGO_CA_', area_numbe)))"
        community_name: "community"
        area_number: "CAST(area_numbe AS INT)"
      primary_key: [community_area_id]
      unique_key: [area_number]
      tags: [dim, geospatial, chicago]

    dim_ward:
      from: bronze.chicago_wards
      type: dimension
      derive:
        ward_id: "ABS(HASH(CONCAT('CHICAGO_WARD_', ward)))"
        ward_number: "CAST(ward AS INT)"
      primary_key: [ward_id]
      unique_key: [ward_number]
      tags: [dim, geospatial, chicago]

    dim_police_district:
      from: bronze.chicago_police_districts
      type: dimension
      derive:
        district_id: "ABS(HASH(CONCAT('CHICAGO_DIST_', dist_num)))"
        district_number: "dist_num"
        district_name: "dist_label"
      primary_key: [district_id]
      unique_key: [district_number]
      tags: [dim, geospatial, chicago]

    dim_police_beat:
      from: bronze.chicago_police_beats
      type: dimension
      derive:
        beat_id: "ABS(HASH(CONCAT('CHICAGO_BEAT_', beat_num)))"
        beat_number: "beat_num"
        district_number: "district"
        district_id: "ABS(HASH(CONCAT('CHICAGO_DIST_', district)))"
      primary_key: [beat_id]
      unique_key: [beat_number]
      foreign_keys:
        - {column: district_id, references: dim_police_district.district_id}
      tags: [dim, geospatial, chicago]

  edges:
    beat_to_district:
      from: dim_police_beat
      to: dim_police_district
      on: [district_id=district_id]
      type: many_to_one
      description: "Beat's parent district"

    community_to_foundation:
      from: dim_community_area
      to: geospatial.dim_location
      on: [location_id=location_id]
      type: many_to_one
      cross_model: geospatial
      description: "Link to foundation geospatial"

# Measures
measures:
  simple:
    community_area_count:
      description: "Number of community areas"
      source: dim_community_area.community_area_id
      aggregation: count_distinct
      format: "#,##0"

    ward_count:
      description: "Number of wards"
      source: dim_ward.ward_id
      aggregation: count_distinct
      format: "#,##0"

    beat_count:
      description: "Number of police beats"
      source: dim_police_beat.beat_id
      aggregation: count_distinct
      format: "#,##0"

    district_count:
      description: "Number of police districts"
      source: dim_police_district.district_id
      aggregation: count_distinct
      format: "#,##0"

    total_area_sqmi:
      description: "Total area in square miles"
      source: dim_community_area.area_sqmi
      aggregation: sum
      format: "#,##0.0"

# Metadata
metadata:
  domain: municipal
  entity: chicago
  subdomain: geospatial
  owner: data_engineering
  sla_hours: 24
status: active
---

## Chicago Geospatial Model

Geographic boundaries and hierarchies for the City of Chicago.

### Integer Keys

All dimensions use integer surrogate keys derived from hash:

| Key | Type | Derivation |
|-----|------|------------|
| `community_area_id` | integer | `HASH('CHICAGO_CA_' + area_number)` |
| `ward_id` | integer | `HASH('CHICAGO_WARD_' + ward_number)` |
| `district_id` | integer | `HASH('CHICAGO_DIST_' + district_number)` |
| `beat_id` | integer | `HASH('CHICAGO_BEAT_' + beat_number)` |

### Geographic Units

| Unit | Count | Description |
|------|-------|-------------|
| Community Areas | 77 | Neighborhood boundaries (stable since 1920s) |
| Wards | 50 | Political districts (change with redistricting) |
| Police Districts | 22 | Police administrative districts |
| Police Beats | ~280 | Sub-district patrol areas |

### Hierarchy

```
City of Chicago
├── Community Areas (77)
│   └── Stable boundaries for social/demographic analysis
├── Wards (50)
│   └── Political representation (aldermen)
└── Police Hierarchy
    ├── Districts (22)
    └── Beats (~280)
```

### Community Areas

The 77 community areas have been stable since the 1920s, making them ideal for longitudinal analysis. They are used extensively for:
- Census data aggregation
- Social service planning
- Demographic analysis
- Public health statistics

### Spatial Operations

Uses DuckDB spatial extension:

```sql
-- Find community area for a point
SELECT community_name
FROM chicago_geospatial.dim_community_area
WHERE ST_Contains(ST_GeomFromText(geom_wkt), ST_Point(-87.6298, 41.8781));

-- Crimes in a community area (using integer key join)
SELECT c.*, ca.community_name
FROM chicago_public_safety.fact_crimes c
JOIN chicago_geospatial.dim_community_area ca
  ON c.community_area = ca.area_number
WHERE ca.community_name = 'Loop';

-- Join on integer surrogate keys (preferred for performance)
SELECT c.*, ca.community_name
FROM chicago_public_safety.fact_crimes c
JOIN chicago_geospatial.dim_community_area ca
  ON ABS(HASH(CONCAT('CHICAGO_CA_', c.community_area))) = ca.community_area_id;
```

### Relationship to Cook County

Chicago is contained within Cook County:
- Chicago spans multiple **townships** (county-level geography)
- Property tax data (Cook County) can be joined to Chicago via:
  - Point-in-polygon (expensive)
  - Pre-computed community_area assignment (recommended)

See `geospatial` foundation domain for containment logic.

### Notes

- Community areas are stable and preferred for analysis
- Wards change with redistricting (every 10 years)
- Police beats may be reorganized periodically
- Most Chicago datasets include `community_area` and `ward` columns
- Integer surrogate keys enable efficient joins across models
