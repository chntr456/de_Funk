---
type: domain-base
model: financial_event
version: 2.0
description: "Budget events - appropriations, revenue estimates, position allocations. Extends financial_statement for cross-domain comparison."
extends: _base.accounting.financial_statement

# CANONICAL FIELDS
# Inherited from financial_statement: statement_entry_id, legal_entity_id, account_id,
#   period_end_date_id, period_start_date_id, report_type, amount, reported_currency
# Additional budget-specific fields below:
# [field_name, type, nullable: bool, description: "meaning"]
canonical_fields:
  # Inherited (mapped by budget sources):
  - [statement_entry_id, integer, nullable: false, description: "PK (aliased as budget_event_id)"]
  - [legal_entity_id, integer, nullable: false, description: "FK to owning municipality/entity"]
  - [account_id, integer, nullable: false, description: "FK to chart of accounts (derived from account_code)"]
  - [period_end_date_id, integer, nullable: false, description: "FK to calendar (Dec 31 of fiscal year)"]
  - [period_start_date_id, integer, nullable: true, description: "FK to calendar (Jan 1 of fiscal year)"]
  - [report_type, string, nullable: false, description: "'budget' for all budget events"]
  - [amount, "decimal(18,2)", nullable: false, description: "Budgeted amount"]
  - [reported_currency, string, nullable: true, description: "Currency (USD for US municipal)"]

  # Budget-specific additions:
  - [fiscal_year, integer, nullable: false, description: "Budget fiscal year"]
  - [event_type, string, nullable: false, description: "APPROPRIATION, REVENUE, POSITION"]
  - [domain_source, string, nullable: false, description: "Origin domain"]
  - [department_code, string, nullable: true, description: "Department code (null if n/a)"]
  - [department_description, string, nullable: true, description: "Department name (null if n/a)"]
  - [fund_code, string, nullable: true, description: "Fund code"]
  - [fund_description, string, nullable: true, description: "Fund name"]
  - [account_code, string, nullable: true, description: "Account/appropriation code (raw string)"]
  - [account_description, string, nullable: true, description: "Account name"]
  - [description, string, nullable: true, description: "Line-item description"]

tables:
  _fact_budget_events:
    type: fact
    primary_key: [budget_event_id]
    partition_by: [fiscal_year]

    # [column, type, nullable, description, {options}]
    schema:
      # Inherited financial_statement columns
      - [budget_event_id, integer, false, "PK (maps to statement_entry_id)", {derived: "ABS(HASH(CONCAT(event_type, '_', fiscal_year, '_', COALESCE(department_code,''), '_', COALESCE(account_code,''))))"}]
      - [legal_entity_id, integer, false, "FK to owning entity"]
      - [account_id, integer, false, "FK to chart of accounts", {derived: "ABS(HASH(COALESCE(account_code, 'UNCLASSIFIED')))", fk: "_dim_chart_of_accounts.account_id"}]
      - [period_end_date_id, integer, false, "FK to calendar (Dec 31)", {fk: temporal.dim_calendar.date_id, derived: "CAST(CONCAT(fiscal_year, '1231') AS INT)"}]
      - [period_start_date_id, integer, true, "FK to calendar (Jan 1)", {fk: temporal.dim_calendar.date_id, derived: "CAST(CONCAT(fiscal_year, '0101') AS INT)"}]
      - [report_type, string, false, "'budget'", {default: "'budget'"}]
      - [amount, "decimal(18,2)", false, "Budgeted amount"]
      - [reported_currency, string, true, "Currency", {default: "'USD'"}]

      # Budget-specific columns
      - [fiscal_year, integer, false, "Budget year"]
      - [event_type, string, false, "APPROPRIATION, REVENUE, POSITION"]
      - [domain_source, string, false, "Origin domain"]
      - [department_code, string, true, "Department code"]
      - [department_description, string, true, "Department name"]
      - [fund_code, string, true, "Fund code"]
      - [fund_description, string, true, "Fund name"]
      - [account_code, string, true, "Raw account code (also used to derive account_id)"]
      - [account_description, string, true, "Account name"]
      - [description, string, true, "Line-item description"]

    measures:
      # Inherited from financial_statement: entry_count, total_amount, avg_line_item,
      #   entity_count, period_count, total_revenue_by_type, total_expenses_by_type, etc.
      # Budget-specific measures:
      - [total_budget, sum, amount, "Total budgeted amount", {format: "$#,##0.00"}]
      - [line_item_count, count_distinct, budget_event_id, "Budget line items", {format: "#,##0"}]
      - [appropriation_total, expression, "SUM(CASE WHEN event_type = 'APPROPRIATION' THEN amount ELSE 0 END)", "Total appropriations", {format: "$#,##0.00"}]
      - [revenue_total, expression, "SUM(CASE WHEN event_type = 'REVENUE' THEN amount ELSE 0 END)", "Total revenue", {format: "$#,##0.00"}]
      - [position_total, expression, "SUM(CASE WHEN event_type = 'POSITION' THEN amount ELSE 0 END)", "Total position salaries", {format: "$#,##0.00"}]
      - [budget_surplus, expression, "SUM(CASE WHEN event_type = 'REVENUE' THEN amount ELSE 0 END) - SUM(CASE WHEN event_type = 'APPROPRIATION' THEN amount ELSE 0 END)", "Revenue minus appropriations", {format: "$#,##0.00"}]
      - [position_pct, expression, "SUM(CASE WHEN event_type = 'POSITION' THEN amount ELSE 0 END) / NULLIF(SUM(CASE WHEN event_type = 'APPROPRIATION' THEN amount ELSE 0 END), 0) * 100", "Personnel as % of appropriations", {format: "#,##0.0%"}]

graph:
  edges:
    # [edge_name, from, to, on, type, cross_model]
    - [budget_to_calendar, _fact_budget_events, temporal.dim_calendar, [period_end_date_id=date_id], many_to_one, temporal]

federation:
  enabled: true
  union_key: domain_source
  primary_key: budget_event_id

domain: accounting
tags: [base, template, accounting, budget, financial_statement]
status: active
---

## Financial Event Base Template

Budget and fiscal planning events. Extends `_base.accounting.financial_statement` so that budget data shares the same `legal_entity_id + account_id + amount` structure as SEC filings and other financial reports.

### Inheritance from Financial Statement

| financial_statement field | Budget mapping |
|--------------------------|----------------|
| `statement_entry_id` | `budget_event_id` (composite hash) |
| `legal_entity_id` | Municipality or entity that owns the budget |
| `account_id` | `ABS(HASH(account_code))` — links to chart of accounts |
| `period_end_date_id` | Dec 31 of fiscal year |
| `period_start_date_id` | Jan 1 of fiscal year |
| `report_type` | `'budget'` (vs `'annual'`, `'quarterly'` for actuals) |
| `amount` | Budgeted dollar amount |
| `reported_currency` | `'USD'` |

This means the shared measures from `financial_statement` (like `total_revenue_by_type`, `net_position`, `expense_ratio`) work on budget data too. Filter by `report_type` to compare actuals vs budgets for the same entity.

### Budget-vs-Actual Analysis

```sql
-- Compare budgeted vs actual revenue for Chicago
SELECT
    cal.year,
    fs.report_type,
    SUM(CASE WHEN coa.account_type = 'REVENUE' THEN fs.amount ELSE 0 END) as revenue
FROM _fact_financial_statements fs
JOIN _dim_chart_of_accounts coa ON fs.account_id = coa.account_id
JOIN temporal.dim_calendar cal ON fs.period_end_date_id = cal.date_id
WHERE fs.legal_entity_id = ABS(HASH(CONCAT('CITY_', 'Chicago')))
  AND fs.report_type IN ('annual', 'budget')
GROUP BY cal.year, fs.report_type
ORDER BY cal.year, fs.report_type;
```

### Event Types

| Type | Description | Source Example |
|------|-------------|---------------|
| APPROPRIATION | Authorized spending | Budget ordinance expenditures |
| REVENUE | Estimated income | Budget ordinance revenue |
| POSITION | Budgeted positions/salaries | Position and salary allocations |

### Usage

```yaml
extends: _base.accounting.financial_event
```
