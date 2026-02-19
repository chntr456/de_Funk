---
type: domain-model-table
table: dim_property_class
extends: _base.property.parcel._dim_property_class
table_type: dimension
transform: distinct
group_by: [class]
primary_key: [property_class_id]
unique_key: [property_class_code]

schema:
  - [property_class_id, string, false, "PK - Property class code", {derived: "class"}]
  - [property_class_code, string, false, "Natural key (classification code)", {derived: "class"}]
  - [property_class_name, string, true, "Class description", {derived: "COALESCE(class_description, class)"}]
  - [property_category, string, true, "Category rollup", {derived: "CASE WHEN class BETWEEN '200' AND '299' THEN 'RESIDENTIAL' WHEN class BETWEEN '500' AND '599' THEN 'COMMERCIAL' WHEN class BETWEEN '300' AND '399' THEN 'INDUSTRIAL' WHEN class IN ('0', '000', 'EX') THEN 'EXEMPT' ELSE 'OTHER' END", enum: [RESIDENTIAL, COMMERCIAL, INDUSTRIAL, EXEMPT, OTHER]}]
---

## Property Class Dimension

Distinct property classification codes derived from assessed values data.

### Category Mapping (Cook County)

Cook County uses 3-digit numeric class codes. The `property_category` column rolls these into 5 standard categories:

| Code Range | Category | Examples |
|-----------|----------|----------|
| 200-299 | RESIDENTIAL | 202 (1-story, <1000 sqft), 203 (1-story, 1001-1800), 211 (2-3 story, multi) |
| 300-399 | INDUSTRIAL | 300 (industrial land), 313 (manufacturing) |
| 500-599 | COMMERCIAL | 500 (commercial land), 517 (office), 535 (hotel) |
| 0, 000, EX | EXEMPT | Government, religious, educational |
| All other | OTHER | Vacant land, agricultural, railroad |

### Source

Derived from `fact_assessed_values.property_class` using `SELECT DISTINCT class`. No separate source file — this is a data-derived dimension.
