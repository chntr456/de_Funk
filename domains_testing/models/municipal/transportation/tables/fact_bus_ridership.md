---
type: domain-model-table
table: fact_bus_ridership
extends: _base.transportation.transit._fact_ridership
table_type: fact
primary_key: [route_id, date]
partition_by: [year]

schema:
  - [route_id, string, false, "Bus route ID"]
  - [date, date, false, "Ridership date"]
  - [year, integer, false, "Year", {derived: "YEAR(date)"}]
  - [date_id, integer, false, "FK to dim_calendar", {fk: temporal.dim_calendar.date_id, derived: "CAST(DATE_FORMAT(date, 'yyyyMMdd') AS INT)"}]
  - [rides, long, true, "Total boardings"]

measures:
  - [total_bus_rides, sum, rides, "Total bus rides", {format: "#,##0"}]
---

## Bus Ridership Fact Table

Daily bus route ridership totals.
