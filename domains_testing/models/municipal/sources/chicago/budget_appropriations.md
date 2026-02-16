---
type: domain-model-source
source: budget_appropriations
extends: _base.accounting.financial_event
maps_to: fact_budget_events
from: bronze.chicago_budget_appropriations
event_type: APPROPRIATION
domain_source: "'chicago'"
bronze_table: chicago/chicago_budget_appropriations
description: "Budget appropriations by department"
update_frequency: annual

aliases:
  - [fiscal_year, year]
  - [department_code, department_code]
  - [department_description, department_description]
  - [fund_code, fund_code]
  - [fund_description, fund_description]
  - [account_code, appropriation_account]
  - [account_description, appropriation_account_description]
  - [amount, amount]
  - [description, "null"]
---

## Budget Appropriations Source

Annual budget appropriations by department and fund.
