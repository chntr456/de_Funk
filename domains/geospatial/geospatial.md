---
type: domain-model
model: geospatial
version: 3.0
description: "Geographic and location dimensions - foundation for spatial analysis"
tags: [geography, location, foundation, shared]

# Inheritance - extends base geospatial template
extends: _base.geospatial.geospatial

# Dependencies
depends_on: []  # Foundation model - no dependencies

# Storage
storage:
  root: storage/silver/geospatial
  format: delta

# Build
build:
  partitions: []
  sort_by: [location_id]
  optimize: true

# Tables
tables:
  dim_location:
    type: dimension
    description: "Master location dimension - geographic hierarchy"
    primary_key: [location_id]

    # Schema: [column, type, nullable, description, {options}]
    schema:
      # Keys - integer
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

      # Attributes
      - [population, long, true, "Population estimate"]
      - [land_area_sqmi, double, true, "Land area in square miles"]
      - [timezone, string, true, "IANA timezone"]

    # Measures on the table
    measures:
      - [location_count, count_distinct, location_id, "Number of locations", {format: "#,##0"}]
      - [total_population, sum, population, "Total population", {format: "#,##0"}]
      - [avg_population, avg, population, "Average population", {format: "#,##0"}]

  dim_state:
    type: dimension
    description: "US States dimension"
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

  dim_county:
    type: dimension
    description: "US Counties dimension"
    primary_key: [county_id]

    schema:
      - [county_id, integer, false, "PK - Integer surrogate", {derived: "ABS(HASH(CONCAT('COUNTY_', county_fips)))"}]
      - [state_id, integer, false, "FK to dim_state", {fk: dim_state.state_id}]
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

  dim_city:
    type: dimension
    description: "Cities dimension"
    primary_key: [city_id]

    schema:
      - [city_id, integer, false, "PK - Integer surrogate", {derived: "ABS(HASH(CONCAT('CITY_', city_code)))"}]
      - [state_id, integer, true, "FK to dim_state", {fk: dim_state.state_id}]
      - [county_id, integer, true, "FK to dim_county", {fk: dim_county.county_id}]
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

# Graph
graph:
  nodes:
    dim_location:
      from: self  # Can be loaded from various sources or generated
      type: dimension
      primary_key: [location_id]
      tags: [dim, location, master]

    dim_state:
      from: bronze.us_states  # Or census data source
      type: dimension
      primary_key: [state_id]
      unique_key: [state_fips]
      tags: [dim, state]

    dim_county:
      from: bronze.us_counties
      type: dimension
      primary_key: [county_id]
      unique_key: [county_fips]
      foreign_keys:
        - {column: state_id, references: dim_state.state_id}
      tags: [dim, county]

    dim_city:
      from: bronze.us_cities
      type: dimension
      primary_key: [city_id]
      unique_key: [city_code]
      foreign_keys:
        - {column: state_id, references: dim_state.state_id}
        - {column: county_id, references: dim_county.county_id}
      tags: [dim, city]

  edges:
    county_to_state:
      from: dim_county
      to: dim_state
      on: [state_id=state_id]
      type: many_to_one

    city_to_state:
      from: dim_city
      to: dim_state
      on: [state_id=state_id]
      type: many_to_one

    city_to_county:
      from: dim_city
      to: dim_county
      on: [county_id=county_id]
      type: many_to_one

# Metadata
metadata:
  domain: geospatial
  owner: data_engineering
  sla_hours: 24
status: active
---

## Geospatial Model

Foundation model providing geographic dimensions for spatial analysis.

### Geographic Hierarchy

```
dim_state (50 states + territories)
    └── dim_county (3,143 counties)
            └── dim_city (cities)
                    └── dim_location (any level)
```

### Integer Keys

| Key | Type | Derivation |
|-----|------|------------|
| `location_id` | integer | `HASH(type + code)` |
| `state_id` | integer | `HASH('STATE_' + fips)` |
| `county_id` | integer | `HASH('COUNTY_' + fips)` |
| `city_id` | integer | `HASH('CITY_' + code)` |

### Cross-Model Usage

Other models join to geospatial for location filtering:

```yaml
# In chicago domain config
edges:
  crime_to_location:
    from: fact_crime
    to: geospatial.dim_location
    on: [location_id=location_id]
    type: many_to_one
```

### Query Pattern

```sql
-- Get data with geographic context
SELECT
    c.city_name,
    s.state_abbr,
    f.total_value
FROM fact_something f
JOIN geospatial.dim_city c ON f.city_id = c.city_id
JOIN geospatial.dim_state s ON c.state_id = s.state_id
WHERE s.state_abbr = 'IL'
```

### Notes

- Foundation model with no dependencies
- Other models link TO geospatial via location FKs
- Supports multiple geographic levels
- FIPS codes used as natural keys
