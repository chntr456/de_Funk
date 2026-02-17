---
type: domain-base
model: financial_statement
version: 1.0
description: "Periodic financial reporting - income statements, balance sheets, cash flows structured by chart of accounts"
extends: _base._base_.event

# CANONICAL FIELDS
# [field_name, type, nullable: bool, description: "meaning"]
canonical_fields:
  - [statement_entry_id, integer, nullable: false, description: "Primary key"]
  - [legal_entity_id, integer, nullable: false, description: "FK to reporting entity (company or municipality)"]
  - [account_id, integer, nullable: false, description: "FK to chart of accounts line item"]
  - [period_end_date_id, integer, nullable: false, description: "FK to temporal.dim_calendar (period end)"]
  - [period_start_date_id, integer, nullable: true, description: "FK to temporal.dim_calendar (period start)"]
  - [report_type, string, nullable: false, description: "annual, quarterly"]
  - [amount, double, nullable: false, description: "Line item value"]
  - [reported_currency, string, nullable: true, description: "Reporting currency (USD, EUR, etc.)"]

tables:
  _fact_financial_statements:
    type: fact
    primary_key: [statement_entry_id]
    partition_by: [period_end_date_id]

    # [column, type, nullable, description, {options}]
    schema:
      - [statement_entry_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT(legal_entity_id, '_', account_id, '_', period_end_date_id, '_', report_type)))"}]
      - [legal_entity_id, integer, false, "FK to reporting entity"]
      - [account_id, integer, false, "FK to chart of accounts", {derived: "ABS(HASH(account_code))"}]
      - [period_end_date_id, integer, false, "FK to calendar (period end)", {fk: temporal.dim_calendar.date_id}]
      - [period_start_date_id, integer, true, "FK to calendar (period start)", {fk: temporal.dim_calendar.date_id}]
      - [report_type, string, false, "annual or quarterly"]
      - [amount, double, false, "Line item value"]
      - [reported_currency, string, true, "Reporting currency"]

    measures:
      - [entry_count, count_distinct, statement_entry_id, "Statement entries", {format: "#,##0"}]
      - [total_amount, sum, amount, "Total amount", {format: "$#,##0"}]

graph:
  edges:
    # [edge_name, from, to, on, type, cross_model]
    - [statement_to_period_end, _fact_financial_statements, temporal.dim_calendar, [period_end_date_id=date_id], many_to_one, temporal]
    - [statement_to_period_start, _fact_financial_statements, temporal.dim_calendar, [period_start_date_id=date_id], many_to_one, temporal]

domain: accounting
tags: [base, template, accounting, financial_statement, SEC]
status: active
---

## Financial Statement Base Template

Periodic financial reporting data — income statements, balance sheets, and cash flow statements. Each row is one line item for one entity in one reporting period.

### Relationship to Chart of Accounts

Financial statements are structured by a chart of accounts. The `account_id` FK links each line item to a classification in `_base.accounting.chart_of_accounts`. The implementing model provides the concrete account dimension:

- **Corporate models**: `dim_financial_account` with SEC line items (TOTAL_REVENUE, NET_INCOME, etc.)
- **Municipal models**: Government accounting chart (GAAP fund-based accounts)

### Relationship to Entity

The `legal_entity_id` FK is generic. Source aliases map it to the concrete entity:

```yaml
# Corporate: legal_entity_id maps to company_id
aliases:
  - [legal_entity_id, "ABS(HASH(CONCAT('COMPANY_', ticker)))"]

# Municipal: legal_entity_id maps to municipality_id
aliases:
  - [legal_entity_id, "ABS(HASH(CONCAT('CITY_', municipality_name)))"]
```

### Unpivot Transform

Source data typically arrives as wide tables (one column per line item). Sources use `transform: unpivot` with `unpivot_aliases:` to convert columns into rows:

```yaml
transform: unpivot
unpivot_aliases:
  - [totalRevenue, TOTAL_REVENUE]
  - [netIncome, NET_INCOME]
```

### Usage

```yaml
extends: _base.accounting.financial_statement
```
