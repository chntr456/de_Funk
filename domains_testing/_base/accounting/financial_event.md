---
type: domain-base
model: financial_event
version: 1.0
description: "Budget events - appropriations, revenue estimates, position allocations"
extends: _base._base_.event

# CANONICAL FIELDS
# [field_name, type, nullable: bool, description: "meaning"]
canonical_fields:
  - [budget_event_id, integer, nullable: false, description: "Primary key"]
  - [date_id, integer, nullable: false, description: "FK to temporal.dim_calendar"]
  - [fiscal_year, integer, nullable: false, description: "Budget fiscal year"]
  - [event_type, string, nullable: false, description: "APPROPRIATION, REVENUE, POSITION"]
  - [domain_source, string, nullable: false, description: "Origin domain"]
  - [department_code, string, nullable: true, description: "Department code (null if n/a)"]
  - [department_description, string, nullable: true, description: "Department name (null if n/a)"]
  - [fund_code, string, nullable: true, description: "Fund code"]
  - [fund_description, string, nullable: true, description: "Fund name"]
  - [account_code, string, nullable: true, description: "Account/appropriation code"]
  - [account_description, string, nullable: true, description: "Account name"]
  - [amount, "decimal(18,2)", nullable: false, description: "Budgeted amount"]
  - [description, string, nullable: true, description: "Line-item description"]

tables:
  _fact_budget_events:
    type: fact
    primary_key: [budget_event_id]
    partition_by: [fiscal_year]

    # [column, type, nullable, description, {options}]
    schema:
      - [budget_event_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT(event_type, '_', fiscal_year, '_', COALESCE(department_code,''), '_', COALESCE(account_code,''))))"}]
      - [date_id, integer, false, "FK to calendar (Jan 1 of fiscal year)", {fk: temporal.dim_calendar.date_id, derived: "CAST(CONCAT(fiscal_year, '0101') AS INT)"}]
      - [fiscal_year, integer, false, "Budget year"]
      - [event_type, string, false, "APPROPRIATION, REVENUE, POSITION"]
      - [domain_source, string, false, "Origin domain"]
      - [department_code, string, true, "Department code"]
      - [department_description, string, true, "Department name"]
      - [fund_code, string, true, "Fund code"]
      - [fund_description, string, true, "Fund name"]
      - [account_code, string, true, "Appropriation/revenue account code"]
      - [account_description, string, true, "Account name"]
      - [amount, "decimal(18,2)", false, "Budgeted amount"]
      - [description, string, true, "Line-item description"]

    measures:
      - [total_budget, sum, amount, "Total budgeted amount", {format: "$#,##0.00"}]
      - [line_item_count, count_distinct, budget_event_id, "Budget line items", {format: "#,##0"}]
      - [appropriation_total, expression, "SUM(CASE WHEN event_type = 'APPROPRIATION' THEN amount ELSE 0 END)", "Total appropriations", {format: "$#,##0.00"}]
      - [revenue_total, expression, "SUM(CASE WHEN event_type = 'REVENUE' THEN amount ELSE 0 END)", "Total revenue", {format: "$#,##0.00"}]
      - [position_total, expression, "SUM(CASE WHEN event_type = 'POSITION' THEN amount ELSE 0 END)", "Total position salaries", {format: "$#,##0.00"}]
      - [budget_surplus, expression, "SUM(CASE WHEN event_type = 'REVENUE' THEN amount ELSE 0 END) - SUM(CASE WHEN event_type = 'APPROPRIATION' THEN amount ELSE 0 END)", "Revenue minus appropriations", {format: "$#,##0.00"}]

graph:
  edges:
    # [edge_name, from, to, on, type, cross_model]
    - [budget_to_calendar, _fact_budget_events, temporal.dim_calendar, [date_id=date_id], many_to_one, temporal]

federation:
  enabled: true
  union_key: domain_source
  primary_key: budget_event_id

domain: accounting
tags: [base, template, accounting, budget]
status: active
---

## Financial Event Base Template

Budget and fiscal planning events. Supports multi-source unions across appropriations, revenue estimates, and position allocations.

### Event Types

| Type | Description | Source Example |
|------|-------------|---------------|
| APPROPRIATION | Authorized spending | Budget ordinance expenditures |
| REVENUE | Estimated income | Budget ordinance revenue |
| POSITION | Budgeted positions/salaries | Position and salary allocations |

### Budget Analysis

Federation enables cross-domain budget comparison:

```sql
-- Revenue vs Appropriations by year
SELECT fiscal_year,
    SUM(CASE WHEN event_type = 'REVENUE' THEN amount ELSE 0 END) as revenue,
    SUM(CASE WHEN event_type = 'APPROPRIATION' THEN amount ELSE 0 END) as appropriations
FROM accounting.v_all_budget_events
GROUP BY fiscal_year
ORDER BY fiscal_year;
```

### Usage

```yaml
extends: _base.accounting.financial_event
```
