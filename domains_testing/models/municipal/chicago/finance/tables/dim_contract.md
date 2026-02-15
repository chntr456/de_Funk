---
type: domain-model-table
table: dim_contract
table_type: dimension
from: bronze.contracts
primary_key: [contract_id]
unique_key: [contract_number]

# Base columns from bronze (source-specific fields not in canonical ledger schema)
# [column, type, nullable, description, {options}]
schema:
  - [contract_id, integer, false, "PK", {derived: "ABS(HASH(contract_number))"}]
  - [contract_number, string, false, "Natural key"]
  - [specification_number, string, true, "Specification reference"]
  - [vendor_name, string, true, "Vendor on contract"]
  - [vendor_id, integer, true, "FK to dim_vendor", {fk: dim_vendor.vendor_id, derived: "ABS(HASH(COALESCE(vendor_name, 'UNKNOWN')))"}]
  - [description, string, true, "Contract description"]
  - [department, string, true, "Awarding department"]
  - [department_id, integer, true, "FK to dim_department", {fk: dim_department.org_unit_id, derived: "ABS(HASH(COALESCE(department, 'UNKNOWN')))"}]
  - [procurement_type, string, true, "Procurement method"]
  - [award_amount, "decimal(18,2)", true, "Contract award value"]
  - [start_date, date, true, "Contract start"]
  - [end_date, date, true, "Contract end"]
  - [is_active, boolean, false, "Currently active", {derived: "end_date >= CURRENT_DATE OR end_date IS NULL"}]

# Enrichment: payment accrual tracking (materialized at build time)
# Joins fact_ledger_entries back to this dimension to compute paid-vs-award metrics
enrich:
  - from: fact_ledger_entries
    join: [contract_id = contract_id]
    # [column, type, nullable, description, {options}]
    columns:
      - [total_paid, "decimal(18,2)", true, "Total payments against contract", {derived: "SUM(transaction_amount)"}]
      - [payment_count, integer, true, "Number of payments made", {derived: "COUNT(DISTINCT entry_id)"}]
      - [first_payment_date, date, true, "First payment date", {derived: "MIN(transaction_date)"}]
      - [last_payment_date, date, true, "Most recent payment", {derived: "MAX(transaction_date)"}]

  - derived:
      - [remaining_balance, "decimal(18,2)", true, "Award minus paid", {derived: "COALESCE(award_amount, 0) - COALESCE(total_paid, 0)"}]
      - [utilization_pct, "decimal(5,4)", true, "Percent of award utilized", {derived: "COALESCE(total_paid, 0) / NULLIF(award_amount, 0)"}]
      - [is_fully_paid, boolean, true, "All funds disbursed", {derived: "COALESCE(total_paid, 0) >= COALESCE(award_amount, 0) AND award_amount > 0"}]

measures:
  - [contract_count, count_distinct, contract_id, "Number of contracts", {format: "#,##0"}]
  - [total_award_amount, sum, award_amount, "Total award value", {format: "$#,##0.00"}]
  - [total_contract_paid, sum, total_paid, "Total paid against contracts", {format: "$#,##0.00"}]
  - [total_remaining, sum, remaining_balance, "Total remaining on contracts", {format: "$#,##0.00"}]
  - [avg_utilization, avg, utilization_pct, "Avg contract utilization", {format: "0.0%"}]
  - [fully_paid_count, expression, "SUM(CASE WHEN is_fully_paid THEN 1 ELSE 0 END)", "Fully paid contracts", {format: "#,##0"}]
---

## Contract Dimension

Sourced from **bronze.contracts** (exception to the "dimensions from facts" pattern — contract-specific columns like `specification_number`, `procurement_type`, `start_date`, `end_date` are not in the canonical ledger schema).

### Accrual Enrichment

Each contract is enriched with payment tracking from `fact_ledger_entries`:

| Column | Source | Meaning |
|--------|--------|---------|
| total_paid | fact_ledger_entries | Sum of all payments referencing this contract |
| payment_count | fact_ledger_entries | How many payment transactions |
| remaining_balance | derived | award_amount - total_paid |
| utilization_pct | derived | What fraction of the award has been paid out |
| is_fully_paid | derived | Whether all contracted funds have been disbursed |

### Example Query

```sql
-- Contracts with significant remaining balance
SELECT contract_number, vendor_name, award_amount, total_paid,
       remaining_balance, utilization_pct
FROM dim_contract
WHERE remaining_balance > 100000
  AND is_active = true
ORDER BY remaining_balance DESC;
```
