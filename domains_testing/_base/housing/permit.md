---
type: domain-base
model: permit
version: 1.0
description: "Building permits - construction, renovation, demolition with cost and fee tracking"
extends: _base._base_.event

# CANONICAL FIELDS
# [field_name, type, nullable: bool, description: "meaning"]
canonical_fields:
  - [permit_id, integer, nullable: false, description: "Primary key"]
  - [permit_number, string, nullable: true, description: "Official permit number"]
  - [permit_type_id, integer, nullable: false, description: "FK to dim_permit_type"]
  - [work_type_id, integer, nullable: true, description: "FK to dim_work_type"]
  - [date_id, integer, nullable: false, description: "FK to temporal.dim_calendar (issue date)"]
  - [issue_date, date, nullable: false, description: "Permit issue date"]
  - [year, integer, nullable: false, description: "Issue year (partition key)"]
  - [address, string, nullable: true, description: "Construction address"]
  - [ward, integer, nullable: true, description: "Political ward"]
  - [community_area, integer, nullable: true, description: "Community area / district"]
  - [latitude, double, nullable: true, description: "Location latitude"]
  - [longitude, double, nullable: true, description: "Location longitude"]
  - [total_fee, "decimal(18,2)", nullable: true, description: "Total permit fees"]
  - [estimated_cost, "decimal(18,2)", nullable: true, description: "Estimated construction cost"]

tables:
  _dim_permit_type:
    type: dimension
    primary_key: [permit_type_id]
    unique_key: [permit_type_code]

    # [column, type, nullable, description, {options}]
    schema:
      - [permit_type_id, integer, false, "PK", {derived: "ABS(HASH(permit_type_code))"}]
      - [permit_type_code, string, false, "Permit type code"]
      - [permit_type_name, string, true, "Display name"]
      - [permit_category, string, true, "NEW_CONSTRUCTION, ALTERATION, DEMOLITION, OTHER", {enum: [NEW_CONSTRUCTION, ALTERATION, DEMOLITION, OTHER]}]

    measures:
      - [permit_type_count, count_distinct, permit_type_id, "Permit types", {format: "#,##0"}]

  _dim_work_type:
    type: dimension
    primary_key: [work_type_id]
    unique_key: [work_type_code]

    # [column, type, nullable, description, {options}]
    schema:
      - [work_type_id, integer, false, "PK", {derived: "ABS(HASH(work_type_code))"}]
      - [work_type_code, string, false, "Work type code"]
      - [work_type_name, string, true, "Display name"]
      - [work_category, string, true, "RESIDENTIAL, COMMERCIAL, INDUSTRIAL, OTHER", {enum: [RESIDENTIAL, COMMERCIAL, INDUSTRIAL, OTHER]}]

    measures:
      - [work_type_count, count_distinct, work_type_id, "Work types", {format: "#,##0"}]

  _fact_permits:
    type: fact
    primary_key: [permit_id]
    partition_by: [year]

    # [column, type, nullable, description, {options}]
    schema:
      - [permit_id, integer, false, "PK", {derived: "ABS(HASH(permit_number))"}]
      - [permit_number, string, true, "Official permit number"]
      - [permit_type_id, integer, false, "FK to dim_permit_type", {fk: _dim_permit_type.permit_type_id}]
      - [work_type_id, integer, true, "FK to dim_work_type", {fk: _dim_work_type.work_type_id}]
      - [date_id, integer, false, "FK to calendar (issue date)", {fk: temporal.dim_calendar.date_id, derived: "CAST(DATE_FORMAT(issue_date, 'yyyyMMdd') AS INT)"}]
      - [issue_date, date, false, "Permit issue date"]
      - [year, integer, false, "Issue year", {derived: "YEAR(issue_date)"}]
      - [address, string, true, "Construction address"]
      - [ward, integer, true, "Political ward"]
      - [community_area, integer, true, "Community area"]
      - [latitude, double, true, "Latitude"]
      - [longitude, double, true, "Longitude"]
      - [total_fee, "decimal(18,2)", true, "Total permit fees"]
      - [estimated_cost, "decimal(18,2)", true, "Estimated construction cost"]

    measures:
      - [permit_count, count_distinct, permit_id, "Total permits", {format: "#,##0"}]
      - [total_fees, sum, total_fee, "Total permit fees", {format: "$#,##0.00"}]
      - [total_estimated_cost, sum, estimated_cost, "Total estimated cost", {format: "$#,##0.00"}]
      - [avg_estimated_cost, avg, estimated_cost, "Avg estimated cost", {format: "$#,##0.00"}]

graph:
  edges:
    # [edge_name, from, to, on, type, cross_model]
    - [permit_to_type, _fact_permits, _dim_permit_type, [permit_type_id=permit_type_id], many_to_one, null]
    - [permit_to_work_type, _fact_permits, _dim_work_type, [work_type_id=work_type_id], many_to_one, null]
    - [permit_to_calendar, _fact_permits, temporal.dim_calendar, [date_id=date_id], many_to_one, temporal]

domain: housing
tags: [base, template, housing, permit, construction]
status: active
---

## Permit Base Template

Building and construction permits with permit type classification, work type taxonomy, and cost/fee tracking.

### Permit Categories

| Category | Description |
|----------|-------------|
| NEW_CONSTRUCTION | New building construction |
| ALTERATION | Renovation, remodeling, addition |
| DEMOLITION | Building demolition |
| OTHER | Electrical, plumbing, mechanical |

### Work Categories

| Category | Description |
|----------|-------------|
| RESIDENTIAL | Single-family, multi-family |
| COMMERCIAL | Office, retail, mixed-use |
| INDUSTRIAL | Manufacturing, warehouse |
| OTHER | Institutional, government |

### Usage

```yaml
extends: _base.housing.permit
```
