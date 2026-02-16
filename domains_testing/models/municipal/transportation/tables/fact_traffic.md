---
type: domain-model-table
table: fact_traffic
table_type: fact
from: bronze.chicago_traffic
primary_key: [segment_id, timestamp]

schema:
  - [segment_id, string, false, "Traffic segment ID"]
  - [timestamp, timestamp, true, "Measurement timestamp"]
  - [speed, double, true, "Average speed"]
  - [congestion_level, string, true, "Congestion level"]
---

## Traffic Fact Table

Traffic congestion data by segment.
