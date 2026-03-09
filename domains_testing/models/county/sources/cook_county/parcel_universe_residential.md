---
type: domain-model-source
source: parcel_universe_residential
extends: _base.property.residential
maps_to: dim_residential_parcel
from: bronze.cook_county_parcel_universe
domain_source: "'cook_county'"

aliases:
  - [parcel_id, "LPAD(REGEXP_REPLACE(pin, '[^0-9]', ''), 14, '0')"]
  - [parcel_code, "LPAD(REGEXP_REPLACE(pin, '[^0-9]', ''), 14, '0')"]
  - [property_class, class]
  - [bedrooms, bdrm]
  - [bathrooms, "COALESCE(fbath, 0) + COALESCE(hbath, 0) * 0.5"]
  - [stories, stories]
  - [garage_spaces, garage_spaces]
  - [basement, bsmt_desc]
  - [exterior_wall, ext_wall]
---

## Residential Parcel Universe

Same bronze source as `parcel_universe` but maps residential-specific columns (bedrooms, bathrooms, stories, etc.). Filtered downstream by `dim_property_class.property_category = 'RESIDENTIAL'`.

### Source Fields

| Canonical | Source Column | Notes |
|-----------|-------------|-------|
| bedrooms | bdrm | Integer count |
| bathrooms | fbath + hbath*0.5 | Full baths + half baths |
| stories | stories | Allows 1.5, 2.5 |
| garage_spaces | garage_spaces | Integer count |
| basement | bsmt_desc | FULL, PARTIAL, CRAWL, NONE |
| exterior_wall | ext_wall | Material description |
