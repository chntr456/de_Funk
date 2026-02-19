---
type: domain-base
model: commercial_parcel
version: 1.0
description: "Commercial property parcels - office, retail, mixed-use buildings"
extends: _base.property.parcel
subset_of: _base.property.parcel
subset_value: COMMERCIAL

canonical_fields:
  - [commercial_sqft, double, nullable: true, description: "Commercial floor area in square feet"]
  - [commercial_units, integer, nullable: true, description: "Number of commercial units"]
  - [residential_units, integer, nullable: true, description: "Number of residential units (mixed-use buildings)"]
  - [space_type, string, nullable: true, description: "OFFICE, RETAIL, MIXED_USE, WAREHOUSE"]
  - [floors, integer, nullable: true, description: "Number of floors"]

tables:
  _dim_commercial_parcel:
    type: dimension
    extends: _dim_parcel
    primary_key: [parcel_id]

    additional_schema:
      - [commercial_sqft, double, true, "Commercial floor area sq ft"]
      - [commercial_units, integer, true, "Number of commercial units"]
      - [residential_units, integer, true, "Residential units (mixed-use)"]
      - [space_type, string, true, "Space classification", {enum: [OFFICE, RETAIL, MIXED_USE, WAREHOUSE]}]
      - [floors, integer, true, "Number of floors"]

    measures:
      - [avg_commercial_sqft, avg, commercial_sqft, "Average commercial sq ft", {format: "#,##0"}]
      - [total_commercial_units, sum, commercial_units, "Total commercial units", {format: "#,##0"}]

domain: property
tags: [base, template, property, commercial]
status: active
---

## Commercial Parcel Base Template

Extends the core parcel base with commercial-specific attributes.

### Inherited from Parcel Base

All fields from `_base.property.parcel`: parcel_id, property_class, township_code, year_built, land_sqft, building_sqft, lat/lon, tax_code.

### Commercial Fields

| Field | Type | Description |
|-------|------|-------------|
| commercial_sqft | double | Commercial floor area in square feet |
| commercial_units | integer | Number of commercial units |
| residential_units | integer | Residential units in mixed-use buildings |
| space_type | string | OFFICE, RETAIL, MIXED_USE, WAREHOUSE |
| floors | integer | Number of floors |

### Usage

```yaml
extends: _base.property.commercial
```
