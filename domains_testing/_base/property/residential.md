---
type: domain-base
model: residential_parcel
version: 1.0
description: "Residential property parcels - single-family, multi-family, condominiums"
extends: _base.property.parcel
subset_of: _base.property.parcel
subset_value: RESIDENTIAL

canonical_fields:
  - [bedrooms, integer, nullable: true, description: "Number of bedrooms"]
  - [bathrooms, double, nullable: true, description: "Number of bathrooms (1.5, 2.5, etc.)"]
  - [stories, double, nullable: true, description: "Number of stories"]
  - [garage_spaces, integer, nullable: true, description: "Garage/parking spaces"]
  - [basement, string, nullable: true, description: "Basement type (FULL, PARTIAL, CRAWL, NONE)"]
  - [exterior_wall, string, nullable: true, description: "Exterior wall material"]

tables:
  _dim_residential_parcel:
    type: dimension
    extends: _dim_parcel
    primary_key: [parcel_id]

    additional_schema:
      - [bedrooms, integer, true, "Number of bedrooms"]
      - [bathrooms, double, true, "Number of bathrooms"]
      - [stories, double, true, "Number of stories"]
      - [garage_spaces, integer, true, "Garage/parking spaces"]
      - [basement, string, true, "Basement type", {enum: [FULL, PARTIAL, CRAWL, NONE]}]
      - [exterior_wall, string, true, "Exterior wall material"]

    measures:
      - [avg_bedrooms, avg, bedrooms, "Average bedrooms", {format: "#,##0.0"}]
      - [avg_bathrooms, avg, bathrooms, "Average bathrooms", {format: "#,##0.0"}]

domain: property
tags: [base, template, property, residential]
status: active
---

## Residential Parcel Base Template

Extends the core parcel base with residential-specific attributes. Use this for models that focus on residential property data.

### Inherited from Parcel Base

All fields from `_base.property.parcel`: parcel_id, property_class, township_code, year_built, land_sqft, building_sqft, lat/lon, tax_code.

### Residential Fields

| Field | Type | Description |
|-------|------|-------------|
| bedrooms | integer | Number of bedrooms |
| bathrooms | double | Number of bathrooms (allows 1.5, 2.5) |
| stories | double | Number of stories (allows 1.5, 2.5) |
| garage_spaces | integer | Garage or parking spaces |
| basement | string | FULL, PARTIAL, CRAWL, NONE |
| exterior_wall | string | Exterior wall material |

### Usage

```yaml
extends: _base.property.residential
```
