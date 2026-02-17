---
type: domain-model-source
source: cash_flow
extends: _base.accounting.chart_of_accounts
maps_to: fact_financial_statements
from: bronze.alpha_vantage_cash_flow
transform: unpivot

aliases:
  - [company_id, "ABS(HASH(CONCAT('COMPANY_', ticker)))"]
  - [period_start_date_id, "CAST(REGEXP_REPLACE(CAST(fiscalDateEnding AS STRING), '-', '') AS INT)"]
  - [period_end_date_id, "CAST(REGEXP_REPLACE(CAST(fiscalDateEnding AS STRING), '-', '') AS INT)"]
  - [report_type, reportType]
  - [reported_currency, reportedCurrency]

unpivot_aliases:
  - [operatingCashflow, OPERATING_CASHFLOW]
  - [capitalExpenditures, CAPITAL_EXPENDITURES]
  - [cashflowFromInvestment, CASHFLOW_FROM_INVESTMENT]
  - [cashflowFromFinancing, CASHFLOW_FROM_FINANCING]
  - [dividendPayout, DIVIDEND_PAYOUT]
---

## Cash Flow
Operating, investing, and financing cash flows from annual and quarterly SEC filings. Unpivoted into row-per-line-item for fact_financial_statements.
