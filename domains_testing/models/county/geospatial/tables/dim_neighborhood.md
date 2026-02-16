---
type: domain-model-table
table: dim_neighborhood
table_type: dimension
from: bronze.cook_county_neighborhoods
primary_key: [nbhd_code]

schema:
  - [nbhd_code, string, false, "PK - Neighborhood code"]
  - [nbhd_name, string, true, "Neighborhood name"]
  - [township_code, string, true, "Township code"]
  - [geometry, string, true, "Neighborhood boundary WKT"]
---

## Neighborhood Dimension

~200 Assessor-defined neighborhoods for property valuation comparables.
