---
type: domain-model-table
table: fact_property_tax
extends: _base.accounting.ledger_entry._fact_ledger_entries
table_type: fact
primary_key: [entry_id]
partition_by: [tax_year]

additional_schema:
  - [parcel_id, string, true, "FK to county property dim_parcel", {fk: county_property.dim_parcel.parcel_id}]
  - [tax_year, integer, false, "Tax levy year"]
  - [assessed_value, "decimal(18,2)", true, "Assessed value at time of levy"]
  - [tax_rate, "decimal(10,6)", true, "Effective tax rate"]
  - [tax_district_id, integer, true, "FK to dim_tax_district", {fk: dim_tax_district.tax_district_id, derived: "ABS(HASH(tax_code))"}]

measures:
  - [total_property_tax, sum, transaction_amount, "Total property tax collected", {format: "$#,##0"}]
  - [avg_tax_per_parcel, expression, "SUM(transaction_amount) / NULLIF(COUNT(DISTINCT parcel_id), 0)", "Average tax per parcel", {format: "$#,##0"}]
  - [tax_entry_count, count_distinct, entry_id, "Number of tax entries", {format: "#,##0"}]
---

## Property Tax Fact Table

Property tax ledger entries. Each row is a tax payment for one parcel in one tax year. Extends the ledger entry base (inherits `entry_id`, `legal_entity_id`, `transaction_amount`, `date_id`, etc.) with property-tax-specific columns.

### Cross-Domain Relationship

The `parcel_id` column FKs to `county_property.dim_parcel`, enabling:

```sql
-- Property tax by township
SELECT p.township_code, SUM(pt.transaction_amount) as total_tax
FROM fact_property_tax pt
JOIN county_property.dim_parcel p ON pt.parcel_id = p.parcel_id
GROUP BY p.township_code;
```

### Amount Derivation

`transaction_amount = assessed_value * tax_rate`

The assessed value comes from `county_property.fact_assessed_values.av_total` for the corresponding parcel and year.
