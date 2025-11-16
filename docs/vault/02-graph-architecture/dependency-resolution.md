# Model Dependency Resolution

**Analysis and resolution strategies for model dependencies**

Source: Migrated from `/MODEL_DEPENDENCY_ANALYSIS.md`
Last Updated: 2025-11-16

---

## Overview

This document analyzes the dependency graph across all domain models in de_Funk. It reveals the interconnection structure, identifies issues with deprecated models, and provides recommendations for maintaining a clean dependency graph.

**Key Findings:**
- 8 models total (7 active + 1 deprecated)
- 3-tier hierarchical structure (Foundation → Core → Portfolio)
- Migration complexity from deprecated `company` model to `equity`/`corporate`
- Several logical connections missing between related domains

---

## Dependency Hierarchy

### Tier 0: Foundation

**core** (no dependencies)
- **Purpose**: Universal time dimension
- **Provides**: `dim_calendar`
- **Depended On By**: All other models

```yaml
model: core
depends_on: []
```

---

### Tier 1: Core Domain Models

**macro** (depends on: core)
- **Purpose**: Macroeconomic indicators
- **Provides**: Unemployment, CPI, GDP data
- **Cross-Model Edges**: None currently defined

```yaml
model: macro
depends_on: [core]
```

**corporate** (depends on: core)
- **Purpose**: Corporate entities (companies)
- **Provides**: Company fundamentals, corporate structure
- **Cross-Model Edges**: Bidirectional with equity

```yaml
model: corporate
depends_on: [core]
```

**company** ⚠️ **DEPRECATED**
- **Status**: Being migrated to equity/corporate split
- **Issue**: Still referenced by etf and forecast models
- **Action Required**: Update all references

---

### Tier 2: Market Data Models

**equity** (depends on: core, corporate)
- **Purpose**: Tradable securities and prices
- **Provides**: Stock prices, equity instruments
- **Cross-Model Edges**: Bidirectional with corporate

```yaml
model: equity
depends_on: [core, corporate]
```

**city_finance** (depends on: core, macro)
- **Purpose**: Municipal finance data
- **Provides**: Local unemployment, building permits
- **Cross-Model Edges**: Declared dependency on macro but no edges defined ⚠️

```yaml
model: city_finance
depends_on: [core, macro]
```

---

### Tier 3: Portfolio & Analytics Models

**etf** (depends on: core, company ⚠️)
- **Purpose**: ETF holdings and prices
- **Provides**: Fund composition, ETF prices
- **Issue**: References deprecated company model
- **Should Depend On**: [core, equity]

```yaml
model: etf
depends_on: [core, company]  # ⚠️ Should be [core, equity]
```

**forecast** (depends on: core, company ⚠️)
- **Purpose**: Time series predictions
- **Provides**: Price forecasts, forecast metrics
- **Issue**: References deprecated company model
- **Should Depend On**: [core, equity]

```yaml
model: forecast
depends_on: [core, company]  # ⚠️ Should be [core, equity]
```

---

## Model Interconnection Matrix

|            | core | macro | city_finance | company | equity | corporate | etf | forecast |
|------------|------|-------|--------------|---------|--------|-----------|-----|----------|
| **core**   | -    | ←     | ←            | ←       | ←      | ←         | ←   | ←        |
| **macro**  | →    | -     |              |         |        |           |     |          |
| **city_finance** | → | ⚠️ | -            |         |        |           |     |          |
| **company** | →   |       |              | -       | ⚠️     |           | ⚠️  | ⚠️       |
| **equity** | →    |       |              |         | -      | ↔         |     |          |
| **corporate** | → |       |              |         | ↔      | -         |     |          |
| **etf**    | →    |       |              | ⚠️      |        |           | -   |          |
| **forecast** | →  |       |              | ⚠️      |        |           |     | -        |

**Legend:**
- → = Outgoing edge/dependency
- ← = Incoming edge/dependency
- ↔ = Bidirectional relationship
- ⚠️ = References deprecated model or missing edge

---

## Critical Issues

### 1. Deprecated Model References

**Problem**: etf and forecast models still reference the deprecated `company` model.

**Impact:**
- Production queries may fail
- Migration to equity/corporate split blocked
- Technical debt accumulation

**Affected Components:**

#### etf → company
```yaml
# etf.yaml (PROBLEMATIC)
edges:
  - from: dim_etf_holdings
    to: company.dim_company  # ⚠️ DEPRECATED
    on: ["holding_ticker=ticker"]
    type: many_to_one

measures:
  holdings_weighted_return:
    source: company.fact_prices.close  # ⚠️ DEPRECATED
```

#### forecast → company
```yaml
# forecast.yaml (PROBLEMATIC)
edges:
  - from: fact_forecasts
    to: company.fact_prices  # ⚠️ DEPRECATED
    on: ["ticker=ticker"]
  - from: fact_forecasts
    to: company.dim_company  # ⚠️ DEPRECATED
    on: ["ticker=ticker"]
```

---

### 2. Missing Declared Dependencies

**Problem**: city_finance declares `depends_on: [macro]` but has no cross-model edges defined.

**Impact:**
- Inconsistency between declaration and implementation
- Unclear how models should relate

**Required Action:**
```yaml
# city_finance.yaml (ADD THIS)
edges:
  - from: fact_local_unemployment
    to: macro.fact_unemployment
    on: ["date=date"]
    type: left
    description: "Compare local vs national unemployment rates"
```

---

## Migration Path

### Phase 1: Fix Deprecated References (CRITICAL)

**Priority**: 🔴 CRITICAL - Blocking production

**etf.yaml Updates:**
```yaml
# BEFORE
edges:
  - from: dim_etf_holdings
    to: company.dim_company
    on: ["holding_ticker=ticker"]

measures:
  holdings_weighted_return:
    source: company.fact_prices.close

# AFTER
edges:
  - from: dim_etf_holdings
    to: equity.dim_equity
    on: ["holding_ticker=ticker"]

measures:
  holdings_weighted_return:
    source: equity.fact_equity_prices.close
```

**forecast.yaml Updates:**
```yaml
# BEFORE
edges:
  - from: fact_forecasts
    to: company.fact_prices
  - from: fact_forecasts
    to: company.dim_company

# AFTER
edges:
  - from: fact_forecasts
    to: equity.fact_equity_prices
    on: ["ticker=ticker", "prediction_date=trade_date"]
  - from: fact_forecasts
    to: equity.dim_equity
    on: ["ticker=ticker"]
```

---

### Phase 2: Add Missing Relationships (HIGH)

**Priority**: 🟠 HIGH - Functional gap

**city_finance → macro:**
```yaml
# city_finance.yaml
edges:
  - from: fact_local_unemployment
    to: macro.fact_unemployment
    on: ["date=date"]
    type: left
    description: "Compare local vs national unemployment rates"
```

**etf → corporate:**
```yaml
# etf.yaml
edges:
  - from: dim_etf_holdings
    to: corporate.dim_corporate
    on: ["holding_ticker=ticker_primary"]
    type: many_to_one
    description: "ETF holdings belong to corporate entities"
```

**forecast → corporate:**
```yaml
# forecast.yaml
edges:
  - from: fact_forecasts
    to: corporate.dim_corporate
    on: ["ticker=ticker_primary"]
    type: left
    description: "Connect predictions to corporate fundamentals"
```

---

### Phase 3: Enhanced Analytics (MEDIUM)

**Priority**: 🟡 MEDIUM - Analytics enhancement

**equity → macro (Correlation Analysis):**
```yaml
# equity.yaml
edges:
  - from: fact_equity_prices
    to: macro.fact_unemployment
    on: ["trade_date=date"]
    type: left
    description: "Analyze macro correlation with equity performance"

  - from: fact_equity_prices
    to: macro.fact_cpi
    on: ["trade_date=date"]
    type: left
    description: "Inflation correlation analysis"
```

**forecast → macro (Macro-Enriched Forecasts):**
```yaml
# forecast.yaml
edges:
  - from: fact_forecasts
    to: macro.economic_indicators_wide
    on: ["prediction_date=date"]
    type: left
    description: "Enrich forecasts with macroeconomic context"
```

---

## Dependency Resolution Algorithm

The model registry uses the following algorithm to resolve dependencies:

### 1. Dependency Declaration

Models declare dependencies in YAML:
```yaml
model: equity
depends_on: [core, corporate]
```

### 2. Build Order Resolution

```python
# Pseudocode
def resolve_build_order(models):
    """Topological sort of model dependency graph."""

    # Build dependency graph
    graph = {}
    for model in models:
        graph[model.name] = model.depends_on

    # Topological sort
    sorted_models = []
    visited = set()

    def visit(model_name):
        if model_name in visited:
            return
        visited.add(model_name)

        # Visit dependencies first
        for dep in graph.get(model_name, []):
            visit(dep)

        sorted_models.append(model_name)

    for model in models:
        visit(model.name)

    return sorted_models
```

### 3. Build Order Example

```
Build Order:
1. core         (no dependencies)
2. macro        (depends on: core)
3. corporate    (depends on: core)
4. city_finance (depends on: core, macro)
5. equity       (depends on: core, corporate)
6. etf          (depends on: core, equity)
7. forecast     (depends on: core, equity)
```

---

## Dependency Validation

### Circular Dependency Detection

```python
def detect_circular_dependencies(models):
    """Detect circular dependencies in model graph."""

    def has_cycle(node, visited, rec_stack, graph):
        visited.add(node)
        rec_stack.add(node)

        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                if has_cycle(neighbor, visited, rec_stack, graph):
                    return True
            elif neighbor in rec_stack:
                return True  # Cycle detected!

        rec_stack.remove(node)
        return False

    graph = {m.name: m.depends_on for m in models}
    visited = set()
    rec_stack = set()

    for model in models:
        if model.name not in visited:
            if has_cycle(model.name, visited, rec_stack, graph):
                raise ValueError(f"Circular dependency detected involving {model.name}")
```

### Missing Dependency Detection

```python
def validate_dependencies(models):
    """Ensure all declared dependencies exist."""

    model_names = {m.name for m in models}

    for model in models:
        for dep in model.depends_on:
            if dep not in model_names:
                raise ValueError(
                    f"Model '{model.name}' depends on '{dep}' which doesn't exist"
                )
```

---

## Best Practices

### 1. Minimize Dependencies

**Good:**
```yaml
model: equity
depends_on: [core, corporate]  # Only essential dependencies
```

**Bad:**
```yaml
model: equity
depends_on: [core, corporate, macro, city_finance]  # Unnecessary dependencies
```

**Rationale**: Fewer dependencies = faster builds, clearer relationships

---

### 2. Foundation Models First

**Pattern**: Place shared dimensions in tier 0
- core (calendar)
- geography (if needed)
- currency (if needed)

**Benefit**: All other models can depend on foundation without creating cycles

---

### 3. Domain Separation

**Pattern**: Separate by business domain
- corporate (company entities)
- equity (tradable securities)
- macro (economic indicators)

**Benefit**: Clear boundaries, independent evolution

---

### 4. Explicit Cross-Model Edges

**Good:**
```yaml
edges:
  - from: dim_equity
    to: corporate.dim_corporate
    on: ["company_id=company_id"]
    description: "Each equity belongs to a corporate entity"
```

**Bad:**
```yaml
depends_on: [corporate]  # Dependency declared but no edges defined
```

**Rationale**: Explicit edges enable query planning and validation

---

## Troubleshooting

### Build Fails with "Dependency not found"

**Error:** `Model 'equity' depends on 'corporate' which is not loaded`

**Cause**: Models built in wrong order

**Solution**: Use model registry which automatically resolves build order:
```python
from models.api.registry import get_model_registry

registry = get_model_registry()
registry.build_all_models()  # Builds in dependency order
```

---

### Circular Dependency Detected

**Error:** `Circular dependency detected: equity → corporate → equity`

**Cause**: Bidirectional dependencies not properly structured

**Solution**: Review edge definitions - bidirectional edges are OK, bidirectional `depends_on` is not:
```yaml
# equity.yaml (CORRECT)
depends_on: [corporate]
edges:
  - to: corporate.dim_corporate  # OK

# corporate.yaml (CORRECT)
depends_on: []  # No dependency on equity!
edges:
  - to: equity.dim_equity  # Edge is OK, dependency is not
```

---

### Cross-Model Query Fails

**Error:** `Table 'corporate.dim_corporate' not found in model 'equity'`

**Cause**: Missing cross-model edge or dependency

**Solution**: Add both dependency and edge:
```yaml
# equity.yaml
depends_on: [corporate]  # Declare dependency
edges:
  - to: corporate.dim_corporate  # Define edge
    on: ["company_id=company_id"]
```

---

## Related Documentation

- [Cross-Model References](cross-model-references.md) - Edge syntax and examples
- [Graph Overview](graph-overview.md) - Graph architecture
- [Query Planner](query-planner.md) - How queries traverse graph
- [BaseModel](../01-core-components/base-model.md) - Model implementation
