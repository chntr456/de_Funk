---
type: domain-base
base_name: crime
version: 3.0
description: "Base template for crime/public safety data across jurisdictions"
tags: [crime, public-safety, base, template]

# Base Tables
tables:
  dim_crime_type:
    type: dimension
    description: "Crime type classification dimension"
    primary_key: [crime_type_id]

    # Schema: [column, type, nullable, description, {options}]
    schema:
      # Keys - integer surrogate
      - [crime_type_id, integer, false, "PK - Integer surrogate", {derived: "ABS(HASH(CONCAT(iucr_code, '_', COALESCE(fbi_code, 'UNK'))))"}]

      # Crime classification
      - [iucr_code, string, true, "Illinois Uniform Crime Reporting code"]
      - [fbi_code, string, true, "FBI Uniform Crime Reporting code"]
      - [primary_type, string, false, "Primary crime type (e.g., THEFT, ASSAULT)"]
      - [description, string, true, "Detailed crime description"]
      - [crime_category, string, true, "High-level category (VIOLENT, PROPERTY, OTHER)"]
      - [crime_subcategory, string, true, "Subcategory for grouping"]
      - [is_index_crime, boolean, true, "FBI Part I (index) crime", {default: false}]

    measures:
      - [crime_type_count, count_distinct, crime_type_id, "Number of crime types", {format: "#,##0"}]

  dim_location_type:
    type: dimension
    description: "Location type dimension for crime locations"
    primary_key: [location_type_id]

    schema:
      - [location_type_id, integer, false, "PK - Integer surrogate", {derived: "ABS(HASH(location_description))"}]
      - [location_description, string, false, "Location description"]
      - [location_category, string, true, "Grouped location category"]

    measures:
      - [location_type_count, count_distinct, location_type_id, "Number of location types", {format: "#,##0"}]

  _fact_crimes_base:
    type: fact
    description: "Base crime incident fact table template"
    primary_key: [incident_id]
    partition_by: [date_id]

    schema:
      # Keys - integer surrogates
      - [incident_id, integer, false, "PK - Integer surrogate", {derived: "ABS(HASH(case_number))"}]
      - [crime_type_id, integer, false, "FK to dim_crime_type", {fk: dim_crime_type.crime_type_id}]
      - [location_type_id, integer, true, "FK to dim_location_type", {fk: dim_location_type.location_type_id}]
      - [date_id, integer, false, "FK to dim_calendar", {fk: temporal.dim_calendar.date_id}]
      - [location_id, integer, true, "FK to geospatial.dim_location", {fk: geospatial.dim_location.location_id}]

      # Incident identifiers
      - [case_number, string, true, "Police case number", {unique: true}]
      - [year, integer, false, "Incident year (for partitioning)"]

      # Geographic
      - [block, string, true, "Block-level address"]
      - [beat, string, true, "Police beat"]
      - [district, string, true, "Police district"]
      - [ward, integer, true, "Political ward"]
      - [community_area, integer, true, "Community area number"]
      - [latitude, double, true, "Latitude coordinate"]
      - [longitude, double, true, "Longitude coordinate"]

      # Flags
      - [arrest_made, boolean, true, "Whether arrest was made", {default: false}]
      - [domestic, boolean, true, "Domestic-related incident", {default: false}]

    measures:
      - [crime_count, count_distinct, incident_id, "Total crime incidents", {format: "#,##0"}]
      - [arrest_count, expression, "SUM(CASE WHEN arrest_made THEN 1 ELSE 0 END)", "Crimes with arrest", {format: "#,##0"}]
      - [domestic_count, expression, "SUM(CASE WHEN domestic THEN 1 ELSE 0 END)", "Domestic crimes", {format: "#,##0"}]
      - [arrest_rate, expression, "100.0 * SUM(CASE WHEN arrest_made THEN 1 ELSE 0 END) / COUNT(*)", "Arrest rate %", {format: "#,##0.0%"}]

  _fact_arrests_base:
    type: fact
    description: "Base arrest record fact table template"
    primary_key: [arrest_id]
    partition_by: [date_id]

    schema:
      - [arrest_id, integer, false, "PK - Integer surrogate"]
      - [incident_id, integer, true, "FK to fact_crimes", {fk: _fact_crimes_base.incident_id}]
      - [crime_type_id, integer, false, "FK to dim_crime_type", {fk: dim_crime_type.crime_type_id}]
      - [date_id, integer, false, "FK to dim_calendar", {fk: temporal.dim_calendar.date_id}]
      - [location_id, integer, true, "FK to geospatial.dim_location", {fk: geospatial.dim_location.location_id}]
      - [beat, string, true, "Police beat"]
      - [district, string, true, "Police district"]
      - [community_area, integer, true, "Community area number"]

    measures:
      - [total_arrests, count_distinct, arrest_id, "Total arrests", {format: "#,##0"}]

# Graph Templates
graph:
  nodes:
    dim_crime_type:
      type: dimension
      description: "Crime type dimension populated from IUCR codes or similar"
      derive:
        crime_type_id: "ABS(HASH(CONCAT(iucr_code, '_', COALESCE(fbi_code, 'UNK'))))"
        crime_category: "CASE WHEN primary_type IN ('HOMICIDE', 'ASSAULT', 'BATTERY', 'ROBBERY') THEN 'VIOLENT' WHEN primary_type IN ('THEFT', 'BURGLARY', 'MOTOR VEHICLE THEFT') THEN 'PROPERTY' ELSE 'OTHER' END"
      primary_key: [crime_type_id]
      unique_key: [iucr_code, fbi_code]
      tags: [dim, crime]

    dim_location_type:
      type: dimension
      description: "Location type dimension from distinct location descriptions"
      derive:
        location_type_id: "ABS(HASH(location_description))"
      primary_key: [location_type_id]
      unique_key: [location_description]
      tags: [dim, location]

    _fact_crimes_base:
      type: fact
      description: "Base crime facts template"
      derive:
        crime_type_id: "ABS(HASH(CONCAT(iucr, '_', COALESCE(fbi_code, 'UNK'))))"
        location_type_id: "ABS(HASH(COALESCE(location_description, 'UNKNOWN')))"
        date_id: "CAST(DATE_FORMAT(incident_date, 'yyyyMMdd') AS INT)"
        incident_id: "ABS(HASH(case_number))"
      primary_key: [incident_id]
      unique_key: [case_number]
      foreign_keys:
        - {column: crime_type_id, references: dim_crime_type.crime_type_id}
        - {column: location_type_id, references: dim_location_type.location_type_id}
        - {column: date_id, references: temporal.dim_calendar.date_id}
      tags: [fact, crime]

  edges:
    crime_to_type:
      from: _fact_crimes_base
      to: dim_crime_type
      on: [crime_type_id=crime_type_id]
      type: many_to_one

    crime_to_location_type:
      from: _fact_crimes_base
      to: dim_location_type
      on: [location_type_id=location_type_id]
      type: many_to_one

    crime_to_calendar:
      from: _fact_crimes_base
      to: temporal.dim_calendar
      on: [date_id=date_id]
      type: many_to_one
      cross_model: temporal

# Metadata
domain: public_safety
tags: [base, template, crime]
status: active
---

## Base Crime Template

Reusable base template for crime/public safety data with integer surrogate keys.

### Key Design

All keys are **integers** for storage efficiency:

| Key | Type | Derivation |
|-----|------|------------|
| `crime_type_id` | integer | `HASH(iucr + fbi_code)` |
| `location_type_id` | integer | `HASH(location_description)` |
| `date_id` | integer | `YYYYMMDD` format |
| `incident_id` | integer | `HASH(case_number)` |

### Crime Categories

Standard taxonomy:

```
VIOLENT
├── HOMICIDE
├── ASSAULT
├── BATTERY
└── ROBBERY

PROPERTY
├── THEFT
├── BURGLARY
└── MOTOR VEHICLE THEFT

OTHER
└── All remaining types
```

### Inheritance

City-specific models inherit using `extends`:

```yaml
# In city/chicago/public_safety.md
extends: _base.crime

tables:
  fact_crimes:
    extends: _base.crime._fact_crimes_base
    # Add Chicago-specific columns...
```

### Models Using This Base

- `chicago_public_safety` - Chicago crime data
- (future) `nyc_public_safety` - NYC crime data
- (future) `la_public_safety` - LA crime data
