---
type: domain-model-source
source: company_overview
extends: _base.entity.company
maps_to: dim_company
from: bronze.alpha_vantage_company_overview

aliases:
  - [company_id, "ABS(HASH(CONCAT('COMPANY_', Symbol)))"]
  - [ticker, Symbol]
  - [company_name, Name]
  - [cik, CIK]
  - [asset_type, AssetType]
  - [exchange_code, Exchange]
  - [sector, Sector]
  - [industry, Industry]
  - [country, Country]
  - [currency, Currency]
  - [address, Address]
  - [official_site, TBD]
  - [fiscal_year_end, FiscalYearEnd]
  - [is_active, "true"]
---

## Company Overview
Company reference data: name, sector, industry, exchange, CIK for SEC linkage.
