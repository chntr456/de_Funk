---
type: domain-base
model: financial_statement
version: 1.0
description: "Periodic financial reporting - income statements, balance sheets, cash flows, budgets structured by chart of accounts"
extends: _base._base_.event

# CANONICAL FIELDS
# [field_name, type, nullable: bool, description: "meaning"]
canonical_fields:
  - [statement_entry_id, integer, nullable: false, description: "Primary key"]
  - [legal_entity_id, integer, nullable: false, description: "FK to reporting entity (company or municipality)"]
  - [account_id, integer, nullable: false, description: "FK to chart of accounts line item"]
  - [period_end_date_id, integer, nullable: false, description: "FK to temporal.dim_calendar (period end)"]
  - [period_start_date_id, integer, nullable: true, description: "FK to temporal.dim_calendar (period start)"]
  - [report_type, string, nullable: false, description: "annual, quarterly, budget"]
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
      # Simple aggregations (work on any financial_statement fact)
      - [entry_count, count_distinct, statement_entry_id, "Statement entries", {format: "#,##0"}]
      - [total_amount, sum, amount, "Total amount", {format: "$#,##0"}]
      - [avg_line_item, avg, amount, "Average line item", {format: "$#,##0.00"}]
      - [entity_count, count_distinct, legal_entity_id, "Reporting entities", {format: "#,##0"}]
      - [period_count, count_distinct, period_end_date_id, "Reporting periods", {format: "#,##0"}]

      # Account-type measures (JOIN to chart of accounts via account_type — works for corporate AND municipal)
      - [total_revenue_by_type, expression, "SUM(CASE WHEN coa.account_type = 'REVENUE' THEN fs.amount ELSE 0 END)", "Revenue (all accounts)", {format: "$#,##0", joins: "_fact_financial_statements fs JOIN _dim_chart_of_accounts coa ON fs.account_id = coa.account_id"}]
      - [total_expenses_by_type, expression, "SUM(CASE WHEN coa.account_type = 'EXPENSE' THEN fs.amount ELSE 0 END)", "Expenses (all accounts)", {format: "$#,##0", joins: "_fact_financial_statements fs JOIN _dim_chart_of_accounts coa ON fs.account_id = coa.account_id"}]
      - [net_position, expression, "SUM(CASE WHEN coa.account_type = 'REVENUE' THEN fs.amount WHEN coa.account_type = 'EXPENSE' THEN -fs.amount ELSE 0 END)", "Revenue minus expenses", {format: "$#,##0", joins: "_fact_financial_statements fs JOIN _dim_chart_of_accounts coa ON fs.account_id = coa.account_id"}]
      - [expense_ratio, expression, "SUM(CASE WHEN coa.account_type = 'EXPENSE' THEN fs.amount ELSE 0 END) / NULLIF(SUM(CASE WHEN coa.account_type = 'REVENUE' THEN fs.amount ELSE 0 END), 0)", "Expense-to-revenue ratio", {format: "#,##0.00", joins: "_fact_financial_statements fs JOIN _dim_chart_of_accounts coa ON fs.account_id = coa.account_id"}]

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

Periodic financial reporting data — income statements, balance sheets, cash flows, and budgets. Each row is one line item for one entity in one reporting period. The `report_type` discriminator distinguishes actuals from budgets.

### What Extends This

| Template | report_type values | Use case |
|----------|-------------------|----------|
| *(direct use)* | `annual`, `quarterly` | SEC filings (10-K, 10-Q) |
| `_base.accounting.financial_event` | `budget` | Municipal/corporate budgets |

### Shared Measures

The account-type measures (`total_revenue_by_type`, `total_expenses_by_type`, `net_position`, `expense_ratio`) work across ANY implementing model because they rely on `account_type` from the chart of accounts, not specific account codes. This enables:

- Compare Chicago's budgeted revenue vs Apple's reported revenue — same measure, different `legal_entity_id`
- Budget-vs-actual analysis — filter `report_type IN ('annual', 'budget')` for the same entity

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
