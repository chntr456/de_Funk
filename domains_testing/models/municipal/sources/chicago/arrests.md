---
type: domain-model-source
source: arrests
extends: _base.public_safety.crime
maps_to: _fact_arrests
from: bronze.chicago_arrests

aliases:
  - [legal_entity_id, "ABS(HASH(CONCAT('CITY_', 'Chicago')))"]
  - [arrest_id, TBD]
  - [incident_id, TBD]
  - [crime_type_id, TBD]
  - [date_id, TBD]
  - [beat, beat]
  - [district, district]
  - [community_area, TBD]
  - [year, TBD]
---

## Arrests
Arrest records linked to crime incidents.
