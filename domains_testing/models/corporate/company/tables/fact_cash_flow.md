---
type: domain-model-table
table: fact_cash_flow
table_type: fact
from: bronze.alpha_vantage.cash_flow
primary_key: [cash_flow_id]
partition_by: [period_end_date_id]

schema:
  - [cash_flow_id, integer, false, "PK"]
  - [company_id, integer, false, "FK to dim_company", {fk: dim_company.company_id}]
  - [period_start_date_id, integer, false, "FK to dim_calendar", {fk: temporal.dim_calendar.date_id}]
  - [period_end_date_id, integer, false, "FK to dim_calendar", {fk: temporal.dim_calendar.date_id}]
  - [report_type, string, true, "annual or quarterly"]
  - [operating_cashflow, double, true, "Cash from operations"]
  - [capital_expenditures, double, true, "CapEx"]
  - [cashflow_from_investment, double, true, "Cash from investing"]
  - [cashflow_from_financing, double, true, "Cash from financing"]
  - [dividend_payout, double, true, "Dividends paid"]
  - [net_income, double, true, "Net income"]

measures:
  - [total_operating_cf, sum, operating_cashflow, "Total operating cash flow", {format: "$#,##0"}]
  - [total_capex, sum, capital_expenditures, "Total CapEx", {format: "$#,##0"}]
---

## Cash Flow Fact Table

Cash flow statement data from SEC filings.
