---
type: domain-model-source
source: splits
extends: _base.finance.corporate_action
maps_to: _fact_splits
from: bronze.alpha_vantage_splits

aliases:
  - [action_id, TBD]
  - [security_id, "ABS(HASH(symbol))"]
  - [ticker, symbol]
  - [action_type, "'SPLIT'"]
  - [effective_date, effective_date]
  - [effective_date_id, "CAST(REGEXP_REPLACE(CAST(effective_date AS STRING), '-', '') AS INT)"]
  - [split_factor, split_coefficient]
---

## Splits
Historical stock splits with effective date and split ratio.
