---
type: api-endpoint          
provider: Cook County Data Portal                 
multiple_endpoints: false   
endpoint_pattern:  /api/v3/views/7pny-nedm/query.json           
method: GET                              
auth: inherit               
domain: regulatory            
legal_entity_type: county        
subject_entity_type: [county, property]       
data_tags: [ geospatial, appeals, parcel, board of review]
status: active                                
update_cadence: monthly
last_verified:              
last_reviewed:             
notes:                      
---

## Description

Historic land, building, and total assessed values for all Cook County parcels appealed with the Board of Review, from 2010 to present. The Board of Review uses these values for reporting, evaluating assessment performance over time, and research.  
  
When working with Parcel Index Numbers (PINs) make sure to zero-pad them to 14 digits. Some datasets may lose leading zeros for PINs when downloaded  
  
This data is parcel-level. Each row contains the assessed values for a single PIN for a single year. Important notes:  
• Assessed values are available when the Board of Review closes appeals and certifies the values.  
• The values in this data are assessed values, NOT market values. Assessed values must be adjusted by their level of assessment ([https://prodassets.cookcountyassessor.com/s3fs-public/form_documents/classcode.pdf](https://prodassets.cookcountyassessor.com/s3fs-public/form_documents/classcode.pdf)) to arrive at market value. Note that levels of assessment may have changed throughout the time period covered by this data set.  
• This data set will be updated when each township is certified. However, note that there may be discrepancies between the Board of Review’s data and the Assessor's site and this data set, as each pull from a slightly different system.  
• Current property class codes, their levels of assessment, and descriptions can be found on the Assessor's website ([https://prodassets.cookcountyassessor.com/s3fs-public/form_documents/classcode.pdf](https://prodassets.cookcountyassessor.com/s3fs-public/form_documents/classcode.pdf)). Note that class codes details can change across time.  
• The Change Reason and No Change Reason fields are only populated starting with the 2015 year data.  
  
All data provided here is prepared for internal purposes by the County of Cook only is provided to the public as a courtesy.  
  
While efforts have been made to be as accurate as possible, Cook County provides the data for personal use “as is”. The data is not guaranteed to be accurate, correct, or complete. Information provided should not be used as a substitute for legal, business, tax, or other professional advice. The recipient/viewer should contact appropriate regulating agencies to determine accuracy or suitability of the data for a particular use. This data may not be used in states that do not allow the exclusion or limitation of incidental or consequential damages.  
  
Cook County or its staff assume no liability whatsoever for any losses that might occur from the use, misuse, or inability to use its geospatial data, maps or websites. All materials appearing on a map, geospatial data or County web site are transmitted without warranty of any kind and are subject to the terms on this disclaimer.


## Request Notes
Query params, limits, filters.

## Homelab Usage
Cron jobs, ingest scripts, storage paths.

## Known Quirks
Downtime patterns, format changes, gotchas.