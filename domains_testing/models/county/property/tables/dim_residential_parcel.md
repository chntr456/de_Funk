---
type: domain-model-table
table: dim_residential_parcel
extends: _base.property.residential._dim_residential_parcel
table_type: dimension
primary_key: [parcel_id]
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

Residential subset of dim_parcel with property-specific attributes (bedrooms, bathrooms, stories, etc.). Filtered to `property_category = 'RESIDENTIAL'` from dim_property_class.

Joins back to dim_parcel via parcel_id for the full parcel record. The graph auto-join can produce a wide view at query time.
