---
type: domain-base
model: industrial_parcel
version: 1.0
description: "Industrial property parcels - manufacturing, warehouse, distribution"
extends: _base.property.parcel
subset_of: _base.property.parcel
subset_value: INDUSTRIAL

canonical_fields:
  - [industrial_sqft, double, nullable: true, description: "Industrial floor area in square feet"]
  - [loading_docks, integer, nullable: true, description: "Number of loading docks"]
  - [ceiling_height, double, nullable: true, description: "Ceiling height in feet"]
  - [zoning_class, string, nullable: true, description: "Industrial zoning classification"]

tables:
  _dim_industrial_parcel:
    type: dimension
    extends: _dim_parcel
    primary_key: [parcel_id]

    additional_schema:
      - [industrial_sqft, double, true, "Industrial floor area sq ft"]
      - [loading_docks, integer, true, "Number of loading docks"]
      - [ceiling_height, double, true, "Ceiling height in feet"]
      - [zoning_class, string, true, "Industrial zoning classification"]

    measures:
      - [avg_industrial_sqft, avg, industrial_sqft, "Average industrial sq ft", {format: "#,##0"}]
      - [total_loading_docks, sum, loading_docks, "Total loading docks", {format: "#,##0"}]

domain: property
tags: [base, template, property, industrial]
status: active
---

## Industrial Parcel Base Template

Extends the core parcel base with industrial-specific attributes.

### Inherited from Parcel Base

All fields from `_base.property.parcel`: parcel_id, property_class, township_code, year_built, land_sqft, building_sqft, lat/lon, tax_code.

### Industrial Fields

| Field | Type | Description |
|-------|------|-------------|
| industrial_sqft | double | Industrial floor area in square feet |
| loading_docks | integer | Number of loading docks |
| ceiling_height | double | Ceiling height in feet |
| zoning_class | string | Industrial zoning classification code |

### Usage

```yaml
extends: _base.property.industrial
```
