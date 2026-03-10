---
type: domain-model-source
source: parcel_universe
extends: _base.property.parcel
maps_to: dim_parcel
from: bronze.cook_county_parcel_universe
domain_source: "'cook_county'"

aliases:
  # Common fields
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

  # Residential fields (populated for class 200-299)
  - [bedrooms, bdrm]
  - [bathrooms, "COALESCE(fbath, 0) + COALESCE(hbath, 0) * 0.5"]
  - [stories, stories]
  - [garage_spaces, garage_spaces]
  - [basement, bsmt_desc]
  - [exterior_wall, ext_wall]

  # Commercial fields (populated for class 500-599)
  - [commercial_sqft, comm_sqft]
  - [commercial_units, comm_units]
  - [residential_units, res_units]
  - [space_type, use_type]
  - [floors, num_floors]

  # Industrial fields (populated for class 300-399)
  - [industrial_sqft, ind_sqft]
  - [loading_docks, loading_docks]
  - [ceiling_height, ceiling_ht]
  - [zoning_class, zoning]
---

## Parcel Universe

Complete inventory of all Cook County parcels. Single source provides common fields plus all type-specific columns (residential, commercial, industrial). Columns are naturally null for non-matching property types in the source data.
