---
type: domain-model
model: company
version: 3.0
description: "Corporate legal entities with SEC registration and fundamentals"
depends_on: [temporal]

storage:
  format: delta
  bronze:
    provider: alpha_vantage
    tables:
      - [company_overview, alpha_vantage/company_overview]
      - [income_statement, alpha_vantage/income_statement]
      - [balance_sheet, alpha_vantage/balance_sheet]
      - [cash_flow, alpha_vantage/cash_flow]
      - [earnings, alpha_vantage/earnings]
  silver:
    root: storage/silver/corporate/

graph:
  edges:
    - [income_to_company, fact_income_statement, dim_company, [company_id=company_id], many_to_one, null]
    - [income_to_period_start, fact_income_statement, temporal.dim_calendar, [period_start_date_id=date_id], many_to_one, temporal]
    - [income_to_period_end, fact_income_statement, temporal.dim_calendar, [period_end_date_id=date_id], many_to_one, temporal]
    - [balance_to_company, fact_balance_sheet, dim_company, [company_id=company_id], many_to_one, null]
    - [balance_to_period_start, fact_balance_sheet, temporal.dim_calendar, [period_start_date_id=date_id], many_to_one, temporal]
    - [balance_to_period_end, fact_balance_sheet, temporal.dim_calendar, [period_end_date_id=date_id], many_to_one, temporal]
    - [cashflow_to_company, fact_cash_flow, dim_company, [company_id=company_id], many_to_one, null]
    - [cashflow_to_period_start, fact_cash_flow, temporal.dim_calendar, [period_start_date_id=date_id], many_to_one, temporal]
    - [cashflow_to_period_end, fact_cash_flow, temporal.dim_calendar, [period_end_date_id=date_id], many_to_one, temporal]
    - [earnings_to_company, fact_earnings, dim_company, [company_id=company_id], many_to_one, null]
    - [earnings_to_calendar, fact_earnings, temporal.dim_calendar, [report_date_id=date_id], many_to_one, temporal]

build:
  partitions: []
  sort_by: [company_id]
  optimize: true
  phases:
    1: { tables: [dim_company] }
    2: { tables: [fact_income_statement, fact_balance_sheet, fact_cash_flow, fact_earnings] }

measures:
  simple:
    - [company_count, count_distinct, dim_company.company_id, "Number of companies", {format: "#,##0"}]
    - [total_revenue_sum, sum, fact_income_statement.total_revenue, "Total revenue", {format: "$#,##0"}]
    - [avg_net_income, avg, fact_income_statement.net_income, "Average net income", {format: "$#,##0"}]
  computed:
    - [avg_margin, expression, "AVG(net_income / NULLIF(total_revenue, 0) * 100)", "Average profit margin", {format: "#,##0.00%", source_table: fact_income_statement}]
    - [debt_to_equity, expression, "AVG(long_term_debt / NULLIF(total_shareholder_equity, 0))", "Debt to equity", {format: "#,##0.00", source_table: fact_balance_sheet}]

metadata:
  domain: corporate
  owner: data_engineering
status: active
---

## Company Model

Corporate legal entities with SEC registration and financial statements.

### Architecture

```
dim_company (CIK-based)
  | company_id FK
  |-- fact_income_statement
  |-- fact_balance_sheet
  |-- fact_cash_flow
  +-- fact_earnings
```
