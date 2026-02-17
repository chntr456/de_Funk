---
type: domain-base
model: traffic
version: 1.0
description: "Road traffic - segment speed, congestion, and flow observations"
extends: _base._base_.event

depends_on: [temporal]

# CANONICAL FIELDS
# [field_name, type, nullable: bool, description: "meaning"]
canonical_fields:
  - [segment_id, string, nullable: false, description: "Road segment identifier"]
  - [timestamp, timestamp, nullable: false, description: "Observation time"]
  - [date_id, integer, nullable: false, description: "FK to temporal.dim_calendar"]
  - [speed, double, nullable: true, description: "Observed speed"]
  - [congestion_level, string, nullable: true, description: "Congestion classification"]

tables:
  _fact_traffic:
    type: fact
    primary_key: [segment_id, timestamp]

    # [column, type, nullable, description, {options}]
    schema:
      - [segment_id, string, false, "Road segment identifier"]
      - [timestamp, timestamp, false, "Observation time"]
      - [date_id, integer, false, "FK to calendar", {fk: temporal.dim_calendar.date_id, derived: "CAST(DATE_FORMAT(timestamp, 'yyyyMMdd') AS INT)"}]
      - [speed, double, true, "Observed speed"]
      - [congestion_level, string, true, "Congestion classification"]

    measures:
      - [avg_speed, avg, speed, "Average speed", {format: "#,##0.0"}]

graph:
  edges:
    # [edge_name, from, to, on, type, cross_model]
    - [traffic_to_calendar, _fact_traffic, temporal.dim_calendar, [date_id=date_id], many_to_one, temporal]

domain: transportation
tags: [base, template, transportation, traffic, congestion]
status: active
---

## Traffic Base Template

Road traffic observations — segment-level speed and congestion data. Distinct from `_base.transportation.transit` which covers public transit stations and ridership.

### Traffic vs Transit

| | Traffic | Transit |
|---|---------|--------|
| **Subject** | Road segments | Stations / routes |
| **Grain** | Per-segment per-timestamp | Per-station/route per-day |
| **Metrics** | Speed, congestion | Ridership count |
| **Use Case** | Congestion analysis, commute times | Ridership trends, service planning |

### Usage

```yaml
extends: _base.transportation.traffic
```
