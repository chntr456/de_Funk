---
type: domain-model-source
source: business_licenses
extends: _base.regulatory.inspection
maps_to: fact_licenses
from: bronze.chicago_business_licenses

aliases:
  - [legal_entity_id, "ABS(HASH(CONCAT('CITY_', 'Chicago')))"]
  - [domain_source, "'chicago'"]
  - [license_id, "ABS(HASH(CAST(id AS STRING)))"]
  - [business_name, doing_business_as_name]
  - [issue_date, date_issued]
  - [date_id, "CAST(DATE_FORMAT(date_issued, 'yyyyMMdd') AS INT)"]
  - [expiration_date, expiration_date]
  - [year, "YEAR(date_issued)"]
  - [address, address]
  - [ward, ward]
  - [community_area, TBD]
  - [status, license_status]
  - [license_type, license_description]
---

## Business Licenses
Business license issuance and renewal records with status tracking.
