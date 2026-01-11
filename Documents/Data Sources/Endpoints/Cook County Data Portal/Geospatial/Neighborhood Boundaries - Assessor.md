---
type: api-endpoint          
provider: Cook County Data Portal                 
multiple_endpoints: false   
endpoint_pattern:  /api/v3/views/pcdw-pxtg/query.json           
method: GET                              
auth: inherit               
domain: geospatial            
legal_entity_type: county 
subject_entity_type: [county, property]       
data_tags: [ geospatial,  reference]
status: active                                
update_cadence: monthly
last_verified:              
last_reviewed:             
notes:                      
---

## Description

Neighborhood polygons used by the Cook County Assessor's Office for valuation and reporting. These neighborhoods are specific to the Assessor. They are intended to represent homogenous housing submarkets, NOT Chicago community areas or municipalities.  
  
These neighborhoods were reconstructed from individual parcels using spatial buffering and simplification. The full transformation script can be found on [the Assessor's GitHub](https://github.com/ccao-data/data-architecture/blob/master/aws-s3/scripts-ccao-data-warehouse-us-east-1/spatial-ccao-neighborhood.R).  
  
[Read about the Assessor's 2025 Open Data Refresh.](https://datacatalog.cookcountyil.gov/stories/s/gzdr-q7c4)

## Request Notes
Query params, limits, filters.

## Homelab Usage
Cron jobs, ingest scripts, storage paths.

## Known Quirks
Downtime patterns, format changes, gotchas.