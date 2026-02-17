---
type: domain-model-source
source: balance_sheet
extends: _base.accounting.financial_statement
maps_to: fact_financial_statements
from: bronze.alpha_vantage_balance_sheet
transform: unpivot

aliases:
  - [statement_entry_id, TBD]
  - [entity_id, "ABS(HASH(CONCAT('COMPANY_', ticker)))"]
  - [account_id, "ABS(HASH(account_code))"]
  - [period_end_date_id, "CAST(REGEXP_REPLACE(CAST(fiscalDateEnding AS STRING), '-', '') AS INT)"]
  - [period_start_date_id, "CAST(REGEXP_REPLACE(CAST(fiscalDateEnding AS STRING), '-', '') AS INT)"]
  - [report_type, reportType]
  - [amount, TBD]
  - [reported_currency, reportedCurrency]

unpivot_aliases:
  - [totalAssets, TOTAL_ASSETS]
  - [totalCurrentAssets, TOTAL_CURRENT_ASSETS]
  - [cashAndCashEquivalentsAtCarryingValue, CASH_AND_EQUIVALENTS]
  - [totalLiabilities, TOTAL_LIABILITIES]
  - [totalCurrentLiabilities, TOTAL_CURRENT_LIABILITIES]
  - [longTermDebt, LONG_TERM_DEBT]
  - [totalShareholderEquity, TOTAL_SHAREHOLDER_EQUITY]
  - [retainedEarnings, RETAINED_EARNINGS]
  - [commonStockSharesOutstanding, SHARES_OUTSTANDING]
---

## Balance Sheet
Assets, liabilities, equity from annual and quarterly SEC filings. Unpivoted into row-per-line-item for fact_financial_statements.
