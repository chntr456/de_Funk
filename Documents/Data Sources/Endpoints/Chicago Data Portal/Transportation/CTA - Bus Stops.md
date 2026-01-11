---
type: api-endpoint          
provider: Chicago Data Portal                  
multiple_endpoints:
endpoint_pattern:            
method:                               
auth:             
domain: transportation             
legal_entity_type: municipal          
subject_entity_type: [municipal, infrustructure]       
data_tags: [ geospatial, reference]
status: active                                
update_cadence: irregular
last_verified:              
last_reviewed:             
notes:                      
---

## Description

CTA Bus Stops - Point data representing over 11,000 CTA bus stops. The Stop ID is used to get Bus Tracker information. this information is currently stored as a .kmz [file](https://data.cityofchicago.org/Transportation/CTA-Bus-Stops-kml/84eu-buny/about_data).
  
Projected Coordinate System: NAD_1983_StatePlane_Illinois_East_FIPS_1201_Feet



## Request Notes
Query params, limits, filters.

## Homelab Usage
Cron jobs, ingest scripts, storage paths.

## Known Quirks
Downtime patterns, format changes, gotchas.