---
type: domain-model-table
table: fact_rail_ridership
extends: _base.transportation.transit._fact_ridership
table_type: fact
from: bronze.chicago_cta_l_ridership
primary_key: [station_id, date]
partition_by: [year]

schema:
  - [station_id, integer, false, "FK to dim_transit_station", {fk: dim_transit_station.station_id, derived: "CAST(station_id AS INT)"}]
  - [date, date, false, "Ridership date"]
  - [year, integer, false, "Year", {derived: "YEAR(date)"}]
  - [day_type_id, string, true, "FK to dim_day_type", {fk: dim_day_type.day_type_id, derived: "daytype"}]
  - [rides, long, true, "Total station entries"]

measures:
  - [total_rides, sum, rides, "Total rides", {format: "#,##0"}]
  - [avg_daily_rides, avg, rides, "Avg daily rides", {format: "#,##0"}]
---

## Rail Ridership Fact Table

Daily L station ridership since 2001. Counts are station entries (turnstile passes).
