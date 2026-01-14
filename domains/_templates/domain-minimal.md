---
type: domain-model
model:                                  # Model name
version: 1.0
python_module:                          # models/domains/{category}/{model}/
depends_on: [temporal]

storage:
  root:                                 # storage/silver/{model}/
  format: delta

schema:
  dimensions:
    dim_{entity}:
      primary_key: [{entity}_id]
      columns:
        {entity}_id: {type: string}
        name: {type: string}
        is_active: {type: boolean}

  facts:
    fact_{entity}_data:
      columns:
        {entity}_id: {type: string}
        date_key: {type: date}
        value: {type: double}
      partitions: [date_key]

graph:
  nodes:
    dim_{entity}:
      source: bronze.{source}
      type: dimension
    fact_{entity}_data:
      source: bronze.{source}
      type: fact

  edges:
    - {from: fact_{entity}_data, to: dim_{entity}, on: [{entity}_id]}

measures:
  simple:
    total_value: {source: fact_{entity}_data.value, aggregation: sum}
    avg_value: {source: fact_{entity}_data.value, aggregation: avg}
    count_{entity}: {source: dim_{entity}.{entity}_id, aggregation: count_distinct}

domain:                                 # securities | corporate | municipal | economic
status: active
---

## {Model Name}

{Brief description}

## Usage

```python
model = session.load_model("{model}")
df = model.get_table("dim_{entity}")
```
