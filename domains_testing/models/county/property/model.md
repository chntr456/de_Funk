---
type: domain-model
model: county_property
version: 3.0
description: "County property assessments, parcels, and sales"
extends: [_base.property.parcel]
depends_on: [temporal, county_geospatial]

storage:
  format: delta
  sources_from: sources/{entity}/
  silver:
    root: storage/silver/county/{entity}/property/

graph:
  edges:
    - [assessed_to_parcel, fact_assessed_values, dim_parcel, [parcel_id=parcel_id], many_to_one, null]
    - [sales_to_parcel, fact_parcel_sales, dim_parcel, [parcel_id=parcel_id], many_to_one, null]
    - [assessed_to_calendar, fact_assessed_values, temporal.dim_calendar, ["CAST(DATE_FORMAT(MAKE_DATE(year, 1, 1), 'yyyyMMdd') AS INT)=date_id"], many_to_one, temporal]
    - [sales_to_calendar, fact_parcel_sales, temporal.dim_calendar, [sale_date_id=date_id], many_to_one, temporal]
    - [parcel_to_township, dim_parcel, county_geospatial.dim_township, [township_code=township_code], many_to_one, county_geospatial]

build:
  partitions: [year]
  sort_by: [parcel_id, year]
  optimize: true
  phases:
    1: { tables: [dim_parcel, dim_property_class] }
    2: { tables: [fact_assessed_values, fact_parcel_sales] }

measures:
  simple:
    - [parcel_count, count_distinct, dim_parcel.parcel_id, "Number of parcels", {format: "#,##0"}]
    - [total_assessed_value, sum, fact_assessed_values.av_total, "Total assessed value", {format: "$#,##0"}]
    - [avg_assessed_value, avg, fact_assessed_values.av_total, "Average assessed value", {format: "$#,##0"}]
    - [total_sales_volume, sum, fact_parcel_sales.sale_price, "Total sales volume", {format: "$#,##0"}]
    - [avg_sale_price, avg, fact_parcel_sales.sale_price, "Average sale price", {format: "$#,##0"}]
    - [sale_count, count, fact_parcel_sales.parcel_id, "Number of sales", {format: "#,##0"}]
  computed:
    - [median_sale_price, expression, "PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY sale_price)", "Median sale price", {format: "$#,##0", source_table: fact_parcel_sales}]

metadata:
  domain: county
  subdomain: property
status: active
---

## County Property Model

Property assessments, parcels, and sales.

### Key Concepts

**PIN Format**: 14-digit Parcel Index Number, must be zero-padded.

**Assessment Stages**:
1. `mailed` - Initial values sent to owners
2. `certified` - After Assessor appeals
3. `bor_certified` - After Board of Review appeals
