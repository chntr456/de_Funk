---
type: domain-model-source
source: cash_flow
extends: _base.accounting.financial_statement
maps_to: fact_financial_statements
from: bronze.alpha_vantage_cash_flow
transform: unpivot
domain_source: "'alpha_vantage'"

aliases:
  - [legal_entity_id, "ABS(HASH(CONCAT('COMPANY_', ticker)))"]
  - [period_end_date_id, "CAST(REGEXP_REPLACE(CAST(fiscal_date_ending AS STRING), '-', '') AS INT)"]
  - [period_start_date_id, "CAST(REGEXP_REPLACE(CAST(fiscal_date_ending AS STRING), '-', '') AS INT)"]
  - [report_type, report_type]
  - [amount, value]
  - [reported_currency, reported_currency]

unpivot_aliases:
  - [operating_cashflow, OPERATING_CASHFLOW]
  - [capital_expenditures, CAPITAL_EXPENDITURES]
  - [cashflow_from_investment, CASHFLOW_FROM_INVESTMENT]
  - [cashflow_from_financing, CASHFLOW_FROM_FINANCING]
  - [dividend_payout, DIVIDEND_PAYOUT]
---

## Cash Flow
Operating, investing, and financing cash flows from annual and quarterly SEC filings. Unpivoted into row-per-line-item for fact_financial_statements.
