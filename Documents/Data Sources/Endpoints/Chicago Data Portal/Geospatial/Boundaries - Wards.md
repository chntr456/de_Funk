---
type: api-endpoint          
provider: Chicago Data Portal                  
multiple_endpoints: true   
endpoint_pattern: /api/v3/views/htai-wnw4/query.json
method: GET                              
auth: inherit               
domain: Geospatial             
legal_entity_type: municipal          
subject_entity_type: [municipal, geographic-area]       
data_tags: [regulatory, geospatial, reference]
status: active                                
update_cadence: irregular
last_verified:              
last_reviewed:             
notes:                      
---

## Description

Ward boundaries in Chicago corresponding to the dates when a new City Council is sworn in, based on the immediately preceding elections. Neither this description nor the dataset should be relied upon in situations where legal precision is required.  
  
​​​​​This dataset is in a forma​​t for spatial datasets that is inherently tabular but allows for a map as a derived view. Please click the indicated link below for such a map.

Ward boundaries changed corresponding to census changes the prior wards were in effect May 2015 to May 2023. [prior bondaries](https://data.cityofchicago.org/Facilities-Geographic-Boundaries/WARDS_2015/k9yb-bpqx/about_data)

## Available wards boundaries

| Year | view_id | Format | Notes |
|----|----|----|----|
| May 2023 - current | p293-wvbd| JSON | provisional |
| May 2015 - May 2023 | k9yb-bpqx | JSON | provisional |


## Request Notes


## Homelab Usage
Cron jobs, ingest scripts, storage paths.

## Known Quirks
Downtime patterns, format changes, gotchas.