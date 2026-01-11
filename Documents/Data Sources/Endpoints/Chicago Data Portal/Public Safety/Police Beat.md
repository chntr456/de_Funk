---
type: api-endpoint          
provider: Chicago Data Portal                  
multiple_endpoints: false   
endpoint_pattern: /api/v3/views/n9it-hstw/query.json  
method: GET                              
auth: inherit               
domain: public-safety             
legal_entity_type: municipal          
subject_entity_type: [municipal, geographic-area]       
data_tags: [police, geospatial, reference]
status: active                                
update_cadence: irregular
last_verified:              
last_reviewed:             
notes:                      
---



## Description

Current police beat boundaries in Chicago. The data can be viewed on the Chicago Data Portal with a web browser. However, to view or use the files outside of a web browser, you will need to use compression software and special GIS software, such as ESRI ArcGIS (shapefile) or Google Earth (KML or KMZ), is required.

For simplicity grabbing only current beats, however a different set of beats where in place at different times.


## Request Notes


## Homelab Usage
Cron jobs, ingest scripts, storage paths.

## Known Quirks
Downtime patterns, format changes, gotchas.