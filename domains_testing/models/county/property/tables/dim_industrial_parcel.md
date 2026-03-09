---
type: domain-model-table
table: dim_industrial_parcel
extends: _base.property.industrial._dim_industrial_parcel
table_type: dimension
primary_key: [parcel_id]

enrich:
  - {join: dim_property_class, on: [property_class=property_class_code], fields: [property_category]}

filters:
  - "property_category = 'INDUSTRIAL'"

additional_schema:
  - [parcel_code, string, false, "Natural key (PIN)"]

measures:
  - [industrial_count, count_distinct, parcel_id, "Industrial parcels", {format: "#,##0"}]
  - [avg_industrial_sqft, avg, industrial_sqft, "Average industrial sq ft", {format: "#,##0"}]
  - [total_loading_docks, sum, loading_docks, "Total loading docks", {format: "#,##0"}]
---

## Industrial Parcel Dimension

Industrial subset of dim_parcel with property-specific attributes (industrial_sqft, loading_docks, ceiling_height, etc.).

### Data Flow

```
bronze.cook_county_parcel_universe
  → source: parcel_universe_industrial (aliases: ind_sqft→industrial_sqft, etc.)
  → enrich: JOIN dim_property_class ON property_class = property_class_code
  → filter: property_category = 'INDUSTRIAL'
  → dim_industrial_parcel
```

### Build Order

Phase 2 — requires `dim_property_class` (phase 1) for category filtering.

Joins back to `dim_parcel` via `parcel_id` (one_to_one, optional). Graph auto-join produces wide view at query time.
