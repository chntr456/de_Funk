---
type: domain-model
model: municipal_transportation
version: 3.0
description: "Municipal transit ridership and traffic data"
depends_on: [temporal, municipal_geospatial]

storage:
  format: delta
  sources_from: sources/{entity}/
  silver:
    root: storage/silver/municipal/{entity}/transportation/

graph:
  edges:
    - [ridership_to_station, fact_l_ridership, dim_l_station, [station_id=station_id], many_to_one, null]
    - [ridership_to_day_type, fact_l_ridership, dim_day_type, [day_type_id=day_type_id], many_to_one, null]

build:
  partitions: [year]
  optimize: true
  phases:
    1: { tables: [dim_l_station, dim_day_type] }
    2: { tables: [fact_l_ridership, fact_bus_ridership, fact_traffic] }

measures:
  simple:
    - [total_l_rides, sum, fact_l_ridership.rides, "Total L station entries", {format: "#,##0"}]
    - [avg_daily_rides, avg, fact_l_ridership.rides, "Avg daily ridership", {format: "#,##0"}]
    - [station_count, count_distinct, dim_l_station.station_id, "Number of L stations", {format: "#,##0"}]
  computed:
    - [rides_per_station, expression, "total_l_rides / station_count", "Rides per station", {format: "#,##0"}]

metadata:
  domain: municipal
  subdomain: transportation
status: active
---

## Municipal Transportation Model

Transit ridership and traffic data.

### Day Types

| Code | Meaning |
|------|---------|
| W | Weekday |
| A | Saturday |
| U | Sunday/Holiday |

### Notes

- L counts are station entries (turnstile passes), not boardings
