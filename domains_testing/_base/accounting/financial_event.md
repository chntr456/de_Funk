---
type: domain-base
model: financial_event
version: 3.0
description: "Base for all financial occurrences — any event involving money, an entity, and a date"
extends: _base._base_.event

depends_on: [temporal]

# CANONICAL FIELDS
# The universal financial event: something financial happened to an entity on a date.
# All accounting templates inherit these core fields.
# [field_name, type, nullable: bool, description: "meaning"]
canonical_fields:
  - [event_id, integer, nullable: false, description: "Primary key"]
  - [legal_entity_id, integer, nullable: false, description: "FK to entity involved"]
  - [date_id, integer, nullable: false, description: "FK to temporal.dim_calendar"]
  - [amount, "decimal(18,2)", nullable: false, description: "Monetary value"]
  - [event_type, string, nullable: false, description: "Event classification (PAYMENT, BUDGET, STATEMENT, etc.)"]
  - [reported_currency, string, nullable: true, description: "Currency (USD, EUR, etc.)"]

tables:
  # Generic financial event fact (used directly by simple event models)
  _fact_financial_events:
    type: fact
    primary_key: [event_id]
    partition_by: [date_id]

    # [column, type, nullable, description, {options}]
    schema:
      - [event_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT(event_type, '_', source_id)))"}]
      - [legal_entity_id, integer, false, "FK to entity"]
      - [date_id, integer, false, "FK to calendar", {fk: temporal.dim_calendar.date_id}]
      - [amount, "decimal(18,2)", false, "Monetary value"]
      - [event_type, string, false, "Event classification"]
      - [reported_currency, string, true, "Currency", {default: "'USD'"}]

    measures:
      - [total_amount, sum, amount, "Total amount", {format: "$#,##0.00"}]
      - [event_count, count_distinct, event_id, "Number of events", {format: "#,##0"}]
      - [avg_amount, avg, amount, "Average event amount", {format: "$#,##0.00"}]
      - [entity_count, count_distinct, legal_entity_id, "Entities involved", {format: "#,##0"}]

    python_measures:
      net_present_value:
        function: "accounting.measures.calculate_npv"
        description: "NPV of cash flows discounted to earliest date"
        params:
          discount_rate: 0.05
          amount_col: "amount"
          date_col: "date_id"
        returns: [legal_entity_id, event_type, npv]

      spending_velocity:
        function: "accounting.measures.calculate_spending_velocity"
        description: "Rolling spend rate — trailing 30/90/365-day totals and trend"
        params:
          amount_col: "amount"
          date_col: "date_id"
          windows: [30, 90, 365]
          partition_cols: [legal_entity_id, event_type]
        returns: [legal_entity_id, event_type, date_id, spend_30d, spend_90d, spend_365d, trend]

  # Budget-specific fact table (for models that extend with budget semantics)
  _fact_budget_events:
    type: fact
    primary_key: [budget_event_id]
    partition_by: [fiscal_year]

    # [column, type, nullable, description, {options}]
    schema:
      - [budget_event_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT(event_type, '_', fiscal_year, '_', COALESCE(department_code,''), '_', COALESCE(account_code,''))))"}]
      - [legal_entity_id, integer, false, "FK to owning entity"]
      - [account_id, integer, false, "FK to chart of accounts", {derived: "ABS(HASH(COALESCE(account_code, 'UNCLASSIFIED')))", fk: "_dim_chart_of_accounts.account_id"}]
      - [period_end_date_id, integer, false, "FK to calendar (Dec 31)", {fk: temporal.dim_calendar.date_id, derived: "CAST(CONCAT(fiscal_year, '1231') AS INT)"}]
      - [period_start_date_id, integer, true, "FK to calendar (Jan 1)", {fk: temporal.dim_calendar.date_id, derived: "CAST(CONCAT(fiscal_year, '0101') AS INT)"}]
      - [report_type, string, false, "'budget'", {default: "'budget'"}]
      - [amount, "decimal(18,2)", false, "Budgeted amount"]
      - [reported_currency, string, true, "Currency", {default: "'USD'"}]
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
    - [event_to_calendar, _fact_financial_events, temporal.dim_calendar, [date_id=date_id], many_to_one, temporal]
    - [budget_to_calendar, _fact_budget_events, temporal.dim_calendar, [period_end_date_id=date_id], many_to_one, temporal]

federation:
  enabled: true
  union_key: domain_source
  primary_key: budget_event_id

domain: accounting
tags: [base, template, accounting, financial_event, budget]
status: active
---

## Financial Event Base Template

The root of the accounting hierarchy. A financial event is any occurrence involving money, an entity, and a date. All accounting templates inherit from this.

### Inheritance Chain

```
_base._base_.event
└── _base.accounting.financial_event       ← YOU ARE HERE (NPV, spending_velocity defined)
    └── _base.accounting.ledger_entry      ← adds payee, categorization, source tracking
        └── _base.accounting.financial_statement  ← adds account structure, report periods
```

### Real-World Flow

1. **Financial event occurs** — money moves, a budget is allocated, a statement is filed
2. **Gets recorded as a ledger entry** — categorized with payee, department, expense type
3. **Entries aggregate into financial statements** — periodic summaries by chart of accounts

### Python Measures (Inherited by ALL Accounting Templates)

| Measure | Description | Defined Here |
|---------|-------------|:---:|
| `net_present_value` | NPV of cash flows discounted to earliest date | **yes** |
| `spending_velocity` | Rolling 30/90/365-day spend rate with trend | **yes** |

These are the foundational financial measures. `ledger_entry` and `financial_statement` inherit them and override column params to match their schemas.

### Provided Tables

| Table | Purpose | Used By |
|-------|---------|---------|
| `_fact_financial_events` | Generic event rows (amount + date + entity) | Simple event models |
| `_fact_budget_events` | Budget appropriations, revenue, positions | Municipal budget models |

### Budget Event Types

| Type | Description | Source Example |
|------|-------------|---------------|
| APPROPRIATION | Authorized spending | Budget ordinance expenditures |
| REVENUE | Estimated income | Budget ordinance revenue |
| POSITION | Budgeted positions/salaries | Position and salary allocations |

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

### Usage

```yaml
extends: _base.accounting.financial_event
```
