---
type: domain-model-source
source: assessed_values
extends: _base.property.parcel
maps_to: _fact_assessed_values
from: bronze.cook_county_assessed_values

aliases:
  - [parcel_id, "LPAD(REGEXP_REPLACE(pin, '[^0-9]', ''), 14, '0')"]
  - [year, year]
  - [date_id, "CAST(CONCAT(year, '0101') AS INT)"]
  - [assessment_stage, stage_name]
  - [av_land, land]
  - [av_building, bldg]
  - [av_total, total]
  - [property_class, class]
  - [township_code, township_code]
---

## Assessed Values
Annual property assessed values 1999-present across assessment stages (mailed, certified, board-certified).
