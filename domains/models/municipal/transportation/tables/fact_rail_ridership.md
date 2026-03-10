---
type: domain-model-table
table: fact_rail_ridership
extends: _base.transportation.transit._fact_ridership
table_type: fact
primary_key: [station_id, date]
partition_by: [year]

schema:
  - [station_id, integer, false, "FK to dim_transit_station", {fk: dim_transit_station.station_id, derived: "CAST(station_id AS INT)"}]
  - [date, date, false, "Ridership date"]
  - [year, integer, false, "Year", {derived: "YEAR(date)"}]
  - [date_id, integer, false, "FK to dim_calendar", {fk: temporal.dim_calendar.date_id, derived: "CAST(DATE_FORMAT(date, 'yyyyMMdd') AS INT)"}]
  - [rides, long, true, "Total station entries"]

measures:
  - [total_rides, sum, rides, "Total rides", {format: "#,##0"}]
  - [avg_daily_rides, avg, rides, "Avg daily rides", {format: "#,##0"}]
---

## Rail Ridership Fact Table

Daily L station ridership since 2001. Counts are station entries (turnstile passes).
