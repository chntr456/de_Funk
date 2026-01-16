---
type: domain-model
model: chicago_public_safety
version: 1.0
description: "Chicago crime and arrest data"


# Dependencies
depends_on:
  - chicago_geospatial

# Schema Template Reference
schema_template: _schema/crime.md

# Storage
storage:
  root: storage/silver/chicago/public_safety
  format: delta

# Build
build:
  partitions: [year]
  optimize: true

# Sources
sources:
  crimes:
    bronze_table: chicago_crimes
    description: "Crime incidents 2001-present"
    column_mappings:
      incident_id: id
      incident_date: date
      crime_type: primary_type
      crime_subtype: description
      iucr_code: iucr
      fbi_code: fbi_code
      arrest_made: arrest
      domestic: domestic

  arrests:
    bronze_table: chicago_arrests
    description: "Arrest records"

  iucr_codes:
    bronze_table: chicago_iucr_codes
    description: "Illinois Uniform Crime Reporting codes"

# Schema
schema:
  dimensions:
    dim_crime_type:
      description: "Crime type dimension (IUCR + FBI codes)"
      primary_key: [crime_type_id]
      columns:
        crime_type_id: {type: string, required: true, description: "Composite key"}
        iucr_code: {type: string, description: "Illinois UCR code"}
        fbi_code: {type: string, description: "FBI UCR code"}
        primary_type: {type: string, description: "Primary crime type"}
        description: {type: string, description: "Crime description"}
        crime_category: {type: string, description: "Taxonomy level 1 (VIOLENT, PROPERTY, etc.)"}
        crime_subcategory: {type: string, description: "Taxonomy level 2"}
        is_index_crime: {type: boolean, description: "FBI Part I crime"}

    dim_location_type:
      description: "Location type dimension"
      primary_key: [location_type_id]
      columns:
        location_type_id: {type: string, required: true}
        location_description: {type: string}
        location_category: {type: string, description: "Grouped location type"}

  facts:
    fact_crimes:
      description: "Crime incidents fact table"
      primary_key: [incident_id]
      columns:
        incident_id: {type: string, required: true, description: "Unique crime identifier"}
        case_number: {type: string, description: "CPD case number"}
        incident_date: {type: timestamp, description: "Date/time of incident"}
        year: {type: int, description: "Year of incident"}
        crime_type_id: {type: string, description: "FK to dim_crime_type"}
        location_type_id: {type: string, description: "FK to dim_location_type"}
        block: {type: string, description: "Block-level address"}
        beat: {type: string, description: "Police beat"}
        district: {type: string, description: "Police district"}
        ward: {type: int, description: "City ward"}
        community_area: {type: int, description: "Community area number"}
        arrest_made: {type: boolean, description: "Whether arrest was made"}
        domestic: {type: boolean, description: "Domestic-related incident"}
        latitude: {type: double}
        longitude: {type: double}

    fact_arrests:
      description: "Arrest records fact table"
      primary_key: [arrest_id]
      columns:
        arrest_id: {type: string, required: true}
        arrest_date: {type: timestamp}
        crime_type_id: {type: string}
        beat: {type: string}
        district: {type: string}
        community_area: {type: int}

# Graph
graph:
  nodes:
    dim_crime_type:
      from: bronze.chicago_iucr_codes
      type: dimension
      derive:
        crime_type_id: "CONCAT(iucr, '_', COALESCE(fbi_code, 'UNK'))"
        crime_category: "CASE WHEN primary_type IN ('HOMICIDE', 'ASSAULT', 'BATTERY', 'ROBBERY') THEN 'VIOLENT' WHEN primary_type IN ('THEFT', 'BURGLARY', 'MOTOR VEHICLE THEFT') THEN 'PROPERTY' ELSE 'OTHER' END"
      unique_key: [crime_type_id]

    dim_location_type:
      from: bronze.chicago_crimes
      type: dimension
      transform: distinct
      columns: [location_description]
      derive:
        location_type_id: "MD5(COALESCE(location_description, 'UNKNOWN'))"
      unique_key: [location_type_id]

    fact_crimes:
      from: bronze.chicago_crimes
      type: fact
      derive:
        crime_type_id: "CONCAT(iucr, '_', COALESCE(fbi_code, 'UNK'))"
        location_type_id: "MD5(COALESCE(location_description, 'UNKNOWN'))"
      unique_key: [incident_id]

  edges:
    crime_to_type:
      from: fact_crimes
      to: dim_crime_type
      on: [crime_type_id=crime_type_id]
      type: many_to_one

    crime_to_location_type:
      from: fact_crimes
      to: dim_location_type
      on: [location_type_id=location_type_id]
      type: many_to_one

    crime_to_community_area:
      from: fact_crimes
      to: chicago_geospatial.dim_community_area
      on: [community_area=area_number]
      type: many_to_one
      description: "Crime to community area"

# Measures
measures:
  simple:
    crime_count:
      description: "Total crime incidents"
      source: fact_crimes.incident_id
      aggregation: count
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

  computed:
    arrest_rate:
      description: "Percentage of crimes resulting in arrest"
      formula: "arrest_count / crime_count * 100"
      format: "#,##0.0%"

    domestic_rate:
      description: "Percentage of domestic-related crimes"
      formula: "domestic_crime_count / crime_count * 100"
      format: "#,##0.0%"

# Metadata
metadata:
  domain: city
  entity: chicago
  subdomain: public_safety
status: active
---

## Chicago Public Safety Model

Crime and arrest data for the City of Chicago.

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

Uses `_schema/crime.md` template with Chicago-specific mappings:

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
```

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
WHERE c.year = 2023
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
```
