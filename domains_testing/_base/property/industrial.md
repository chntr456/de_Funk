---
type: domain-base
model: industrial_parcel
version: 2.0
description: "Industrial property fields — absorbed into _base.property.parcel wide table"
extends: _base.property.parcel
subset_of: _base.property.parcel
subset_value: INDUSTRIAL

# These fields are now columns on _dim_parcel with {subset: INDUSTRIAL}
canonical_fields:
  - [industrial_sqft, double, nullable: true, description: "Industrial floor area in square feet"]
  - [loading_docks, integer, nullable: true, description: "Number of loading docks"]
  - [ceiling_height, double, nullable: true, description: "Ceiling height in feet"]
  - [zoning_class, string, nullable: true, description: "Industrial zoning classification"]

domain: property
tags: [base, template, property, industrial, wide-table]
status: active
---

## Industrial Parcel Base Template

Defines industrial-specific fields absorbed into `_base.property.parcel._dim_parcel` as nullable columns with `{subset: INDUSTRIAL}` metadata.

### Industrial Fields

| Field | Type | Description |
|-------|------|-------------|
| industrial_sqft | double | Industrial floor area in square feet |
| loading_docks | integer | Number of loading docks |
| ceiling_height | double | Ceiling height in feet |
| zoning_class | string | Industrial zoning classification code |
