---
type: domain-base
model: residential_parcel
version: 2.0
description: "Residential property fields — absorbed into _base.property.parcel wide table"
extends: _base.property.parcel
subset_of: _base.property.parcel
subset_value: RESIDENTIAL

# These fields are now columns on _dim_parcel with {subset: RESIDENTIAL}
# Kept here as documentation of the residential field contract
canonical_fields:
  - [bedrooms, integer, nullable: true, description: "Number of bedrooms"]
  - [bathrooms, double, nullable: true, description: "Number of bathrooms (1.5, 2.5, etc.)"]
  - [stories, double, nullable: true, description: "Number of stories"]
  - [garage_spaces, integer, nullable: true, description: "Garage/parking spaces"]
  - [basement, string, nullable: true, description: "Basement type (FULL, PARTIAL, CRAWL, NONE)"]
  - [exterior_wall, string, nullable: true, description: "Exterior wall material"]

# No separate table — fields live on _dim_parcel (wide table pattern)
# Tables block removed in v2.0

domain: property
tags: [base, template, property, residential, wide-table]
status: active
---

## Residential Parcel Base Template

Defines residential-specific fields that are absorbed into `_base.property.parcel._dim_parcel` as nullable columns with `{subset: RESIDENTIAL}` metadata. No separate dimension table is created.

### Wide Table Pattern (v2.0)

In v1.0, this template defined `_dim_residential_parcel` as a separate table. In v2.0, these fields are columns on the parent `_dim_parcel` table, partitioned by `property_category`. This eliminates:
- Separate subset dimension tables
- Optional one_to_one edges for auto-join
- Extra build phases and source files

Query residential parcels: `SELECT * FROM dim_parcel WHERE property_category = 'RESIDENTIAL'`

### Residential Fields

| Field | Type | Description |
|-------|------|-------------|
| bedrooms | integer | Number of bedrooms |
| bathrooms | double | Number of bathrooms (allows 1.5, 2.5) |
| stories | double | Number of stories (allows 1.5, 2.5) |
| garage_spaces | integer | Garage or parking spaces |
| basement | string | FULL, PARTIAL, CRAWL, NONE |
| exterior_wall | string | Exterior wall material |
