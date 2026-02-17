---
type: domain-model-source
source: company_overview
extends: _base.entity.legal
maps_to: dim_company
from: bronze.alpha_vantage_company_overview

aliases:
  - [ticker, Symbol]
  - [company_name, Name]
  - [description, Description]
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
---

## Company Overview
Company reference data: name, sector, industry, exchange, market cap, shares outstanding, CIK for SEC linkage.
