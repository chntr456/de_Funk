---
type: schema-template
name: property
description: "Canonical schema for property assessment data (county-agnostic)"
domain: property
entity: parcel

# Canonical Schema (what Silver looks like)
canonical_schema:
  # Identifiers
  parcel_id: {type: string, required: true, description: "Parcel identifier (PIN)"}
  parcel_id_10: {type: string, description: "10-digit PIN"}
  parcel_id_14: {type: string, description: "14-digit PIN (zero-padded)"}

  # Temporal
  year: {type: int, required: true, description: "Assessment/tax year"}
  assessment_stage: {type: string, description: "Stage: mailed, certified, bor_certified"}

  # Location
  township_code: {type: string, description: "Township code"}
  township_name: {type: string, description: "Township name"}

  # Property Classification
  property_class: {type: string, description: "Property class code"}
  property_category: {type: string, description: "Taxonomy level 1 (RESIDENTIAL, COMMERCIAL, etc.)"}
  property_type: {type: string, description: "Taxonomy level 2"}

  # Assessed Values
  av_land: {type: double, description: "Land assessed value"}
  av_building: {type: double, description: "Building assessed value"}
  av_total: {type: double, description: "Total assessed value"}

  # Market Values (derived from AV / level of assessment)
  mv_land: {type: double, description: "Land market value (estimated)"}
  mv_building: {type: double, description: "Building market value (estimated)"}
  mv_total: {type: double, description: "Total market value (estimated)"}

  # Physical Characteristics
  land_sqft: {type: double, description: "Land square footage"}
  building_sqft: {type: double, description: "Building square footage"}
  year_built: {type: int, description: "Year built"}
  stories: {type: double, description: "Number of stories"}
  units: {type: int, description: "Number of units"}
  bedrooms: {type: int, description: "Number of bedrooms"}
  bathrooms: {type: double, description: "Number of bathrooms"}

  # Sale Information (if from sales table)
  sale_date: {type: date, description: "Date of sale"}
  sale_price: {type: double, description: "Sale price"}
  sale_type: {type: string, description: "Type of sale"}

  # Geospatial
  latitude: {type: double, description: "Latitude"}
  longitude: {type: double, description: "Longitude"}

# Column Mappings
column_mappings:
  parcel_id: [pin, parcel_id, parcel_number, ain]
  year: [year, tax_year, assessment_year]
  assessment_stage: [stage_name, stage, assessment_stage]
  township_code: [township_code, township, twp]
  property_class: [class, property_class, class_code]
  av_land: [av_land, land_av, assessed_land]
  av_building: [av_bldg, av_building, building_av, assessed_building]
  av_total: [av_tot, av_total, total_av, assessed_total]
  land_sqft: [land_sqft, lot_size, land_sf]
  building_sqft: [building_sqft, bldg_sf, living_area]

# Value Normalization
normalization:
  parcel_id:
    - zfill: 14  # Zero-pad to 14 digits
  property_class:
    - uppercase
    - trim

# Property Class Taxonomy (Cook County specific, but pattern is reusable)
taxonomy:
  RESIDENTIAL:
    SINGLE_FAMILY:
      - "202"   # Single-family, 1 story
      - "203"   # Single-family, 1+ story
      - "204"   # Single-family, 2 story
      - "205"   # Single-family, split-level
      - "206"   # Single-family, townhouse
      - "207"   # Single-family, 2+ story
      - "208"   # Single-family, manufactured
      - "209"   # Single-family, coach house
      - "210"   # Single-family, old style
      - "211"   # Single-family, old style 2+ story
      - "212"   # Single-family, converted
      - "218"   # Single-family, 3+ story
      - "219"   # Single-family, 4+ story
    MULTI_FAMILY:
      - "211"   # 2-6 units
      - "212"   # 2-6 units
      - "213"   # 2-6 units
      - "278"   # 7+ units
      - "299"   # Multi-family other
    CONDO:
      - "297"   # Condo parking
      - "299"   # Condo unit
      - "399"   # Condo commercial
    _OTHER: []

  COMMERCIAL:
    RETAIL:
      - "517"   # Retail
      - "522"   # Strip mall
    OFFICE:
      - "516"   # Office
      - "517"   # Office
    INDUSTRIAL:
      - "535"   # Warehouse
      - "550"   # Industrial
      - "580"   # Manufacturing
    MIXED_USE:
      - "590"   # Mixed commercial
    _OTHER: []

  VACANT:
    VACANT_LAND:
      - "100"   # Vacant land
      - "190"   # Vacant land
    _OTHER: []

  EXEMPT:
    GOVERNMENT:
      - "EXEMPT"
    RELIGIOUS:
      - "RELIGIOUS"
    _OTHER: []

  _OTHER: []

# Dimension Tables
dimensions:
  dim_parcel:
    description: "Parcel dimension (property characteristics)"
    columns:
      parcel_id: {type: string}
      township_code: {type: string}
      township_name: {type: string}
      property_class: {type: string}
      property_category: {type: string}
      property_type: {type: string}
      year_built: {type: int}
      land_sqft: {type: double}
      building_sqft: {type: double}

  dim_property_class:
    description: "Property class dimension"
    columns:
      property_class_id: {type: string}
      property_class_name: {type: string}
      property_category: {type: string}
      property_type: {type: string}
      level_of_assessment: {type: double}

  dim_township:
    description: "Township dimension"
    columns:
      township_code: {type: string}
      township_name: {type: string}
      county: {type: string}

status: active
---

## Property Schema Template

County-agnostic schema template for property assessment and parcel data.

### Usage

```yaml
---
type: domain-model
model: cook_county_property
schema_template: _schema/property.md
---
```

### Key Concepts

**PIN (Parcel Index Number)**:
- 14-digit identifier for Cook County
- Must be zero-padded (leading zeros often dropped in exports)
- Format: Township (2) + Section (2) + Block (3) + Parcel (4) + Unit (3)

**Assessment Stages**:
- `mailed`: Initial values sent to property owners
- `certified`: Values after Assessor appeals
- `bor_certified`: Values after Board of Review appeals

**Level of Assessment**:
- Assessed Value = Market Value × Level of Assessment
- Levels vary by property class and change over time
- Must lookup historical levels for accurate market value estimates

### Taxonomy

Property classes grouped by use type. Cook County uses numeric codes; other counties may use different schemes.

### Notes

- PIN formatting critical for joins across datasets
- Market value is derived, not stored in source
- Assessment stage affects which values are "final"
