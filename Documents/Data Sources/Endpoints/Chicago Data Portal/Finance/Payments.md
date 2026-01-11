---
type: api-endpoint
provider: Chicago Data Portal
multiple_endpoints: true
endpoint_pattern: /api/v3/views/s4vu-giwb/query.json
method: GET
auth: inherit
domain: finance
legal_entity_type: municipal
subject_entity_tags: [municipal, corporate]
data_tags: [spending]
status: active
update_cadence: daily
last_verified:
last_reviewed:
notes:
---

## Description
All vendor payments made by the City of Chicago from 1996 to present. Payments from 1996 through 2002 have been rolled-up and appear as "2002." Total payment information is summarized for each vendor and contract number for data older than two years. These data are extracted from the City’s Vendor, Contract, and Payment Search.  
  
Time Period: 1996 to present.  
  
Frequency: Data is updated daily.

## Request Notes
Query params, limits, filters.

## Homelab Usage
Cron jobs, ingest scripts, storage paths.

## Known Quirks
Downtime patterns, format changes, gotchas.