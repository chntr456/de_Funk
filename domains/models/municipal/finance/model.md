---
type: domain-model
model: municipal_finance
version: 3.1
description: "Municipal payments, contracts, and budget data"

extends:
  - _base.accounting.ledger_entry
  - _base.accounting.financial_statement
  - _base.accounting.fund
  - _base.accounting.chart_of_accounts
  - _base.property.tax_district

depends_on: [temporal, municipal_entity, county_property]

storage:
  format: delta
  sources_from: sources/{entity}/
  silver:
    root: storage/silver/municipal/{entity}/finance/

graph:
  edges:
    # [edge_name, from, to, on, type, cross_model]
    # auto_edges inherited: date_id→calendar (ledger_entries, property_tax)

    # Ledger → dimensions
    - [entry_to_vendor, fact_ledger_entries, dim_vendor, [vendor_id=vendor_id], many_to_one, null]
    - [entry_to_department, fact_ledger_entries, dim_department, [department_id=org_unit_id], many_to_one, null]
    - [entry_to_contract, fact_ledger_entries, dim_contract, [contract_id=contract_id], many_to_one, null, optional: true]
    - [entry_to_account, fact_ledger_entries, dim_chart_of_accounts, [account_id=account_id], many_to_one, null]

    # Budget → dimensions (budget extends financial_statement: account_id, period dates)
    - [budget_to_calendar, fact_budget_events, temporal.dim_calendar, [period_end_date_id=date_id], many_to_one, temporal]
    - [budget_to_department, fact_budget_events, dim_department, [department_id=org_unit_id], many_to_one, null]
    - [budget_to_fund, fact_budget_events, dim_fund, [fund_id=fund_id], many_to_one, null]
    - [budget_to_account, fact_budget_events, dim_chart_of_accounts, [account_id=account_id], many_to_one, null]

    # Entity → municipality (cross-model to municipal_entity)
    - [entry_to_municipality, fact_ledger_entries, municipal_entity.dim_municipality, [legal_entity_id=municipality_id], many_to_one, municipal_entity]
    - [budget_to_municipality, fact_budget_events, municipal_entity.dim_municipality, [legal_entity_id=municipality_id], many_to_one, municipal_entity]

    # Dimension → dimension
    - [contract_to_vendor, dim_contract, dim_vendor, [vendor_id=vendor_id], many_to_one, null]
    - [contract_to_department, dim_contract, dim_department, [department_id=org_unit_id], many_to_one, null]

    # Property tax → county property
    - [property_tax_to_parcel, fact_property_tax, county_property.dim_parcel, [parcel_id=parcel_id], many_to_one, county_property]
    - [property_tax_to_tax_district, fact_property_tax, dim_tax_district, [tax_district_id=tax_district_id], many_to_one, null]

  paths:
    payment_to_contract_vendor:
      description: "Drill from payment → contract → vendor"
      steps:
        - {from: fact_ledger_entries, to: dim_contract, via: contract_id}
        - {from: dim_contract, to: dim_vendor, via: vendor_id}
    budget_to_account_fund:
      description: "Budget line item → account classification + fund"
      steps:
        - {from: fact_budget_events, to: dim_chart_of_accounts, via: account_id}
        - {from: fact_budget_events, to: dim_fund, via: fund_id}
    property_tax_chain:
      description: "Property tax → parcel → tax district"
      steps:
        - {from: fact_property_tax, to: county_property.dim_parcel, via: parcel_id}
        - {from: fact_property_tax, to: dim_tax_district, via: tax_district_id}

build:
  partitions: [date_id]
  optimize: true
  phases:
    1:
      description: "Build fact tables from source unions"
      tables: [fact_ledger_entries, fact_budget_events, fact_property_tax]
      persist: true
    2:
      description: "Build dimensions from facts (+ bronze for dim_contract)"
      tables: [dim_vendor, dim_department, dim_contract, dim_fund, dim_chart_of_accounts, dim_tax_district]
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
    - [budget_line_count, count_distinct, fact_budget_events.statement_entry_id, "Budget line items", {format: "#,##0"}]
    - [department_count, count_distinct, dim_department.org_unit_id, "City departments", {format: "#,##0"}]
    - [contract_count, count_distinct, dim_contract.contract_id, "Total contracts", {format: "#,##0"}]

  computed:
    # [name, expression_type, SQL, description, {options}]
    - [payments_per_vendor, expression, "SUM(fact_ledger_entries.transaction_amount) / NULLIF(COUNT(DISTINCT dim_vendor.vendor_id), 0)", "Average payments per vendor", {format: "$#,##0.00"}]
    - [budget_surplus, expression, "SUM(CASE WHEN fact_budget_events.event_type = 'REVENUE' THEN fact_budget_events.amount ELSE 0 END) - SUM(CASE WHEN fact_budget_events.event_type = 'APPROPRIATION' THEN fact_budget_events.amount ELSE 0 END)", "Revenue minus appropriations", {format: "$#,##0.00"}]
    - [vendor_payment_pct, expression, "SUM(CASE WHEN fact_ledger_entries.entry_type = 'VENDOR_PAYMENT' THEN fact_ledger_entries.transaction_amount ELSE 0 END) / NULLIF(SUM(fact_ledger_entries.transaction_amount), 0)", "Vendor payments as % of total", {format: "0.00%"}]

federation:
  enabled: true
  union_key: domain_source

metadata:
  domain: municipal
  subdomain: finance
status: active
---

## Municipal Finance Model

Payments, contracts, and budget data. Extends accounting base templates for federation with other municipal and corporate ledger models. Entity sources in `sources/{entity}/` provide column aliases from bronze to canonical schema.

### Architecture

```
sources/                        tables/
  payments.md ─────────┐
  contracts.md ────────┤──→ fact_ledger_entries.md ──→ dim_vendor.md (enrich)
                       │                           ──→ dim_department.md (enrich)
  budget_approp.md ────┤                           ──→ dim_contract.md (enrich)
  budget_revenue.md ───┤──→ fact_budget_events.md  ──→ dim_fund.md
  budget_positions.md ─┘    (extends fin_stmt)     ──→ dim_chart_of_accounts.md
```

### Budget-vs-Actual

Budget line items flow through `fact_budget_events` which extends the `_fact_financial_statements` base with `report_type = 'budget'`. This enables direct comparison:

```sql
-- Same chart of accounts, same entity, different report_type
SELECT report_type, coa.account_type, SUM(amount)
FROM fact_budget_events be
JOIN dim_chart_of_accounts coa ON be.account_id = coa.account_id
WHERE be.legal_entity_id = dim_municipality.municipality_id
GROUP BY report_type, coa.account_type;
```

### Entity

The `dim_municipality` dimension lives in `municipal_entity` (separate entity model). All fact tables FK to it via `legal_entity_id`. This model declares `depends_on: [municipal_entity]` to ensure the entity dimension is built first.
