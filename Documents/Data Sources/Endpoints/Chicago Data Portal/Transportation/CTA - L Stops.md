---
type: api-endpoint          
provider: Chicago Data Portal                  
multiple_endpoints: false   
endpoint_pattern:  /api/v3/views/8pix-ypme/query.json           
method: GET                              
auth: inherit               
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

This list of 'L' stops provides location and basic service availability information for each place on the CTA system where a train stops, along with formal station names and stop descriptions.

## Request Notes
Query params, limits, filters.

## Homelab Usage
Cron jobs, ingest scripts, storage paths.

## Known Quirks
Downtime patterns, format changes, gotchas.