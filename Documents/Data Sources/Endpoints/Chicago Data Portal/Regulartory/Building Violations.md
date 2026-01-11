---
type: api-endpoint          
provider: Chicago Data Portal                  
multiple_endpoints: false   
endpoint_pattern:  /api/v3/views/22u3-xenr/query.json           
method: GET                              
auth: inherit               
domain: regulatory             
legal_entity_type: municipal          
subject_entity_type: [municipal, property]       
data_tags: [violation, inspection, geospatial]
status: active                                
update_cadence: daily
last_verified:              
last_reviewed:             
notes:                      
---



## Description
Violations issued by the Department of Buildings from 2006 to the present. Lenders and title companies, please note: These data are historical in nature and should not be relied upon for real estate transactions. For transactional purposes such as closings, please consult the title commitment for outstanding enforcement actions in the Circuit Court of Cook County or the Chicago Department of Administrative Hearings. Violations are always associated to an inspection and there can be multiple violation records to one inspection record. Related Applications: Building Data Warehouse [http://www.cityofchicago.org/city/en/depts/bldgs/provdrs/inspect/svcs/building_violationsonline.html](http://www.cityofchicago.org/city/en/depts/bldgs/provdrs/inspect/svcs/building_violationsonline.html). The information presented on this website is informational only and does not necessarily reflect the current condition of the building or property. The dataset contains cases where a respondent has been found to be liable as well as cases where the respondent has been found to be not liable.


## Request Notes
Query params, limits, filters.

## Homelab Usage
Cron jobs, ingest scripts, storage paths.

## Known Quirks
Downtime patterns, format changes, gotchas.
