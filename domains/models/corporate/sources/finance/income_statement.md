---
type: domain-model-source
source: income_statement
extends: _base.accounting.financial_statement
maps_to: fact_financial_statements
from: bronze.alpha_vantage_income_statement
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
  - [total_revenue, TOTAL_REVENUE]
  - [cost_of_revenue, COST_OF_REVENUE]
  - [gross_profit, GROSS_PROFIT]
  - [operating_expenses, OPERATING_EXPENSES]
  - [operating_income, OPERATING_INCOME]
  - [ebitda, EBITDA]
  - [net_income, NET_INCOME]
---

## Income Statement
Revenue, expenses, profit metrics from annual and quarterly SEC filings. Unpivoted into row-per-line-item for fact_financial_statements.
