# Domain Templates

Templates for creating domain models in de_Funk using **YAML front matter** pattern.

> **Pattern**: All structured configuration in YAML front matter (`---` delimiters),
> documentation in markdown body below. Same pattern as endpoint templates.

## Templates

| Template | Use Case |
|----------|----------|
| `domain-model.md` | Full model with schema, graph, measures |
| `domain-minimal.md` | Quick-start minimal template |
| `domain-base.md` | Base template for inheritance |

## Quick Start

```bash
# 1. Copy template to domain directory
cp domains/_templates/domain-model.md domains/{category}/{model_name}.md

# 2. Create Python module
mkdir -p models/domains/{category}/{model_name}
touch models/domains/{category}/{model_name}/__init__.py
touch models/domains/{category}/{model_name}/model.py
```

## Front Matter Structure

```yaml
---
type: domain-model
model: stocks                          # Model name
version: 1.0
python_module: models/domains/securities/stocks/

depends_on: [temporal, company]        # Model dependencies
inherits_from: _base.securities        # Optional inheritance

storage:
  root: storage/silver/stocks
  format: delta

schema:
  dimensions:
    dim_stock:
      primary_key: [ticker]
      columns:
        ticker: {type: string, description: "Stock symbol"}
        # ...

  facts:
    fact_stock_prices:
      columns:
        ticker: {type: string}
        trade_date: {type: date}
        close: {type: double}
      partitions: [trade_date]

graph:
  nodes:
    dim_stock: {source: bronze.securities_reference, type: dimension}
    fact_stock_prices: {source: bronze.securities_prices_daily, type: fact}

  edges:
    - {from: fact_stock_prices, to: dim_stock, on: [ticker]}

measures:
  simple:
    avg_close: {source: fact_stock_prices.close, aggregation: avg}
  python:
    module: measures.py
    class: StocksMeasures

domain: securities
status: active
---
```

## Python Module Structure

```
models/domains/{category}/{model_name}/
├── __init__.py       # Exports: from .model import {Model}Model
├── model.py          # class {Model}Model(BaseModel)
├── builder.py        # (Optional) Custom build logic
└── measures.py       # (Optional) Python measures class
```

### `__init__.py`
```python
from .model import {Model}Model
__all__ = ['{Model}Model']
```

### `model.py`
```python
from models.base.model import BaseModel

class {Model}Model(BaseModel):
    """Domain model for {model_name}."""
    pass
```

### `measures.py` (optional)
```python
class {Model}Measures:
    def __init__(self, model):
        self.model = model

    def calculate_custom_metric(self, **kwargs):
        # Complex Python measure logic
        pass
```

## Domain Categories

| Category | Description | Examples |
|----------|-------------|----------|
| `foundation` | Core infrastructure | temporal, geospatial |
| `securities` | Tradable instruments | stocks, options, etfs |
| `corporate` | Business entities | company |
| `municipal` | Government data | city_finance |
| `economic` | Economic indicators | macro |

## File Locations

| Content | Location |
|---------|----------|
| Domain config (markdown) | `domains/{category}/{model}.md` |
| Python model code | `models/domains/{category}/{model}/` |
| YAML configs (current) | `configs/models/{model}/` |

## Current State

**Production configs** currently use YAML in `configs/models/`.
These markdown templates define the **future unified format**.

Migration: Create `.md` files in `domains/`, then update `ModelConfigLoader`
to parse front matter from markdown.

## See Also

- [PROPOSAL.md](./PROPOSAL.md) - Design rationale for front matter pattern
- [Data Sources/_Templates/](../../Data%20Sources/_Templates/) - Endpoint template examples
- [configs/models/](../../configs/models/) - Current YAML configs
- [models/domains/](../../models/domains/) - Python implementations
