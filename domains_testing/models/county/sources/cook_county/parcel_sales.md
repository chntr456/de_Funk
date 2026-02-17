---
type: domain-model-source
source: parcel_sales
extends: _base.property.parcel
maps_to: fact_parcel_sales
from: bronze.cook_county_parcel_sales

aliases:
  - [legal_entity_id, "ABS(HASH(CONCAT('COUNTY_', 'Cook County')))"]
  - [domain_source, "'cook_county'"]
  - [parcel_id, "LPAD(REGEXP_REPLACE(pin, '[^0-9]', ''), 14, '0')"]
  - [sale_date, sale_date]
  - [sale_date_id, "CAST(DATE_FORMAT(sale_date, 'yyyyMMdd') AS INT)"]
  - [year, "YEAR(sale_date)"]
  - [sale_price, sale_price]
  - [sale_type, sale_type]
---

## Parcel Sales
Property sales transactions with sale price, date, and type for all Cook County parcels.
