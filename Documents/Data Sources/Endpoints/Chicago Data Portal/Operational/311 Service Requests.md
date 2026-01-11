---
type: api-endpoint          
provider: Chicago Data Portal                  
multiple_endpoints: false   
endpoint_pattern:  /api/v3/views/v6vf-nfxy/query.json       
method: GET                              
auth: inherit               
domain: operational             
legal_entity_type: municipal          
subject_entity_type: [municipal, individual]       
data_tags: [service requests, geospatial]
status: active                                
update_cadence: daily
last_verified:              
last_reviewed:             
notes:                      
---



## Description
311 Service Requests received by the City of Chicago. This dataset includes requests created after the launch of the new 311 system on 12/18/2018 and some records from the previous system, indicated in the LEGACY_RECORD column.

For purposes of all columns indicating geographic areas or locations, please note that requests of the type 311 INFORMATION ONLY CALL often are entered with the address of the City's 311 Center.

## Request Notes
Query params, limits, filters.

## Homelab Usage
Cron jobs, ingest scripts, storage paths.

## Known Quirks
Downtime patterns, format changes, gotchas.