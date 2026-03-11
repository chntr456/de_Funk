---
type: domain-model-source
source: balance_sheet
extends: _base.accounting.financial_statement
maps_to: fact_financial_statements
from: bronze.alpha_vantage_balance_sheet
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
  - [total_assets, TOTAL_ASSETS]
  - [total_current_assets, TOTAL_CURRENT_ASSETS]
  - [cash_and_equivalents, CASH_AND_EQUIVALENTS]
  - [total_liabilities, TOTAL_LIABILITIES]
  - [total_current_liabilities, TOTAL_CURRENT_LIABILITIES]
  - [long_term_debt, LONG_TERM_DEBT]
  - [total_shareholder_equity, TOTAL_SHAREHOLDER_EQUITY]
  - [retained_earnings, RETAINED_EARNINGS]
  - [shares_outstanding, SHARES_OUTSTANDING]
---

## Balance Sheet
Assets, liabilities, equity from annual and quarterly SEC filings. Unpivoted into row-per-line-item for fact_financial_statements.
