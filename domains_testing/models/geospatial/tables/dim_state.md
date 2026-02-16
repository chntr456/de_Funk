---
type: domain-model-table
table: dim_state
table_type: dimension
from: bronze.us_states
primary_key: [state_id]
unique_key: [state_fips]

schema:
  - [state_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT('STATE_', state_fips)))"}]
  - [state_fips, string, false, "FIPS state code (2 digits)"]
  - [state_abbr, string, false, "State abbreviation"]
  - [state_name, string, false, "Full state name"]
  - [region, string, true, "Census region"]
  - [division, string, true, "Census division"]
  - [latitude, double, true, "Centroid latitude"]
  - [longitude, double, true, "Centroid longitude"]

measures:
  - [state_count, count_distinct, state_id, "Number of states", {format: "#,##0"}]
---

## State Dimension

US states and territories from FIPS codes.
