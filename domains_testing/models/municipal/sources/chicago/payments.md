---
type: domain-model-source
source: payments
maps_to: fact_ledger_entries
from: bronze.payments
entry_type: VENDOR_PAYMENT
domain_source: "'chicago'"

# [canonical_field, source_expression]
aliases:
  - [source_id, voucher_number]
  - [payee, vendor_name]
  - [transaction_amount, amount]
  - [transaction_date, check_date]
  - [organizational_unit, department]
  - [expense_category, "null"]
  - [fund_code, "null"]
  - [contract_number, contract_number]
  - [description, description]
---

## Payments Source

Chicago vendor payments (1996-present) from the Vendor, Contract, and Payment Search dataset.

### Source Schema

| Column | Type | Description |
|--------|------|-------------|
| voucher_number | string | Payment voucher identifier |
| vendor_name | string | Receiving vendor |
| amount | decimal | Payment amount |
| check_date | date | Check/payment date |
| department | string | City department |
| contract_number | string | Related contract (nullable) |
| description | string | Payment description |

### Data Notes

- Payments from 1996-2002 are rolled up and appear as "2002"
- Data older than 2 years is summarized by vendor and contract
- Updated daily
