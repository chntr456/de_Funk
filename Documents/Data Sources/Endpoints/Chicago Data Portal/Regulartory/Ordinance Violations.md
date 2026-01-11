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
data_tags: [violation, ordinance, geospatial]
status: active                                
update_cadence: daily
last_verified:              
last_reviewed:             
notes:                      
---

## Description

List of ordinance violations filed with the Department of Administrative Hearings. This data set reflects violations brought before the Chicago Department of Administrative Hearings. It does not reflect violations brought before the Circuit Court of Cook County. Each row of data represents a unique violation. Multiple violations may be associated with a single case. The most recent status of the case is shown in the dataset and is updated daily. Hearing date corresponds to the date of the most recent hearing. Each case often consists of multiple hearings and may encounter continuances due to various circumstances before a final disposition is rendered. The case disposition, date of the disposition, and any applicable fines and administrative costs are listed when the case is fully completed. The latest hearing status or disposition reflects the condition of the property at that time and may not reflect the current condition of the property. When multiple respondents are cited, each respondent is separated by a pipe ("|") character. Respondents sometimes are added to cases for technical legal reasons so are not necessarily the parties believed to have committed the violations. This dataset currently lists violations issued by the Department of Buildings. Additional ordinance violations will be added over time. Therefore, it is advisable to use the department-specific filtered view listed under the More Views button for purposes that require only one department's violations.

**Note: For questions related to a specific violation or code requirements, please contact the department that issued the violation notice. For questions regarding the hearings process, a hearing date, or a hearing disposition, please contact the Department of Administrative Hearings.** Contact information can be found under "Government" at the top of [https://www.chicago.gov](https://www.chicago.gov/). For questions related to using the dataset, please use the Contact Dataset Owner button below.

## Request Notes
Query params, limits, filters.

## Homelab Usage
Cron jobs, ingest scripts, storage paths.

## Known Quirks
Downtime patterns, format changes, gotchas.