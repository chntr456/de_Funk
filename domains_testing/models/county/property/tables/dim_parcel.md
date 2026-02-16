---
type: domain-model-table
table: dim_parcel
extends: _base.property.parcel._dim_parcel
table_type: dimension
from: bronze.cook_county_parcel_universe
primary_key: [parcel_id]

schema:
  - [parcel_id, string, false, "PK - 14-digit PIN", {derived: "LPAD(pin, 14, '0')"}]
  - [township_code, string, true, "Township code"]
  - [property_class, string, true, "Property class code", {derived: "class"}]
  - [nbhd, string, true, "Neighborhood code"]
  - [year_built, integer, true, "Year built"]
  - [land_sqft, double, true, "Land area in square feet"]
  - [building_sqft, double, true, "Building area in square feet"]
  - [tax_code, string, true, "Tax code"]

measures:
  - [parcel_count, count_distinct, parcel_id, "Number of parcels", {format: "#,##0"}]
---

## Parcel Dimension

All parcels in Cook County with characteristics from the parcel universe.
PIN must be zero-padded to 14 digits for cross-dataset joins.
