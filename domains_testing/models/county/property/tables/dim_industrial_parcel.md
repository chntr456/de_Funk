---
type: domain-model-table
table: dim_industrial_parcel
extends: _base.property.industrial._dim_industrial_parcel
table_type: dimension
primary_key: [parcel_id]
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

Industrial subset of dim_parcel with property-specific attributes (industrial_sqft, loading_docks, ceiling_height, etc.). Filtered to `property_category = 'INDUSTRIAL'` from dim_property_class.
