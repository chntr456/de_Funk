---
type: domain-model-source
source: parcel_universe
extends: _base.property.parcel
maps_to: dim_parcel
from: bronze.cook_county_parcel_universe
domain_source: "'cook_county'"

aliases:
  - [parcel_id, "LPAD(REGEXP_REPLACE(pin, '[^0-9]', ''), 14, '0')"]
  - [parcel_code, "LPAD(REGEXP_REPLACE(pin, '[^0-9]', ''), 14, '0')"]
  - [property_class, class]
  - [township_code, township_code]
  - [neighborhood_code, nbhd]
  - [year_built, year_built]
  - [land_sqft, land_sqft]
  - [building_sqft, building_sqft]
  - [latitude, TBD]
  - [longitude, TBD]
  - [tax_code, tax_code]
---

## Parcel Universe
Complete inventory of all Cook County parcels with PIN, township, property class, year built, and square footage.
