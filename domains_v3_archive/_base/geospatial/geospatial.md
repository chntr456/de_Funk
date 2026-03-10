---
type: domain-base
base_name: geospatial
version: 3.0
description: "Base template for geographic/location dimensions"
tags: [geography, location, geospatial, base, template]

# Base Tables
tables:
  dim_location:
    type: dimension
    description: "Master location dimension template - hierarchical geography"
    primary_key: [location_id]

    # Schema: [column, type, nullable, description, {options}]
    schema:
      # Keys - integer surrogate
      - [location_id, integer, false, "PK - Integer surrogate", {derived: "ABS(HASH(CONCAT(location_type, '_', location_code)))"}]

      # Location identifiers
      - [location_type, string, false, "Type: country, state, county, city, zip, tract, block", {enum: [country, state, county, city, zip, census_tract, block]}]
      - [location_code, string, false, "Unique code within type (FIPS, ZIP, etc.)"]
      - [location_name, string, false, "Display name"]

      # Hierarchy (nullable - depends on level)
      - [country_code, string, true, "ISO 3166-1 alpha-2 country code"]
      - [state_code, string, true, "FIPS state code (2 digits)"]
      - [county_code, string, true, "FIPS county code (3 digits)"]
      - [city_code, string, true, "City identifier"]
      - [zip_code, string, true, "ZIP/postal code"]
      - [census_tract, string, true, "Census tract code"]

      # Geographic coordinates
      - [latitude, double, true, "Centroid latitude"]
      - [longitude, double, true, "Centroid longitude"]
      - [geom_wkt, string, true, "Geometry as WKT (Well-Known Text)"]

      # Common attributes
      - [population, long, true, "Population estimate"]
      - [land_area_sqmi, double, true, "Land area in square miles"]
      - [timezone, string, true, "IANA timezone"]

    measures:
      - [location_count, count_distinct, location_id, "Number of locations", {format: "#,##0"}]
      - [total_population, sum, population, "Total population", {format: "#,##0"}]
      - [avg_population, avg, population, "Average population", {format: "#,##0"}]

  _dim_state_base:
    type: dimension
    description: "State/Province dimension template"
    primary_key: [state_id]

    schema:
      - [state_id, integer, false, "PK - Integer surrogate", {derived: "ABS(HASH(CONCAT('STATE_', state_fips)))"}]
      - [state_fips, string, false, "FIPS state code (2 digits)", {unique: true}]
      - [state_abbr, string, false, "State abbreviation (2 letters)"]
      - [state_name, string, false, "Full state name"]
      - [region, string, true, "Census region"]
      - [division, string, true, "Census division"]
      - [latitude, double, true, "Centroid latitude"]
      - [longitude, double, true, "Centroid longitude"]

    measures:
      - [state_count, count_distinct, state_id, "Number of states", {format: "#,##0"}]

  _dim_county_base:
    type: dimension
    description: "County dimension template"
    primary_key: [county_id]

    schema:
      - [county_id, integer, false, "PK - Integer surrogate", {derived: "ABS(HASH(CONCAT('COUNTY_', county_fips)))"}]
      - [state_id, integer, false, "FK to dim_state", {fk: _dim_state_base.state_id}]
      - [county_fips, string, false, "Full FIPS code (5 digits)", {unique: true}]
      - [county_name, string, false, "County name"]
      - [state_fips, string, false, "State FIPS (2 digits)"]
      - [latitude, double, true, "Centroid latitude"]
      - [longitude, double, true, "Centroid longitude"]
      - [population, long, true, "Population estimate"]
      - [land_area_sqmi, double, true, "Land area in square miles"]

    measures:
      - [county_count, count_distinct, county_id, "Number of counties", {format: "#,##0"}]
      - [total_county_pop, sum, population, "Total county population", {format: "#,##0"}]

  _dim_city_base:
    type: dimension
    description: "City dimension template"
    primary_key: [city_id]

    schema:
      - [city_id, integer, false, "PK - Integer surrogate", {derived: "ABS(HASH(CONCAT('CITY_', city_code)))"}]
      - [state_id, integer, true, "FK to dim_state", {fk: _dim_state_base.state_id}]
      - [county_id, integer, true, "FK to dim_county", {fk: _dim_county_base.county_id}]
      - [city_code, string, false, "Unique city identifier", {unique: true}]
      - [city_name, string, false, "City name"]
      - [state_abbr, string, true, "State abbreviation"]
      - [latitude, double, true, "Centroid latitude"]
      - [longitude, double, true, "Centroid longitude"]
      - [population, long, true, "Population estimate"]
      - [timezone, string, true, "IANA timezone"]

    measures:
      - [city_count, count_distinct, city_id, "Number of cities", {format: "#,##0"}]
      - [total_city_pop, sum, population, "Total city population", {format: "#,##0"}]

# Graph Templates
graph:
  nodes:
    dim_location:
      type: dimension
      primary_key: [location_id]
      unique_key: [location_type, location_code]
      tags: [dim, location, master]

    _dim_state_base:
      type: dimension
      primary_key: [state_id]
      unique_key: [state_fips]
      tags: [dim, state]

    _dim_county_base:
      type: dimension
      primary_key: [county_id]
      unique_key: [county_fips]
      foreign_keys:
        - {column: state_id, references: _dim_state_base.state_id}
      tags: [dim, county]

    _dim_city_base:
      type: dimension
      primary_key: [city_id]
      unique_key: [city_code]
      foreign_keys:
        - {column: state_id, references: _dim_state_base.state_id}
        - {column: county_id, references: _dim_county_base.county_id}
      tags: [dim, city]

  edges:
    county_to_state:
      from: _dim_county_base
      to: _dim_state_base
      on: [state_id=state_id]
      type: many_to_one

    city_to_state:
      from: _dim_city_base
      to: _dim_state_base
      on: [state_id=state_id]
      type: many_to_one

    city_to_county:
      from: _dim_city_base
      to: _dim_county_base
      on: [county_id=county_id]
      type: many_to_one

# Metadata
domain: geospatial
tags: [base, template, geography, location]
status: active
---

## Base Geospatial Template

Reusable base template for geographic/location dimensions with integer surrogate keys.

### Key Design

All keys are **integers** for storage efficiency:

| Key | Type | Derivation |
|-----|------|------------|
| `location_id` | integer | `HASH(type + code)` |
| `state_id` | integer | `HASH('STATE_' + fips)` |
| `county_id` | integer | `HASH('COUNTY_' + fips)` |
| `city_id` | integer | `HASH('CITY_' + code)` |

### Geographic Hierarchy

Standard US hierarchy:

```
Country (US)
└── State (50 + territories)
    └── County (3,143)
        └── City
            └── Census Tract
                └── Block
```

### Extension Points

City-specific models can extend with local geography:
- Community Areas (Chicago - 77)
- Police Districts
- School Districts
- Legislative Districts

```yaml
# In municipal/chicago/geospatial.md
extends: _base.geospatial

tables:
  dim_community_area:
    type: dimension
    schema:
      - [community_area_id, integer, false, "PK", {derived: "ABS(HASH(...))"}]
      - [area_number, integer, false, "Community area number"]
      - [community_name, string, false, "Name"]
```

### Cross-Model Usage

Other models join to geospatial for location filtering:

```yaml
# In domain model
edges:
  fact_to_location:
    from: fact_table
    to: geospatial.dim_location
    on: [location_id=location_id]
    type: many_to_one
    cross_model: geospatial
```

### Spatial Operations

Geometry stored as WKT for DuckDB spatial extension:

```sql
-- Point-in-polygon
SELECT location_name
FROM dim_location
WHERE ST_Contains(ST_GeomFromText(geom_wkt), ST_Point(-87.6, 41.8));
```
