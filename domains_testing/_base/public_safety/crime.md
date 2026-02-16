---
type: domain-base
base_name: crime
namespace: _base.public_safety.crime
version: 3.0
description: "Base template for crime/incident data across jurisdictions"
extends: _base.event

canonical_fields:
  - [incident_id, integer, false, "PK - incident surrogate"]
  - [case_number, string, true, "Police case number"]
  - [crime_type_id, integer, false, "FK to dim_crime_type"]
  - [location_type_id, integer, true, "FK to dim_location_type"]
  - [date_id, integer, false, "FK to dim_calendar"]
  - [year, integer, false, "Incident year (partition key)"]
  - [block, string, true, "Block-level address"]
  - [beat, string, true, "Police beat"]
  - [district, string, true, "Police district"]
  - [ward, integer, true, "Political ward"]
  - [community_area, integer, true, "Community area number"]
  - [latitude, double, true, "Latitude"]
  - [longitude, double, true, "Longitude"]
  - [arrest_made, boolean, true, "Whether arrest was made"]
  - [domestic, boolean, true, "Domestic-related"]

tables:
  dim_crime_type:
    table_type: dimension
    primary_key: [crime_type_id]
    schema:
      - [crime_type_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT(iucr_code, '_', COALESCE(fbi_code, 'UNK'))))"}]
      - [iucr_code, string, true, "Illinois Uniform Crime Reporting code"]
      - [fbi_code, string, true, "FBI UCR code"]
      - [primary_type, string, false, "Primary crime type"]
      - [description, string, true, "Detailed description"]
      - [crime_category, string, true, "VIOLENT, PROPERTY, OTHER"]
      - [crime_subcategory, string, true, "Subcategory"]
      - [is_index_crime, boolean, true, "FBI Part I crime", {default: false}]

  dim_location_type:
    table_type: dimension
    primary_key: [location_type_id]
    schema:
      - [location_type_id, integer, false, "PK", {derived: "ABS(HASH(location_description))"}]
      - [location_description, string, false, "Location description"]
      - [location_category, string, true, "Grouped category"]

  _fact_crimes:
    table_type: fact
    primary_key: [incident_id]
    partition_by: [year]
    schema:
      - [incident_id, integer, false, "PK", {derived: "ABS(HASH(case_number))"}]
      - [crime_type_id, integer, false, "FK to dim_crime_type", {fk: dim_crime_type.crime_type_id}]
      - [location_type_id, integer, true, "FK to dim_location_type", {fk: dim_location_type.location_type_id}]
      - [date_id, integer, false, "FK to dim_calendar", {fk: temporal.dim_calendar.date_id}]
      - [case_number, string, true, "Police case number"]
      - [year, integer, false, "Incident year"]
      - [block, string, true, "Block-level address"]
      - [beat, string, true, "Police beat"]
      - [district, string, true, "Police district"]
      - [ward, integer, true, "Political ward"]
      - [community_area, integer, true, "Community area"]
      - [latitude, double, true, "Latitude"]
      - [longitude, double, true, "Longitude"]
      - [arrest_made, boolean, true, "Arrest made", {default: false}]
      - [domestic, boolean, true, "Domestic-related", {default: false}]
    measures:
      - [crime_count, count_distinct, incident_id, "Total crimes", {format: "#,##0"}]
      - [arrest_count, expression, "SUM(CASE WHEN arrest_made THEN 1 ELSE 0 END)", "Arrests", {format: "#,##0"}]
      - [arrest_rate, expression, "100.0 * SUM(CASE WHEN arrest_made THEN 1 ELSE 0 END) / COUNT(*)", "Arrest rate %", {format: "#,##0.0%"}]

  _fact_arrests:
    table_type: fact
    primary_key: [arrest_id]
    partition_by: [year]
    schema:
      - [arrest_id, integer, false, "PK"]
      - [incident_id, integer, true, "FK to fact_crimes"]
      - [crime_type_id, integer, false, "FK to dim_crime_type"]
      - [date_id, integer, false, "FK to dim_calendar"]
      - [beat, string, true, "Police beat"]
      - [district, string, true, "Police district"]
      - [community_area, integer, true, "Community area"]
      - [year, integer, false, "Arrest year"]
    measures:
      - [total_arrests, count_distinct, arrest_id, "Total arrests", {format: "#,##0"}]

graph:
  edges:
    - [crime_to_type, _fact_crimes, dim_crime_type, [crime_type_id=crime_type_id], many_to_one, null]
    - [crime_to_location_type, _fact_crimes, dim_location_type, [location_type_id=location_type_id], many_to_one, null]
    - [crime_to_calendar, _fact_crimes, temporal.dim_calendar, [date_id=date_id], many_to_one, temporal]
---

## Base Crime Template

Reusable template for crime/public safety data. Provides standard crime taxonomy (VIOLENT, PROPERTY, OTHER), location types, and incident/arrest fact tables.

### Crime Categories

```
VIOLENT: HOMICIDE, ASSAULT, BATTERY, ROBBERY
PROPERTY: THEFT, BURGLARY, MOTOR VEHICLE THEFT
OTHER: All remaining types
```

### Models Using This Base

- `chicago_public_safety` - Chicago crime data (extends with Chicago-specific geography)
