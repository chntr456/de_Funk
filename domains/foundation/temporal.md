---
type: domain-model
model: temporal
version: 2.2
description: "Time and calendar dimensions - foundation for all time-series analysis"
tags: [time, calendar, dates, foundation, shared]


# Dependencies
depends_on: []  # Foundation model - no dependencies

# Storage
storage:
  root: storage/silver/temporal
  format: delta

# Build
build:
  partitions: []
  sort_by: [date]
  optimize: true

# Calendar Generation Config
calendar_config:
  start_date: "2000-01-01"
  end_date: "2050-12-31"
  fiscal_year_start_month: 1  # January

# Schema
schema:
  dimensions:
    dim_calendar:
      description: "Universal calendar dimension with rich date attributes"
      primary_key: [date]
      columns:
        date: {type: date, description: "Primary key: YYYY-MM-DD"}
        year: {type: integer, description: "Calendar year"}
        quarter: {type: integer, description: "Calendar quarter (1-4)"}
        month: {type: integer, description: "Month number (1-12)"}
        month_name: {type: string, description: "Month name"}
        month_abbr: {type: string, description: "Month abbreviation"}
        week_of_year: {type: integer, description: "ISO week number (1-53)"}
        day_of_month: {type: integer, description: "Day of month (1-31)"}
        day_of_week: {type: integer, description: "Day of week (1=Mon, 7=Sun)"}
        day_of_week_name: {type: string, description: "Day name"}
        day_of_week_abbr: {type: string, description: "Day abbreviation"}
        day_of_year: {type: integer, description: "Day of year (1-366)"}
        is_weekend: {type: boolean, description: "Saturday or Sunday"}
        is_weekday: {type: boolean, description: "Monday-Friday"}
        is_month_start: {type: boolean, description: "First day of month"}
        is_month_end: {type: boolean, description: "Last day of month"}
        is_quarter_start: {type: boolean, description: "First day of quarter"}
        is_quarter_end: {type: boolean, description: "Last day of quarter"}
        is_year_start: {type: boolean, description: "First day of year"}
        is_year_end: {type: boolean, description: "Last day of year"}
        fiscal_year: {type: integer, description: "Fiscal year"}
        fiscal_quarter: {type: integer, description: "Fiscal quarter (1-4)"}
        fiscal_month: {type: integer, description: "Fiscal month (1-12)"}
        days_in_month: {type: integer, description: "Days in month"}
        year_month: {type: string, description: "YYYY-MM format"}
        year_quarter: {type: string, description: "YYYY-Q1 format"}
        date_str: {type: string, description: "YYYY-MM-DD as string"}
      tags: [dim, calendar, time, shared]

  facts: {}  # No fact tables - reference dimensions only

# Graph - dim_calendar is self-generated (custom_node_loading override)
graph:
  nodes:
    dim_calendar:
      from: self  # Generated programmatically, not from bronze
      type: dimension
      unique_key: [date]
      tags: [dim, calendar]

  edges: {}  # Other models link TO temporal, not from it

# Measures
measures:
  simple:
    day_count:
      description: "Number of days"
      source: dim_calendar.date
      aggregation: count
      format: "#,##0"

    weekday_count:
      description: "Number of weekdays"
      source: dim_calendar.date
      aggregation: count
      filters: ["is_weekday = true"]
      format: "#,##0"

    weekend_count:
      description: "Number of weekend days"
      source: dim_calendar.date
      aggregation: count
      filters: ["is_weekend = true"]
      format: "#,##0"

# Metadata
metadata:
  domain: foundation
  owner: data_engineering
  sla_hours: 1
status: active
---

## Temporal Model

Foundation model providing time and calendar dimensions for all time-series analysis.

### Key Features

- **Self-Generating**: Creates calendar directly during silver build (no bronze dependency)
- **Dimension**: `dim_calendar` - Universal calendar with rich date attributes
- **Foundation**: All models with date-based facts join to this
- **Coverage**: 2000-01-01 to 2050-12-31

### Usage

```python
model = session.load_model("temporal")
calendar = model.get_table("dim_calendar")

# Filter to weekdays only
weekdays = model.get_table("dim_calendar", filters={"is_weekday": True})

# Get specific year
year_2024 = model.get_table("dim_calendar", filters={"year": 2024})
```

### Cross-Model Usage

Other models join to `dim_calendar` for date filtering:

```yaml
# In other model's graph config
edges:
  prices_to_calendar:
    from: fact_prices
    to: temporal.dim_calendar
    on: [trade_date=date]
    type: left
```

### Temporal Normalization

Downstream models (stocks, company) encode their date columns as foreign keys to `dim_calendar`:

| Model | Date Column | Joins To |
|-------|-------------|----------|
| stocks.fact_prices | trade_date | temporal.dim_calendar.date |
| company.fact_financials | report_date | temporal.dim_calendar.date |

This enables:
- Consistent date filtering across models
- Time-based aggregations (YTD, QTD, MTD)
- Fiscal period calculations

### Notes

- Foundation model with no dependencies
- Other models link TO temporal, not from it
- Pre-computed attributes for efficient filtering
- ~18,628 rows (51 years of dates)
