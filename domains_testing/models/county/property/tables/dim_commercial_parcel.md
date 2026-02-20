---
type: domain-model-table
table: dim_commercial_parcel
extends: _base.property.commercial._dim_commercial_parcel
table_type: dimension
primary_key: [parcel_id]
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

Commercial subset of dim_parcel with property-specific attributes (commercial_sqft, floors, space_type, etc.). Filtered to `property_category = 'COMMERCIAL'` from dim_property_class.
