---
type: domain-model-source
source: building_permits
extends: _base.housing.permit
maps_to: _fact_permits
from: bronze.chicago_building_permits

aliases:
  - [legal_entity_id, "ABS(HASH(CONCAT('CITY_', 'Chicago')))"]
  - [permit_id, "ABS(HASH(permit_))"]
  - [permit_number, permit_]
  - [permit_type_id, "ABS(HASH(permit_type))"]
  - [work_type_id, "ABS(HASH(work_description))"]
  - [issue_date, issue_date]
  - [date_id, "CAST(DATE_FORMAT(issue_date, 'yyyyMMdd') AS INT)"]
  - [year, "YEAR(issue_date)"]
  - [address, street_address]
  - [ward, TBD]
  - [community_area, community_area]
  - [latitude, latitude]
  - [longitude, longitude]
  - [total_fee, total_fee]
  - [estimated_cost, estimated_cost]
  - [permit_type, permit_type]
  - [work_type, work_description]
---

## Building Permits
Construction, renovation, and demolition permits with fees and estimated costs.
