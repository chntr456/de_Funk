---
type: reference
description: "Guide for graph definitions - edges only in v5.0"
---

## graph Guide

In v5.0, graph only contains `edges`. Source/filter/derive are defined in table definitions.

### Edge Format (Tabular)

```yaml
graph:
  edges:
    # [edge_name, from, to, on, type, cross_model]
    - [prices_to_stock, fact_stock_prices, dim_stock, [security_id=security_id], many_to_one, null]
    - [prices_to_calendar, fact_stock_prices, temporal.dim_calendar, [date_id=date_id], many_to_one, temporal]
```

### Edge Columns

| Position | Name | Required | Description |
|----------|------|----------|-------------|
| 0 | edge_name | Yes | Unique edge identifier |
| 1 | from | Yes | Source table (in this model) |
| 2 | to | Yes | Target table (can be `model.table` for cross-model) |
| 3 | on | Yes | Join conditions `[col1=col2]` |
| 4 | type | Yes | `many_to_one`, `one_to_one`, `one_to_many` |
| 5 | cross_model | No | Target model name (null for same-model) |

### Cross-Model Edges

When `to` references another model, set `cross_model`:

```yaml
- [entry_to_calendar, fact_entries, temporal.dim_calendar, [date_id=date_id], many_to_one, temporal]
- [stock_to_company, dim_stock, company.dim_company, [company_id=company_id], many_to_one, company]
```

### Optional Edges (Left Joins)

For nullable FKs, append `optional: true` as a 7th element:

```yaml
- [entry_to_chart, fact_entries, dim_chart, [expense_category=account_code], many_to_one, null, optional: true]
```

### v5.0 Change

Graph `nodes:` with `select:`, `derive:`, `drop:` are **deprecated**. Those are now in table schema.
