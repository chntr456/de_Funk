---
type: reference
description: "Guide for table definitions in domain models"
---

## tables Guide

Tables define the output schema. In v5.0, tables are the single source of truth for column definitions.

### Table Keys

| Key | Required | Description |
|-----|----------|-------------|
| `type` | Yes | `dimension`, `fact`, or `intermediate` |
| `extends` | No | Inherit from base table |
| `from` | Conditional | Source table (single source) |
| `filter` | No | SQL WHERE on source |
| `source` | Conditional | `union(source1, source2)` for multi-source |
| `primary_key` | Yes | PK columns |
| `partition_by` | No | Delta partition columns |
| `schema` | Yes (or inherited) | Column definitions |

### Schema Column Format

```yaml
# [column, type, nullable, description, {options}]
schema:
  - [entry_id, integer, false, "PK", {derived: "ABS(HASH(...))"}]
  - [date_id, integer, false, "FK", {fk: temporal.dim_calendar.date_id}]
  - [amount, "decimal(18,2)", false, "Amount"]
  - [department, string, true, "Nullable field"]
```

### Options

| Option | Description | Example |
|--------|-------------|---------|
| `derived` | SQL expression | `{derived: "ABS(HASH(ticker))"}` |
| `fk` | Foreign key | `{fk: temporal.dim_calendar.date_id}` |
| `enum` | Allowed values | `{enum: [EXPENSE, REVENUE]}` |
| `default` | Default value | `{default: true}` |
| `unique` | Unique constraint | `{unique: true}` |
| `format` | Display format | `{format: "$#,##0.00"}` |

### Single Source Table

```yaml
tables:
  dim_stock:
    extends: _base.finance.securities._dim_security
    type: dimension
    from: bronze.alpha_vantage.listing_status
    filter: "assetType = 'Stock'"
    primary_key: [security_id]
```

### Multi-Source Union Table

```yaml
tables:
  fact_ledger_entries:
    extends: _base.accounting.ledger_entry._fact_ledger_entries
    type: fact
    source: union(vendor_payments, employee_salaries, contracts)
    primary_key: [entry_id]
    partition_by: [date_id]
```
