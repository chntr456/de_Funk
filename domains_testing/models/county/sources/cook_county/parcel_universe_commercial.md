---
type: domain-model-source
source: parcel_universe_commercial
extends: _base.property.commercial
maps_to: dim_commercial_parcel
from: bronze.cook_county_parcel_universe
domain_source: "'cook_county'"

aliases:
  - [parcel_id, "LPAD(REGEXP_REPLACE(pin, '[^0-9]', ''), 14, '0')"]
  - [parcel_code, "LPAD(REGEXP_REPLACE(pin, '[^0-9]', ''), 14, '0')"]
  - [property_class, class]
  - [commercial_sqft, comm_sqft]
  - [commercial_units, comm_units]
  - [residential_units, res_units]
  - [space_type, use_type]
  - [floors, num_floors]
---

## Commercial Parcel Universe

Same bronze source as `parcel_universe` but maps commercial-specific columns (square footage, units, space type). Filtered downstream by `dim_property_class.property_category = 'COMMERCIAL'`.

### Source Fields

| Canonical | Source Column | Notes |
|-----------|-------------|-------|
| commercial_sqft | comm_sqft | Commercial floor area |
| commercial_units | comm_units | Number of commercial units |
| residential_units | res_units | Residential units in mixed-use |
| space_type | use_type | OFFICE, RETAIL, MIXED_USE, WAREHOUSE |
| floors | num_floors | Number of floors |
