---
type: domain-model-table
table: fact_budget_events
extends: _fact_budget_events
persist: true

# Sources auto-discovered: any sources/*.md with maps_to: fact_budget_events
# Currently: budget_appropriations (APPROPRIATION) + budget_revenue (REVENUE) + budget_positions (POSITION)

# Additional FK columns beyond base schema
# [column, type, nullable, description, {options}]
additional_schema:
  - [department_id, integer, true, "FK to dim_department", {fk: dim_department.org_unit_id, derived: "ABS(HASH(COALESCE(department_code, 'UNKNOWN')))"}]
  - [fund_id, integer, true, "FK to dim_fund", {fk: dim_fund.fund_id, derived: "CASE WHEN fund_code IS NOT NULL THEN ABS(HASH(fund_code)) ELSE null END"}]
  - [chart_account_id, integer, true, "FK to dim_chart_of_accounts", {fk: dim_chart_of_accounts.account_id, derived: "CASE WHEN account_code IS NOT NULL THEN ABS(HASH(account_code)) ELSE null END"}]
---

## Budget Events Fact

Extends `_base.accounting.financial_event._fact_budget_events`. Sources are auto-discovered from `sources/*.md` where `maps_to: fact_budget_events`.

### Inherited Schema (from base)

| Column | Type | Description |
|--------|------|-------------|
| budget_event_id | integer | PK (hash of event_type + fiscal_year + dept + account) |
| date_id | integer | FK to temporal.dim_calendar (Jan 1 of fiscal year) |
| fiscal_year | integer | Budget year |
| event_type | string | APPROPRIATION, REVENUE, POSITION |
| domain_source | string | 'chicago' |
| department_code | string | Department code (nullable for revenue) |
| department_description | string | Department name (nullable for revenue) |
| fund_code | string | Fund code (nullable for positions) |
| fund_description | string | Fund name (nullable for positions) |
| account_code | string | Account/title code |
| account_description | string | Account/title name |
| amount | decimal(18,2) | Budgeted amount |
| description | string | Line-item description |

### Additional FK Columns (this model)

| Column | Derived From | Target |
|--------|-------------|--------|
| department_id | HASH(department_code) | dim_department.org_unit_id |
| fund_id | HASH(fund_code) | dim_fund.fund_id |
| chart_account_id | HASH(account_code) | dim_chart_of_accounts.account_id |
