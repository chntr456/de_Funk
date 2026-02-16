---
type: domain-model-source
source: contracts
maps_to: fact_ledger_entries
from: bronze.contracts
entry_type: CONTRACT
domain_source: "'chicago'"

# [canonical_field, source_expression]
aliases:
  - [source_id, contract_number]
  - [payee, vendor_name]
  - [transaction_amount, award_amount]
  - [transaction_date, start_date]
  - [organizational_unit, department]
  - [expense_category, procurement_type]
  - [fund_code, "null"]
  - [contract_number, contract_number]
  - [description, description]
---

## Contracts Source

Chicago city contracts with award amounts and terms.

### Source Schema

| Column | Type | Description |
|--------|------|-------------|
| contract_number | string | Contract identifier |
| specification_number | string | Specification reference |
| vendor_name | string | Contracted vendor |
| description | string | Contract description |
| award_amount | decimal | Contract award value |
| start_date | date | Contract start |
| end_date | date | Contract end |
| procurement_type | string | Procurement method |
| department | string | Awarding department |

### Mapping Notes

- `transaction_amount` maps to `award_amount` (the committed value, not payments)
- `transaction_date` maps to `start_date` (contract inception)
- `expense_category` maps to `procurement_type` (how the contract was procured)
- Contract-specific columns (specification_number, end_date, procurement_type) are available in `dim_contract` which reads directly from bronze
