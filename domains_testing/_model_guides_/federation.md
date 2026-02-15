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
# In domain-base
federation:
  enabled: true
  union_key: domain_source
  primary_key: entry_id
```

### Fields

| Field | Required | Description |
|-------|----------|-------------|
| `enabled` | Yes | Enable federation |
| `union_key` | Yes | Column identifying source model |
| `primary_key` | Yes | Shared PK across children |
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
- The `union_key` column must be populated by each child's `domain_source` derive
