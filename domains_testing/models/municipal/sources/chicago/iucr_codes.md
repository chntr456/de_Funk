---
type: domain-model-source
source: iucr_codes
extends: _base.public_safety.crime
maps_to: dim_crime_type
from: bronze.chicago_iucr_codes

aliases:
  - [iucr_code, iucr]
  - [fbi_code, TBD]
  - [primary_type, primary_description]
  - [description, secondary_description]
  - [crime_category, TBD]
  - [crime_subcategory, TBD]
  - [is_index_crime, TBD]
---

## IUCR Codes
Crime type classification reference. Maps IUCR codes to categories.
