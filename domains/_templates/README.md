# Domain Templates

This directory contains templates for creating new domain models in de_Funk.

> **Note**: These templates define the future markdown-based domain configuration format.
> Current production configs use YAML files in `configs/models/`. See migration notes below.

## Quick Start

1. **Copy the appropriate template** to your domain directory
2. **Replace placeholders** (marked with `{curly braces}`)
3. **Create corresponding Python module** in `models/domains/{category}/{model_name}/`

## Python Module Structure

Each domain needs a corresponding Python module:

```
models/domains/{category}/{model_name}/
├── __init__.py       # Module exports
├── model.py          # Model class (extends BaseModel)
├── builder.py        # (Optional) Custom builder logic
└── measures.py       # (Optional) Python measures
```

## Templates

| Template | Use Case |
|----------|----------|
| `model.md` | Complete model with schema, graph, and measures |
| `base.md` | Base template for inheritance patterns |

## Creating a New Domain

### Step 1: Create Domain Directory

```bash
# For a new domain category
mkdir -p domains/{category}/{model_name}

# For an existing category
mkdir -p domains/securities/{model_name}
```

### Step 2: Create Model Markdown

```bash
cp domains/_templates/model.md domains/{category}/{model_name}.md
```

### Step 3: Edit the Markdown

Replace all placeholders:
- `{model_name}` - e.g., `bonds`
- `{Model Name}` - e.g., `Bonds`
- `{entity}` - e.g., `bond`
- `{metric}` - e.g., `yield`
- `{domain_category}` - e.g., `securities`

### Step 4: Create Python Module

```bash
mkdir -p models/domains/{category}/{model_name}
```

Create `models/domains/{category}/{model_name}/__init__.py`:

```python
"""
{Model Name} model.

Provides:
- {ModelClass}: Domain model for {model_name} data
"""

from .model import {ModelClass}

__all__ = ['{ModelClass}']
```

Create `models/domains/{category}/{model_name}/model.py`:

```python
"""
{ModelClass} - Domain model for {model_name}.
"""

from models.base.model import BaseModel


class {ModelClass}(BaseModel):
    """
    {Model description}.

    YAML Config: domains/{category}/{model_name}.md
    """

    # Add model-specific methods here
    pass
```

### Step 5: Register the Model

Add to `models/registry.py`:

```python
try:
    from models.domains.{category}.{model_name} import {ModelClass}
    self.register_model_class('{model_name}', {ModelClass})
except Exception:
    pass
```

## Markdown Block Syntax

Domains use special markdown blocks for configuration:

| Block | Purpose |
|-------|---------|
| `$model${...}` | Model metadata and dependencies |
| `$schema${...}` | Dimension and fact definitions |
| `$graph${...}` | Nodes, edges, and paths |
| `$measures${...}` | Measure definitions |

### Example

```markdown
$schema${
dimensions:
  dim_example:
    columns:
      id:
        type: string
        description: "Primary key"
}
```

## Domain Categories

| Category | Description | Examples |
|----------|-------------|----------|
| `foundation` | Core infrastructure | temporal, geospatial |
| `securities` | Tradable instruments | stocks, options, etfs |
| `corporate` | Business entities | company |
| `municipal` | Government data | city_finance |
| `economic` | Economic indicators | macro |

## Inheritance

Models can inherit from base templates:

```markdown
$model${
inherits_from: _base.securities
}

$schema${
dimensions:
  dim_my_security:
    extends: _base.securities._dim_security
    columns:
      # Adds to inherited columns
      custom_field: string
}
```

## Best Practices

1. **One model per markdown file** - Keep models focused
2. **Use descriptive names** - `dim_` prefix for dimensions, `fact_` for facts
3. **Document everything** - Add descriptions to all columns and measures
4. **Follow the hierarchy** - Place models in appropriate domain categories
5. **Test incrementally** - Validate schema before adding measures

## Validation

To validate your domain markdown:

```bash
python -m scripts.validate.validate_domain domains/{category}/{model_name}.md
```

## Current vs Future Configuration

### Current Production Configs (YAML)

Production models currently use YAML files in `configs/models/`:

```
configs/models/{model_name}/
├── model.yaml        # Metadata, dependencies
├── schema.yaml       # Dimensions and facts
├── graph.yaml        # Nodes, edges, paths
└── measures.yaml     # Measure definitions
```

### Future Markdown Configs

These templates define a unified markdown format with embedded YAML blocks:

```markdown
# Model Name

$model${
model: model_name
version: 1.0
...
}

$schema${
dimensions:
  ...
}
```

### Migration Path

To migrate from YAML to markdown format:
1. Create `domains/{category}/{model_name}.md` using these templates
2. Copy YAML content into appropriate `$block${}` sections
3. Update `ModelConfigLoader` to parse markdown (future work)

## See Also

- [CLAUDE.md](../../CLAUDE.md) - Architecture and conventions
- [docs/guide/](../../docs/guide/) - Detailed documentation
- [configs/models/](../../configs/models/) - Current YAML configurations
- [models/domains/](../../models/domains/) - Python model implementations
