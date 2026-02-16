---
type: domain-model-table
table: dim_stock
table_type: dimension
from: bronze.alpha_vantage.listing_status
primary_key: [stock_id]
unique_key: [ticker]

schema:
  - [stock_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT('STOCK_', ticker)))"}]
  - [security_id, integer, false, "FK to securities.dim_security", {fk: securities_master.dim_security.security_id, derived: "ABS(HASH(ticker))"}]
  - [company_id, integer, true, "FK to dim_company", {fk: company.dim_company.company_id, derived: "ABS(HASH(CONCAT('COMPANY_', ticker)))"}]
  - [ticker, string, false, "Trading symbol"]
  - [security_name, string, true, "Security name"]
  - [exchange_code, string, true, "Exchange code"]
  - [asset_type, string, true, "Asset type"]
  - [stock_type, string, true, "Stock type", {enum: [common, preferred, adr, rights, units, warrants], derived: "'common'"}]

measures:
  - [stock_count, count_distinct, stock_id, "Number of stocks", {format: "#,##0"}]
---

## Stock Dimension

Stock equities filtered from listing_status (asset_type = 'stocks').
