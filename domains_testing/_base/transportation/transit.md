---
type: domain-base
model: transit
version: 1.0
description: "Public transit - stations, routes, and ridership data"
extends: _base._base_.event

# CANONICAL FIELDS
# [field_name, type, nullable: bool, description: "meaning"]
canonical_fields:
  - [station_id, integer, nullable: false, description: "PK for transit stations"]
  - [station_name, string, nullable: false, description: "Station display name"]
  - [transit_mode, string, nullable: false, description: "RAIL, BUS, SUBWAY, FERRY, LIGHT_RAIL"]
  - [line_name, string, nullable: true, description: "Route/line name(s)"]
  - [ada_accessible, boolean, nullable: true, description: "ADA accessible"]
  - [latitude, double, nullable: true, description: "Station latitude"]
  - [longitude, double, nullable: true, description: "Station longitude"]
  - [route_id, string, nullable: true, description: "Route identifier"]
  - [route_name, string, nullable: true, description: "Route display name"]
  - [date_id, integer, nullable: false, description: "FK to temporal.dim_calendar"]
  - [day_type, string, nullable: true, description: "Weekday, Saturday, Sunday/Holiday"]
  - [rides, long, nullable: false, description: "Ridership count"]

tables:
  _dim_transit_station:
    type: dimension
    primary_key: [station_id]
    unique_key: [station_name, transit_mode]

    # [column, type, nullable, description, {options}]
    schema:
      - [station_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT(station_name, '_', transit_mode)))"}]
      - [station_name, string, false, "Display name"]
      - [transit_mode, string, false, "Mode", {enum: [RAIL, BUS, SUBWAY, FERRY, LIGHT_RAIL]}]
      - [line_name, string, true, "Route/line(s) served"]
      - [ada_accessible, boolean, true, "ADA accessible"]
      - [latitude, double, true, "Station latitude"]
      - [longitude, double, true, "Station longitude"]
      - [is_active, boolean, false, "Currently operational", {default: true}]

    measures:
      - [station_count, count_distinct, station_id, "Number of stations", {format: "#,##0"}]

  _dim_day_type:
    type: dimension
    primary_key: [day_type_id]
    static: true

    # [column, type, nullable, description, {options}]
    schema:
      - [day_type_id, string, false, "PK (W, A, U)"]
      - [day_type_code, string, false, "Code"]
      - [day_type_name, string, false, "Display name"]

    data:
      - [W, W, Weekday]
      - [A, A, Saturday]
      - [U, U, "Sunday/Holiday"]

  _fact_ridership:
    type: fact
    primary_key: [ridership_id]
    partition_by: [year]

    # [column, type, nullable, description, {options}]
    schema:
      - [ridership_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT(COALESCE(CAST(station_id AS STRING), route_id), '_', CAST(date_id AS STRING))))"}]
      - [station_id, integer, true, "FK to dim_transit_station (null for bus)", {fk: _dim_transit_station.station_id}]
      - [route_id, string, true, "Route identifier (null for rail)"]
      - [date_id, integer, false, "FK to calendar", {fk: temporal.dim_calendar.date_id}]
      - [year, integer, false, "Ridership year"]
      - [day_type_id, string, true, "FK to dim_day_type", {fk: _dim_day_type.day_type_id}]
      - [transit_mode, string, false, "RAIL, BUS, etc."]
      - [rides, long, false, "Ridership count"]

    measures:
      - [total_rides, sum, rides, "Total ridership", {format: "#,##0"}]
      - [avg_daily_rides, avg, rides, "Avg daily ridership", {format: "#,##0"}]

graph:
  edges:
    # [edge_name, from, to, on, type, cross_model]
    - [ridership_to_station, _fact_ridership, _dim_transit_station, [station_id=station_id], many_to_one, null]
    - [ridership_to_day_type, _fact_ridership, _dim_day_type, [day_type_id=day_type_id], many_to_one, null]
    - [ridership_to_calendar, _fact_ridership, temporal.dim_calendar, [date_id=date_id], many_to_one, temporal]


domain: transportation
tags: [base, template, transportation, transit, ridership]
status: active
---

## Transit Base Template

Public transit ridership data. Supports multiple transit modes (rail, bus, subway) via the `transit_mode` discriminator on the fact table. For road traffic data, see `_base.transportation.traffic`.

### Transit Modes

| Mode | Description | Key |
|------|-------------|-----|
| RAIL | Heavy rail / metro | station_id |
| BUS | Bus routes | route_id |
| SUBWAY | Underground rail | station_id |
| LIGHT_RAIL | Streetcar / tram | station_id |
| FERRY | Water transit | station_id |

### Ridership Fact Design

Rail ridership keys on `station_id`, bus ridership keys on `route_id`. Both share the same fact table with `transit_mode` as discriminator.

### Day Types

Static dimension with 3 rows:
- **W** - Weekday
- **A** - Saturday
- **U** - Sunday/Holiday

### Usage

```yaml
extends: _base.transportation.transit
```
