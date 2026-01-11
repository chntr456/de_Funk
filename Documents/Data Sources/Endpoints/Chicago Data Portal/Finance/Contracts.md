---
type: api-endpoint
provider: Chicago Data Portal
multiple_endpoints: true
endpoint_pattern: /api/v3/views/rsxa-ify5/query.json
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
Contracts and modifications awarded by the City of Chicago since 1993. This data is currently maintained in the City’s Financial Management and Purchasing System (FMPS), which is used throughout the City for contract management and payment.

  
Blanket vs. Standard Contracts: Only blanket contracts (contracts for repeated purchases) have FMPS end dates. Standard contracts (for example, construction contracts) terminate upon completion and acceptance of all deliverables. These dates are tracked outside of FMPS.  
  
Negative Modifications: Some contracts are modified to delete scope and money from a contract. These reductions are indicated by negative numbers in the Award Amount field of this dataset.  
  
Data Owner: Procurement Services.  
Time Period: 1993 to present.  
Frequency: Data is updated daily.

## Request Notes
Query params, limits, filters.

## Homelab Usage
Cron jobs, ingest scripts, storage paths.

## Known Quirks
Downtime patterns, format changes, gotchas.
