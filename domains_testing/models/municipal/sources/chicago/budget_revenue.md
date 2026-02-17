---
type: domain-model-source
source: budget_revenue
extends: _base.accounting.financial_event
maps_to: fact_budget_events
from: bronze.chicago_budget_revenue
event_type: REVENUE
domain_source: "'chicago'"
aliases:
  # Inherited from financial_statement
  - [legal_entity_id, "ABS(HASH(CONCAT('CITY_', 'Chicago')))"]
  - [account_id, "ABS(HASH(COALESCE(revenue_source_code, 'UNCLASSIFIED')))"]
  - [period_end_date_id, "CAST(CONCAT(year, '1231') AS INT)"]
  - [period_start_date_id, "CAST(CONCAT(year, '0101') AS INT)"]
  - [report_type, "'budget'"]
  - [amount, amount]
  - [reported_currency, "'USD'"]
  # Budget-specific
  - [fiscal_year, year]
  - [department_code, "null"]
  - [department_description, "null"]
  - [fund_code, fund_code]
  - [fund_description, fund_description]
  - [account_code, revenue_source_code]
  - [account_description, revenue_source_description]
  - [description, "null"]
---

## Budget Revenue Source

Annual revenue estimates by fund and revenue source.
