---
type: domain-model-source
source: listing_status
extends: _base.finance.securities
maps_to: dim_security
from: bronze.alpha_vantage_listing_status

aliases:
  - [ticker, symbol]
  - [security_name, name]
  - [asset_type, assetType]
  - [exchange_code, exchange]
  - [currency, "'USD'"]
  - [is_active, "delistingDate IS NULL"]
  - [ipo_date, ipoDate]
  - [delisting_date, delistingDate]
---

## Listing Status
All active and delisted US securities (~12,499 tickers). Primary source for the securities master dimension.
