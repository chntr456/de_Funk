---
type: domain-model-source
source: food_inspections
extends: _base.regulatory.inspection
maps_to: _fact_inspections
from: bronze.chicago_food_inspections

aliases:
  - [inspection_id, "ABS(HASH(CAST(inspection_id AS STRING)))"]
  - [facility_id, "ABS(HASH(CAST(license_ AS STRING)))"]
  - [inspection_type_id, "ABS(HASH(inspection_type))"]
  - [inspection_date, inspection_date]
  - [date_id, "CAST(DATE_FORMAT(inspection_date, 'yyyyMMdd') AS INT)"]
  - [year, "YEAR(inspection_date)"]
  - [result, results]
  - [violations, violations]
  - [address, address]
  - [ward, TBD]
  - [community_area, TBD]
  - [latitude, latitude]
  - [longitude, longitude]
  - [facility_name, dba_name]
  - [facility_type, facility_type]
  - [risk_level, risk]
  - [inspection_type, inspection_type]
---

## Food Inspections
Inspection results for food establishments. Pass/fail/conditional outcomes with violation details.
