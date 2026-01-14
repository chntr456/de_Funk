---
type: domain-model
model: chicago_geospatial
version: 1.0
description: "Chicago geographic boundaries and hierarchies"

# Python Module
python_module: models/domains/city/chicago/geospatial/

# Dependencies
depends_on: []  # Foundation geospatial model

# Storage
storage:
  root: storage/silver/chicago/geospatial
  format: delta

# Build
build:
  partitions: []
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

# Schema
schema:
  dimensions:
    dim_community_area:
      description: "Chicago community areas (77 neighborhoods)"
      primary_key: [area_number]
      columns:
        area_number: {type: int, required: true, description: "Community area number (1-77)"}
        community_name: {type: string, description: "Community area name"}
        geometry: {type: geometry, description: "Area boundary polygon"}
        centroid_lat: {type: double, description: "Centroid latitude"}
        centroid_lon: {type: double, description: "Centroid longitude"}
        area_sqmi: {type: double, description: "Area in square miles"}

    dim_ward:
      description: "Chicago city wards (50 political districts)"
      primary_key: [ward_number]
      columns:
        ward_number: {type: int, required: true, description: "Ward number (1-50)"}
        alderman: {type: string, description: "Current alderman"}
        geometry: {type: geometry, description: "Ward boundary polygon"}
        area_sqmi: {type: double}

    dim_police_district:
      description: "Chicago police districts"
      primary_key: [district_number]
      columns:
        district_number: {type: string, required: true}
        district_name: {type: string}
        geometry: {type: geometry}

    dim_police_beat:
      description: "Chicago police beats (sub-districts)"
      primary_key: [beat_number]
      columns:
        beat_number: {type: string, required: true}
        district_number: {type: string, description: "Parent district"}
        geometry: {type: geometry}

# Graph
graph:
  nodes:
    dim_community_area:
      from: bronze.chicago_community_areas
      type: dimension
      derive:
        area_number: area_numbe
        community_name: community
      unique_key: [area_number]

    dim_ward:
      from: bronze.chicago_wards
      type: dimension
      unique_key: [ward_number]

    dim_police_district:
      from: bronze.chicago_police_districts
      type: dimension
      unique_key: [district_number]

    dim_police_beat:
      from: bronze.chicago_police_beats
      type: dimension
      unique_key: [beat_number]

  edges:
    beat_to_district:
      from: dim_police_beat
      to: dim_police_district
      on: [district_number=district_number]
      type: many_to_one
      description: "Beat's parent district"

# Measures
measures:
  simple:
    community_area_count:
      description: "Number of community areas"
      source: dim_community_area.area_number
      aggregation: count_distinct
      format: "#,##0"

    ward_count:
      description: "Number of wards"
      source: dim_ward.ward_number
      aggregation: count_distinct
      format: "#,##0"

    beat_count:
      description: "Number of police beats"
      source: dim_police_beat.beat_number
      aggregation: count_distinct
      format: "#,##0"

    total_area_sqmi:
      description: "Total area in square miles"
      source: dim_community_area.area_sqmi
      aggregation: sum
      format: "#,##0.0"

# Metadata
metadata:
  domain: city
  entity: chicago
  subdomain: geospatial
status: active
---

## Chicago Geospatial Model

Geographic boundaries and hierarchies for the City of Chicago.

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
FROM dim_community_area
WHERE ST_Contains(geometry, ST_Point(-87.6298, 41.8781));

-- Crimes in a community area
SELECT c.*
FROM chicago_public_safety.fact_crimes c
WHERE c.community_area = 32;  -- Loop

-- Spatial join (slow, prefer pre-computed joins)
SELECT c.*, ca.community_name
FROM chicago_public_safety.fact_crimes c
JOIN dim_community_area ca
  ON ST_Contains(ca.geometry, ST_Point(c.longitude, c.latitude));
```

### Relationship to Cook County

Chicago is contained within Cook County:
- Chicago spans multiple **townships** (county-level geography)
- Property tax data (Cook County) can be joined to Chicago via:
  - Point-in-polygon (expensive)
  - Pre-computed community_area assignment (recommended)

See `foundation/geospatial.md` for containment logic.

### Notes

- Community areas are stable and preferred for analysis
- Wards change with redistricting (every 10 years)
- Police beats may be reorganized periodically
- Most Chicago datasets include `community_area` and `ward` columns
