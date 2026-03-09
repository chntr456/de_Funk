---
type: domain-model-table
table: fact_assessed_values
extends: _base.property.parcel._fact_assessed_values
table_type: fact
primary_key: [parcel_id, year, assessment_stage]
partition_by: [year]

schema:
  - [parcel_id, string, false, "FK to dim_parcel", {fk: dim_parcel.parcel_id, derived: "LPAD(pin, 14, '0')"}]
  - [year, integer, false, "Assessment year"]
  - [date_id, integer, false, "FK to calendar (Jan 1 of assessment year)", {fk: temporal.dim_calendar.date_id, derived: "CAST(CONCAT(year, '0101') AS INT)"}]
  - [assessment_stage, string, false, "mailed, certified, bor_certified", {derived: "stage_name"}]
  - [av_land, double, true, "Assessed value - land", {derived: "av_land"}]
  - [av_building, double, true, "Assessed value - building", {derived: "av_bldg"}]
  - [av_total, double, true, "Assessed value - total", {derived: "av_tot"}]
  - [property_class, string, true, "Property class", {derived: "class"}]
  - [township_code, string, true, "Township code"]

measures:
  - [total_assessed_value, sum, av_total, "Total assessed value", {format: "$#,##0"}]
  - [avg_assessed_value, avg, av_total, "Average assessed value", {format: "$#,##0"}]
---

## Assessed Values Fact Table

Annual assessed values by parcel. Filters: `year >= 2010`.
