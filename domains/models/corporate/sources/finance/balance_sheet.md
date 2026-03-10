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
  - [statement_entry_id, "ABS(HASH(CONCAT(legal_entity_id, '_', account_id, '_', period_end_date_id, '_', report_type)))"]
  - [account_id, "ABS(HASH(account_code))"]
  - [period_end_date_id, "CAST(REGEXP_REPLACE(CAST(fiscalDateEnding AS STRING), '-', '') AS INT)"]
  - [period_start_date_id, "CAST(REGEXP_REPLACE(CAST(fiscalDateEnding AS STRING), '-', '') AS INT)"]
  - [report_type, reportType]
  - [amount, value]
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
