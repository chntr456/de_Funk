---
type: api-endpoint          
provider: Chicago Data Portal                  
multiple_endpoints: false   
endpoint_pattern:  /api/v3/views/4ijn-s7e5/query.json        
method: GET                              
auth: inherit               
domain: regulatory             
legal_entity_type: municipal          
subject_entity_type: [municipal, facility]       
data_tags: [violation, inspection, geographic]
status: active                                
update_cadence: daily
last_verified:              
last_reviewed:             
notes:                      
---



## Description
This information is derived from inspections of restaurants and other food establishments in Chicago from January 1, 2010 to the present. Inspections are performed by staff from the Chicago Department of Public Health’s Food Protection Program using a standardized procedure. The results of the inspection are inputted into a database, then reviewed and approved by a State of Illinois Licensed Environmental Health Practitioner (LEHP). For descriptions of the data elements included in this set, please click [here](https://data.cityofchicago.org/api/assets/BAD5301B-681A-4202-9D25-51B2CAE672FF).

## Request Notes
Query params, limits, filters.

## Homelab Usage
Cron jobs, ingest scripts, storage paths.

## Known Quirks
Downtime patterns, format changes, gotchas.
