---
type: domain-model-source
source: arrests
extends: _base.public_safety.crime
maps_to: fact_arrests
from: bronze.chicago_arrests

aliases:
  - [legal_entity_id, "ABS(HASH(CONCAT('CITY_', 'Chicago')))"]
  - [domain_source, "'chicago'"]
  - [arrest_id, "ABS(HASH(arrest_key))"]
  - [incident_id, "null"]
  - [crime_type_id, "ABS(HASH(CONCAT(iucr, '_', COALESCE(fbi_code, 'UNK'))))"]
  - [date_id, "CAST(DATE_FORMAT(arrest_date, 'yyyyMMdd') AS INT)"]
  - [beat, beat]
  - [district, district]
  - [community_area, community_area]
  - [year, "YEAR(arrest_date)"]
---

## Arrests
Arrest records linked to crime incidents.
