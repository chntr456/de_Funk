---
type: reference
description: "Guide for federation - cross-model union queries"
---

## federation Guide

Federation enables querying across multiple domain-models that share the same base template.

### How It Works

1. Multiple domain-models extend the same domain-base
2. All produce the same canonical schema
3. Query engine creates UNION views across children
4. `union_key` column identifies which child each row came from

### Base Template Config

```yaml
# In domain-base (single-fact base — primary_key specified)
federation:
  enabled: true
  union_key: domain_source
  primary_key: entry_id

# In domain-base (multi-fact base — primary_key omitted)
federation:
  enabled: true
  union_key: domain_source
```

### Fields

| Field | Required | Description |
|-------|----------|-------------|
| `enabled` | Yes | Enable federation |
| `union_key` | Yes | Column identifying source model |
| `primary_key` | Conditional | Shared PK across children. Required for single-fact bases (e.g., `ledger_entry`). Omit for multi-fact bases (e.g., `crime` has `_fact_crimes` + `_fact_arrests` with different PKs) |
| `materialize` | No | Create physical union table (default: false = view) |
| `refresh` | No | Refresh schedule: `daily`, `hourly` |

### Query Pattern

```sql
-- Auto-generated federation view
SELECT * FROM accounting.v_all_ledger_entries
-- Unions: chicago_ledger, cook_county_ledger, corporate_ledger
-- All have same canonical columns
```

### Requirements

- All children must extend the same base
- All children must output the same canonical schema
- The `union_key` column (`domain_source`) must exist in every fact table schema in the base template
- Each source file must declare `domain_source:` as a top-level key with the origin value (e.g., `"'chicago'"`)

### domain_source Column

The `domain_source` column is defined on the root event base (`_base._base_.event`) and must be carried into every fact table schema throughout the inheritance chain. This column is `nullable: false` — every fact row must identify its origin.

Sources declare it as a top-level key:

```yaml
---
type: domain-model-source
source: payments
maps_to: fact_ledger_entries
from: bronze.payments
domain_source: "'chicago'"
---
```

The loader injects it as a literal column value in the SELECT.
