---
type: domain-model
model: chicago_regulatory
version: 1.0
description: "Chicago inspections, violations, and business licenses"


# Dependencies
depends_on:
  - chicago_geospatial

# Storage
storage:
  root: storage/silver/chicago/regulatory
  format: delta

# Build
build:
  partitions: [year]
  optimize: true

# Sources
sources:
  food_inspections:
    bronze_table: chicago_food_inspections
    description: "Food establishment inspections"

  building_violations:
    bronze_table: chicago_building_violations
    description: "Building code violations"

  ordinance_violations:
    bronze_table: chicago_ordinance_violations
    description: "Municipal ordinance violations"

  business_licenses:
    bronze_table: chicago_business_licenses
    description: "Business licenses issued"

# Schema
schema:
  dimensions:
    dim_facility:
      description: "Facility dimension (food establishments)"
      primary_key: [facility_id]
      columns:
        facility_id: {type: string, required: true}
        facility_name: {type: string, description: "Business name"}
        facility_type: {type: string, description: "Restaurant, Grocery, School, etc."}
        risk_level: {type: string, description: "Risk 1 (High), Risk 2 (Medium), Risk 3 (Low)"}
        address: {type: string}
        ward: {type: int}
        community_area: {type: int}
        latitude: {type: double}
        longitude: {type: double}

    dim_inspection_type:
      description: "Inspection type dimension"
      primary_key: [inspection_type_id]
      columns:
        inspection_type_id: {type: string, required: true}
        inspection_type: {type: string}
        is_routine: {type: boolean}

    dim_violation_type:
      description: "Violation type dimension"
      primary_key: [violation_type_id]
      columns:
        violation_type_id: {type: string, required: true}
        violation_code: {type: string}
        violation_description: {type: string}
        severity: {type: string, description: "Critical, Serious, Minor"}

    dim_license_type:
      description: "Business license type dimension"
      primary_key: [license_type_id]
      columns:
        license_type_id: {type: string, required: true}
        license_type: {type: string}
        license_category: {type: string}

  facts:
    fact_food_inspections:
      description: "Food inspection results"
      primary_key: [inspection_id]
      columns:
        inspection_id: {type: string, required: true}
        facility_id: {type: string}
        inspection_type_id: {type: string}
        inspection_date: {type: date}
        year: {type: int}
        result: {type: string, description: "Pass, Fail, Pass w/ Conditions, etc."}
        violations: {type: string, description: "Violation details"}

    fact_building_violations:
      description: "Building code violations"
      primary_key: [violation_id]
      columns:
        violation_id: {type: string, required: true}
        violation_type_id: {type: string}
        violation_date: {type: date}
        year: {type: int}
        address: {type: string}
        ward: {type: int}
        community_area: {type: int}
        status: {type: string, description: "Open, Closed, Complied"}

    fact_business_licenses:
      description: "Business licenses issued"
      primary_key: [license_id]
      columns:
        license_id: {type: string, required: true}
        license_type_id: {type: string}
        business_name: {type: string}
        issue_date: {type: date}
        expiration_date: {type: date}
        year: {type: int}
        address: {type: string}
        ward: {type: int}
        community_area: {type: int}
        status: {type: string}

# Graph
graph:
  nodes:
    dim_facility:
      from: bronze.chicago_food_inspections
      type: dimension
      transform: aggregate
      group_by: [license_]
      derive:
        facility_id: "MD5(CAST(license_ AS STRING))"
      unique_key: [facility_id]

    dim_inspection_type:
      from: bronze.chicago_food_inspections
      type: dimension
      transform: distinct
      columns: [inspection_type]
      derive:
        inspection_type_id: "MD5(COALESCE(inspection_type, 'UNKNOWN'))"
        is_routine: "inspection_type LIKE '%Canvass%' OR inspection_type = 'Routine'"
      unique_key: [inspection_type_id]

    fact_food_inspections:
      from: bronze.chicago_food_inspections
      type: fact
      derive:
        facility_id: "MD5(CAST(license_ AS STRING))"
        inspection_type_id: "MD5(COALESCE(inspection_type, 'UNKNOWN'))"
      unique_key: [inspection_id]

  edges:
    inspection_to_facility:
      from: fact_food_inspections
      to: dim_facility
      on: [facility_id=facility_id]
      type: many_to_one

    inspection_to_type:
      from: fact_food_inspections
      to: dim_inspection_type
      on: [inspection_type_id=inspection_type_id]
      type: many_to_one

# Measures
measures:
  simple:
    inspection_count:
      description: "Number of inspections"
      source: fact_food_inspections.inspection_id
      aggregation: count
      format: "#,##0"

    pass_count:
      description: "Inspections with Pass result"
      source: fact_food_inspections.inspection_id
      aggregation: count
      filters:
        - "result = 'Pass'"
      format: "#,##0"

    fail_count:
      description: "Inspections with Fail result"
      source: fact_food_inspections.inspection_id
      aggregation: count
      filters:
        - "result = 'Fail'"
      format: "#,##0"

    facility_count:
      description: "Number of facilities"
      source: dim_facility.facility_id
      aggregation: count_distinct
      format: "#,##0"

    violation_count:
      description: "Number of building violations"
      source: fact_building_violations.violation_id
      aggregation: count
      format: "#,##0"

    license_count:
      description: "Number of business licenses"
      source: fact_business_licenses.license_id
      aggregation: count
      format: "#,##0"

  computed:
    pass_rate:
      description: "Percentage of inspections passed"
      formula: "pass_count / inspection_count * 100"
      format: "#,##0.0%"

    fail_rate:
      description: "Percentage of inspections failed"
      formula: "fail_count / inspection_count * 100"
      format: "#,##0.0%"

# Metadata
metadata:
  domain: city
  entity: chicago
  subdomain: regulatory
status: active
---

## Chicago Regulatory Model

Inspections, violations, and business licenses for the City of Chicago.

### Data Sources

| Source | Bronze Table | Description |
|--------|--------------|-------------|
| Food Inspections | chicago_food_inspections | Restaurant/food establishment inspections |
| Building Violations | chicago_building_violations | Building code violations |
| Ordinance Violations | chicago_ordinance_violations | Municipal ordinance violations |
| Business Licenses | chicago_business_licenses | Business licenses issued |

### Food Inspection Results

| Result | Description |
|--------|-------------|
| Pass | No critical or serious violations |
| Pass w/ Conditions | Minor violations, follow-up required |
| Fail | Critical violations, must be corrected |
| Out of Business | Establishment closed |
| Not Ready | Inspection not completed |

### Risk Levels

| Level | Description | Inspection Frequency |
|-------|-------------|---------------------|
| Risk 1 (High) | Full food prep | More frequent |
| Risk 2 (Medium) | Limited food prep | Regular |
| Risk 3 (Low) | Prepackaged only | Less frequent |

### Example Queries

```sql
-- Inspection results by facility type
SELECT
    f.facility_type,
    i.result,
    COUNT(*) as inspection_count
FROM fact_food_inspections i
JOIN dim_facility f ON i.facility_id = f.facility_id
WHERE i.year = 2023
GROUP BY f.facility_type, i.result
ORDER BY f.facility_type, inspection_count DESC;

-- Pass rate by community area
SELECT
    ca.community_name,
    COUNT(*) as total_inspections,
    SUM(CASE WHEN i.result = 'Pass' THEN 1 ELSE 0 END) as passed,
    ROUND(100.0 * SUM(CASE WHEN i.result = 'Pass' THEN 1 ELSE 0 END) / COUNT(*), 1) as pass_rate
FROM fact_food_inspections i
JOIN dim_facility f ON i.facility_id = f.facility_id
JOIN chicago_geospatial.dim_community_area ca ON f.community_area = ca.area_number
WHERE i.year = 2023
GROUP BY ca.community_name
ORDER BY pass_rate ASC;

-- Active business licenses by type
SELECT
    lt.license_type,
    COUNT(*) as active_licenses
FROM fact_business_licenses l
JOIN dim_license_type lt ON l.license_type_id = lt.license_type_id
WHERE l.status = 'Active'
  AND l.expiration_date > CURRENT_DATE
GROUP BY lt.license_type
ORDER BY active_licenses DESC;
```
