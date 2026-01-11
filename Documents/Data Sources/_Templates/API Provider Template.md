---
type: api-provider          # logic type for the notes
provider:                   # Human-readable name of the data source or platform Example: "Chicago Data Portal", "FRED", "NOAA"
api_type: soda              # The request / query dialect used by this provider. soda | rest | graphql | rpc | custom
category: public            # public | self-hosted | internal
base_url:                   # Base API URL that all endpoint paths are appended to 
homepage:                   # Human-facing website (landing pages, dataset browsers). (https://data.cityofchicago.org)
auth_model: api-key         # Authentication model used by the provider.  none | api-key | oauth2 | basic
env_api_key:                # Name of key to load into .env
data_domains: []              # Broad subject areas this provider covers 
legal_entity_type:          # Type of publisher / legal entity
data_tags: []                  # Tags describing data characteristics
status: active              # active | unstable | archived
rate_limit: true            # Whether the provider enforces rate limiting
bulk_download: true         # Whether the provider allows bulk downloads
last_verified:              # Last time this provider was tested
last_reviewed:              # Last time document was reviewed initial date is peer review completion
notes:                      # any general items to include as comments
---

## Description
What this provider is and what kind of data it exposes.


## Homelab Usage Notes
Cron jobs, ingest scripts, caching, retry behavior.

## Known Quirks
Schema drift, field name changes, downtime patterns, rate limits.
