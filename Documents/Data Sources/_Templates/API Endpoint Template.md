---
type: api-endpoint          # logic type for the notes
provider:                   # Name of the provider this endpoint belongs to Must match a provider note
multiple_endpoints: false   # Whether mutliple sources are required to accumalte all data covered
endpoint_pattern:           # Example: /resource/{dataset_id}.{format}
method: GET                 # HTTP method used to access the endpoint
format: json                # json | csv | xml | geojson
auth: inherit               # inherit | none | api-key | basic
domain:                     # choose from domain list below
legal_entity_type:          # Type of publisher / legal entity. Usually inherited from provider
subject_entity_type: []       # Who is the data about [corportate,municipal] 
data_tags: []                 # Descriptive tags about the dataset. Pick many [time-series, public, daily] 
status: active              # active | flaky | deprecated
rate_limit: inherit         # Whether this endpoint enforces rate limits
pagination: false           # Whether pagination is required for full data pulls
bulk_download: false        # Whether bulk downloads (full dataset) are available
update_cadence: irregular   # Typical data refresh cadence. annual | monthly | irrergular
last_verified:              # Last time this endpoint was tested
last_reviewed:              # Last time document was reviewed initial date after peer review
notes:                      # any general items to include as comments
---



## Description
What data this endpoint returns.

## Request Notes
Query params, limits, filters.

## Homelab Usage
Cron jobs, ingest scripts, storage paths.

## Known Quirks
Downtime patterns, format changes, gotchas.
