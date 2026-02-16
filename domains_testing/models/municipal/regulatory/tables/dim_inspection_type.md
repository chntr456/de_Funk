---
type: domain-model-table
table: dim_inspection_type
table_type: dimension
from: bronze.chicago_food_inspections
transform: distinct
group_by: [inspection_type]
primary_key: [inspection_type_id]

schema:
  - [inspection_type_id, integer, false, "PK", {derived: "ABS(HASH(COALESCE(inspection_type, 'UNKNOWN')))"}]
  - [inspection_type, string, false, "Inspection type"]
  - [is_routine, boolean, true, "Routine inspection", {derived: "inspection_type LIKE '%Canvass%' OR inspection_type = 'Routine'"}]
---

## Inspection Type Dimension

Distinct food inspection types.
