---
type: domain-model-table
table: dim_residential_parcel
extends: _base.property.residential._dim_residential_parcel
table_type: dimension
primary_key: [parcel_id]

enrich:
  - {join: dim_property_class, on: [property_class=property_class_code], fields: [property_category]}

filters:
  - "property_category = 'RESIDENTIAL'"

additional_schema:
  - [parcel_code, string, false, "Natural key (PIN)"]

measures:
  - [residential_count, count_distinct, parcel_id, "Residential parcels", {format: "#,##0"}]
  - [avg_bedrooms, avg, bedrooms, "Average bedrooms", {format: "#,##0.0"}]
  - [avg_bathrooms, avg, bathrooms, "Average bathrooms", {format: "#,##0.0"}]
---

## Residential Parcel Dimension

Residential subset of dim_parcel with property-specific attributes (bedrooms, bathrooms, stories, etc.).

### Data Flow

```
bronze.cook_county_parcel_universe
  → source: parcel_universe_residential (aliases: bdrm→bedrooms, fbath+hbath→bathrooms, etc.)
  → enrich: JOIN dim_property_class ON property_class = property_class_code
  → filter: property_category = 'RESIDENTIAL'
  → dim_residential_parcel
```

### Build Order

Phase 2 — requires `dim_property_class` (phase 1) for category filtering.

Joins back to `dim_parcel` via `parcel_id` (one_to_one, optional). Graph auto-join produces wide view at query time.
