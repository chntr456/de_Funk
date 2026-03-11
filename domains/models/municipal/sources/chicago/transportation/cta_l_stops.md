---
type: domain-model-source
source: cta_l_stops
extends: _base.transportation.transit
maps_to: dim_transit_station
from: bronze.chicago_cta_l_stops
domain_source: "'chicago'"

aliases:
  - [station_id, "ABS(HASH(CONCAT(station_name, '_', 'RAIL')))"]
  - [station_name, station_name]
  - [transit_mode, "'RAIL'"]
  - [line_name, "'TBD'"]
  - [ada_accessible, ada]
  - [latitude, "CAST(NULL AS DOUBLE)"]
  - [longitude, "CAST(NULL AS DOUBLE)"]
---

## CTA L Stops
L train station reference data with line assignments and ADA accessibility.
