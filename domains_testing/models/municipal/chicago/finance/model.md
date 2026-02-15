---
type: domain-model
model: chicago_finance
version: 2.0
description: "Chicago payments, contracts, and budget data"

extends:
  - _base.accounting.ledger_entry
  - _base.accounting.financial_event
  - _base.entity.organizational_entity
  - _base.accounting.fund
  - _base.accounting.chart_of_accounts

depends_on: [temporal]

storage:
  format: delta
  bronze:
    provider: chicago
    # [local_name, provider/endpoint]
    tables:
      - [payments, chicago/chicago_payments]
      - [contracts, chicago/chicago_contracts]
      - [budget_appropriations, chicago/chicago_budget_appropriations]
      - [budget_revenue, chicago/chicago_budget_revenue]
      - [budget_positions, chicago/chicago_budget_positions]
  silver:
    root: storage/silver/chicago/finance/

graph:
  edges:
    # [edge_name, from, to, on, type, cross_model]

    # Ledger → dimensions
    - [entry_to_calendar, fact_ledger_entries, temporal.dim_calendar, [date_id=date_id], many_to_one, temporal]
    - [entry_to_vendor, fact_ledger_entries, dim_vendor, [vendor_id=vendor_id], many_to_one, null]
    - [entry_to_department, fact_ledger_entries, dim_department, [department_id=org_unit_id], many_to_one, null]
    - [entry_to_contract, fact_ledger_entries, dim_contract, [contract_id=contract_id], many_to_one, null]

    # Budget → dimensions
    - [budget_to_calendar, fact_budget_events, temporal.dim_calendar, [date_id=date_id], many_to_one, temporal]
    - [budget_to_department, fact_budget_events, dim_department, [department_id=org_unit_id], many_to_one, null]
    - [budget_to_fund, fact_budget_events, dim_fund, [fund_id=fund_id], many_to_one, null]
    - [budget_to_account, fact_budget_events, dim_chart_of_accounts, [chart_account_id=account_id], many_to_one, null]

    # Dimension → dimension
    - [contract_to_vendor, dim_contract, dim_vendor, [vendor_id=vendor_id], many_to_one, null]
    - [contract_to_department, dim_contract, dim_department, [department_id=org_unit_id], many_to_one, null]

build:
  partitions: [date_id]
  optimize: true
  phases:
    1:
      description: "Build fact tables from source unions"
      tables: [fact_ledger_entries, fact_budget_events]
      persist: true
    2:
      description: "Build dimensions from facts (+ bronze for dim_contract)"
      tables: [dim_vendor, dim_department, dim_contract, dim_fund, dim_chart_of_accounts]
      persist: true
      enrich: true

measures:
  simple:
    # [name, aggregation, column, description, {options}]
    - [total_payments, sum, fact_ledger_entries.transaction_amount, "Total payment amount", {format: "$#,##0.00"}]
    - [payment_count, count_distinct, fact_ledger_entries.entry_id, "Number of payments", {format: "#,##0"}]
    - [vendor_count, count_distinct, dim_vendor.vendor_id, "Unique vendors", {format: "#,##0"}]
    - [avg_payment, avg, fact_ledger_entries.transaction_amount, "Average payment", {format: "$#,##0.00"}]
    - [total_budget, sum, fact_budget_events.amount, "Total budget amount", {format: "$#,##0.00"}]
    - [budget_line_count, count_distinct, fact_budget_events.budget_event_id, "Budget line items", {format: "#,##0"}]
    - [department_count, count_distinct, dim_department.org_unit_id, "City departments", {format: "#,##0"}]
    - [contract_count, count_distinct, dim_contract.contract_id, "Total contracts", {format: "#,##0"}]

  computed:
    # [name, expression_type, SQL, description, {options}]
    - [payments_per_vendor, expression, "SUM(fact_ledger_entries.transaction_amount) / NULLIF(COUNT(DISTINCT dim_vendor.vendor_id), 0)", "Average payments per vendor", {format: "$#,##0.00"}]
    - [budget_surplus, expression, "SUM(CASE WHEN fact_budget_events.event_type = 'REVENUE' THEN fact_budget_events.amount ELSE 0 END) - SUM(CASE WHEN fact_budget_events.event_type = 'APPROPRIATION' THEN fact_budget_events.amount ELSE 0 END)", "Revenue minus appropriations", {format: "$#,##0.00"}]
    - [vendor_payment_pct, expression, "SUM(CASE WHEN fact_ledger_entries.entry_type = 'VENDOR_PAYMENT' THEN fact_ledger_entries.transaction_amount ELSE 0 END) / NULLIF(SUM(fact_ledger_entries.transaction_amount), 0)", "Vendor payments as % of total", {format: "0.00%"}]
    - [contract_pct, expression, "SUM(CASE WHEN fact_ledger_entries.entry_type = 'CONTRACT' THEN fact_ledger_entries.transaction_amount ELSE 0 END) / NULLIF(SUM(fact_ledger_entries.transaction_amount), 0)", "Contracts as % of total", {format: "0.00%"}]
    - [position_budget_pct, expression, "SUM(CASE WHEN fact_budget_events.event_type = 'POSITION' THEN fact_budget_events.amount ELSE 0 END) / NULLIF(SUM(CASE WHEN fact_budget_events.event_type = 'APPROPRIATION' THEN fact_budget_events.amount ELSE 0 END), 0)", "Personnel as % of appropriations", {format: "0.00%"}]

federation:
  enabled: true
  union_key: domain_source

metadata:
  domain: municipal
  entity: chicago
  subdomain: finance
status: active
---

## Chicago Finance Model

Payments, contracts, and budget data for the City of Chicago. Extends accounting base templates for federation with other municipal and corporate ledger models.

### Architecture

```
sources/                        tables/
  payments.md ─────────┐
  contracts.md ────────┤──→ fact_ledger_entries.md ──→ dim_vendor.md (enrich)
                       │                           ──→ dim_department.md (enrich)
  budget_approp.md ────┤                           ──→ dim_contract.md (enrich)
  budget_revenue.md ───┤──→ fact_budget_events.md ──→ dim_fund.md
  budget_positions.md ─┘                           ──→ dim_chart_of_accounts.md
```

### Build Order

1. **Facts first** — union sources, apply aliases, compute FK hashes
2. **Dimensions second** — aggregate from canonicalized facts (not raw bronze)
3. **Enrichment** — join facts back to dims for accrual metrics (budget-vs-actual, paid-vs-award)

### Federation

When other domain-models extend the same accounting bases (e.g., `cook_county_finance`, `corporate_finance`), federation views automatically union them:

```sql
SELECT domain_source, fiscal_year,
    SUM(CASE WHEN event_type = 'REVENUE' THEN amount ELSE 0 END) as revenue,
    SUM(CASE WHEN event_type = 'APPROPRIATION' THEN amount ELSE 0 END) as spending
FROM accounting.v_all_budget_events
GROUP BY domain_source, fiscal_year;
```
