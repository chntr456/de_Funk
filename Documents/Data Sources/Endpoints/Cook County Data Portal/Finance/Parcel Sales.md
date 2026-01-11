---
type: api-endpoint          
provider: Cook County Data Portal                 
multiple_endpoints: false   
endpoint_pattern:  /api/v3/views/wvhk-k5uv/query.json           
method: GET                              
auth: inherit               
domain: finance           
legal_entity_type: county        
subject_entity_type: [county, property]       
data_tags: [ geospatial, property tax, parcel, sales]
status: active                                
update_cadence: monthly
last_verified:              
last_reviewed:             
notes:                      
---

## Description

Parcel sales for real property in Cook County, from 1999 to present. The Assessor's Office uses this data in its modeling to estimate the fair market value of unsold properties.  
  
When working with Parcel Index Numbers (PINs) make sure to zero-pad them to 14 digits. Some datasets may lose leading zeros for PINs when downloaded.  
  
Sale document numbers correspond to those of the Cook County Clerk, and can be used on the [Clerk's website](https://ccrd.cookcountyclerkil.gov/i2/default.aspx) to find more information about each sale.  
  
NOTE: These sales _are_ filtered, but likely include non-arms-length transactions - sales less than $10,000 along with quit claims, executor deeds, beneficial interests are excluded. While the Data Department will upload what it has access to monthly, sales are reported on a lag, with many records not populating until months after their official recording date.  
  
Current property class codes, their levels of assessment, and descriptions can be found [on the Assessor's website](https://prodassets.cookcountyassessor.com/s3fs-public/form_documents/classcode.pdf). Note that class codes details can change across time.  
  
For more information on the sourcing of attached data and the preparation of this dataset, see the [Assessor's Standard Operating Procedures for Open Data](https://github.com/ccao-data/wiki/blob/master/SOPs/Open-Data.md) on GitHub.  
  
[Read about the Assessor's 2025 Open Data Refresh.](https://datacatalog.cookcountyil.gov/stories/s/gzdr-q7c4)

**Update 10/31/2023:** Sales are no longer filtered out of this data set based on deed type, sale price, or recency of sale for a given PIN with the same price. If users wish to recreate the former filtering schema they should set _sale_filter_same_sale_within_365_, _sale_filter_less_than_10k_, and _sale_filter_deed_type_ to False.

## Request Notes
Query params, limits, filters.

## Homelab Usage
Cron jobs, ingest scripts, storage paths.

## Known Quirks
Downtime patterns, format changes, gotchas.