---
type: api-endpoint          
provider: Chicago Data Portal                  
multiple_endpoints: false   
endpoint_pattern:  /api/v3/views/r5kz-chrr/query.json           
method: GET                              
auth: inherit               
domain: regulatory             
legal_entity_type: municipal          
subject_entity_type: [municipal, facility]       
data_tags: [licenses, geospatial]
status: active                                
update_cadence: daily
last_verified:              
last_reviewed:             
notes:                      
---


## Description

NOTE, 9/25/2025 - We have populated the Address column for [additional records](https://data.cityofchicago.org/stories/s/pnmi-a3z5).  
  
Business licenses issued by the Department of Business Affairs and Consumer Protection in the City of Chicago from 2002 to the present. This dataset contains a large number of records/rows of data and may not be viewed in full in Microsoft Excel. Therefore, when downloading the file, select CSV from the Export menu. Open the file in an ASCII text editor, such as Notepad or Wordpad, to view and search.  
  
Data fields requiring description are detailed below.  
  
APPLICATION TYPE: ‘ISSUE’ is the record associated with the initial license application. ‘RENEW’ is a subsequent renewal record. All renewal records are created with a term start date and term expiration date. ‘C_LOC’ is a change of location record. It means the business moved. ‘C_CAPA’ is a change of capacity record. Only a few license types may file this type of application. ‘C_EXPA’ only applies to businesses that have liquor licenses. It means the business location expanded. 'C_SBA' is a change of business activity record. It means that a new business activity was added or an existing business activity was marked as expired.  
  
LICENSE STATUS: ‘AAI’ means the license was issued. ‘AAC’ means the license was cancelled during its term. ‘REV’ means the license was revoked. 'REA' means the license revocation has been appealed.  
  
LICENSE STATUS CHANGE DATE: This date corresponds to the date a license was cancelled (AAC), revoked (REV) or appealed (REA).  
  
Business License Owner information may be accessed at: [https://data.cityofchicago.org/dataset/Business-Owners/ezma-pppn](https://data.cityofchicago.org/dataset/Business-Owners/ezma-pppn). To identify the owner of a business, you will need the account number or legal name, which may be obtained from this Business Licenses dataset.  
  
Data Owner: Business Affairs and Consumer Protection. Time Period: January 1, 2002 to present. Frequency: Data is updated daily.


## Request Notes
Query params, limits, filters.

## Homelab Usage
Cron jobs, ingest scripts, storage paths.

## Known Quirks
Downtime patterns, format changes, gotchas.