---
type: domain-model-table
table: fact_income_statement
table_type: fact
from: bronze.alpha_vantage.income_statement
primary_key: [income_statement_id]
partition_by: [period_end_date_id]

schema:
  - [income_statement_id, integer, false, "PK"]
  - [company_id, integer, false, "FK to dim_company", {fk: dim_company.company_id}]
  - [period_start_date_id, integer, false, "FK to dim_calendar", {fk: temporal.dim_calendar.date_id}]
  - [period_end_date_id, integer, false, "FK to dim_calendar", {fk: temporal.dim_calendar.date_id}]
  - [report_type, string, true, "annual or quarterly"]
  - [total_revenue, double, true, "Total revenue"]
  - [gross_profit, double, true, "Gross profit"]
  - [operating_income, double, true, "Operating income"]
  - [net_income, double, true, "Net income"]
  - [ebitda, double, true, "EBITDA"]
  - [reported_currency, string, true, "Reporting currency"]

measures:
  - [total_revenue_sum, sum, total_revenue, "Total revenue", {format: "$#,##0"}]
  - [avg_net_income, avg, net_income, "Avg net income", {format: "$#,##0"}]
---

## Income Statement Fact Table

Income statement data from SEC filings via Alpha Vantage.
