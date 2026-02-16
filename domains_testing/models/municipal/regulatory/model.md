---
type: domain-model
model: municipal_regulatory
version: 3.0
description: "Municipal inspections, violations, and business licenses"
extends: [_base.regulatory.inspection]
depends_on: [municipal_geospatial]

storage:
  format: delta
  sources_from: sources/{entity}/
  silver:
    root: storage/silver/municipal/{entity}/regulatory/

graph:
  edges:
    - [inspection_to_facility, fact_food_inspections, dim_facility, [facility_id=facility_id], many_to_one, null]
    - [inspection_to_type, fact_food_inspections, dim_inspection_type, [inspection_type_id=inspection_type_id], many_to_one, null]

build:
  partitions: [year]
  optimize: true
  phases:
    1: { tables: [dim_facility, dim_inspection_type, dim_violation_type, dim_license_type] }
    2: { tables: [fact_food_inspections, fact_building_violations, fact_business_licenses] }

measures:
  simple:
    - [inspection_count, count, fact_food_inspections.inspection_id, "Inspections", {format: "#,##0"}]
    - [facility_count, count_distinct, dim_facility.facility_id, "Facilities", {format: "#,##0"}]
    - [violation_count, count, fact_building_violations.violation_id, "Violations", {format: "#,##0"}]
    - [license_count, count, fact_business_licenses.license_id, "Licenses", {format: "#,##0"}]
  computed:
    - [pass_rate, expression, "pass_count / inspection_count * 100", "Pass rate %", {format: "#,##0.0%"}]

metadata:
  domain: municipal
  subdomain: regulatory
status: active
---

## Municipal Regulatory Model

Food inspections, building violations, and business licenses.

### Risk Levels

| Level | Description |
|-------|-------------|
| Risk 1 (High) | Full food prep |
| Risk 2 (Medium) | Limited food prep |
| Risk 3 (Low) | Prepackaged only |
