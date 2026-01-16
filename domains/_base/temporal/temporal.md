---
type: domain-base
base_name: temporal
version: 3.0
description: "Base template for calendar/time dimensions"
tags: [calendar, dates, temporal, base, template]

# Base Tables
tables:
  dim_calendar:
    type: dimension
    description: "Master calendar dimension template"
    primary_key: [date_id]

    # Schema: [column, type, nullable, description, {options}]
    schema:
      # Primary key - integer YYYYMMDD format
      - [date_id, integer, false, "PK - Integer surrogate (YYYYMMDD)", {derived: "CAST(DATE_FORMAT(date, 'yyyyMMdd') AS INT)"}]
      - [date, date, false, "Calendar date (natural key)", {unique: true}]

      # Year attributes
      - [year, integer, false, "Calendar year"]
      - [year_month, string, false, "YYYY-MM format"]
      - [year_quarter, string, false, "YYYY-Q# format"]

      # Quarter attributes
      - [quarter, integer, false, "Calendar quarter (1-4)"]
      - [is_quarter_start, boolean, false, "First day of quarter"]
      - [is_quarter_end, boolean, false, "Last day of quarter"]

      # Month attributes
      - [month, integer, false, "Month number (1-12)"]
      - [month_name, string, false, "Full month name"]
      - [month_abbr, string, false, "3-letter month abbreviation"]
      - [days_in_month, integer, false, "Days in this month"]
      - [is_month_start, boolean, false, "First day of month"]
      - [is_month_end, boolean, false, "Last day of month"]

      # Week attributes
      - [week_of_year, integer, false, "ISO week number (1-53)"]
      - [day_of_week, integer, false, "Day of week (1=Mon, 7=Sun)"]
      - [day_of_week_name, string, false, "Full day name"]
      - [day_of_week_abbr, string, false, "3-letter day abbreviation"]
      - [is_weekend, boolean, false, "Saturday or Sunday"]
      - [is_weekday, boolean, false, "Monday through Friday"]

      # Day attributes
      - [day_of_month, integer, false, "Day of month (1-31)"]
      - [day_of_year, integer, false, "Day of year (1-366)"]
      - [is_year_start, boolean, false, "January 1st"]
      - [is_year_end, boolean, false, "December 31st"]

      # Fiscal attributes (configurable per model)
      - [fiscal_year, integer, false, "Fiscal year"]
      - [fiscal_quarter, integer, false, "Fiscal quarter (1-4)"]
      - [fiscal_month, integer, false, "Fiscal month (1-12)"]

    measures:
      - [day_count, count, date_id, "Number of days", {format: "#,##0"}]
      - [weekday_count, count, date_id, "Number of weekdays", {format: "#,##0", filter: "is_weekday = true"}]
      - [weekend_count, count, date_id, "Number of weekend days", {format: "#,##0", filter: "is_weekend = true"}]

# Graph Templates
graph:
  nodes:
    dim_calendar:
      from: self  # Generated programmatically or from seed data
      type: dimension
      primary_key: [date_id]
      unique_key: [date]
      tags: [dim, calendar, master]

  edges: {}  # Other models link TO temporal, not from it

# Metadata
domain: temporal
tags: [base, template, calendar]
status: active
---

## Base Temporal Template

Reusable base template for calendar/time dimensions with integer date_id keys.

### Key Design

Primary key is **integer** in YYYYMMDD format:

| Key | Type | Example |
|-----|------|---------|
| `date_id` | integer | 20250116 = January 16, 2025 |

This provides:
- Efficient storage (4 bytes vs 10+ for date string)
- Fast integer comparisons
- Natural sort order
- Easy range queries: `WHERE date_id BETWEEN 20250101 AND 20251231`

### date_id Pattern

All fact tables should use `date_id` instead of date columns:

```yaml
# OLD - date column on fact (BAD)
fact_prices:
  schema:
    - [trade_date, date, false, "Trading date"]

# NEW - integer FK to dim_calendar (GOOD)
fact_prices:
  schema:
    - [date_id, integer, false, "FK to dim_calendar", {fk: temporal.dim_calendar.date_id}]
```

### Standard Attributes

Base template includes:
- Year/Quarter/Month/Week/Day hierarchies
- Weekend/Weekday flags
- Month start/end flags
- Fiscal period support (configurable)

### Extension Points

Models extending this template can add:
- `is_trading_day` - for securities (NYSE holidays)
- `is_holiday` - for specific jurisdiction
- Custom fiscal calendar start month
- Additional regional calendars

### Usage

```yaml
# In foundation/temporal.md
extends: _base.temporal
calendar_config:
  start_date: "2000-01-01"
  end_date: "2050-12-31"
  fiscal_year_start_month: 1
```
