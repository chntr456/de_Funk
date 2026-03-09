---
type: domain-base
model: parcel
version: 2.0
description: "Property parcels - land records, assessments, and sales transactions"
extends: _base._base_.entity

# CANONICAL FIELDS
# [field_name, type, nullable: bool, description: "meaning"]
canonical_fields:
  # Common (all parcels)
  - [parcel_id, string, nullable: false, description: "Primary key (PIN or parcel number)"]
  - [parcel_code, string, nullable: false, description: "Natural key (standardized PIN)"]
  - [property_class, string, nullable: true, description: "Property classification code"]
  - [property_category, string, nullable: true, description: "Category (denormalized from dim_property_class)"]
  - [township_code, string, nullable: true, description: "Township/municipality code"]
  - [neighborhood_code, string, nullable: true, description: "Neighborhood/area code"]
  - [year_built, integer, nullable: true, description: "Year of construction"]
  - [land_sqft, double, nullable: true, description: "Land area in square feet"]
  - [building_sqft, double, nullable: true, description: "Building area in square feet"]
  - [latitude, double, nullable: true, description: "Parcel centroid latitude"]
  - [longitude, double, nullable: true, description: "Parcel centroid longitude"]
  - [tax_code, string, nullable: true, description: "Tax district code"]

  # Residential (populated when property_category = RESIDENTIAL)
  - [bedrooms, integer, nullable: true, description: "Number of bedrooms"]
  - [bathrooms, double, nullable: true, description: "Number of bathrooms (1.5, 2.5, etc.)"]
  - [stories, double, nullable: true, description: "Number of stories"]
  - [garage_spaces, integer, nullable: true, description: "Garage/parking spaces"]
  - [basement, string, nullable: true, description: "Basement type (FULL, PARTIAL, CRAWL, NONE)"]
  - [exterior_wall, string, nullable: true, description: "Exterior wall material"]

  # Commercial (populated when property_category = COMMERCIAL)
  - [commercial_sqft, double, nullable: true, description: "Commercial floor area in square feet"]
  - [commercial_units, integer, nullable: true, description: "Number of commercial units"]
  - [residential_units, integer, nullable: true, description: "Number of residential units (mixed-use)"]
  - [space_type, string, nullable: true, description: "OFFICE, RETAIL, MIXED_USE, WAREHOUSE"]
  - [floors, integer, nullable: true, description: "Number of floors"]

  # Industrial (populated when property_category = INDUSTRIAL)
  - [industrial_sqft, double, nullable: true, description: "Industrial floor area in square feet"]
  - [loading_docks, integer, nullable: true, description: "Number of loading docks"]
  - [ceiling_height, double, nullable: true, description: "Ceiling height in feet"]
  - [zoning_class, string, nullable: true, description: "Industrial zoning classification"]

tables:
  _dim_parcel:
    type: dimension
    primary_key: [parcel_id]
    unique_key: [parcel_code]
    partition_by: [property_category]

    # [column, type, nullable, description, {options}]
    schema:
      # Common fields (all parcels)
      - [parcel_id, string, false, "PK (PIN)", {derived: "LPAD(REGEXP_REPLACE(pin, '[^0-9]', ''), 14, '0')"}]
      - [parcel_code, string, false, "Natural key"]
      - [property_class, string, true, "Classification code"]
      - [property_category, string, true, "Category (denormalized)", {enum: [RESIDENTIAL, COMMERCIAL, INDUSTRIAL, EXEMPT, OTHER]}]
      - [township_code, string, true, "Township"]
      - [neighborhood_code, string, true, "Neighborhood"]
      - [year_built, integer, true, "Construction year"]
      - [land_sqft, double, true, "Land area sq ft"]
      - [building_sqft, double, true, "Building area sq ft"]
      - [latitude, double, true, "Centroid latitude"]
      - [longitude, double, true, "Centroid longitude"]
      - [tax_code, string, true, "Tax district"]

      # Residential fields (null when property_category != RESIDENTIAL)
      - [bedrooms, integer, true, "Number of bedrooms", {subset: RESIDENTIAL}]
      - [bathrooms, double, true, "Number of bathrooms", {subset: RESIDENTIAL}]
      - [stories, double, true, "Number of stories", {subset: RESIDENTIAL}]
      - [garage_spaces, integer, true, "Garage/parking spaces", {subset: RESIDENTIAL}]
      - [basement, string, true, "Basement type", {subset: RESIDENTIAL, enum: [FULL, PARTIAL, CRAWL, NONE]}]
      - [exterior_wall, string, true, "Exterior wall material", {subset: RESIDENTIAL}]

      # Commercial fields (null when property_category != COMMERCIAL)
      - [commercial_sqft, double, true, "Commercial floor area sq ft", {subset: COMMERCIAL}]
      - [commercial_units, integer, true, "Number of commercial units", {subset: COMMERCIAL}]
      - [residential_units, integer, true, "Residential units (mixed-use)", {subset: COMMERCIAL}]
      - [space_type, string, true, "Space classification", {subset: COMMERCIAL, enum: [OFFICE, RETAIL, MIXED_USE, WAREHOUSE]}]
      - [floors, integer, true, "Number of floors", {subset: COMMERCIAL}]

      # Industrial fields (null when property_category != INDUSTRIAL)
      - [industrial_sqft, double, true, "Industrial floor area sq ft", {subset: INDUSTRIAL}]
      - [loading_docks, integer, true, "Number of loading docks", {subset: INDUSTRIAL}]
      - [ceiling_height, double, true, "Ceiling height in feet", {subset: INDUSTRIAL}]
      - [zoning_class, string, true, "Industrial zoning classification", {subset: INDUSTRIAL}]

    measures:
      - [parcel_count, count_distinct, parcel_id, "Number of parcels", {format: "#,##0"}]
      - [avg_bedrooms, avg, bedrooms, "Average bedrooms", {format: "#,##0.0", subset: RESIDENTIAL}]
      - [avg_bathrooms, avg, bathrooms, "Average bathrooms", {format: "#,##0.0", subset: RESIDENTIAL}]
      - [avg_commercial_sqft, avg, commercial_sqft, "Average commercial sq ft", {format: "#,##0", subset: COMMERCIAL}]
      - [total_commercial_units, sum, commercial_units, "Total commercial units", {format: "#,##0", subset: COMMERCIAL}]
      - [avg_industrial_sqft, avg, industrial_sqft, "Average industrial sq ft", {format: "#,##0", subset: INDUSTRIAL}]
      - [total_loading_docks, sum, loading_docks, "Total loading docks", {format: "#,##0", subset: INDUSTRIAL}]

  _dim_property_class:
    type: dimension
    primary_key: [property_class_id]
    unique_key: [property_class_code]

    # [column, type, nullable, description, {options}]
    schema:
      - [property_class_id, string, false, "PK (classification code)"]
      - [property_class_code, string, false, "Natural key"]
      - [property_class_name, string, true, "Description"]
      - [property_category, string, true, "RESIDENTIAL, COMMERCIAL, INDUSTRIAL, EXEMPT, OTHER", {enum: [RESIDENTIAL, COMMERCIAL, INDUSTRIAL, EXEMPT, OTHER]}]
      - [applicable_fields, string, true, "Comma-separated list of subset fields applicable to this class"]

    measures:
      - [class_count, count_distinct, property_class_id, "Property classes", {format: "#,##0"}]

  _fact_assessed_values:
    type: fact
    primary_key: [parcel_id, year, assessment_stage]
    partition_by: [year]

    # [column, type, nullable, description, {options}]
    schema:
      - [parcel_id, string, false, "FK to dim_parcel", {fk: _dim_parcel.parcel_id}]
      - [year, integer, false, "Assessment year"]
      - [date_id, integer, false, "FK to calendar (Jan 1 of assessment year)", {fk: temporal.dim_calendar.date_id, derived: "CAST(CONCAT(year, '0101') AS INT)"}]
      - [assessment_stage, string, false, "Stage (mailed, certified, appeal)", {enum: [MAILED, CERTIFIED, BOARD_CERTIFIED, APPEAL]}]
      - [av_land, "decimal(18,2)", true, "Assessed value - land"]
      - [av_building, "decimal(18,2)", true, "Assessed value - building"]
      - [av_total, "decimal(18,2)", true, "Assessed value - total"]
      - [property_class, string, true, "Classification at assessment time"]
      - [township_code, string, true, "Township at assessment time"]

    measures:
      - [total_assessed_value, sum, av_total, "Total assessed value", {format: "$#,##0.00"}]
      - [avg_assessed_value, avg, av_total, "Average assessed value", {format: "$#,##0.00"}]
      - [assessment_count, count, parcel_id, "Assessment records", {format: "#,##0"}]

  _fact_parcel_sales:
    type: fact
    primary_key: [parcel_id, sale_date]
    partition_by: [year]

    # [column, type, nullable, description, {options}]
    schema:
      - [parcel_id, string, false, "FK to dim_parcel", {fk: _dim_parcel.parcel_id}]
      - [sale_date, date, false, "Date of sale"]
      - [sale_date_id, integer, false, "FK to calendar", {fk: temporal.dim_calendar.date_id, derived: "CAST(DATE_FORMAT(sale_date, 'yyyyMMdd') AS INT)"}]
      - [year, integer, false, "Sale year", {derived: "YEAR(sale_date)"}]
      - [sale_price, "decimal(18,2)", true, "Sale price"]
      - [sale_type, string, true, "Transaction type"]

    measures:
      - [total_sales_volume, sum, sale_price, "Total sales volume", {format: "$#,##0.00"}]
      - [avg_sale_price, avg, sale_price, "Average sale price", {format: "$#,##0.00"}]
      - [sale_count, count, parcel_id, "Number of sales", {format: "#,##0"}]

subsets:
  discriminator: _dim_property_class.property_category
  pattern: wide_table
  description: "Type-specific fields are stored as nullable columns on _dim_parcel, partitioned by property_category. Column metadata {subset: VALUE} marks which fields belong to each category. dim_property_class.applicable_fields lists active fields per class."
  values:
    RESIDENTIAL:
      description: "Single-family, multi-family, condos"
      filter: "property_category = 'RESIDENTIAL'"
      fields: [bedrooms, bathrooms, stories, garage_spaces, basement, exterior_wall]
    COMMERCIAL:
      description: "Office, retail, mixed-use"
      filter: "property_category = 'COMMERCIAL'"
      fields: [commercial_sqft, commercial_units, residential_units, space_type, floors]
    INDUSTRIAL:
      description: "Manufacturing, warehouse, distribution"
      filter: "property_category = 'INDUSTRIAL'"
      fields: [industrial_sqft, loading_docks, ceiling_height, zoning_class]
    EXEMPT:
      description: "Government, religious, educational"
      filter: "property_category = 'EXEMPT'"
    OTHER:
      description: "Vacant land, agricultural"
      filter: "property_category = 'OTHER'"

auto_edges:
  - [date_id, temporal.dim_calendar, [date_id=date_id], many_to_one, temporal]

behaviors:
  - temporal        # Has auto_edges for date_id → calendar
  - subsettable     # Has subsets: block (property_category discriminator)

graph:
  # auto_edges: date_id→calendar (assessed_values only; parcel_sales uses sale_date_id — explicit below)
  edges:
    - [assessment_to_parcel, _fact_assessed_values, _dim_parcel, [parcel_id=parcel_id], many_to_one, null]
    - [sale_to_parcel, _fact_parcel_sales, _dim_parcel, [parcel_id=parcel_id], many_to_one, null]
    - [sale_to_calendar, _fact_parcel_sales, temporal.dim_calendar, [sale_date_id=date_id], many_to_one, temporal]
    - [parcel_to_property_class, _dim_parcel, _dim_property_class, [property_class=property_class_code], many_to_one, null]
    - [assessment_to_property_class, _fact_assessed_values, _dim_property_class, [property_class=property_class_code], many_to_one, null]

views:
  _view_equalized_values:
    type: derived
    from: _fact_assessed_values
    join: [{table: _dim_tax_district, on: [tax_code=tax_code], fields: [equalization_factor]}]
    description: "Assessed values with equalization factor applied"
    assumptions:
      equalization_factor:
        type: "decimal(10,6)"
        default: 1.0
        description: "State equalization factor (by township/year)"
        source: "Joined from dim_tax_district or overridden per model"
    schema:
      - [parcel_id, string, false, "FK to dim_parcel"]
      - [year, integer, false, "Assessment year"]
      - [assessment_stage, string, false, "Stage"]
      - [av_total, "decimal(18,2)", false, "Raw assessed value"]
      - [equalization_factor, "decimal(10,6)", false, "Applied factor"]
      - [ev_total, "decimal(18,2)", false, "Equalized assessed value", {derived: "av_total * equalization_factor"}]
    measures:
      - [total_equalized_value, sum, ev_total, "Total equalized value", {format: "$#,##0.00"}]
      - [avg_equalized_value, avg, ev_total, "Average equalized value", {format: "$#,##0.00"}]

  _view_estimated_tax:
    type: derived
    from: _view_equalized_values
    join: [{table: _dim_tax_district, on: [tax_code=tax_code], fields: [total_rate]}]
    description: "Estimated tax bills from equalized values and tax rates"
    assumptions:
      total_rate:
        type: "decimal(10,6)"
        default: null
        description: "Composite tax rate from all overlapping districts"
        source: "Joined from dim_tax_district"
    schema:
      - [parcel_id, string, false, "FK to dim_parcel"]
      - [year, integer, false, "Assessment year"]
      - [ev_total, "decimal(18,2)", false, "Equalized value (from parent view)"]
      - [total_rate, "decimal(10,6)", false, "Composite tax rate"]
      - [estimated_tax, "decimal(18,2)", false, "Estimated tax bill", {derived: "ev_total * total_rate"}]
    measures:
      - [total_estimated_tax, sum, estimated_tax, "Total estimated tax", {format: "$#,##0.00"}]
      - [avg_estimated_tax, avg, estimated_tax, "Average estimated tax", {format: "$#,##0.00"}]

  _view_township_summary:
    type: rollup
    from: _fact_assessed_values
    grain: [township_code, year, assessment_stage]
    description: "Township-level assessment summary"
    schema:
      - [township_code, string, false, "Township"]
      - [year, integer, false, "Assessment year"]
      - [assessment_stage, string, false, "Stage"]
      - [parcel_count, integer, false, "Parcels in township", {derived: "COUNT(DISTINCT parcel_id)"}]
      - [total_av, "decimal(18,2)", false, "Total assessed value", {derived: "SUM(av_total)"}]
      - [avg_av, "decimal(18,2)", false, "Average assessed value", {derived: "AVG(av_total)"}]

domain: property
tags: [base, template, property, parcel, assessment]
status: active
---

## Parcel Base Template

Property parcel data including land records, assessments, and sales. Parcel IDs (PINs) are standardized to 14-digit zero-padded format for cross-dataset joins.

### Wide Table Pattern

All property-type-specific fields (residential, commercial, industrial) are stored as nullable columns on a single `_dim_parcel` table, partitioned by `property_category`. The `{subset: VALUE}` metadata on each column marks which property category it belongs to. Columns are null for non-matching categories.

`_dim_property_class` serves as the **field dictionary** — `applicable_fields` lists which subset columns are populated for each classification code.

### Delta Lake Advantages

- **Partition pruning**: `WHERE property_category = 'RESIDENTIAL'` reads only residential partition
- **Null compression**: Columnar storage makes sparse columns essentially free
- **No join overhead**: All fields available without subset table joins
- **Schema evolution**: New property types add columns without breaking existing queries

### Assessment Stages

| Stage | Description |
|-------|-------------|
| MAILED | Initial mailed assessment |
| CERTIFIED | Certified by assessor |
| BOARD_CERTIFIED | Certified by board of review |
| APPEAL | Post-appeal value |

### Property Categories

```
RESIDENTIAL: Single-family, multi-family, condos
  → bedrooms, bathrooms, stories, garage_spaces, basement, exterior_wall
COMMERCIAL: Office, retail, mixed-use
  → commercial_sqft, commercial_units, residential_units, space_type, floors
INDUSTRIAL: Manufacturing, warehouse
  → industrial_sqft, loading_docks, ceiling_height, zoning_class
EXEMPT: Government, religious, educational
  → (no type-specific fields)
OTHER: Vacant land, agricultural
  → (no type-specific fields)
```

### Views (Layered Calculations)

```
_fact_assessed_values (physical table)
     ↓ (join dim_tax_district for equalization_factor)
_view_equalized_values (adds ev_total = av_total × equalization_factor)
     ↓ (join dim_tax_district for total_rate)
_view_estimated_tax (adds estimated_tax = ev_total × total_rate)

_fact_assessed_values (physical table)
     ↓ (GROUP BY township_code, year, assessment_stage)
_view_township_summary (parcel_count, total_av, avg_av)
```

### Usage

```yaml
extends: _base.property.parcel
```
