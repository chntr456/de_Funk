---
type: domain-model-table
table: dim_day_type
extends: _base.transportation.transit._dim_day_type
table_type: dimension
from: static
primary_key: [day_type_id]

values:
  - {day_type_id: "W", day_type_code: "W", day_type_name: "Weekday"}
  - {day_type_id: "A", day_type_code: "A", day_type_name: "Saturday"}
  - {day_type_id: "U", day_type_code: "U", day_type_name: "Sunday/Holiday"}

schema:
  - [day_type_id, string, false, "PK"]
  - [day_type_code, string, false, "Day type code"]
  - [day_type_name, string, false, "Display name"]
---

## Day Type Dimension

Static CTA day type reference (W=Weekday, A=Saturday, U=Sunday/Holiday).
