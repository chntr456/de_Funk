---
type: domain-model-table
table: dim_zoning_district
table_type: dimension
from: bronze.chicago_zoning_districts
primary_key: [zone_class]

schema:
  - [zone_class, string, false, "Zoning classification"]
  - [zone_description, string, true, "Description"]
  - [zone_category, string, true, "Category", {derived: "CASE WHEN zone_class LIKE 'R%' THEN 'Residential' WHEN zone_class LIKE 'B%' THEN 'Business' WHEN zone_class LIKE 'C%' THEN 'Commercial' WHEN zone_class LIKE 'M%' THEN 'Manufacturing' WHEN zone_class LIKE 'PD%' THEN 'Planned Development' ELSE 'Other' END"}]
  - [geometry, string, true, "District boundary WKT"]
---

## Zoning District Dimension

Chicago zoning classifications.
