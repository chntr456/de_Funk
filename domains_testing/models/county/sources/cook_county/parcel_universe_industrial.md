---
type: domain-model-source
source: parcel_universe_industrial
extends: _base.property.industrial
maps_to: dim_industrial_parcel
from: bronze.cook_county_parcel_universe
domain_source: "'cook_county'"

aliases:
  - [parcel_id, "LPAD(REGEXP_REPLACE(pin, '[^0-9]', ''), 14, '0')"]
  - [parcel_code, "LPAD(REGEXP_REPLACE(pin, '[^0-9]', ''), 14, '0')"]
  - [property_class, class]
  - [industrial_sqft, ind_sqft]
  - [loading_docks, loading_docks]
  - [ceiling_height, ceiling_ht]
  - [zoning_class, zoning]
---

## Industrial Parcel Universe

Same bronze source as `parcel_universe` but maps industrial-specific columns (square footage, loading docks, ceiling height). Filtered downstream by `dim_property_class.property_category = 'INDUSTRIAL'`.

### Source Fields

| Canonical | Source Column | Notes |
|-----------|-------------|-------|
| industrial_sqft | ind_sqft | Industrial floor area |
| loading_docks | loading_docks | Number of loading docks |
| ceiling_height | ceiling_ht | Ceiling height in feet |
| zoning_class | zoning | Industrial zoning code |
