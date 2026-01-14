---
type: domain-model
model:                                  # Model name (e.g., "stocks", "company")
version: 1.0

# Python Module
python_module:                          # models/domains/{category}/{model}/

# Dependencies
depends_on:
  - temporal                            # Most models depend on calendar dimension

# Inheritance (optional)
inherits_from:                          # e.g., _base.securities

# Storage
storage:
  root:                                 # storage/silver/{model}/
  format: delta

# Schema
schema:
  dimensions:
    dim_{entity}:
      description: "{Entity} dimension"
      primary_key: [{entity}_id]
      columns:
        {entity}_id: {type: string, description: "Unique identifier"}
        name: {type: string, description: "Display name"}
        is_active: {type: boolean, description: "Active flag", default: true}
        created_at: {type: timestamp, description: "Record creation time"}
        updated_at: {type: timestamp, description: "Last update time"}

  facts:
    fact_{entity}_{metric}:
      description: "{Metric} data for {entity}"
      columns:
        {entity}_id: {type: string, description: "FK to dim_{entity}"}
        date_key: {type: date, description: "Observation date"}
        value: {type: double, description: "Metric value"}
      partitions: [date_key]
      foreign_keys:
        - column: {entity}_id
          references: dim_{entity}.{entity}_id
        - column: date_key
          references: dim_calendar.date_key

# Graph
graph:
  nodes:
    dim_{entity}:
      type: dimension
      source: bronze.{source_table}
      columns: [{entity}_id, name, is_active]
      filters: ["is_active = true"]

    fact_{entity}_{metric}:
      type: fact
      source: bronze.{source_table}
      columns: [{entity}_id, date_key, value]
      partitions: [date_key]

  edges:
    - from: fact_{entity}_{metric}
      to: dim_{entity}
      join_type: inner
      on: ["{entity}_id"]

    - from: fact_{entity}_{metric}
      to: dim_calendar
      join_type: left
      on: ["date_key"]
      cross_model: temporal

  paths:
    {entity}_with_dates:
      description: "Pre-joined {entity} with calendar"
      start: fact_{entity}_{metric}
      through: [dim_{entity}, dim_calendar]
      materialize: true

# Measures
measures:
  simple:
    total_{metric}:
      description: "Total {metric}"
      source: fact_{entity}_{metric}.value
      aggregation: sum
      format: "#,##0.00"
      tags: [core]

    avg_{metric}:
      description: "Average {metric}"
      source: fact_{entity}_{metric}.value
      aggregation: avg
      format: "#,##0.00"
      tags: [core]

    count_{entity}:
      description: "Distinct {entity} count"
      source: dim_{entity}.{entity}_id
      aggregation: count_distinct
      format: "#,##0"
      tags: [core]

  computed:
    {metric}_growth:
      description: "Period-over-period growth"
      expression: "(current - previous) / previous * 100"
      format: "#,##0.00%"
      depends_on: [total_{metric}]
      tags: [derived]

  python:
    module: measures.py                 # Optional: {model}/measures.py
    class: {Model}Measures              # e.g., StocksMeasures

# Metadata
domain:                                 # securities | corporate | municipal | economic | foundation
tags: []
status: active                          # active | deprecated | draft
last_verified:
last_reviewed:
notes: ""
---

## Description

{Detailed description of what this model represents, its purpose, and key use cases.}

## Data Sources

| Source | Provider | Update Frequency |
|--------|----------|------------------|
| {bronze_table} | {provider} | {frequency} |

## Usage

```python
from models.domains.{category}.{model} import {Model}Model
from models.api.session import UniversalSession

session = UniversalSession(backend="duckdb")
model = session.load_model("{model}")

# Get dimension data
entities = model.get_table("dim_{entity}")

# Calculate measures
total = model.calculate_measure("total_{metric}")
avg = model.calculate_measure("avg_{metric}", filters={"ticker": "AAPL"})
```

## Homelab Usage

```bash
# Build this model
python -m scripts.build.rebuild_model --model {model}

# Query via DuckDB
python -m scripts.query.run_query "SELECT * FROM {model}.dim_{entity} LIMIT 10"
```

## Notes

- {Important considerations}
- {Data quality notes}
- {Known limitations}

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | YYYY-MM-DD | Initial model |
