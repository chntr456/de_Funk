---
type: domain-model-table
table: dim_property_class
extends: _base.property.parcel._dim_property_class
table_type: dimension
transform: distinct
group_by: [class]
primary_key: [property_class_id]

schema:
  - [property_class_id, string, false, "PK - Property class code", {derived: "class"}]
  - [property_class_name, string, true, "Class description", {derived: "class"}]
---

## Property Class Dimension

Distinct property classification codes from assessed values.
