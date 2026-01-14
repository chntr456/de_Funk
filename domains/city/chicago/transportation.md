---
type: domain-model
model: chicago_transportation
version: 1.0
description: "Chicago CTA ridership and traffic data"

# Python Module
python_module: models/domains/city/chicago/transportation/

# Dependencies
depends_on:
  - foundation_temporal
  - chicago_geospatial

# Storage
storage:
  root: storage/silver/chicago/transportation
  format: delta

# Build
build:
  partitions: [year]
  optimize: true

# Sources
sources:
  l_ridership:
    bronze_table: chicago_cta_l_ridership
    description: "Daily L station ridership since 2001"

  l_stops:
    bronze_table: chicago_cta_l_stops
    description: "L station reference"

  bus_ridership:
    bronze_table: chicago_cta_bus_ridership
    description: "Daily bus route ridership"

  bus_stops:
    bronze_table: chicago_cta_bus_stops
    description: "Bus stop reference"

  traffic:
    bronze_table: chicago_traffic
    description: "Traffic congestion by segment"

# Schema
schema:
  dimensions:
    dim_l_station:
      description: "L station dimension"
      primary_key: [station_id]
      columns:
        station_id: {type: string, required: true}
        station_name: {type: string, description: "Station name"}
        lines: {type: string, description: "Rail lines served (comma-separated)"}
        ada_accessible: {type: boolean, description: "ADA accessible"}
        latitude: {type: double}
        longitude: {type: double}

    dim_bus_route:
      description: "Bus route dimension"
      primary_key: [route_id]
      columns:
        route_id: {type: string, required: true}
        route_name: {type: string}
        route_type: {type: string, description: "Express, Local, etc."}

    dim_day_type:
      description: "Day type dimension"
      primary_key: [day_type_id]
      columns:
        day_type_id: {type: string, required: true}
        day_type_code: {type: string, description: "W=Weekday, A=Saturday, U=Sunday/Holiday"}
        day_type_name: {type: string}

  facts:
    fact_l_ridership:
      description: "Daily L station ridership"
      primary_key: [station_id, date]
      columns:
        station_id: {type: string, required: true}
        date: {type: date, required: true}
        year: {type: int}
        day_type_id: {type: string}
        rides: {type: long, description: "Total station entries"}

    fact_bus_ridership:
      description: "Daily bus route ridership"
      primary_key: [route_id, date]
      columns:
        route_id: {type: string, required: true}
        date: {type: date, required: true}
        year: {type: int}
        day_type_id: {type: string}
        rides: {type: long, description: "Total boardings"}

    fact_traffic:
      description: "Traffic congestion by segment"
      primary_key: [segment_id, timestamp]
      columns:
        segment_id: {type: string, required: true}
        timestamp: {type: timestamp}
        speed: {type: double, description: "Average speed"}
        congestion_level: {type: string, description: "Free flow, Moderate, Heavy, etc."}

# Graph
graph:
  nodes:
    dim_l_station:
      from: bronze.chicago_cta_l_stops
      type: dimension
      unique_key: [station_id]

    dim_day_type:
      from: static
      type: dimension
      values:
        - {day_type_id: "W", day_type_code: "W", day_type_name: "Weekday"}
        - {day_type_id: "A", day_type_code: "A", day_type_name: "Saturday"}
        - {day_type_id: "U", day_type_code: "U", day_type_name: "Sunday/Holiday"}
      unique_key: [day_type_id]

    fact_l_ridership:
      from: bronze.chicago_cta_l_ridership
      type: fact
      derive:
        day_type_id: daytype
      unique_key: [station_id, date]

  edges:
    ridership_to_station:
      from: fact_l_ridership
      to: dim_l_station
      on: [station_id=station_id]
      type: many_to_one

    ridership_to_day_type:
      from: fact_l_ridership
      to: dim_day_type
      on: [day_type_id=day_type_id]
      type: many_to_one

# Measures
measures:
  simple:
    total_l_rides:
      description: "Total L station entries"
      source: fact_l_ridership.rides
      aggregation: sum
      format: "#,##0"

    avg_daily_rides:
      description: "Average daily ridership"
      source: fact_l_ridership.rides
      aggregation: avg
      format: "#,##0"

    station_count:
      description: "Number of L stations"
      source: dim_l_station.station_id
      aggregation: count_distinct
      format: "#,##0"

  computed:
    rides_per_station:
      description: "Average rides per station"
      formula: "total_l_rides / station_count"
      format: "#,##0"

# Metadata
metadata:
  domain: city
  entity: chicago
  subdomain: transportation
status: active
---

## Chicago Transportation Model

CTA ridership and traffic data for the City of Chicago.

### Data Sources

| Source | Bronze Table | Description |
|--------|--------------|-------------|
| L Ridership | chicago_cta_l_ridership | Daily station entries since 2001 |
| L Stops | chicago_cta_l_stops | Station reference |
| Bus Ridership | chicago_cta_bus_ridership | Daily route totals |
| Bus Stops | chicago_cta_bus_stops | Stop reference |
| Traffic | chicago_traffic | Segment congestion |

### Day Types

CTA uses day type codes for reporting:

| Code | Meaning |
|------|---------|
| W | Weekday |
| A | Saturday |
| U | Sunday/Holiday |

**Note**: New Year's Day, Memorial Day, July 4th, Labor Day, Thanksgiving, and Christmas are treated as "Sunday" (U) for ridership reporting.

### L Ridership Notes

- Counts are **station entries** (turnstile passes)
- Cross-platform transfers not counted (no turnstile)
- "Boardings" = statistically estimated actual boardings

### Example Queries

```sql
-- Daily ridership by station
SELECT
    s.station_name,
    r.date,
    r.rides
FROM fact_l_ridership r
JOIN dim_l_station s ON r.station_id = s.station_id
WHERE r.date >= '2024-01-01'
ORDER BY r.rides DESC;

-- Weekday vs Weekend ridership
SELECT
    dt.day_type_name,
    AVG(r.rides) as avg_daily_rides,
    SUM(r.rides) as total_rides
FROM fact_l_ridership r
JOIN dim_day_type dt ON r.day_type_id = dt.day_type_id
WHERE r.year = 2023
GROUP BY dt.day_type_name;

-- Busiest stations
SELECT
    s.station_name,
    SUM(r.rides) as total_rides,
    AVG(r.rides) as avg_daily
FROM fact_l_ridership r
JOIN dim_l_station s ON r.station_id = s.station_id
WHERE r.year = 2023
GROUP BY s.station_name
ORDER BY total_rides DESC
LIMIT 10;
```
