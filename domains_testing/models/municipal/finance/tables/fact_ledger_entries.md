---
type: domain-model-table
table: fact_ledger_entries
extends: _base.accounting.ledger_entry._fact_ledger_entries
table_type: fact
primary_key: [entry_id]
partition_by: [date_id]
persist: true

# Sources auto-discovered: any sources/*.md with maps_to: fact_ledger_entries
# Currently: payments (VENDOR_PAYMENT) + contracts (CONTRACT)

# Additional FK columns beyond base schema
# [column, type, nullable, description, {options}]
additional_schema:
  - [vendor_id, integer, true, "FK to dim_vendor", {fk: dim_vendor.vendor_id, derived: "ABS(HASH(COALESCE(payee, 'UNKNOWN')))"}]
  - [department_id, integer, true, "FK to dim_department", {fk: dim_department.org_unit_id, derived: "ABS(HASH(COALESCE(organizational_unit, 'UNKNOWN')))"}]
  - [contract_id, integer, true, "FK to dim_contract", {fk: dim_contract.contract_id, derived: "CASE WHEN contract_number IS NOT NULL THEN ABS(HASH(contract_number)) ELSE null END"}]
---

## Ledger Entries Fact

Extends `_base.accounting.ledger_entry._fact_ledger_entries`. Sources are auto-discovered from `sources/*.md` where `maps_to: fact_ledger_entries`.

### Inherited Schema (from base)

| Column | Type | Description |
|--------|------|-------------|
| entry_id | integer | PK (hash of entry_type + source_id) |
| date_id | integer | FK to temporal.dim_calendar |
| entry_type | string | VENDOR_PAYMENT, CONTRACT |
| domain_source | string | 'chicago' |
| source_id | string | voucher_number or contract_number |
| payee | string | Vendor name |
| transaction_amount | decimal(18,2) | Payment or award amount |
| transaction_date | date | Check date or contract start |
| organizational_unit | string | Department (nullable) |
| expense_category | string | Procurement type (nullable) |
| fund_code | string | null (not in these sources) |
| contract_number | string | Contract reference (nullable) |
| description | string | Transaction description |

### Additional FK Columns (this model)

| Column | Derived From | Target |
|--------|-------------|--------|
| vendor_id | HASH(payee) | dim_vendor.vendor_id |
| department_id | HASH(organizational_unit) | dim_department.org_unit_id |
| contract_id | HASH(contract_number) | dim_contract.contract_id |
