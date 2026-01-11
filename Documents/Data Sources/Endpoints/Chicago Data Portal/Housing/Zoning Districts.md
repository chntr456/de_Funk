---
type: api-endpoint          
provider: Chicago Data Portal                  
multiple_endpoints: false   
endpoint_pattern:  /api/v3/views/dj47-wfun/query.json          
method: GET                              
auth: inherit               
domain: housing               
legal_entity_type: municipal          
subject_entity_type: [municipal, geographic-area]       
data_tags: [regulatory, geospatial]
status: active                                
update_cadence: irregularly
last_verified:              
last_reviewed:             
notes:                      
---



## Description

Zoning district boundaries by type and classification.Chicago is divided into zoning districts that regulate land use activities across the city. Data is based on the Chicago Zoning Ordinance and Land Use Ordinance ([https://codelibrary.amlegal.com/codes/chicago/latest/chicagozoning_il/0-0-0-48006](https://codelibrary.amlegal.com/codes/chicago/latest/chicagozoning_il/0-0-0-48006)). Zoning Types are defined in this ordinance. For additional information about business uses, review the License/Zoning Reference (LZR) Guide ([http://bit.ly/vvGzne](http://bit.ly/vvGzne)), which is based on the Municipal Code and is intended to assist business owners in determining the proper zoning district and primary business license for specific business types. Related Applications: Zoning Map ([https://gisapps.cityofchicago.org/zoning/](https://gisapps.cityofchicago.org/zoning/))  
  
This dataset is in a format for spatial datasets that is inherently tabular but allows for a map as a derived view. Please click the indicated link below for such a map.  
  
To export the data in either tabular or geographic format, please use the Export button on this dataset.

[Zones: code library](https://codelibrary.amlegal.com/codes/chicago/latest/chicagozoning_il/0-0-0-48902#JD_Ch.17-2)

## Request Notes
Query params, limits, filters.

## Homelab Usage
Cron jobs, ingest scripts, storage paths.

## Known Quirks
Downtime patterns, format changes, gotchas.
