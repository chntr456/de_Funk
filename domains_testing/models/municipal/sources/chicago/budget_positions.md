---
type: domain-model-source
source: budget_positions
extends: _base.accounting.financial_event
maps_to: fact_budget_events
from: bronze.chicago_budget_positions
event_type: POSITION
domain_source: "'chicago'"
aliases:
  # Inherited from financial_statement
  - [legal_entity_id, "ABS(HASH(CONCAT('CITY_', 'Chicago')))"]
  - [budget_event_id, "ABS(HASH(CONCAT('POSITION', '_', year, '_', COALESCE(department_code,''), '_', COALESCE(title_code,''))))"]
  - [account_id, "ABS(HASH(COALESCE(title_code, 'UNCLASSIFIED')))"]
  - [period_end_date_id, "CAST(CONCAT(year, '1231') AS INT)"]
  - [period_start_date_id, "CAST(CONCAT(year, '0101') AS INT)"]
  - [report_type, "'budget'"]
  - [amount, total_budgeted_amount]
  - [reported_currency, "'USD'"]
  # Budget-specific
  - [fiscal_year, year]
  - [department_code, department_code]
  - [department_description, department_description]
  - [fund_code, "null"]
  - [fund_description, "null"]
  - [account_code, title_code]
  - [account_description, title_description]
  - [description, "CONCAT(title_description, ' (', budgeted_unit, ' units)')"]
---

## Budget Positions Source

Annual budgeted employee positions with title and salary allocation.
