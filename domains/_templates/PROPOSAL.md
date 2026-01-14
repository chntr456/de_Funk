# Domain Template Redesign Proposal

## Current Problem

The current domain templates use embedded `$model${}`, `$schema${}`, `$graph${}` blocks which:
- Don't match the endpoint template pattern (YAML front matter)
- Are harder to parse programmatically
- Mix configuration with documentation in confusing ways
- Require custom parser logic

## Proposed Pattern

Follow the same **YAML front matter** pattern used by endpoint templates:

```markdown
---
type: domain-model
model: {model_name}
version: 1.0

# Python Module (required)
python_module: models/domains/{category}/{model_name}/

# Dependencies
depends_on:
  - temporal

# Storage
storage:
  root: storage/silver/{model_name}
  format: delta

# Schema
schema:
  dimensions:
    dim_{entity}:
      primary_key: [{entity}_id]
      columns:
        {entity}_id: {type: string, description: "Unique identifier"}
        name: {type: string, description: "Display name"}

  facts:
    fact_{entity}_data:
      columns:
        {entity}_id: {type: string}
        date_key: {type: date}
        value: {type: double}
      partitions: [date_key]

# Graph
graph:
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

# Measures
measures:
  simple:
    total_value:
      source: fact_{entity}_data.value
      aggregation: sum
    count_{entity}:
      source: dim_{entity}.{entity}_id
      aggregation: count_distinct

  python:
    module: measures.py
    class: {Model}Measures

# Metadata
domain: {category}
tags: [{tag1}, {tag2}]
status: active
last_verified:
---

## Description

{Detailed description of what this model represents, its purpose, and key use cases.}

## Data Sources

| Source | Provider | Update Frequency |
|--------|----------|------------------|
| {table_name} | {provider} | {frequency} |

## Usage

```python
from models.domains.{category}.{model_name} import {Model}Model

model = session.load_model("{model_name}")
df = model.get_table("dim_{entity}")
```

## Notes

- {Important considerations}
- {Known limitations}

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | YYYY-MM-DD | Initial model |
```

## Benefits

1. **Consistency**: Matches endpoint template pattern exactly
2. **Standard YAML parsing**: No custom `$block${}` parser needed
3. **Clear separation**: Config in front matter, docs in markdown body
4. **IDE support**: YAML syntax highlighting works in front matter
5. **Tooling friendly**: Standard markdown + YAML tools work

## File Naming Convention

```
domains/
├── _templates/
│   ├── domain-model.md      # Full template
│   ├── domain-minimal.md    # Minimal template
│   └── domain-base.md       # Base/inheritance template
├── foundation/
│   ├── temporal.md
│   └── geospatial.md
├── securities/
│   ├── stocks.md
│   ├── options.md
│   └── etfs.md
├── corporate/
│   └── company.md
├── municipal/
│   └── city_finance.md
└── economic/
    └── macro.md
```

## Migration Path

1. Create new templates following front matter pattern
2. Update `ModelConfigLoader` to:
   - Parse YAML front matter from markdown files
   - Look in `domains/` for `.md` files
   - Fall back to `configs/models/` YAML for backward compat
3. Migrate existing models one at a time
4. Deprecate `configs/models/` once all migrated

## Parser Changes

```python
import yaml
import re

def load_domain_config(md_path: Path) -> dict:
    """Load domain config from markdown front matter."""
    content = md_path.read_text()

    # Extract YAML front matter
    match = re.match(r'^---\n(.+?)\n---', content, re.DOTALL)
    if match:
        return yaml.safe_load(match.group(1))
    return {}
```

## Comparison: Old vs New

### Old (`$block${}` syntax)
```markdown
# Stocks

$model${
model: stocks
version: 1.0
}

$schema${
dimensions:
  dim_stock: ...
}
```

### New (YAML front matter)
```markdown
---
type: domain-model
model: stocks
version: 1.0

schema:
  dimensions:
    dim_stock: ...
---

# Stocks

Description and documentation here...
```

## Decision

Adopt the YAML front matter pattern to:
- Maintain consistency with endpoint templates
- Simplify parsing
- Improve tooling support
- Follow established markdown conventions
