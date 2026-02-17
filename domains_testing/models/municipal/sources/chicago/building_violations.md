---
type: domain-model-source
source: building_violations
extends: _base.regulatory.inspection
maps_to: fact_violations
from: bronze.chicago_building_violations
domain_source: "'chicago'"

aliases:
  - [legal_entity_id, "ABS(HASH(CONCAT('CITY_', 'Chicago')))"]
  - [violation_id, "ABS(HASH(CAST(id AS STRING)))"]
  - [violation_date, violation_date]
  - [date_id, "CAST(DATE_FORMAT(violation_date, 'yyyyMMdd') AS INT)"]
  - [year, "YEAR(violation_date)"]
  - [violation_type, violation_code]
  - [status, violation_status]
  - [address, address]
  - [ward, TBD]
  - [community_area, TBD]
---

## Building Violations
Building code violation notices with status and address.
