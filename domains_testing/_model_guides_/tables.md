---
type: reference
description: "Guide for table definitions in domain models"
---

## tables Guide

Tables define the output schema. In v5.0, tables are the single source of truth for column definitions. Data sourcing is handled by source files (`maps_to:` links sources to tables); tables do not declare `from:`.

### Table Keys

| Key | Required | Description |
|-----|----------|-------------|
| `type` | Yes | `dimension`, `fact`, or `intermediate` |
| `extends` | No | Inherit from base table |
| `transform` | No | `aggregate`, `distinct`, `unpivot`, or omit |
| `group_by` | If aggregate | Columns to group by |
| `filter` | No | SQL WHERE on source data |
| `primary_key` | Yes | PK columns |
| `partition_by` | No | Delta partition columns |
| `schema` | Yes (or inherited) | Column definitions |
| `additional_schema` | No | Extra columns beyond inherited base |
| `enrich` | No | Enrichment from related fact tables |

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

### Fact Table (extends base, schema inherited)

```yaml
---
type: domain-model-table
table: fact_ledger_entries
table_type: fact
extends: _base.accounting.ledger_entry._fact_ledger_entries
primary_key: [entry_id]
partition_by: [date_id]

additional_schema:
  - [vendor_id, integer, true, "FK to dim_vendor"]
  - [department_id, integer, true, "FK to dim_department"]
---
```

Data flows into fact tables via source files that declare `maps_to: fact_ledger_entries`. Multiple sources unioned automatically.

### Dimension Table (schema explicit)

```yaml
---
type: domain-model-table
table: dim_vendor
table_type: dimension
transform: aggregate
group_by: [payee]
primary_key: [vendor_id]

schema:
  - [vendor_id, integer, false, "PK", {derived: "ABS(HASH(payee))"}]
  - [vendor_name, string, false, "Vendor name"]
  - [total_payments, "decimal(18,2)", true, "Lifetime total", {derived: "SUM(transaction_amount)"}]
---
```
