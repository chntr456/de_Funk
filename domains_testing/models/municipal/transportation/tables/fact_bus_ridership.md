---
type: domain-model-table
table: fact_bus_ridership
table_type: fact
from: bronze.chicago_cta_bus_ridership
primary_key: [route_id, date]
partition_by: [year]

schema:
  - [route_id, string, false, "Bus route ID"]
  - [date, date, false, "Ridership date"]
  - [year, integer, false, "Year", {derived: "YEAR(date)"}]
  - [day_type_id, string, true, "Day type code", {derived: "daytype"}]
  - [rides, long, true, "Total boardings"]

measures:
  - [total_bus_rides, sum, rides, "Total bus rides", {format: "#,##0"}]
---

## Bus Ridership Fact Table

Daily bus route ridership totals.
