---
type: domain-base
base_name:                              # e.g., "securities", "financial"
description: "Reusable base template for {category} models"

# Base Schema Templates (prefixed with _ to indicate template)
schema:
  dimensions:
    _dim_{base_entity}:
      description: "Base {entity} dimension - extend in child models"
      columns:
        {entity}_id: {type: string, description: "Unique identifier"}
        name: {type: string, description: "Display name"}
        is_active: {type: boolean, description: "Active flag", default: true}
        created_at: {type: timestamp, description: "Record creation time"}
        updated_at: {type: timestamp, description: "Last update time"}
      tags: [base, dimension]

  facts:
    _fact_{base_entity}:
      description: "Base {entity} fact - extend in child models"
      columns:
        {entity}_id: {type: string, description: "Link to dimension"}
        date_key: {type: date, description: "Observation date"}
      partitions: [date_key]
      tags: [base, fact]

# Base Graph Templates
graph:
  nodes:
    _node_{base_entity}:
      type: dimension
      description: "Base node pattern"
      columns: [{entity}_id, name, is_active]

  edges:
    _temporal_join:
      description: "Standard calendar join"
      join_type: left
      on_pattern: "{fact}.date_key = dim_calendar.date_key"
      cross_model: temporal

# Base Measures
measures:
  simple:
    _count_{entity}:
      description: "Count of {entities}"
      source: "{dim_table}.{entity}_id"
      aggregation: count_distinct
      format: "#,##0"
      tags: [base, count]

    _active_count:
      description: "Count of active {entities}"
      source: "{dim_table}.{entity}_id"
      aggregation: count_distinct
      filters: ["is_active = true"]
      format: "#,##0"
      tags: [base, count]

# Metadata
domain:                                 # Category this base serves
tags: [base, template]
status: active
---

## Base Template: {Base Name}

This is a **base template** that provides common schema, graph, and measure patterns
for {category} models. Models can inherit from this template using:

```yaml
inherits_from: _base.{base_name}
```

Base templates are NOT instantiated directly - they only provide reusable definitions.

## Inheritance Example

Child models inherit like this:

```yaml
---
type: domain-model
model: my_model
inherits_from: _base.{base_name}

schema:
  dimensions:
    dim_my_entity:
      extends: _base.{base_name}._dim_{base_entity}
      columns:
        # Inherited: {entity}_id, name, is_active, created_at, updated_at
        custom_field: {type: string, description: "Model-specific"}
---
```

## Notes

- Underscore prefix (`_`) indicates template definitions
- Templates are never instantiated directly
- Use `extends` keyword in child models to inherit
- Child definitions override parent definitions (deep merge)
