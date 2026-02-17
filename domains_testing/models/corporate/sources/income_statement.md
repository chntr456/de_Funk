---
type: domain-model-source
source: income_statement
extends: _base.accounting.chart_of_accounts
maps_to: fact_financial_statements
from: bronze.alpha_vantage_income_statement
transform: unpivot

aliases:
  - [company_id, "ABS(HASH(CONCAT('COMPANY_', ticker)))"]
  - [period_start_date_id, "CAST(REGEXP_REPLACE(CAST(fiscalDateEnding AS STRING), '-', '') AS INT)"]
  - [period_end_date_id, "CAST(REGEXP_REPLACE(CAST(fiscalDateEnding AS STRING), '-', '') AS INT)"]
  - [report_type, reportType]
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
