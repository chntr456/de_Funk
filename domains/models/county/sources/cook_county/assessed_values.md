---
type: domain-model-source
source: assessed_values
extends: _base.property.parcel
maps_to: fact_assessed_values
from: bronze.cook_county_assessed_values
domain_source: "'cook_county'"

aliases:
  - [legal_entity_id, "ABS(HASH(CONCAT('COUNTY_', 'Cook County')))"]
  - [parcel_id, "LPAD(REGEXP_REPLACE(pin, '[^0-9]', ''), 14, '0')"]
  - [year, year]
  - [date_id, "CAST(CONCAT(year, '0101') AS INT)"]
  - [assessment_stage, stage_name]
  - [assessed_value_land, land]
  - [assessed_value_building, bldg]
  - [assessed_value_total, total]
  - [property_class, class]
  - [township_code, township_code]
---

## Assessed Values
Annual property assessed values 1999-present across assessment stages (mailed, certified, board-certified).
