---
type: domain-model-source
source: cash_flow
extends: _base.accounting.financial_statement
maps_to: fact_financial_statements
from: bronze.alpha_vantage_cash_flow
transform: unpivot

aliases:
  - [statement_entry_id, TBD]
  - [legal_entity_id, "ABS(HASH(CONCAT('COMPANY_', ticker)))"]
  - [account_id, "ABS(HASH(account_code))"]
  - [period_end_date_id, "CAST(REGEXP_REPLACE(CAST(fiscalDateEnding AS STRING), '-', '') AS INT)"]
  - [period_start_date_id, "CAST(REGEXP_REPLACE(CAST(fiscalDateEnding AS STRING), '-', '') AS INT)"]
  - [report_type, reportType]
  - [amount, TBD]
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
