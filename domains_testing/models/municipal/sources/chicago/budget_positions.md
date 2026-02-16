---
type: domain-model-source
source: budget_positions
maps_to: fact_budget_events
from: bronze.budget_positions
event_type: POSITION
domain_source: "'chicago'"

# [canonical_field, source_expression]
aliases:
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

Chicago Budget Ordinance — Positions and Salaries. Annual budgeted personnel positions by department and title.

### Source Schema

| Column | Type | Description |
|--------|------|-------------|
| year | integer | Fiscal year |
| department_code | string | Department code |
| department_description | string | Department name |
| title_code | string | Position title code |
| title_description | string | Position title |
| budgeted_unit | decimal | Number of budgeted positions |
| total_budgeted_amount | decimal | Total budgeted salary |
| position_control | integer | Position control number |

### Nullable Fields

- `fund_code` and `fund_description` are null — positions are not broken out by fund in this source

### Mapping Notes

- `account_code` maps to `title_code` (position title serves as the "account")
- `description` is a computed concat of title and unit count for readability
