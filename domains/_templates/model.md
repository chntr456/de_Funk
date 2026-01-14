# {Model Name}

> {Brief one-line description of this model}

---

## Overview

{Detailed description of what this model represents, its purpose, and key use cases.}

**Domain**: `{domain_category}` (e.g., securities, corporate, municipal, economic)
**Version**: 1.0
**Status**: Active

### Dependencies

- `temporal` - Calendar dimension for date-based analysis
- `{other_model}` - {reason for dependency}

### Data Sources

| Source | Provider | Update Frequency |
|--------|----------|------------------|
| {table_name} | {provider} | {frequency} |

---

## Model Configuration

$model${
model: {model_name}
version: 1.0
description: "{Brief description}"

inherits_from: null  # or "_base.securities" for securities models

depends_on:
  - temporal

storage:
  root: storage/silver/{model_name}
  format: delta

tags:
  - {domain_category}
  - {additional_tag}
}

---

## Schema

### Dimensions

$schema${
dimensions:
  dim_{entity}:
    description: "{Entity} dimension table"
    primary_key: ["{entity}_id"]
    columns:
      {entity}_id:
        type: string
        description: "Unique identifier"
      name:
        type: string
        description: "Display name"
      # Add more columns as needed
      created_at:
        type: timestamp
        description: "Record creation timestamp"
      updated_at:
        type: timestamp
        description: "Last update timestamp"
    tags:
      - dimension
      - {entity}
}

### Facts

$schema${
facts:
  fact_{entity}_{metric}:
    description: "{Metric} data for {entity}"
    columns:
      {entity}_id:
        type: string
        description: "Foreign key to dim_{entity}"
      date_key:
        type: date
        description: "Date of observation"
      # Metric columns
      value:
        type: double
        description: "Metric value"
      # Add more metric columns as needed
    partitions:
      - date_key
    foreign_keys:
      - column: {entity}_id
        references: dim_{entity}.{entity}_id
      - column: date_key
        references: dim_calendar.date_key
    tags:
      - fact
      - {metric}
}

---

## Graph

### Nodes

$graph${
nodes:
  # Dimension nodes - loaded from Bronze layer
  dim_{entity}:
    type: dimension
    source: bronze.{source_table}
    description: "Load {entity} dimension from Bronze"
    columns:
      - {entity}_id
      - name
      # List columns to select
    filters:
      - "is_active = true"  # Optional filters

  # Fact nodes - loaded from Bronze layer
  fact_{entity}_{metric}:
    type: fact
    source: bronze.{source_table}
    description: "Load {metric} facts from Bronze"
    columns:
      - {entity}_id
      - date_key
      - value
    partitions:
      - date_key
}

### Edges

$graph${
edges:
  # Define relationships between nodes
  - from: fact_{entity}_{metric}
    to: dim_{entity}
    join_type: inner
    on:
      - fact_{entity}_{metric}.{entity}_id = dim_{entity}.{entity}_id
    description: "Link facts to {entity} dimension"

  - from: fact_{entity}_{metric}
    to: dim_calendar
    join_type: left
    on:
      - fact_{entity}_{metric}.date_key = dim_calendar.date_key
    description: "Link facts to calendar dimension"
    cross_model: temporal  # Reference to external model
}

### Materialized Paths

$graph${
paths:
  {entity}_with_dates:
    description: "Pre-joined {entity} facts with calendar context"
    start: fact_{entity}_{metric}
    through:
      - dim_{entity}
      - dim_calendar
    materialize: true
    output_table: {entity}_with_context
}

---

## Measures

### Simple Measures

$measures${
simple_measures:
  total_{metric}:
    description: "Total {metric} value"
    type: simple
    source: fact_{entity}_{metric}.value
    aggregation: sum
    format: "#,##0.00"
    tags:
      - core
      - {metric}

  avg_{metric}:
    description: "Average {metric} value"
    type: simple
    source: fact_{entity}_{metric}.value
    aggregation: avg
    format: "#,##0.00"
    tags:
      - core
      - {metric}

  count_{entity}:
    description: "Count of {entities}"
    type: simple
    source: dim_{entity}.{entity}_id
    aggregation: count_distinct
    format: "#,##0"
    tags:
      - core
}

### Computed Measures

$measures${
computed_measures:
  {metric}_growth:
    description: "Period-over-period growth rate"
    type: computed
    expression: "(current_value - previous_value) / previous_value * 100"
    format: "#,##0.00%"
    depends_on:
      - total_{metric}
    tags:
      - derived
      - growth
}

### Python Measures

$measures${
python_measures:
  # Complex calculations that require Python
  rolling_avg_{metric}:
    description: "Rolling average over window"
    function: "{model_name}.measures.calculate_rolling_avg"
    params:
      window_days: 30
    tags:
      - advanced
      - rolling
}

---

## Usage Examples

### Loading the Model

```python
from models.domains.{domain_category}.{model_name} import {ModelClass}
from models.api.session import UniversalSession

# Initialize session and model
session = UniversalSession(backend="duckdb")
model = session.load_model("{model_name}")

# Get dimension data
entities = model.get_table("dim_{entity}")

# Calculate measures
total = model.calculate_measure("total_{metric}")
```

### Common Queries

```python
# Filter by entity
entity_data = model.get_{entity}_data(entity_id="...")

# Time-series analysis
trends = model.get_{metric}_trends(date_from="2024-01-01", date_to="2024-12-31")
```

---

## Notes

- {Important considerations or caveats}
- {Data quality notes}
- {Known limitations}

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | YYYY-MM-DD | Initial model creation |
