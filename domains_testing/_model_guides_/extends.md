---
type: reference
description: "Guide for extends keyword - inheriting from base templates"
---

## extends Guide

The `extends` keyword links a domain-model to a domain-base template.

### Syntax

```yaml
extends: _base.{category}.{template}
```

### What Gets Inherited

| From Base | Behavior |
|-----------|----------|
| `canonical_fields` | Defines the target schema contract |
| `tables._*` | Table schema inherited when child uses `extends:` on table |
| `measures` | Base measures available on child tables |
| `federation` | Federation config inherited if enabled |
| `graph.edges` | Template edges inherited (child overrides table names) |

### Table-Level Extends

Tables can also extend specific base tables:

```yaml
tables:
  fact_ledger_entries:
    extends: _base.accounting.ledger_entry._fact_ledger_entries
    type: fact
    source: union(vendor_payments, employee_salaries)
    primary_key: [entry_id]
```

### Schema Merge Rules

1. Child inherits all parent columns
2. Child can add new columns
3. Child can override column options (nullable, default)
4. Child cannot change column type
5. Child cannot remove parent columns
