---
type: domain-model-table
table: fact_balance_sheet
table_type: fact
from: bronze.alpha_vantage.balance_sheet
primary_key: [balance_sheet_id]
partition_by: [period_end_date_id]

schema:
  - [balance_sheet_id, integer, false, "PK"]
  - [company_id, integer, false, "FK to dim_company", {fk: dim_company.company_id}]
  - [period_start_date_id, integer, false, "FK to dim_calendar", {fk: temporal.dim_calendar.date_id}]
  - [period_end_date_id, integer, false, "FK to dim_calendar", {fk: temporal.dim_calendar.date_id}]
  - [report_type, string, true, "annual or quarterly"]
  - [reported_currency, string, true, "Reporting currency"]
  - [total_assets, double, true, "Total assets"]
  - [total_current_assets, double, true, "Current assets"]
  - [cash_and_equivalents, double, true, "Cash and equivalents"]
  - [total_liabilities, double, true, "Total liabilities"]
  - [total_current_liabilities, double, true, "Current liabilities"]
  - [long_term_debt, double, true, "Long-term debt"]
  - [total_shareholder_equity, double, true, "Shareholder equity"]
  - [retained_earnings, double, true, "Retained earnings"]
  - [shares_outstanding, double, true, "Shares outstanding"]

measures:
  - [avg_total_assets, avg, total_assets, "Avg total assets", {format: "$#,##0"}]
  - [avg_equity, avg, total_shareholder_equity, "Avg equity", {format: "$#,##0"}]
---

## Balance Sheet Fact Table

Balance sheet data from SEC filings.
