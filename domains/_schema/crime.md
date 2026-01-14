---
type: schema-template
name: crime
description: "Canonical schema for crime/incident data (city-agnostic)"
domain: public_safety
entity: crime

# Canonical Schema (what Silver looks like)
canonical_schema:
  # Identifiers
  incident_id: {type: string, required: true, description: "Unique incident identifier"}
  case_number: {type: string, description: "Police case number"}

  # Temporal
  incident_date: {type: timestamp, required: true, description: "Date/time of incident"}
  year: {type: int, description: "Year of incident (partition key)"}

  # Crime Classification
  crime_type: {type: string, required: true, description: "Primary crime type (normalized)"}
  crime_category: {type: string, description: "Taxonomy level 1 (VIOLENT, PROPERTY, etc.)"}
  crime_group: {type: string, description: "Taxonomy level 2 (ASSAULT, THEFT, etc.)"}
  description: {type: string, description: "Detailed crime description"}

  # Classification Codes
  iucr_code: {type: string, description: "Illinois Uniform Crime Reporting code"}
  fbi_code: {type: string, description: "FBI Uniform Crime Report code"}

  # Outcome
  arrest_made: {type: boolean, description: "Whether arrest was made"}
  domestic: {type: boolean, description: "Whether domestic-related"}

  # Location (text)
  location_description: {type: string, description: "Type of location (STREET, APARTMENT, etc.)"}
  block: {type: string, description: "Block-level address"}

  # Geospatial
  latitude: {type: double, description: "Latitude"}
  longitude: {type: double, description: "Longitude"}

  # Geo Keys (for dimension joins)
  community_area: {type: int, description: "Community area number"}
  ward: {type: int, description: "Ward number"}
  beat: {type: string, description: "Police beat"}
  district: {type: string, description: "Police district"}

# Column Mappings (source variants → canonical)
column_mappings:
  incident_id: [id, incident_id, crime_id, record_id]
  case_number: [case_number, casenumber, case_no]
  incident_date: [date, incident_date, occurred_date, datetime, crime_date]
  crime_type: [primary_type, crime_type, offense_type, type, offense]
  description: [desc, description, offense_description, secondary_type]
  iucr_code: [iucr, iucr_code, ucr_code]
  fbi_code: [fbi_code, fbi, ucr_fbi_code]
  arrest_made: [arrest, arrest_made, was_arrested, arrested]
  domestic: [domestic, is_domestic, domestic_related]
  location_description: [location_description, location, location_type, loc_desc]
  block: [block, address, block_address]
  community_area: [community_area, communityarea, comm_area]
  ward: [ward, ward_number]
  beat: [beat, police_beat]
  district: [district, police_district]

# Value Normalization
normalization:
  crime_type:
    - uppercase
    - trim
  description:
    - uppercase
    - trim
  location_description:
    - uppercase
    - trim

# Crime Taxonomy (with _OTHER catch-all at each level)
taxonomy:
  VIOLENT:
    HOMICIDE:
      - HOMICIDE
      - MURDER
      - MANSLAUGHTER
      - FIRST DEGREE MURDER
      - SECOND DEGREE MURDER
    ASSAULT:
      - ASSAULT
      - BATTERY
      - AGGRAVATED ASSAULT
      - AGGRAVATED BATTERY
      - SIMPLE ASSAULT
      - SIMPLE BATTERY
    ROBBERY:
      - ROBBERY
      - ARMED ROBBERY
      - STRONGARM
      - AGGRAVATED ROBBERY
    SEXUAL_ASSAULT:
      - CRIMINAL SEXUAL ASSAULT
      - SEX OFFENSE
      - CRIM SEXUAL ASSAULT
      - RAPE
    KIDNAPPING:
      - KIDNAPPING
      - ABDUCTION
    _OTHER: []

  PROPERTY:
    THEFT:
      - THEFT
      - LARCENY
      - RETAIL THEFT
      - SHOPLIFTING
      - POCKET-PICKING
      - PURSE-SNATCHING
    BURGLARY:
      - BURGLARY
      - BREAKING AND ENTERING
      - RESIDENTIAL BURGLARY
    MOTOR_VEHICLE_THEFT:
      - MOTOR VEHICLE THEFT
      - AUTO THEFT
      - VEHICLE THEFT
      - STOLEN VEHICLE
    ARSON:
      - ARSON
    CRIMINAL_DAMAGE:
      - CRIMINAL DAMAGE
      - VANDALISM
      - CRIMINAL DAMAGE TO PROPERTY
    _OTHER: []

  DRUGS:
    NARCOTICS:
      - NARCOTICS
      - DRUG ABUSE
      - CONTROLLED SUBSTANCE
      - OTHER NARCOTIC VIOLATION
    _OTHER: []

  FRAUD:
    DECEPTIVE_PRACTICE:
      - DECEPTIVE PRACTICE
      - FRAUD
      - FORGERY
      - COUNTERFEITING
      - IDENTITY THEFT
    _OTHER: []

  WEAPONS:
    WEAPONS_VIOLATION:
      - WEAPONS VIOLATION
      - UNLAWFUL USE OF WEAPON
      - CONCEALED CARRY LICENSE VIOLATION
    _OTHER: []

  PUBLIC_ORDER:
    DISORDERLY:
      - DISORDERLY CONDUCT
      - PUBLIC PEACE VIOLATION
    PROSTITUTION:
      - PROSTITUTION
      - SOLICITATION
    GAMBLING:
      - GAMBLING
    LIQUOR:
      - LIQUOR LAW VIOLATION
    _OTHER: []

  _OTHER: []

# Dimension Tables (created from fact data)
dimensions:
  dim_crime_type:
    description: "Crime type dimension (compressed from taxonomy)"
    source: fact_crimes.crime_type
    columns:
      crime_type_id: {type: string, description: "Normalized crime type"}
      crime_type_name: {type: string, description: "Display name"}
      crime_category: {type: string, description: "Level 1 taxonomy"}
      crime_group: {type: string, description: "Level 2 taxonomy"}
      iucr_code: {type: string, description: "Representative IUCR code"}
      fbi_code: {type: string, description: "Representative FBI code"}

  dim_location_type:
    description: "Location type dimension"
    source: fact_crimes.location_description
    columns:
      location_type_id: {type: string, description: "Normalized location type"}
      location_type_name: {type: string, description: "Display name"}

status: active
---

## Crime Schema Template

City-agnostic schema template for crime/incident data. Used by city domains to normalize crime data from various sources.

### Usage

Reference this template in city domain files:

```yaml
---
type: domain-model
model: chicago_public_safety
schema_template: _schema/crime.md
---
```

### Taxonomy Structure

```
crime_category (Level 1)
└── crime_group (Level 2)
    └── crime_type (raw, normalized)
```

Each level has `_OTHER` catch-all for unmatched values.

### Classification Codes

- **IUCR**: Illinois Uniform Crime Reporting (Chicago-specific)
  - Source: Chicago Data Portal `chicago_iucr_codes`
  - ~400+ codes, includes `index_code` (I/N)

- **FBI UCR**: FBI Uniform Crime Report (national standard)
  - Reference: `_schema/fbi_ucr_codes.md`
  - ~30 codes, Part I (Index) and Part II
  - Used for national crime statistics

Both preserved in Silver for cross-reference.

### Notes

- Column mappings handle schema variations across years/sources
- Value normalization ensures clean dimension tables
- Taxonomy assignment happens at Silver build time
