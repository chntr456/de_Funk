---
type: domain-model-table
table: dim_commercial_parcel
extends: _base.property.commercial._dim_commercial_parcel
table_type: dimension
primary_key: [parcel_id]

enrich:
  - {join: dim_property_class, on: [property_class=property_class_code], fields: [property_category]}

filters:
  - "property_category = 'COMMERCIAL'"

additional_schema:
  - [parcel_code, string, false, "Natural key (PIN)"]

measures:
  - [commercial_count, count_distinct, parcel_id, "Commercial parcels", {format: "#,##0"}]
  - [avg_commercial_sqft, avg, commercial_sqft, "Average commercial sq ft", {format: "#,##0"}]
  - [total_commercial_units, sum, commercial_units, "Total commercial units", {format: "#,##0"}]
---

## Commercial Parcel Dimension

Commercial subset of dim_parcel with property-specific attributes (commercial_sqft, floors, space_type, etc.).

### Data Flow

```
bronze.cook_county_parcel_universe
  → source: parcel_universe_commercial (aliases: comm_sqft→commercial_sqft, etc.)
  → enrich: JOIN dim_property_class ON property_class = property_class_code
  → filter: property_category = 'COMMERCIAL'
  → dim_commercial_parcel
```

### Build Order

Phase 2 — requires `dim_property_class` (phase 1) for category filtering.

Joins back to `dim_parcel` via `parcel_id` (one_to_one, optional). Graph auto-join produces wide view at query time.
