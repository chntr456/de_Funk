---
type: domain-model
model: foundation_geospatial
version: 1.0
description: "Foundation geospatial model providing entity containment relationships"

# Python Module
python_module: models/domains/foundation/geospatial/

# Dependencies
depends_on: []  # Foundation model - no dependencies

# Storage
storage:
  root: storage/silver/foundation/geospatial
  format: delta

# Build
build:
  partitions: []
  optimize: true

# Entity Containment Relationships
# Defines how geographic entities relate to each other
containment:
  # Chicago is contained by Cook County
  chicago_in_cook_county:
    parent: cook_county
    child: chicago
    relationship: contained_by
    notes: "City of Chicago is fully within Cook County"

  # Community areas are within Chicago
  community_areas_in_chicago:
    parent: chicago
    child: community_area
    relationship: contained_by

  # Wards are within Chicago
  wards_in_chicago:
    parent: chicago
    child: ward
    relationship: contained_by

  # Townships are within Cook County (but Chicago spans multiple)
  townships_in_cook_county:
    parent: cook_county
    child: township
    relationship: contained_by

# Cross-Entity Mappings
# Pre-computed lookups for efficient joins
mappings:
  community_area_to_township:
    description: "Map Chicago community areas to Cook County townships"
    source: chicago_geospatial.dim_community_area
    target: cook_county_geospatial.dim_township
    method: spatial_intersection
    output: bridge_community_township
    notes: "Community areas may span multiple townships"

  parcel_to_community_area:
    description: "Map Cook County parcels to Chicago community areas"
    source: cook_county_geospatial.dim_parcel
    target: chicago_geospatial.dim_community_area
    method: point_in_polygon
    filter: "latitude IS NOT NULL AND longitude IS NOT NULL"
    output: bridge_parcel_community
    notes: "Only parcels within Chicago city limits"

# Schema
schema:
  bridges:
    bridge_community_township:
      description: "Bridge table linking community areas to townships"
      primary_key: [community_area, township_code]
      columns:
        community_area: {type: int, required: true}
        township_code: {type: string, required: true}
        intersection_area_sqmi: {type: double, description: "Area of intersection"}
        pct_community_in_township: {type: double, description: "% of community area in township"}
        pct_township_in_community: {type: double, description: "% of township in community area"}
        is_primary: {type: boolean, description: "Primary township for this community"}

    bridge_parcel_community:
      description: "Bridge table linking parcels to community areas"
      primary_key: [parcel_id]
      columns:
        parcel_id: {type: string, required: true, description: "14-digit PIN"}
        community_area: {type: int, description: "Community area number (null if outside Chicago)"}
        ward: {type: int, description: "Ward number (null if outside Chicago)"}
        is_chicago: {type: boolean, description: "Parcel is within Chicago city limits"}

# Graph
graph:
  nodes:
    bridge_community_township:
      from: computed
      type: bridge
      compute:
        method: spatial_intersection
        left: chicago_geospatial.dim_community_area
        right: cook_county_geospatial.dim_township
        left_geom: geometry
        right_geom: geometry
      unique_key: [community_area, township_code]

    bridge_parcel_community:
      from: computed
      type: bridge
      compute:
        method: point_in_polygon
        points: cook_county_geospatial.dim_parcel
        polygons: chicago_geospatial.dim_community_area
        point_lat: latitude
        point_lon: longitude
        polygon_geom: geometry
      derive:
        is_chicago: "community_area IS NOT NULL"
      unique_key: [parcel_id]

  edges:
    # Cross-entity joins enabled by bridge tables
    community_to_township:
      from: chicago_geospatial.dim_community_area
      to: cook_county_geospatial.dim_township
      through: bridge_community_township
      type: many_to_many
      description: "Community area to township(s)"

    parcel_to_community:
      from: cook_county_geospatial.dim_parcel
      to: chicago_geospatial.dim_community_area
      through: bridge_parcel_community
      type: many_to_one
      description: "Parcel to community area (Chicago only)"

# Spatial Operations (DuckDB + Sedona)
spatial:
  backend: duckdb_spatial
  fallback: sedona

  operations:
    point_in_polygon:
      description: "Assign points to containing polygon"
      sql_template: |
        SELECT
          p.*,
          poly.{polygon_id} as {output_column}
        FROM {points_table} p
        LEFT JOIN {polygons_table} poly
          ON ST_Contains(poly.{polygon_geom}, ST_Point(p.{point_lon}, p.{point_lat}))

    spatial_intersection:
      description: "Compute polygon intersection areas"
      sql_template: |
        SELECT
          a.{left_id},
          b.{right_id},
          ST_Area(ST_Intersection(a.{left_geom}, b.{right_geom})) as intersection_area,
          ST_Area(ST_Intersection(a.{left_geom}, b.{right_geom})) / ST_Area(a.{left_geom}) as pct_left_in_right,
          ST_Area(ST_Intersection(a.{left_geom}, b.{right_geom})) / ST_Area(b.{right_geom}) as pct_right_in_left
        FROM {left_table} a
        JOIN {right_table} b
          ON ST_Intersects(a.{left_geom}, b.{right_geom})

# Measures
measures:
  simple:
    chicago_parcel_count:
      description: "Parcels within Chicago"
      source: bridge_parcel_community.parcel_id
      aggregation: count
      filters:
        - "is_chicago = true"
      format: "#,##0"

    non_chicago_parcel_count:
      description: "Parcels outside Chicago"
      source: bridge_parcel_community.parcel_id
      aggregation: count
      filters:
        - "is_chicago = false"
      format: "#,##0"

# Metadata
metadata:
  domain: foundation
  entity: geospatial
  subdomain: containment
status: active
---

## Foundation Geospatial Model

Provides entity containment relationships and cross-entity geographic joins.

### Entity Hierarchy

```
Cook County (county)
│
├── Townships (38)
│   └── Property tax administration
│
├── Municipalities (130+)
│   ├── Chicago (city) ◄── This model provides containment logic
│   │   ├── Community Areas (77)
│   │   ├── Wards (50)
│   │   └── Police Districts/Beats
│   ├── Evanston
│   ├── Oak Park
│   └── ... (other suburbs)
│
└── Unincorporated Areas
```

### Purpose

This model provides:
1. **Containment relationships** - Chicago is within Cook County
2. **Bridge tables** - Pre-computed joins between entities
3. **Spatial operation templates** - DuckDB/Sedona SQL patterns

### Bridge Tables

**Why Bridge Tables?**

Point-in-polygon operations are expensive at query time. Instead, we pre-compute:
- Which parcels are in Chicago
- Which community areas overlap which townships
- Which ward a parcel belongs to

This allows efficient JOINs instead of runtime spatial operations.

### Cross-Entity Queries

**Property tax analysis for Chicago parcels:**
```sql
-- Get Chicago parcels with their assessed values
SELECT
    bp.community_area,
    ca.community_name,
    AVG(av.av_total) as avg_assessed_value,
    COUNT(*) as parcel_count
FROM cook_county_property.fact_assessed_values av
JOIN foundation_geospatial.bridge_parcel_community bp
    ON av.parcel_id = bp.parcel_id
JOIN chicago_geospatial.dim_community_area ca
    ON bp.community_area = ca.area_number
WHERE bp.is_chicago = true
  AND av.year = 2023
GROUP BY bp.community_area, ca.community_name;
```

**Township-level analysis for a community area:**
```sql
-- Which townships does Lincoln Park span?
SELECT
    bct.township_code,
    t.township_name,
    bct.pct_community_in_township
FROM foundation_geospatial.bridge_community_township bct
JOIN cook_county_geospatial.dim_township t
    ON bct.township_code = t.township_code
WHERE bct.community_area = 7  -- Lincoln Park
ORDER BY bct.pct_community_in_township DESC;
```

### Spatial Backend

**Primary**: DuckDB spatial extension
```sql
INSTALL spatial;
LOAD spatial;

SELECT ST_Contains(polygon, ST_Point(lon, lat));
```

**Fallback**: Apache Sedona (for large-scale Spark operations)
```python
from sedona.spark import SedonaContext
sedona = SedonaContext.create(spark)
```

### Build Process

The bridge tables are built during Silver layer construction:
1. Load source geometries
2. Run spatial operations
3. Persist bridge tables
4. Create indexes for efficient JOINs

**Note**: Building bridge tables can be slow for initial load but enables fast queries thereafter.
