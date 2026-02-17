---
type: domain-model-table
table: dim_company
extends: _base.entity.legal._dim_legal_entity
table_type: dimension
primary_key: [company_id]
unique_key: [ticker]

schema:
  - [company_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT('COMPANY_', ticker)))"}]
  - [cik, string, true, "SEC Central Index Key"]
  - [ticker, string, false, "Primary ticker symbol"]
  - [company_name, string, false, "Company name"]
  - [description, string, true, "Company description"]
  - [asset_type, string, true, "Asset type"]
  - [exchange_code, string, true, "Primary exchange"]
  - [sector, string, true, "GICS Sector"]
  - [industry, string, true, "GICS Industry"]
  - [country, string, true, "Country", {default: "US"}]
  - [currency, string, true, "Reporting currency", {default: "USD"}]
  - [address, string, true, "Headquarters address"]
  - [official_site, string, true, "Website URL"]
  - [fiscal_year_end, string, true, "Fiscal year end month"]
  - [is_active, boolean, true, "Active", {default: true}]

measures:
  - [company_count, count_distinct, company_id, "Number of companies", {format: "#,##0"}]
---

## Company Dimension

Corporate entity master from COMPANY_OVERVIEW. CIK-based for SEC filing linkage.
