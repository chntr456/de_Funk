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
data_tags: [budget, public, annual, taxes]
status: active
update_cadence: annual
last_verified:
last_reviewed:
notes:
---

## Description
  
The Annual Appropriation Ordinance is the final City operating budget as approved by the City Council. It reflects the City’s operating budget at the beginning of the fiscal year on January 1
  
This dataset contains the revenue detail portion of the Ordinance for Local funds. “Local” funds are all funds, other than grant funds, used by the City for non-capital operations - including, but not limited to, the Corporate Fund, Water Fund, Midway and O’Hare Airport funds, Vehicle Tax Fund, and the Library Fund.

## Available Years

| Year | view_id | Format | Notes |
|----|----|----|----|
| 2026 | 6694-f78c | JSON | provisional |
| 2025 | e5cq-t86i | JSON | provisional |
| 2024 | rmi8-cugu | JSON | provisional |


## Request Notes
Query params, limits, filters.

## Homelab Usage
Cron jobs, ingest scripts, storage paths.

## Known Quirks
Downtime patterns, format changes, gotchas.
