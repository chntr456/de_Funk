---
type: domain-model
model: cook_county_geospatial
version: 1.0
description: "Cook County geospatial boundaries and hierarchies"


# Dependencies
depends_on: []  # Foundation geospatial model

# Storage
storage:
  root: storage/silver/cook_county/geospatial
  format: delta

# Build
build:
  partitions: []
  optimize: true

# Sources
sources:
  townships:
    bronze_table: cook_county_townships
    description: "Township boundaries"

  municipalities:
    bronze_table: cook_county_municipalities
    description: "Municipality boundaries (cities, villages)"

  neighborhoods:
    bronze_table: cook_county_neighborhoods
    description: "Assessor neighborhood boundaries"

  parcel_proximity:
    bronze_table: cook_county_parcel_proximity
    description: "Parcel proximity to amenities"

# Schema
schema:
  dimensions:
    dim_township:
      description: "Cook County townships (38 townships)"
      primary_key: [township_code]
      columns:
        township_code: {type: string, required: true, description: "2-digit township code"}
        township_name: {type: string, description: "Township name"}
        geometry: {type: geometry, description: "Township boundary polygon"}
        centroid_lat: {type: double, description: "Centroid latitude"}
        centroid_lon: {type: double, description: "Centroid longitude"}
        area_sqmi: {type: double, description: "Area in square miles"}

    dim_municipality:
      description: "Municipalities within Cook County"
      primary_key: [municipality_id]
      columns:
        municipality_id: {type: string, required: true}
        municipality_name: {type: string, description: "City/village name"}
        municipality_type: {type: string, description: "city, village, town, unincorporated"}
        township_code: {type: string, description: "Primary township"}
        geometry: {type: geometry, description: "Municipality boundary"}
        area_sqmi: {type: double}
        is_chicago: {type: boolean, description: "Is City of Chicago"}

    dim_neighborhood:
      description: "Assessor neighborhoods (for valuation)"
      primary_key: [nbhd_code]
      columns:
        nbhd_code: {type: string, required: true, description: "Neighborhood code"}
        nbhd_name: {type: string, description: "Neighborhood name"}
        township_code: {type: string}
        geometry: {type: geometry}

# Graph
graph:
  nodes:
    dim_township:
      from: bronze.cook_county_townships
      type: dimension
      unique_key: [township_code]

    dim_municipality:
      from: bronze.cook_county_municipalities
      type: dimension
      derive:
        is_chicago: "municipality_name = 'Chicago'"
      unique_key: [municipality_id]

    dim_neighborhood:
      from: bronze.cook_county_neighborhoods
      type: dimension
      unique_key: [nbhd_code]

  edges:
    municipality_to_township:
      from: dim_municipality
      to: dim_township
      on: [township_code=township_code]
      type: many_to_one
      description: "Municipality's primary township"

    neighborhood_to_township:
      from: dim_neighborhood
      to: dim_township
      on: [township_code=township_code]
      type: many_to_one

# Measures
measures:
  simple:
    township_count:
      description: "Number of townships"
      source: dim_township.township_code
      aggregation: count_distinct
      format: "#,##0"

    municipality_count:
      description: "Number of municipalities"
      source: dim_municipality.municipality_id
      aggregation: count_distinct
      format: "#,##0"

    total_area_sqmi:
      description: "Total area in square miles"
      source: dim_township.area_sqmi
      aggregation: sum
      format: "#,##0.0"

# Metadata
metadata:
  domain: county
  entity: cook_county
  subdomain: geospatial
status: active
---

## Cook County Geospatial Model

Geographic boundaries and hierarchies for Cook County.

### Geographic Units

| Unit | Count | Description |
|------|-------|-------------|
| Townships | 38 | Property tax administration units |
| Municipalities | 130+ | Cities, villages, towns |
| Neighborhoods | ~200 | Assessor valuation areas |

### Hierarchy

```
Cook County
├── Townships (38)
│   ├── Municipalities (within township)
│   │   └── Chicago (spans multiple townships)
│   └── Unincorporated areas
└── Neighborhoods (Assessor defined)
```

### Spatial Operations

Uses DuckDB spatial extension:

```sql
-- Find township for a point
SELECT t.township_name
FROM dim_township t
WHERE ST_Contains(t.geometry, ST_Point(-87.6298, 41.8781));

-- Parcels in a township
SELECT p.*
FROM dim_parcel p
JOIN dim_township t ON p.township_code = t.township_code
WHERE t.township_name = 'Lake';
```

### Notes

- Chicago spans multiple townships (unique case)
- Township boundaries are stable (property tax admin)
- Neighborhoods are Assessor-defined for valuation comparables
