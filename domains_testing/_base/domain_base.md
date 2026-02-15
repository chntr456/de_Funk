---
type: reference
model: domain_base_overview
version: 1.0
description: "Overview of the domain-base template system"
---

## Domain Base System

The `_base/` directory contains reusable templates that define **what** canonical schemas look like. They are never materialized directly - only inherited by concrete domain-models.

### Template Hierarchy

```
_base_/                          ROOT ABSTRACTIONS
  entity.md                      Any identifiable thing
  event.md                       Any timestamped occurrence

accounting/                      FINANCIAL ACCOUNTING
  chart_of_accounts.md           Account classification (extends entity)
  fund.md                        Fiscal accounting pools (extends entity)
  ledger_entry.md                Payments/payroll/contracts (extends event)
  financial_event.md             Budget/appropriation events (extends event)

finance/                         MARKET FINANCE
  securities.md                  Tradable securities (extends entity)

entity/                          ORGANIZATIONAL
  legal.md                       Companies, municipalities (extends entity)
  organizational_entity.md       Departments, divisions (extends entity)

geography/                       SPATIAL
  geo_location.md                Point locations (extends entity)
  geo_spatial.md                 Boundaries/polygons (extends entity)

temporal/                        TIME
  calendar.md                    Daily calendar dimension
```

### Design Principles

1. **Base is pure** - Only canonical fields, never source-specific names
2. **Tabular format** - canonical_fields and edges use array notation to reduce nesting
3. **Nullable contract** - Fields marked `nullable: true` may be null; domain-models must handle this
4. **Schema is authoritative** - Derived expressions live in table schema, not graph nodes
5. **Integer PKs** - All surrogate keys are `ABS(HASH(...))` integers
6. **date_id everywhere** - All facts FK to `temporal.dim_calendar` via integer date_id

### Canonical Fields Format

```yaml
canonical_fields:
  - [field_name, type, nullable: bool, description: "meaning"]
```

### Edge Format

```yaml
graph:
  edges:
    # [edge_name, from, to, on, type, cross_model]
    - [entry_to_calendar, fact_table, temporal.dim_calendar, [date_id=date_id], many_to_one, temporal]
```

### How Models Use Bases

```yaml
# In models/municipal/chicago/finance.md
type: domain-model
extends: _base.accounting.ledger_entry

# Aliases map source fields to canonical fields
aliases:
  - ["vendor_name", payee]
  - ["amount", transaction_amount]

# Sources handle multi-endpoint unions
sources:
  - [vendor_payments, bronze.chicago.chicago_payments, VENDOR_PAYMENT]
  - [employee_salaries, bronze.chicago.chicago_salaries, PAYROLL]
```
