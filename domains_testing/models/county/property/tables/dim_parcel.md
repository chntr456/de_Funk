---
type: domain-model-table
table: dim_parcel
extends: _base.property.parcel._dim_parcel
table_type: dimension
primary_key: [parcel_id]

unique_key: [parcel_code]

schema:
  - [parcel_id, string, false, "PK - 14-digit PIN", {derived: "LPAD(pin, 14, '0')"}]
  - [parcel_code, string, false, "Natural key (standardized PIN)", {derived: "pin"}]
  - [property_class, string, true, "Property class code", {derived: "class"}]
  - [township_code, string, true, "Township code"]
  - [neighborhood_code, string, true, "Neighborhood code", {derived: "nbhd"}]
  - [year_built, integer, true, "Year built"]
  - [land_sqft, double, true, "Land area in square feet"]
  - [building_sqft, double, true, "Building area in square feet"]
  - [latitude, double, true, "Parcel centroid latitude"]
  - [longitude, double, true, "Parcel centroid longitude"]
  - [tax_code, string, true, "Tax district code"]

measures:
  - [parcel_count, count_distinct, parcel_id, "Number of parcels", {format: "#,##0"}]
---

## Parcel Dimension

All parcels in Cook County with characteristics from the parcel universe.
PIN must be zero-padded to 14 digits for cross-dataset joins. Source field `nbhd` maps to canonical `neighborhood_code`.
