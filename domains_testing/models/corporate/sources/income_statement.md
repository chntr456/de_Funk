---
type: domain-model-source
source: income_statement
extends: _base.accounting.financial_statement
maps_to: fact_financial_statements
from: bronze.alpha_vantage_income_statement
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
  - [totalRevenue, TOTAL_REVENUE]
  - [costOfRevenue, COST_OF_REVENUE]
  - [grossProfit, GROSS_PROFIT]
  - [operatingExpenses, OPERATING_EXPENSES]
  - [operatingIncome, OPERATING_INCOME]
  - [ebitda, EBITDA]
  - [netIncome, NET_INCOME]
---

## Income Statement
Revenue, expenses, profit metrics from annual and quarterly SEC filings. Unpivoted into row-per-line-item for fact_financial_statements.
