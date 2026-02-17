---
type: domain-model-source
source: traffic
extends: _base.transportation.transit
maps_to: _fact_traffic
from: bronze.chicago_traffic

aliases:
  - [segment_id, segmentid]
  - [timestamp, TBD]
  - [date_id, TBD]
  - [speed, current_speed]
  - [congestion_level, TBD]
---

## Traffic
Traffic congestion data by road segment.
