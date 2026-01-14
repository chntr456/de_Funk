---
type: domain-model
model: cook_county_property
version: 1.0
description: "Cook County property assessments, parcels, and sales"

# Schema Template
schema_template: _schema/property.md

# Python Module
python_module: models/domains/county/cook_county/property/

# Dependencies
depends_on:
  - temporal
  - cook_county_geospatial

# Storage
storage:
  root: storage/silver/cook_county/property
  format: delta

# Build
build:
  partitions: [year]
  sort_by: [parcel_id, year]
  optimize: true

# Sources (Bronze → Silver mapping)
sources:
  assessed_values:
    bronze_table: cook_county_assessed_values
    description: "Property assessed values 1999-present"
    column_overrides:
      parcel_id: "LPAD(pin, 14, '0')"
    filters:
      - "year >= 2010"

  parcel_sales:
    bronze_table: cook_county_parcel_sales
    description: "Property sales transactions"
    column_overrides:
      parcel_id: "LPAD(pin, 14, '0')"

  parcel_universe:
    bronze_table: cook_county_parcel_universe
    description: "All parcels with characteristics"
    column_overrides:
      parcel_id: "LPAD(pin, 14, '0')"

  residential_chars:
    bronze_table: cook_county_residential
    description: "Residential property characteristics"

# Schema (extends template)
schema:
  dimensions:
    dim_parcel:
      extends: _schema/property.dim_parcel
      description: "Cook County parcel dimension"
      primary_key: [parcel_id]
      columns:
        # Additional Cook County specific columns
        nbhd: {type: string, description: "Neighborhood code"}
        tax_code: {type: string, description: "Tax code"}

    dim_property_class:
      extends: _schema/property.dim_property_class
      description: "Cook County property class codes"
      primary_key: [property_class_id]

    dim_township:
      extends: _schema/property.dim_township
      description: "Cook County townships"
      primary_key: [township_code]

  facts:
    fact_assessed_values:
      description: "Annual assessed values by parcel"
      primary_key: [parcel_id, year, assessment_stage]
      partitions: [year]
      columns:
        parcel_id: {type: string, required: true}
        year: {type: int, required: true}
        assessment_stage: {type: string, required: true}
        av_land: {type: double}
        av_building: {type: double}
        av_total: {type: double}
        property_class: {type: string}
        township_code: {type: string}

    fact_parcel_sales:
      description: "Property sales transactions"
      primary_key: [parcel_id, sale_date]
      partitions: [year]
      columns:
        parcel_id: {type: string, required: true}
        sale_date: {type: date, required: true}
        sale_price: {type: double}
        sale_type: {type: string}
        year: {type: int}

# Graph
graph:
  nodes:
    dim_parcel:
      from: bronze.cook_county_parcel_universe
      type: dimension
      select:
        parcel_id: "LPAD(pin, 14, '0')"
        township_code: township_code
        property_class: class
        nbhd: nbhd
        year_built: year_built
        land_sqft: land_sqft
        building_sqft: building_sqft
      unique_key: [parcel_id]

    dim_property_class:
      from: bronze.cook_county_assessed_values
      type: dimension
      select:
        property_class_id: class
      derive:
        property_class_name: "class"  # Would need lookup table
      unique_key: [property_class_id]
      distinct: true

    dim_township:
      from: bronze.cook_county_assessed_values
      type: dimension
      select:
        township_code: township_code
      derive:
        township_name: "township_code"  # Would need lookup table
        county: "'Cook'"
      unique_key: [township_code]
      distinct: true

    fact_assessed_values:
      from: bronze.cook_county_assessed_values
      type: fact
      select:
        parcel_id: "LPAD(pin, 14, '0')"
        year: year
        assessment_stage: stage_name
        av_land: av_land
        av_building: av_bldg
        av_total: av_tot
        property_class: class
        township_code: township_code
      unique_key: [parcel_id, year, assessment_stage]

    fact_parcel_sales:
      from: bronze.cook_county_parcel_sales
      type: fact
      select:
        parcel_id: "LPAD(pin, 14, '0')"
        sale_date: sale_date
        sale_price: sale_price
        sale_type: sale_type
      derive:
        year: "YEAR(sale_date)"
      unique_key: [parcel_id, sale_date]

  edges:
    assessed_to_parcel:
      from: fact_assessed_values
      to: dim_parcel
      on: [parcel_id=parcel_id]
      type: many_to_one

    sales_to_parcel:
      from: fact_parcel_sales
      to: dim_parcel
      on: [parcel_id=parcel_id]
      type: many_to_one

    assessed_to_calendar:
      from: fact_assessed_values
      to: temporal.dim_calendar
      on: ["MAKE_DATE(year, 1, 1)=date"]
      type: left

    sales_to_calendar:
      from: fact_parcel_sales
      to: temporal.dim_calendar
      on: [sale_date=date]
      type: left

# Measures
measures:
  simple:
    parcel_count:
      description: "Number of parcels"
      source: dim_parcel.parcel_id
      aggregation: count_distinct
      format: "#,##0"

    total_assessed_value:
      description: "Total assessed value"
      source: fact_assessed_values.av_total
      aggregation: sum
      format: "$#,##0"

    avg_assessed_value:
      description: "Average assessed value"
      source: fact_assessed_values.av_total
      aggregation: avg
      format: "$#,##0"

    total_sales_volume:
      description: "Total sales volume"
      source: fact_parcel_sales.sale_price
      aggregation: sum
      format: "$#,##0"

    avg_sale_price:
      description: "Average sale price"
      source: fact_parcel_sales.sale_price
      aggregation: avg
      format: "$#,##0"

    sale_count:
      description: "Number of sales"
      source: fact_parcel_sales.parcel_id
      aggregation: count
      format: "#,##0"

  computed:
    median_sale_price:
      description: "Median sale price"
      expression: "PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY sale_price)"
      source_table: fact_parcel_sales
      format: "$#,##0"

# Metadata
metadata:
  domain: county
  entity: cook_county
  owner: data_engineering
  data_quality_checks:
    - valid_pin_format
    - positive_assessed_values
    - sale_price_reasonable
status: active
---

## Cook County Property Model

Property assessments, parcels, and sales for Cook County, Illinois.

### Data Sources

| Bronze Table | Endpoint | Description |
|--------------|----------|-------------|
| cook_county_assessed_values | Assessed Values | 1999-present, 3 stages |
| cook_county_parcel_sales | Parcel Sales | Property transactions |
| cook_county_parcel_universe | Parcel Universe | All parcels |
| cook_county_residential | Residential Chars | Residential details |

### Key Concepts

**PIN Format**: 14-digit Parcel Index Number, must be zero-padded.

**Assessment Stages**:
1. `mailed` - Initial values sent to owners
2. `certified` - After Assessor appeals
3. `bor_certified` - After Board of Review appeals

### Usage

```python
model = session.load_model("cook_county_property")

# Get assessed values
av = model.get_table("fact_assessed_values",
                     filters={"year": 2023, "assessment_stage": "bor_certified"})

# Get sales
sales = model.get_table("fact_parcel_sales",
                        filters={"year": 2023})
```

### Notes

- PIN must be zero-padded for joins across datasets
- Market value = Assessed Value / Level of Assessment
- Level of assessment varies by property class and year
