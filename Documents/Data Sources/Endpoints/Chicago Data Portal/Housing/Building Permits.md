---
type: api-endpoint          
provider: Chicago Data Portal                  
multiple_endpoints: false   
endpoint_pattern:  /api/v3/views/ydr8-5enu/query.json          
method: GET                              
auth: inherit               
domain: housing               
legal_entity_type: municipal          
subject_entity_type: [municipal, property]       
data_tags: [regulatory, permits, geospatial]
status: active                                
update_cadence: daily
last_verified:              
last_reviewed:             
notes:                      
---

## Description

**Note, 10/15/2025:** We have added a PERMIT_CONDITION column.  
  
This dataset includes information about building permits issued by the City of Chicago from 2006 to the present, excluding permits that have been voided or revoked after issuance. Most types of permits are issued subject to payment of the applicable permit fee. Work under a permit may not begin until the applicable permit fee is paid.  
  
For more information about building permits, see [http://www.chicago.gov/permit](http://www.chicago.gov/permit).

## Request Notes
Query params, limits, filters.

## Homelab Usage
Cron jobs, ingest scripts, storage paths.

## Known Quirks
Downtime patterns, format changes, gotchas.
