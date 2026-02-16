---
type: domain-model-source
source: budget_appropriations
maps_to: fact_budget_events
from: bronze.budget_appropriations
event_type: APPROPRIATION
domain_source: "'chicago'"

# [canonical_field, source_expression]
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

Chicago Budget Ordinance — Appropriations. Annual authorized spending by department, fund, and account.

### Source Schema

| Column | Type | Description |
|--------|------|-------------|
| year | integer | Fiscal year |
| fund_code | string | Fund code |
| fund_description | string | Fund name |
| department_code | string | Department code |
| department_description | string | Department name |
| appropriation_account | string | Appropriation account code |
| appropriation_account_description | string | Account name |
| amount | decimal | Appropriated amount |
