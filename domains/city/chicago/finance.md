---
type: domain-model
model: chicago_finance
version: 1.0
description: "Chicago payments, contracts, and budget data"


# Dependencies
depends_on:
  - foundation_temporal

# Storage
storage:
  root: storage/silver/chicago/finance
  format: delta

# Build
build:
  partitions: [year]
  optimize: true

# Sources
sources:
  payments:
    bronze_table: chicago_payments
    description: "Vendor payments 1996-present"

  contracts:
    bronze_table: chicago_contracts
    description: "City contracts"

  budget_revenue:
    bronze_table: chicago_budget_revenue
    description: "Budget ordinance - revenue"

  budget_appropriations:
    bronze_table: chicago_budget_appropriations
    description: "Budget ordinance - appropriations"

  budget_positions:
    bronze_table: chicago_budget_positions
    description: "Budget ordinance - positions and salaries"

# Schema
schema:
  dimensions:
    dim_vendor:
      description: "Vendor dimension"
      primary_key: [vendor_id]
      columns:
        vendor_id: {type: string, required: true}
        vendor_name: {type: string, description: "Vendor name"}
        first_payment_date: {type: date, description: "First payment received"}
        last_payment_date: {type: date, description: "Most recent payment"}
        total_payments: {type: double, description: "Lifetime payment total"}

    dim_department:
      description: "City department dimension"
      primary_key: [department_id]
      columns:
        department_id: {type: string, required: true}
        department_name: {type: string, description: "Department name"}

    dim_contract:
      description: "Contract dimension"
      primary_key: [contract_number]
      columns:
        contract_number: {type: string, required: true}
        contract_description: {type: string}
        department_id: {type: string}
        start_date: {type: date}
        end_date: {type: date}
        total_amount: {type: double}

  facts:
    fact_payments:
      description: "Vendor payments fact table"
      primary_key: [voucher_number]
      columns:
        voucher_number: {type: string, required: true}
        vendor_id: {type: string, description: "FK to dim_vendor"}
        contract_number: {type: string, description: "FK to dim_contract"}
        department_id: {type: string, description: "FK to dim_department"}
        amount: {type: double, description: "Payment amount"}
        check_date: {type: date, description: "Payment date"}
        year: {type: int, description: "Payment year"}
        description: {type: string, description: "Payment description"}

    fact_budget:
      description: "Budget fact table"
      primary_key: [budget_id]
      columns:
        budget_id: {type: string, required: true}
        budget_year: {type: int, description: "Fiscal year"}
        department_id: {type: string}
        fund_type: {type: string, description: "Fund type (General, Special, etc.)"}
        budget_type: {type: string, description: "Revenue or Appropriation"}
        amount: {type: double, description: "Budget amount"}

# Graph
graph:
  nodes:
    dim_vendor:
      from: bronze.chicago_payments
      type: dimension
      transform: aggregate
      group_by: [vendor_name]
      derive:
        vendor_id: "MD5(COALESCE(vendor_name, 'UNKNOWN'))"
        first_payment_date: "MIN(check_date)"
        last_payment_date: "MAX(check_date)"
        total_payments: "SUM(amount)"
      unique_key: [vendor_id]

    dim_department:
      from: bronze.chicago_payments
      type: dimension
      transform: distinct
      columns: [department]
      derive:
        department_id: "MD5(COALESCE(department, 'UNKNOWN'))"
        department_name: department
      unique_key: [department_id]

    dim_contract:
      from: bronze.chicago_contracts
      type: dimension
      unique_key: [contract_number]

    fact_payments:
      from: bronze.chicago_payments
      type: fact
      derive:
        vendor_id: "MD5(COALESCE(vendor_name, 'UNKNOWN'))"
        department_id: "MD5(COALESCE(department, 'UNKNOWN'))"
      unique_key: [voucher_number]

  edges:
    payment_to_vendor:
      from: fact_payments
      to: dim_vendor
      on: [vendor_id=vendor_id]
      type: many_to_one

    payment_to_department:
      from: fact_payments
      to: dim_department
      on: [department_id=department_id]
      type: many_to_one

    payment_to_contract:
      from: fact_payments
      to: dim_contract
      on: [contract_number=contract_number]
      type: many_to_one

# Measures
measures:
  simple:
    total_payments:
      description: "Total payment amount"
      source: fact_payments.amount
      aggregation: sum
      format: "$#,##0"

    payment_count:
      description: "Number of payments"
      source: fact_payments.voucher_number
      aggregation: count
      format: "#,##0"

    vendor_count:
      description: "Number of unique vendors"
      source: dim_vendor.vendor_id
      aggregation: count_distinct
      format: "#,##0"

    avg_payment:
      description: "Average payment amount"
      source: fact_payments.amount
      aggregation: avg
      format: "$#,##0.00"

  computed:
    payments_per_vendor:
      description: "Average payments per vendor"
      formula: "total_payments / vendor_count"
      format: "$#,##0"

# Metadata
metadata:
  domain: city
  entity: chicago
  subdomain: finance
status: active
---

## Chicago Finance Model

Payments, contracts, and budget data for the City of Chicago.

### Data Sources

| Source | Bronze Table | Description |
|--------|--------------|-------------|
| Payments | chicago_payments | Vendor payments 1996-present |
| Contracts | chicago_contracts | City contracts |
| Budget Revenue | chicago_budget_revenue | Budget ordinance revenue |
| Budget Appropriations | chicago_budget_appropriations | Budget appropriations |
| Budget Positions | chicago_budget_positions | Positions and salaries |

### Data Notes

- Payments from 1996-2002 rolled up and appear as "2002"
- Data older than 2 years is summarized by vendor and contract
- Updated daily from Vendor, Contract, and Payment Search

### Vendor Analysis

```sql
-- Top vendors by total payments
SELECT
    v.vendor_name,
    SUM(p.amount) as total_payments,
    COUNT(*) as payment_count,
    MIN(p.check_date) as first_payment,
    MAX(p.check_date) as last_payment
FROM fact_payments p
JOIN dim_vendor v ON p.vendor_id = v.vendor_id
GROUP BY v.vendor_name
ORDER BY total_payments DESC
LIMIT 20;

-- Department spending by year
SELECT
    d.department_name,
    p.year,
    SUM(p.amount) as total_spending
FROM fact_payments p
JOIN dim_department d ON p.department_id = d.department_id
GROUP BY d.department_name, p.year
ORDER BY d.department_name, p.year;
```

### Budget Analysis

```sql
-- Revenue vs Appropriations by year
SELECT
    budget_year,
    SUM(CASE WHEN budget_type = 'Revenue' THEN amount ELSE 0 END) as revenue,
    SUM(CASE WHEN budget_type = 'Appropriation' THEN amount ELSE 0 END) as appropriations
FROM fact_budget
GROUP BY budget_year
ORDER BY budget_year;
```
