---
type: api-endpoint          
provider: Cook County Data Portal                 
multiple_endpoints: false   
endpoint_pattern:  /api/v3/views/3723-97qp/query.json           
method: GET                              
auth: inherit               
domain: geospatial            
legal_entity_type: county       
subject_entity_type: [county, property]       
data_tags: [ geospatial,  parcel, reference]
status: active                                
update_cadence: monthly
last_verified:              
last_reviewed:             
notes:                      
---

## Description

Situs and mailing addresses of Cook County parcels. Used by the Assessor's office to mail assessment notices.  
  
_**As of 2017 mailing addresses in this dataset are no longer being regularly updated. We are trying to figure out a solution to this problem.**_  
  
When working with Parcel Index Numbers (PINs) make sure to zero-pad them to 14 digits. Some datasets may lose leading zeros for PINs when downloaded.  
  
Additional notes:  

- Mailing addresses can be out of date or fail to properly reflect deed transfers.
  
- Newer properties may be missing a mailing or property address, as they need to be assigned one by the postal service.
  
- This dataset contains data for the current tax year, which may not yet be complete or final. Assessed values for any given year are subject to change until [review and certification of values by the Cook County Board of Review](https://www.cookcountyassessor.com/assessment-calendar-and-deadlines), though there are a few rare circumstances where values may change for the current or past years after that.
  
- Rowcount for a given year is final once the Assessor [has certified the assessment roll](https://www.cookcountyassessor.com/assessment-calendar-and-deadlines) all townships.
  
- Data will be updated monthly.

For more information on the sourcing of attached data and the preparation of this dataset, see the [Assessor's Standard Operating Procedures for Open Data](https://github.com/ccao-data/wiki/blob/master/SOPs/Open-Data.md) on GitHub.  
  
[Read about the Assessor's 2025 Open Data Refresh.](https://datacatalog.cookcountyil.gov/stories/s/gzdr-q7c4)

## Request Notes
Query params, limits, filters.

## Homelab Usage
Cron jobs, ingest scripts, storage paths.

## Known Quirks
Downtime patterns, format changes, gotchas.