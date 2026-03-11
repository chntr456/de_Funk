---
type: domain-model-source
source: contracts
extends: _base.accounting.ledger_entry
maps_to: fact_ledger_entries
from: bronze.chicago_contracts
entry_type: CONTRACT
domain_source: "'chicago'"
aliases:
  - [legal_entity_id, "ABS(HASH(CONCAT('CITY_', 'Chicago')))"]
  - [entry_id, "ABS(HASH(CONCAT('CONTRACT', '_', contract_number)))"]
  - [date_id, "CAST(DATE_FORMAT(start_date, 'yyyyMMdd') AS INT)"]
  - [source_id, contract_number]
  - [payee, vendor_name]
  - [transaction_amount, award_amount]
  - [transaction_date, start_date]
  - [organizational_unit, department]
  - [expense_category, procurement_type]
  - [fund_code, "null"]
  - [contract_number, contract_number]
  - [description, description]
  - [account_code, "CONCAT('ACTUAL_', COALESCE(department, 'UNCLASSIFIED'))"]
  - [account_id, "ABS(HASH(CONCAT('ACTUAL_', COALESCE(department, 'UNCLASSIFIED'))))"]
---

## Contracts Source

Chicago city contracts with award amounts and vendor info.
