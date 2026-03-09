---
type: domain-base
model: commercial_parcel
version: 2.0
description: "Commercial property fields — absorbed into _base.property.parcel wide table"
extends: _base.property.parcel
subset_of: _base.property.parcel
subset_value: COMMERCIAL

# These fields are now columns on _dim_parcel with {subset: COMMERCIAL}
canonical_fields:
  - [commercial_sqft, double, nullable: true, description: "Commercial floor area in square feet"]
  - [commercial_units, integer, nullable: true, description: "Number of commercial units"]
  - [residential_units, integer, nullable: true, description: "Number of residential units (mixed-use buildings)"]
  - [space_type, string, nullable: true, description: "OFFICE, RETAIL, MIXED_USE, WAREHOUSE"]
  - [floors, integer, nullable: true, description: "Number of floors"]

domain: property
tags: [base, template, property, commercial, wide-table]
status: active
---

## Commercial Parcel Base Template

Defines commercial-specific fields absorbed into `_base.property.parcel._dim_parcel` as nullable columns with `{subset: COMMERCIAL}` metadata.

### Commercial Fields

| Field | Type | Description |
|-------|------|-------------|
| commercial_sqft | double | Commercial floor area in square feet |
| commercial_units | integer | Number of commercial units |
| residential_units | integer | Residential units in mixed-use buildings |
| space_type | string | OFFICE, RETAIL, MIXED_USE, WAREHOUSE |
| floors | integer | Number of floors |
