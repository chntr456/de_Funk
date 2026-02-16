---
type: domain-model-table
table: dim_chart_of_accounts
extends: _dim_chart_of_accounts
table_type: dimension
from: fact_budget_events
transform: distinct
group_by: [account_code]
primary_key: [account_id]
unique_key: [account_code]

# [column, type, nullable, description, {options}]
schema:
  - [account_id, integer, false, "PK", {derived: "ABS(HASH(account_code))"}]
  - [account_code, string, false, "Natural key", {derived: "account_code"}]
  - [account_name, string, false, "Display name", {derived: "account_description"}]
  - [account_type, string, false, "Classification", {derived: "CASE WHEN event_type = 'REVENUE' THEN 'REVENUE' WHEN event_type = 'POSITION' THEN 'EXPENSE' ELSE 'EXPENSE' END"}]
  - [parent_account_id, integer, true, "No hierarchy in source", {derived: "null"}]
  - [level, integer, false, "Flat hierarchy", {derived: "1"}]
  - [is_active, boolean, false, "Currently used", {default: true}]

measures:
  - [account_count, count_distinct, account_id, "Number of accounts", {format: "#,##0"}]
  - [expense_account_count, expression, "SUM(CASE WHEN account_type = 'EXPENSE' THEN 1 ELSE 0 END)", "Expense accounts", {format: "#,##0"}]
  - [revenue_account_count, expression, "SUM(CASE WHEN account_type = 'REVENUE' THEN 1 ELSE 0 END)", "Revenue accounts", {format: "#,##0"}]
---

## Chart of Accounts Dimension

Extends `_base.accounting.chart_of_accounts._dim_chart_of_accounts`. Distinct accounts discovered from **canonicalized budget events**.

### Notes

- Accounts come from all three budget event types (APPROPRIATION, REVENUE, POSITION)
- `account_type` is inferred from the `event_type` of the source budget event:
  - REVENUE events → REVENUE accounts
  - APPROPRIATION and POSITION events → EXPENSE accounts
- Hierarchy is flat (level=1) — Chicago's budget data doesn't provide parent-child account relationships
- `account_code` maps to different source fields by event type:
  - APPROPRIATION: `appropriation_account`
  - REVENUE: `revenue_source_code`
  - POSITION: `title_code`
