---
type: domain-model
model: company
version: 3.1
description: "Corporate legal entities with SEC registration and financial statements"
extends: [_base.entity.company, _base.accounting.financial_statement, _base.corporate.earnings]
depends_on: [temporal]

sources_from: sources/
storage:
  format: delta
  silver:
    root: storage/silver/corporate/

graph:
  edges:
    # [edge_name, from, to, on, type, cross_model]
    - [statement_to_company, fact_financial_statements, dim_company, [company_id=company_id], many_to_one, null]
    - [statement_to_account, fact_financial_statements, dim_financial_account, [account_id=account_id], many_to_one, null]
    - [statement_to_period_start, fact_financial_statements, temporal.dim_calendar, [period_start_date_id=date_id], many_to_one, temporal]
    - [statement_to_period_end, fact_financial_statements, temporal.dim_calendar, [period_end_date_id=date_id], many_to_one, temporal]
    - [earnings_to_company, fact_earnings, dim_company, [company_id=company_id], many_to_one, null]
    - [earnings_to_calendar, fact_earnings, temporal.dim_calendar, [report_date_id=date_id], many_to_one, temporal]

build:
  partitions: []
  sort_by: [company_id]
  optimize: true
  phases:
    1: { tables: [dim_company, dim_financial_account] }
    2: { tables: [fact_financial_statements, fact_earnings] }

measures:
  simple:
    - [company_count, count_distinct, dim_company.company_id, "Number of companies", {format: "#,##0"}]
    - [avg_eps, avg, fact_earnings.reported_eps, "Average EPS", {format: "$#,##0.00"}]
  computed:
    - [total_revenue, expression, "SUM(CASE WHEN fa.account_code = 'TOTAL_REVENUE' THEN fs.amount ELSE 0 END)", "Total revenue", {format: "$#,##0", joins: "fact_financial_statements fs JOIN dim_financial_account fa ON fs.account_id = fa.account_id"}]
    - [net_income, expression, "SUM(CASE WHEN fa.account_code = 'NET_INCOME' THEN fs.amount ELSE 0 END)", "Net income", {format: "$#,##0", joins: "fact_financial_statements fs JOIN dim_financial_account fa ON fs.account_id = fa.account_id"}]
    - [profit_margin, expression, "SUM(CASE WHEN fa.account_code = 'NET_INCOME' THEN fs.amount ELSE 0 END) / NULLIF(SUM(CASE WHEN fa.account_code = 'TOTAL_REVENUE' THEN fs.amount ELSE 0 END), 0) * 100", "Profit margin %", {format: "#,##0.00%"}]
    - [debt_to_equity, expression, "SUM(CASE WHEN fa.account_code = 'LONG_TERM_DEBT' THEN fs.amount ELSE 0 END) / NULLIF(SUM(CASE WHEN fa.account_code = 'TOTAL_SHAREHOLDER_EQUITY' THEN fs.amount ELSE 0 END), 0)", "Debt to equity ratio", {format: "#,##0.00"}]

metadata:
  domain: corporate
  owner: data_engineering
status: active
---

## Company Model

Corporate entities with SEC-filed financial statements normalized into a chart-of-accounts structure.

### Financial Statement Normalization

Financial line items from income statements, balance sheets, and cash flow statements are stored as rows in `fact_financial_statements` with classification in `dim_financial_account`. This enables:

- Cross-company comparison by any line item
- Time-series analysis for any account
- Federation with other financial data sources

### Example Queries

```sql
-- Revenue by company over time
SELECT c.ticker, cal.year, SUM(fs.amount) as revenue
FROM fact_financial_statements fs
JOIN dim_company c ON fs.company_id = c.company_id
JOIN dim_financial_account fa ON fs.account_id = fa.account_id
JOIN temporal.dim_calendar cal ON fs.period_end_date_id = cal.date_id
WHERE fa.account_code = 'TOTAL_REVENUE' AND fs.report_type = 'annual'
GROUP BY c.ticker, cal.year
ORDER BY c.ticker, cal.year;
```
