---
type: domain-model-source
source: budget_revenue
maps_to: fact_budget_events
from: bronze.budget_revenue
event_type: REVENUE
domain_source: "'chicago'"

# [canonical_field, source_expression]
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

Chicago Budget Ordinance — Revenue. Annual estimated revenue by fund and revenue source.

### Source Schema

| Column | Type | Description |
|--------|------|-------------|
| year | integer | Fiscal year |
| fund_code | string | Fund code |
| fund_description | string | Fund name |
| revenue_source_code | string | Revenue source code |
| revenue_source_description | string | Revenue source name |
| amount | decimal | Estimated revenue |

### Nullable Fields

- `department_code` and `department_description` are null — revenue is not broken down by department in this source
