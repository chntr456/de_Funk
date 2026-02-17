---
type: domain-model-source
source: budget_positions
extends: _base.accounting.financial_event
maps_to: fact_budget_events
from: bronze.chicago_budget_positions
event_type: POSITION
domain_source: "'chicago'"
aliases:
  - [legal_entity_id, "ABS(HASH(CONCAT('CITY_', 'Chicago')))"]
  - [fiscal_year, year]
  - [department_code, department_code]
  - [department_description, department_description]
  - [fund_code, "null"]
  - [fund_description, "null"]
  - [account_code, title_code]
  - [account_description, title_description]
  - [amount, total_budgeted_amount]
  - [description, "CONCAT(title_description, ' (', budgeted_unit, ' units)')"]
---

## Budget Positions Source

Annual budgeted employee positions with title and salary allocation.
