# Base: {Base Template Name}

> Reusable base template for {category} models

---

## Overview

This is a **base template** that provides common schema, graph, and measure patterns
for {category} models. Models can inherit from this template using:

```yaml
inherits_from: _base.{template_name}
```

Base templates are NOT instantiated directly - they only provide reusable definitions.

---

## Base Schema

### Dimension Templates

$schema${
dimensions:
  # Use underscore prefix for template definitions
  _dim_{base_entity}:
    description: "Base {entity} dimension - extend in child models"
    columns:
      # Common identifier columns
      {entity}_id:
        type: string
        description: "Unique identifier"
      name:
        type: string
        description: "Display name"

      # Common status columns
      is_active:
        type: boolean
        description: "Active status flag"
        default: true

      # Common audit columns
      created_at:
        type: timestamp
        description: "Record creation time"
      updated_at:
        type: timestamp
        description: "Last modification time"

    tags:
      - base
      - dimension
}

### Fact Templates

$schema${
facts:
  _fact_{base_entity}:
    description: "Base {entity} fact - extend in child models"
    columns:
      # Foreign keys
      {entity}_id:
        type: string
        description: "Link to dimension"
      date_key:
        type: date
        description: "Observation date"

      # Common metric columns
      # (Child models add specific metrics)

    partitions:
      - date_key

    tags:
      - base
      - fact
}

---

## Base Graph

### Node Templates

$graph${
nodes:
  # Base node patterns that children can extend
  _node_{base_entity}:
    type: dimension
    description: "Base node pattern"
    # Children specify source
    columns:
      - {entity}_id
      - name
      - is_active
}

### Common Edges

$graph${
edges:
  # Calendar join pattern - all temporal models need this
  _temporal_join:
    description: "Standard calendar dimension join"
    join_type: left
    on_pattern: "{fact_table}.date_key = dim_calendar.date_key"
    cross_model: temporal
}

---

## Base Measures

### Common Aggregations

$measures${
simple_measures:
  # Measures that apply to all {category} models
  _count_{entity}:
    description: "Count of {entities}"
    type: simple
    source: "{dim_table}.{entity}_id"
    aggregation: count_distinct
    format: "#,##0"
    tags:
      - base
      - count

  _active_count:
    description: "Count of active {entities}"
    type: simple
    source: "{dim_table}.{entity}_id"
    aggregation: count_distinct
    filters:
      - "is_active = true"
    format: "#,##0"
    tags:
      - base
      - count
}

---

## Inheritance Example

Child models inherit from this base like this:

```markdown
# My Model

$model${
model: my_model
inherits_from: _base.{template_name}
...
}

$schema${
dimensions:
  dim_my_entity:
    extends: _base.{template_name}._dim_{base_entity}
    columns:
      # Inherited: {entity}_id, name, is_active, created_at, updated_at
      # Add custom columns:
      custom_field:
        type: string
        description: "Model-specific field"
}
```

---

## Notes

- Underscore prefix (`_`) indicates template definitions
- Templates are never instantiated directly
- Use `extends` keyword in child models to inherit
- Child definitions override parent definitions (deep merge)
