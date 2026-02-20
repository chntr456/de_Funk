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

---

### Current Federation Membership

Maps each federated base template to its known model implementations. When adding a new model that extends a federated base, add it to the appropriate section below.

#### Accounting — Ledger Entry

**Base**: `_base.accounting.ledger_entry` | **PK**: `entry_id`

| Model | domain_source | Fact Table |
|-------|--------------|------------|
| `municipal/finance` | chicago | fact_ledger_entries |
| `corporate/finance` | — | (uses financial_statement instead) |

#### Accounting — Financial Event

**Base**: `_base.accounting.financial_event`

| Model | domain_source | Fact Table(s) |
|-------|--------------|---------------|
| `municipal/finance` | chicago | fact_budget_events, fact_property_tax |
| `corporate/finance` | alpha_vantage | fact_financial_statements, fact_earnings |

#### Public Safety — Crime

**Base**: `_base.public_safety.crime`

| Model | domain_source | Fact Table(s) |
|-------|--------------|---------------|
| `municipal/public_safety` | chicago | fact_crimes, fact_arrests |

#### Operations — Service Request

**Base**: `_base.operations.service_request`

| Model | domain_source | Fact Table(s) |
|-------|--------------|---------------|
| `municipal/operations` | chicago | fact_service_requests |

#### Regulatory — Inspection

**Base**: `_base.regulatory.inspection`

| Model | domain_source | Fact Table(s) |
|-------|--------------|---------------|
| `municipal/regulatory` | chicago | fact_food_inspections, fact_building_violations, fact_business_licenses |

#### Housing — Permit

**Base**: `_base.housing.permit`

| Model | domain_source | Fact Table(s) |
|-------|--------------|---------------|
| `municipal/housing` | chicago | fact_building_permits |

#### Transportation — Transit / Traffic

**Base**: `_base.transportation.transit` / `_base.transportation.traffic`

| Model | domain_source | Fact Table(s) |
|-------|--------------|---------------|
| `municipal/transportation` | chicago | fact_ridership, fact_traffic_observations |

#### Corporate — Earnings

**Base**: `_base.corporate.earnings`

| Model | domain_source | Fact Table(s) |
|-------|--------------|---------------|
| `corporate/finance` | alpha_vantage | fact_earnings |

#### Finance — Corporate Action

**Base**: `_base.finance.corporate_action`

| Model | domain_source | Fact Table(s) |
|-------|--------------|---------------|
| `securities/stocks` | alpha_vantage | fact_dividends, fact_splits |
