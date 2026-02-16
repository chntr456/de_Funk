---
type: domain-model-source
source: payments
extends: _base.accounting.ledger_entry
maps_to: fact_ledger_entries
from: bronze.chicago_payments
entry_type: VENDOR_PAYMENT
domain_source: "'chicago'"
bronze_table: chicago/chicago_payments
description: "Vendor payments 1996-present"
update_frequency: daily

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

Chicago vendor payments. Data older than 2 years summarized by vendor/contract.
