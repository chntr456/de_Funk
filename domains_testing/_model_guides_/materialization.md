---
type: reference
description: "Guide for materialization - what gets built and how"
---

## materialization Guide

### What Gets Materialized

| Type | Prefix | Materialized? |
|------|--------|---------------|
| domain-base | `_base/` | Never - template only |
| domain-model | `models/` | Yes - writes to Silver |
| template table | `_table_name` | Never - inherited by children |
| concrete table | `table_name` | Yes - written to storage |
| intermediate | `_int_table` | Configurable via `persist: false` |

### Build Phases

```yaml
build:
  partitions: [date_id]
  optimize: true

  phases:
    1:
      tables: [dim_department, dim_vendor]
      persist: true
    2:
      tables: [fact_ledger_entries]
      persist: true
```

### Storage Format

All materialized tables use Delta Lake:
- ACID transactions
- Time travel / version history
- Schema evolution
- Merge/upsert support

### Paths

```
storage/silver/{model}/{table}/
```

Example: `storage/silver/chicago/ledger/fact_ledger_entries/`
