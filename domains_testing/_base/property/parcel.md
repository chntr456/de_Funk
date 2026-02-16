---
type: domain-base
model: parcel
version: 1.0
description: "Property parcels - land records, assessments, and sales transactions"
extends: _base._base_.entity

# CANONICAL FIELDS
# [field_name, type, nullable: bool, description: "meaning"]
canonical_fields:
  - [parcel_id, string, nullable: false, description: "Primary key (PIN or parcel number)"]
  - [parcel_code, string, nullable: false, description: "Natural key (standardized PIN)"]
  - [property_class, string, nullable: true, description: "Property classification code"]
  - [township_code, string, nullable: true, description: "Township/municipality code"]
  - [neighborhood_code, string, nullable: true, description: "Neighborhood/area code"]
  - [year_built, integer, nullable: true, description: "Year of construction"]
  - [land_sqft, double, nullable: true, description: "Land area in square feet"]
  - [building_sqft, double, nullable: true, description: "Building area in square feet"]
  - [latitude, double, nullable: true, description: "Parcel centroid latitude"]
  - [longitude, double, nullable: true, description: "Parcel centroid longitude"]
  - [tax_code, string, nullable: true, description: "Tax district code"]

tables:
  _dim_parcel:
    type: dimension
    primary_key: [parcel_id]
    unique_key: [parcel_code]

    # [column, type, nullable, description, {options}]
    schema:
      - [parcel_id, string, false, "PK (PIN)", {derived: "LPAD(REGEXP_REPLACE(pin, '[^0-9]', ''), 14, '0')"}]
      - [parcel_code, string, false, "Natural key"]
      - [property_class, string, true, "Classification code"]
      - [township_code, string, true, "Township"]
      - [neighborhood_code, string, true, "Neighborhood"]
      - [year_built, integer, true, "Construction year"]
      - [land_sqft, double, true, "Land area sq ft"]
      - [building_sqft, double, true, "Building area sq ft"]
      - [latitude, double, true, "Centroid latitude"]
      - [longitude, double, true, "Centroid longitude"]
      - [tax_code, string, true, "Tax district"]

    measures:
      - [parcel_count, count_distinct, parcel_id, "Number of parcels", {format: "#,##0"}]

  _dim_property_class:
    type: dimension
    primary_key: [property_class_id]
    unique_key: [property_class_code]

    # [column, type, nullable, description, {options}]
    schema:
      - [property_class_id, string, false, "PK (classification code)"]
      - [property_class_code, string, false, "Natural key"]
      - [property_class_name, string, true, "Description"]
      - [property_category, string, true, "RESIDENTIAL, COMMERCIAL, INDUSTRIAL, EXEMPT, OTHER", {enum: [RESIDENTIAL, COMMERCIAL, INDUSTRIAL, EXEMPT, OTHER]}]

    measures:
      - [class_count, count_distinct, property_class_id, "Property classes", {format: "#,##0"}]

  _fact_assessed_values:
    type: fact
    primary_key: [parcel_id, year, assessment_stage]
    partition_by: [year]

    # [column, type, nullable, description, {options}]
    schema:
      - [parcel_id, string, false, "FK to dim_parcel", {fk: _dim_parcel.parcel_id}]
      - [year, integer, false, "Assessment year"]
      - [date_id, integer, false, "FK to calendar (Jan 1 of assessment year)", {fk: temporal.dim_calendar.date_id, derived: "CAST(CONCAT(year, '0101') AS INT)"}]
      - [assessment_stage, string, false, "Stage (mailed, certified, appeal)", {enum: [MAILED, CERTIFIED, BOARD_CERTIFIED, APPEAL]}]
      - [av_land, "decimal(18,2)", true, "Assessed value - land"]
      - [av_building, "decimal(18,2)", true, "Assessed value - building"]
      - [av_total, "decimal(18,2)", true, "Assessed value - total"]
      - [property_class, string, true, "Classification at assessment time"]
      - [township_code, string, true, "Township at assessment time"]

    measures:
      - [total_assessed_value, sum, av_total, "Total assessed value", {format: "$#,##0.00"}]
      - [avg_assessed_value, avg, av_total, "Average assessed value", {format: "$#,##0.00"}]
      - [assessment_count, count, parcel_id, "Assessment records", {format: "#,##0"}]

  _fact_parcel_sales:
    type: fact
    primary_key: [parcel_id, sale_date]
    partition_by: [year]

    # [column, type, nullable, description, {options}]
    schema:
      - [parcel_id, string, false, "FK to dim_parcel", {fk: _dim_parcel.parcel_id}]
      - [sale_date, date, false, "Date of sale"]
      - [sale_date_id, integer, false, "FK to calendar", {fk: temporal.dim_calendar.date_id, derived: "CAST(DATE_FORMAT(sale_date, 'yyyyMMdd') AS INT)"}]
      - [year, integer, false, "Sale year", {derived: "YEAR(sale_date)"}]
      - [sale_price, "decimal(18,2)", true, "Sale price"]
      - [sale_type, string, true, "Transaction type"]

    measures:
      - [total_sales_volume, sum, sale_price, "Total sales volume", {format: "$#,##0.00"}]
      - [avg_sale_price, avg, sale_price, "Average sale price", {format: "$#,##0.00"}]
      - [sale_count, count, parcel_id, "Number of sales", {format: "#,##0"}]

graph:
  edges:
    # [edge_name, from, to, on, type, cross_model]
    - [assessment_to_parcel, _fact_assessed_values, _dim_parcel, [parcel_id=parcel_id], many_to_one, null]
    - [assessment_to_calendar, _fact_assessed_values, temporal.dim_calendar, [date_id=date_id], many_to_one, temporal]
    - [sale_to_parcel, _fact_parcel_sales, _dim_parcel, [parcel_id=parcel_id], many_to_one, null]
    - [sale_to_calendar, _fact_parcel_sales, temporal.dim_calendar, [sale_date_id=date_id], many_to_one, temporal]

domain: property
tags: [base, template, property, parcel, assessment]
status: active
---

## Parcel Base Template

Property parcel data including land records, assessments, and sales. Parcel IDs (PINs) are standardized to 14-digit zero-padded format for cross-dataset joins.

### Assessment Stages

| Stage | Description |
|-------|-------------|
| MAILED | Initial mailed assessment |
| CERTIFIED | Certified by assessor |
| BOARD_CERTIFIED | Certified by board of review |
| APPEAL | Post-appeal value |

### Property Categories

```
RESIDENTIAL: Single-family, multi-family, condos
COMMERCIAL: Office, retail, mixed-use
INDUSTRIAL: Manufacturing, warehouse
EXEMPT: Government, religious, educational
OTHER: Vacant land, agricultural
```

### Usage

```yaml
extends: _base.property.parcel
```
