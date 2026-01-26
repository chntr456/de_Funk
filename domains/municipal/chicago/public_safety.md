---
type: domain-model
model: chicago_public_safety
version: 3.0
description: "Chicago crime and arrest data - extends base crime domain"
tags: [crime, public-safety, chicago, municipal]

# Inheritance
extends: _base.public_safety.crime

# Dependencies
depends_on:
  - temporal
  - geospatial
  - chicago_geospatial

# Storage
storage:
  root: storage/silver/chicago/public_safety
  format: delta

# Build
build:
  partitions: [year]
  sort_by: [date_id, incident_id]
  optimize: true

# Sources
sources:
  crimes:
    bronze_table: chicago_crimes
    description: "Crime incidents 2001-present"

  arrests:
    bronze_table: chicago_arrests
    description: "Arrest records"

  iucr_codes:
    bronze_table: chicago_iucr_codes
    description: "Illinois Uniform Crime Reporting codes"

# Tables - extend base crime tables with Chicago-specific additions
tables:
  dim_crime_type:
    extends: _base.public_safety.crime.dim_crime_type
    # Inherits: crime_type_id, iucr_code, fbi_code, primary_type, description,
    #           crime_category, crime_subcategory, is_index_crime
    # No additional columns needed - base schema is sufficient

  dim_location_type:
    extends: _base.public_safety.crime.dim_location_type
    # Inherits: location_type_id, location_description, location_category
    # No additional columns needed

  fact_crimes:
    extends: _base.public_safety.crime._fact_crimes_base
    type: fact
    description: "Chicago crime incidents fact table"
    primary_key: [incident_id]
    partition_by: [year]

    # Schema extends base with Chicago-specific columns
    schema:
      # Keys - inherited from base
      - [incident_id, integer, false, "PK - Integer surrogate", {derived: "ABS(HASH(case_number))"}]
      - [crime_type_id, integer, false, "FK to dim_crime_type", {fk: dim_crime_type.crime_type_id}]
      - [location_type_id, integer, true, "FK to dim_location_type", {fk: dim_location_type.location_type_id}]
      - [date_id, integer, false, "FK to dim_calendar", {fk: temporal.dim_calendar.date_id}]
      - [location_id, integer, true, "FK to geospatial.dim_location", {fk: geospatial.dim_location.location_id}]

      # Chicago-specific identifiers
      - [case_number, string, true, "CPD case number", {unique: true}]
      - [year, integer, false, "Incident year (for partitioning)"]

      # Chicago geographic (inherited pattern from base)
      - [block, string, true, "Block-level address"]
      - [beat, string, true, "Police beat"]
      - [district, string, true, "Police district"]
      - [ward, integer, true, "City ward"]
      - [community_area, integer, true, "Community area number"]
      - [latitude, double, true, "Latitude coordinate"]
      - [longitude, double, true, "Longitude coordinate"]

      # Flags (inherited from base)
      - [arrest_made, boolean, true, "Whether arrest was made", {default: false}]
      - [domestic, boolean, true, "Domestic-related incident", {default: false}]

      # Chicago-specific additions
      - [updated_on, timestamp, true, "Last data update timestamp"]

    measures:
      - [crime_count, count_distinct, incident_id, "Total crime incidents", {format: "#,##0"}]
      - [arrest_count, expression, "SUM(CASE WHEN arrest_made THEN 1 ELSE 0 END)", "Crimes with arrest", {format: "#,##0"}]
      - [domestic_count, expression, "SUM(CASE WHEN domestic THEN 1 ELSE 0 END)", "Domestic crimes", {format: "#,##0"}]
      - [arrest_rate, expression, "100.0 * SUM(CASE WHEN arrest_made THEN 1 ELSE 0 END) / COUNT(*)", "Arrest rate %", {format: "#,##0.0%"}]

  fact_arrests:
    extends: _base.public_safety.crime._fact_arrests_base
    type: fact
    description: "Chicago arrest records fact table"
    primary_key: [arrest_id]
    partition_by: [year]

    schema:
      - [arrest_id, integer, false, "PK - Integer surrogate", {derived: "ABS(HASH(arrest_key))"}]
      - [incident_id, integer, true, "FK to fact_crimes", {fk: fact_crimes.incident_id}]
      - [crime_type_id, integer, false, "FK to dim_crime_type", {fk: dim_crime_type.crime_type_id}]
      - [date_id, integer, false, "FK to dim_calendar", {fk: temporal.dim_calendar.date_id}]
      - [location_id, integer, true, "FK to geospatial.dim_location", {fk: geospatial.dim_location.location_id}]

      # Chicago geographic
      - [beat, string, true, "Police beat"]
      - [district, string, true, "Police district"]
      - [community_area, integer, true, "Community area number"]
      - [year, integer, false, "Arrest year (for partitioning)"]

      # Arrest-specific
      - [arrest_key, string, true, "Unique arrest identifier", {unique: true}]

    measures:
      - [total_arrests, count_distinct, arrest_id, "Total arrests", {format: "#,##0"}]

# Graph - extend base with Chicago-specific sources and edges
graph:
  extends: _base.public_safety.crime.graph

  nodes:
    dim_crime_type:
      extends: _base.public_safety.crime.dim_crime_type
      from: bronze.chicago_iucr_codes
      type: dimension
      derive:
        crime_type_id: "ABS(HASH(CONCAT(iucr, '_', COALESCE(fbi_code, 'UNK'))))"
        crime_category: "CASE WHEN primary_type IN ('HOMICIDE', 'ASSAULT', 'BATTERY', 'ROBBERY') THEN 'VIOLENT' WHEN primary_type IN ('THEFT', 'BURGLARY', 'MOTOR VEHICLE THEFT') THEN 'PROPERTY' ELSE 'OTHER' END"
      primary_key: [crime_type_id]
      unique_key: [iucr_code, fbi_code]
      tags: [dim, crime, chicago]

    dim_location_type:
      extends: _base.public_safety.crime.dim_location_type
      from: bronze.chicago_crimes
      type: dimension
      transform: distinct
      columns: [location_description]
      derive:
        location_type_id: "ABS(HASH(COALESCE(location_description, 'UNKNOWN')))"
      primary_key: [location_type_id]
      unique_key: [location_description]
      tags: [dim, location, chicago]

    fact_crimes:
      extends: _base.public_safety.crime._fact_crimes_base
      from: bronze.chicago_crimes
      type: fact
      derive:
        incident_id: "ABS(HASH(case_number))"
        crime_type_id: "ABS(HASH(CONCAT(iucr, '_', COALESCE(fbi_code, 'UNK'))))"
        location_type_id: "ABS(HASH(COALESCE(location_description, 'UNKNOWN')))"
        date_id: "CAST(DATE_FORMAT(date, 'yyyyMMdd') AS INT)"
      primary_key: [incident_id]
      unique_key: [case_number]
      foreign_keys:
        - {column: crime_type_id, references: dim_crime_type.crime_type_id}
        - {column: location_type_id, references: dim_location_type.location_type_id}
        - {column: date_id, references: temporal.dim_calendar.date_id}
      tags: [fact, crime, chicago]

    fact_arrests:
      extends: _base.public_safety.crime._fact_arrests_base
      from: bronze.chicago_arrests
      type: fact
      derive:
        arrest_id: "ABS(HASH(arrest_key))"
        date_id: "CAST(DATE_FORMAT(arrest_date, 'yyyyMMdd') AS INT)"
        crime_type_id: "ABS(HASH(CONCAT(iucr, '_', COALESCE(fbi_code, 'UNK'))))"
      primary_key: [arrest_id]
      unique_key: [arrest_key]
      foreign_keys:
        - {column: crime_type_id, references: dim_crime_type.crime_type_id}
        - {column: date_id, references: temporal.dim_calendar.date_id}
      tags: [fact, arrest, chicago]

  edges:
    # Inherited from base: crime_to_type, crime_to_location_type, crime_to_calendar

    # Chicago-specific edges
    crime_to_community_area:
      from: fact_crimes
      to: chicago_geospatial.dim_community_area
      on: [community_area=area_number]
      type: many_to_one
      description: "Crime to community area"

    crime_to_ward:
      from: fact_crimes
      to: chicago_geospatial.dim_ward
      on: [ward=ward_number]
      type: many_to_one
      description: "Crime to ward"

    crime_to_district:
      from: fact_crimes
      to: chicago_geospatial.dim_police_district
      on: [district=district_number]
      type: many_to_one
      description: "Crime to police district"

    arrest_to_crime_type:
      from: fact_arrests
      to: dim_crime_type
      on: [crime_type_id=crime_type_id]
      type: many_to_one

    arrest_to_calendar:
      from: fact_arrests
      to: temporal.dim_calendar
      on: [date_id=date_id]
      type: many_to_one
      cross_model: temporal

# Measures - extend base measures with Chicago-specific
measures:
  simple:
    crime_count:
      description: "Total crime incidents"
      source: fact_crimes.incident_id
      aggregation: count_distinct
      format: "#,##0"

    arrest_count:
      description: "Crimes resulting in arrest"
      source: fact_crimes.incident_id
      aggregation: count
      filters:
        - "arrest_made = true"
      format: "#,##0"

    domestic_crime_count:
      description: "Domestic-related crimes"
      source: fact_crimes.incident_id
      aggregation: count
      filters:
        - "domestic = true"
      format: "#,##0"

    total_arrests:
      description: "Total arrest records"
      source: fact_arrests.arrest_id
      aggregation: count_distinct
      format: "#,##0"

  computed:
    arrest_rate:
      description: "Percentage of crimes resulting in arrest"
      formula: "arrest_count / crime_count * 100"
      format: "#,##0.1%"

    domestic_rate:
      description: "Percentage of domestic-related crimes"
      formula: "domestic_crime_count / crime_count * 100"
      format: "#,##0.1%"

# Metadata
metadata:
  domain: municipal
  entity: chicago
  subdomain: public_safety
  owner: data_engineering
  sla_hours: 24
status: active
---

## Chicago Public Safety Model

Crime and arrest data for the City of Chicago, extending the base crime domain.

### Inheritance

This model extends `_base.crime` to reuse standard crime data structures:
- Integer surrogate keys (`crime_type_id`, `incident_id`, etc.)
- Standard crime taxonomy (VIOLENT, PROPERTY, OTHER)
- Base measures (crime_count, arrest_rate)
- FK pattern using `date_id` instead of date columns

### Data Sources

| Source | Bronze Table | Description |
|--------|--------------|-------------|
| Crimes | chicago_crimes | Incidents 2001-present |
| Arrests | chicago_arrests | Arrest records |
| IUCR Codes | chicago_iucr_codes | Crime classification |

### Crime Classification

Chicago uses dual classification:
- **IUCR** (Illinois Uniform Crime Reporting) - State-level codes
- **FBI UCR** - Federal classification for national comparison

### Crime Taxonomy

Standard taxonomy from base crime domain:

```
VIOLENT
├── HOMICIDE (IUCR 0110-0142)
├── ASSAULT (IUCR 0510-0558)
├── BATTERY (IUCR 0460-0497)
└── ROBBERY (IUCR 0310-0337)

PROPERTY
├── THEFT (IUCR 0810-0870)
├── BURGLARY (IUCR 0610-0650)
└── MOTOR VEHICLE THEFT (IUCR 0910-0930)

OTHER
└── All remaining types
```

### Chicago-Specific Extensions

This model adds Chicago geographic dimensions:
- **Community Areas** (77) - Stable neighborhood boundaries
- **Wards** (50) - Political districts
- **Police Districts** (22) - CPD administrative areas
- **Police Beats** (~280) - Patrol areas

### Privacy Notes

- Addresses shown at block level only
- Specific locations not identified
- Most recent 7 days excluded from data

### Example Queries

```sql
-- Crimes by community area
SELECT
    ca.community_name,
    ct.crime_category,
    COUNT(*) as crime_count
FROM fact_crimes c
JOIN dim_crime_type ct ON c.crime_type_id = ct.crime_type_id
JOIN chicago_geospatial.dim_community_area ca ON c.community_area = ca.area_number
JOIN temporal.dim_calendar d ON c.date_id = d.date_id
WHERE d.calendar_year = 2023
GROUP BY ca.community_name, ct.crime_category;

-- Arrest rate by crime type
SELECT
    ct.primary_type,
    COUNT(*) as total_crimes,
    SUM(CASE WHEN c.arrest_made THEN 1 ELSE 0 END) as arrests,
    ROUND(100.0 * SUM(CASE WHEN c.arrest_made THEN 1 ELSE 0 END) / COUNT(*), 1) as arrest_rate
FROM fact_crimes c
JOIN dim_crime_type ct ON c.crime_type_id = ct.crime_type_id
GROUP BY ct.primary_type
ORDER BY total_crimes DESC;

-- Monthly crime trends
SELECT
    d.year_month,
    ct.crime_category,
    COUNT(*) as incidents
FROM fact_crimes c
JOIN temporal.dim_calendar d ON c.date_id = d.date_id
JOIN dim_crime_type ct ON c.crime_type_id = ct.crime_type_id
GROUP BY d.year_month, ct.crime_category
ORDER BY d.year_month;
```

### Related Models

- **chicago_geospatial** - Geographic dimensions (community areas, wards, districts)
- **temporal** - Calendar dimension for time-series analysis
- **geospatial** - Foundation geographic model
