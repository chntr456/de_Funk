# {Model Name}

> {Brief description}

**Python Module**: `models/domains/{domain_category}/{model_name}/`

$model${
model: {model_name}
version: 1.0
depends_on:
  - temporal
storage:
  root: storage/silver/{model_name}
  format: delta
}

---

## Schema

$schema${
dimensions:
  dim_{entity}:
    primary_key: [{entity}_id]
    columns:
      {entity}_id: string
      name: string
      is_active: boolean

facts:
  fact_{entity}_data:
    columns:
      {entity}_id: string
      date_key: date
      value: double
    partitions: [date_key]
}

---

## Graph

$graph${
nodes:
  dim_{entity}:
    source: bronze.{source_table}
    type: dimension

  fact_{entity}_data:
    source: bronze.{source_table}
    type: fact

edges:
  - from: fact_{entity}_data
    to: dim_{entity}
    on: [{entity}_id]
}

---

## Measures

$measures${
simple_measures:
  total_value:
    source: fact_{entity}_data.value
    aggregation: sum

  avg_value:
    source: fact_{entity}_data.value
    aggregation: avg

  count_{entity}:
    source: dim_{entity}.{entity}_id
    aggregation: count_distinct
}
