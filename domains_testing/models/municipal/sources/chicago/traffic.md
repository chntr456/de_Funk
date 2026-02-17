---
type: domain-model-source
source: traffic
extends: _base.transportation.traffic
maps_to: _fact_traffic
from: bronze.chicago_traffic

aliases:
  - [legal_entity_id, "ABS(HASH(CONCAT('CITY_', 'Chicago')))"]
  - [segment_id, segmentid]
  - [timestamp, TBD]
  - [date_id, TBD]
  - [speed, current_speed]
  - [congestion_level, TBD]
---

## Traffic
Traffic congestion data by road segment.
