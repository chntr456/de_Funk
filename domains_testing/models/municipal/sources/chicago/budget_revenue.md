---
type: domain-model-source
source: budget_revenue
extends: _base.accounting.financial_event
maps_to: fact_budget_events
from: bronze.chicago_budget_revenue
event_type: REVENUE
domain_source: "'chicago'"
bronze_table: chicago/chicago_budget_revenue
description: "Budget revenue estimates"
update_frequency: annual

aliases:
  - [fiscal_year, year]
  - [department_code, "null"]
  - [department_description, "null"]
  - [fund_code, fund_code]
  - [fund_description, fund_description]
  - [account_code, revenue_source_code]
  - [account_description, revenue_source_description]
  - [amount, amount]
  - [description, "null"]
---

## Budget Revenue Source

Annual revenue estimates by fund and revenue source.
