---
type: domain-model-source
source: dividends
extends: _base.finance.securities
maps_to: fact_dividends
from: bronze.alpha_vantage_dividends

aliases:
  - [ticker, symbol]
  - [ex_dividend_date, ex_dividend_date]
  - [ex_dividend_date_id, "CAST(REGEXP_REPLACE(CAST(ex_dividend_date AS STRING), '-', '') AS INT)"]
  - [dividend_amount, amount]
  - [record_date, record_date]
  - [payment_date, payment_date]
  - [declaration_date, declaration_date]
  - [dividend_type, TBD]
---

## Dividends
Historical dividend payments including ex-date, payment date, and amount.
