# YAML Inheritance

**How model configuration inheritance works in de_Funk**

---

## Overview

de_Funk v2.0 introduces a **YAML inheritance system** allowing models to inherit from base templates. This reduces duplication and ensures consistency across similar models.

---

## Inheritance Keywords

### `inherits_from` (Model-Level)

Used in `model.yaml` to inherit from another model's configuration.

```yaml
# stocks/model.yaml
model: stocks
version: 2.0
inherits_from: _base.securities
```

### `extends` (Component-Level)

Used in schema/graph/measures files to extend specific components.

```yaml
# stocks/schema.yaml
extends: _base.securities.schema

dimensions:
  dim_stock:
    extends: _base.securities._dim_security
```

---

## Resolution Process

### 1. Load Base Template

```python
# ModelConfigLoader loads base first
base_config = load_yaml("configs/models/_base/securities/schema.yaml")
```

### 2. Load Child Config

```python
child_config = load_yaml("configs/models/stocks/schema.yaml")
```

### 3. Deep Merge

```python
def deep_merge(base, child):
    """Child values override base, preserving structure."""
    result = copy.deepcopy(base)
    for key, value in child.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result
```

### 4. Resolve References

```python
# Replace template references like "{asset_type}" with actual values
config = resolve_references(merged_config, {"asset_type": "stocks"})
```

---

## Inheritance Examples

### Schema Inheritance

**Base** (`_base/securities/schema.yaml`):
```yaml
dimensions:
  _dim_security:
    columns:
      ticker: {type: string}
      security_name: {type: string}
      asset_type: {type: string}
```

**Child** (`stocks/schema.yaml`):
```yaml
extends: _base.securities.schema

dimensions:
  dim_stock:
    extends: _base.securities._dim_security
    columns:
      company_id: {type: string}
      cik: {type: string}
```

**Result**:
```yaml
dimensions:
  dim_stock:
    columns:
      ticker: {type: string}        # Inherited
      security_name: {type: string}  # Inherited
      asset_type: {type: string}     # Inherited
      company_id: {type: string}     # Added
      cik: {type: string}            # Added
```

---

### Measure Inheritance

**Base** (`_base/securities/measures.yaml`):
```yaml
simple_measures:
  avg_close_price:
    source: _fact_prices.close
    aggregation: avg

  total_volume:
    source: _fact_prices.volume
    aggregation: sum
```

**Child** (`stocks/measures.yaml`):
```yaml
extends: _base.securities.measures

simple_measures:
  avg_market_cap:
    source: dim_stock.market_cap
    aggregation: avg

python_measures:
  sharpe_ratio:
    function: "stocks.measures.calculate_sharpe_ratio"
```

**Result**:
```yaml
simple_measures:
  avg_close_price: ...     # Inherited
  total_volume: ...        # Inherited
  avg_market_cap: ...      # Added

python_measures:
  sharpe_ratio: ...        # Added
```

---

### Graph Inheritance

**Base** (`_base/securities/graph.yaml`):
```yaml
nodes:
  _dim_security_base:
    from: bronze.securities_reference
    filters: ["asset_type = '{asset_type}'"]

  _fact_prices_base:
    from: bronze.securities_prices_daily
    filters: ["asset_type = '{asset_type}'"]

edges:
  _prices_to_calendar:
    from: "{fact_prices}"
    to: core.dim_calendar
    on: [trade_date = date]
```

**Child** (`stocks/graph.yaml`):
```yaml
extends: _base.securities.graph

# Override with specific values
nodes:
  dim_stock:
    extends: _base.securities._dim_security_base
    # asset_type resolved to 'stocks'

  fact_stock_prices:
    extends: _base.securities._fact_prices_base

edges:
  prices_to_stock:
    from: fact_stock_prices
    to: dim_stock
    on: [ticker = ticker]
```

---

## Override Behavior

### Addition (Default)

New keys are added to parent:

```yaml
# Base
columns:
  ticker: {type: string}

# Child
columns:
  company_id: {type: string}

# Result
columns:
  ticker: {type: string}
  company_id: {type: string}
```

### Override

Child replaces parent value:

```yaml
# Base
columns:
  ticker: {type: string, required: false}

# Child
columns:
  ticker: {type: string, required: true}  # Overrides

# Result
columns:
  ticker: {type: string, required: true}
```

### Deletion

Use `null` to remove inherited item:

```yaml
# Base
simple_measures:
  avg_close_price: ...
  total_volume: ...

# Child (remove total_volume)
simple_measures:
  total_volume: null

# Result
simple_measures:
  avg_close_price: ...
```

---

## Template Variables

Use `{variable}` syntax for template replacement:

**Base**:
```yaml
filters:
  - "asset_type = '{asset_type}'"
```

**Resolution Context**:
```python
context = {"asset_type": "stocks"}
```

**Result**:
```yaml
filters:
  - "asset_type = 'stocks'"
```

---

## ModelConfigLoader

### Usage

```python
from config.model_loader import ModelConfigLoader
from pathlib import Path

loader = ModelConfigLoader(Path("configs/models"))

# Load with inheritance resolved
config = loader.load_model_config("stocks")

# Access components
schema = config["schema"]
graph = config["graph"]
measures = config["measures"]
```

### Internal Process

```python
class ModelConfigLoader:
    def load_model_config(self, model_name):
        # 1. Load model.yaml
        model_config = self._load_yaml(f"{model_name}/model.yaml")

        # 2. Check for inheritance
        if "inherits_from" in model_config:
            base = self.load_model_config(model_config["inherits_from"])

        # 3. Load components
        components = {}
        for component in ["schema", "graph", "measures"]:
            comp_config = self._load_component(model_name, component)

            # Resolve extends
            if "extends" in comp_config:
                base_comp = self._load_base_component(comp_config["extends"])
                comp_config = self._deep_merge(base_comp, comp_config)

            components[component] = comp_config

        return {**model_config, **components}
```

---

## Best Practices

### 1. Use Templates for Shared Patterns

```yaml
# Good: Define once in base
_base/securities/schema.yaml:
  dimensions:
    _dim_security:
      columns:
        ticker: ...

# Reuse in children
stocks/schema.yaml:
  extends: _base.securities.schema
```

### 2. Prefix Base Items with Underscore

```yaml
# Convention: Base items start with _
_dim_security    # Template (not instantiated)
_fact_prices     # Template (not instantiated)
dim_stock        # Concrete (instantiated)
```

### 3. Keep Base Generic

```yaml
# Good: Base is asset-agnostic
_base/securities/schema.yaml:
  asset_type: {type: string, enum: [stocks, options, etfs, futures]}

# Each child specializes
stocks/schema.yaml:
  # Adds stocks-specific: company_id, shares_outstanding
```

### 4. Document Inheritance

```yaml
# Comment what's inherited vs. added
dimensions:
  dim_stock:
    extends: _base.securities._dim_security
    columns:
      # Inherited: ticker, security_name, asset_type, exchange_code, etc.
      # Added below:
      company_id: ...
```

---

## Debugging Inheritance

### View Resolved Config

```python
loader = ModelConfigLoader(Path("configs/models"))
config = loader.load_model_config("stocks")

import yaml
print(yaml.dump(config, default_flow_style=False))
```

### Check Inheritance Chain

```python
def get_inheritance_chain(loader, model_name):
    chain = [model_name]
    config = loader._load_yaml(f"{model_name}/model.yaml")
    while "inherits_from" in config:
        parent = config["inherits_from"]
        chain.append(parent)
        config = loader._load_yaml(f"{parent}/model.yaml")
    return chain

# Example: ['stocks', '_base.securities']
```

---

## Related Documentation

- [Base Securities](base-securities.md) - Base template details
- [Stocks Model](../stocks/) - Example child model
- [Configuration](../../11-configuration/) - Config system
