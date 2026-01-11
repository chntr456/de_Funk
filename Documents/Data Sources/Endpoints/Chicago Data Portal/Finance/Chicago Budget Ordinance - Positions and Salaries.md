---
type: api-endpoint
provider: Chicago Data Portal
multiple_endpoints: true
endpoint_pattern: /api/v3/views/{view_id}/query.json
method: GET
auth: inherit
domain: finance
legal_entity_type: municipal
subject_entity_tags: [municipal]
data_tags: [budget, public, annual, admin]
status: active
update_cadence: annual
last_verified:
last_reviewed:
notes:
---

## Description
The Annual Appropriation Ordinance is the final City operating budget as approved by the City Council. It reflects the City’s operating budget at the beginning of the fiscal year on January 1.
  
This dataset displays the positions and related salaries detailed in the budget as of January 1. It is extracted from the personnel portion of the Appropriation Ordinance. The dataset presents the position titles (without names) and salaries described in the budget, but does not provide a reflection of the current city workforce with full names and salaries.  
  
Disclaimer: the “Total Budgeted Units” column displays either A) the number of employees AND vacancies associated with a given position, or B) the number of budgeted units (ie. hours/months) for that position. “Position Control” determines whether Total Budgeted Units column will count employees and vacancies or hours/months. If a Position Control is 1, then employees and vacancies are displayed; if a Position Control is 0, then the total number of hours/months recorded is displayed.

## Available Years

| Year | view_id | Format | Notes |
|----|----|----|----|
| 2026 | 6694-f78c | JSON | provisional |
| 2025 | 2bp7-w85v | JSON | provisional |
| 2024 | jeta-egyx | JSON | provisional |
| 2023 | pkjy-hzin | JSON | provisional |
| 2022 | v2mx-icwv | JSON | provisional |
| 2021 | gcwx-xm5a | JSON | provisional |
| 2020 | txys-725h | JSON | provisional |
| 2019 | 7zkb-yr4j | JSON | provisional |
| 2018 | 9d7d-7f2b | JSON | provisional |
| 2017 | vcfx-7p4u | JSON | provisional |
| 2016 | ipsp-k4xh | JSON | provisional |
| 2015 | f338-e9ns | JSON | provisional |
| 2014 | etzw-ycze | JSON | provisional |
| 2013 | 78az-bt2s | JSON | provisional |
| 2012 | 4n2t-us8h | JSON | provisional |
| 2011 | g398-fhbm | JSON | provisional |


## Request Notes
Query params, limits, filters.

## Homelab Usage
Cron jobs, ingest scripts, storage paths.

## Known Quirks
Downtime patterns, format changes, gotchas.
