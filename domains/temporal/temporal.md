---
type: domain-model
model: temporal
version: 3.0
description: "Master calendar dimension - foundation for all time-series joins"
tags: [calendar, dates, foundation, shared]

# Inheritance - extends base calendar template
extends: _base.temporal.calendar

# Dependencies
depends_on: []  # Foundation model - no dependencies

# Storage
storage:
  root: storage/silver/temporal
  format: delta
  auto_vacuum: true  # Disable time travel to save storage (default: true)

# Build
build:
  partitions: []
  sort_by: [date_id]
  optimize: true

# Calendar Generation Config
calendar_config:
  start_date: "2000-01-01"
  end_date: "2050-12-31"
  fiscal_year_start_month: 1

# Tables
tables:
  dim_calendar:
    type: dimension
    description: "Master calendar - all date FKs reference this table"
    primary_key: [date_id]

    # Schema: [column, type, nullable, description, {options}]
    schema:
      # Primary key - integer YYYYMMDD format
      - [date_id, integer, false, "PK - Integer surrogate (YYYYMMDD)", {derived: "CAST(DATE_FORMAT(date, 'yyyyMMdd') AS INT)"}]
      - [date, date, false, "Calendar date (natural key)", {unique: true}]

      # Year attributes
      - [year, integer, false, "Calendar year (2000-2050)"]
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

      # Fiscal attributes
      - [fiscal_year, integer, false, "Fiscal year"]
      - [fiscal_quarter, integer, false, "Fiscal quarter (1-4)"]
      - [fiscal_month, integer, false, "Fiscal month (1-12)"]

      # Trading calendar (securities)
      - [is_trading_day, boolean, true, "NYSE trading day", {default: true}]
      - [is_holiday, boolean, true, "US federal holiday", {default: false}]

    # Measures belong on the table
    measures:
      - [day_count, count, date_id, "Number of days", {format: "#,##0"}]
      - [weekday_count, count, date_id, "Number of weekdays", {format: "#,##0", filter: "is_weekday = true"}]
      - [weekend_count, count, date_id, "Number of weekend days", {format: "#,##0", filter: "is_weekend = true"}]
      - [trading_day_count, count, date_id, "Number of trading days", {format: "#,##0", filter: "is_trading_day = true"}]

# Graph
graph:
  nodes:
    dim_calendar:
      from: self  # Generated programmatically during build
      type: dimension
      primary_key: [date_id]
      unique_key: [date]
      tags: [dim, calendar, master]

  edges: {}  # Other models link TO temporal, not from it

# Metadata
metadata:
  domain: temporal
  owner: data_engineering
  sla_hours: 1
status: active
---

## Temporal Model

Master calendar dimension providing the single source of truth for all dates.

### Integer Primary Key

All date columns in fact tables should be replaced with `date_id` (integer FK):

```yaml
# OLD - date column on fact
fact_stock_prices:
  schema:
    - [trade_date, date, false, "Trading date"]  # BAD

# NEW - integer FK to dim_calendar
fact_stock_prices:
  schema:
    - [date_id, integer, false, "FK to dim_calendar", {fk: temporal.dim_calendar.date_id}]
```

### date_id Format

`date_id` is an integer in YYYYMMDD format:
- January 16, 2025 = `20250116`
- December 31, 2000 = `20001231`

This provides:
- Efficient storage (4 bytes vs 10+ for date string)
- Fast integer comparisons
- Natural sort order
- Easy range queries: `WHERE date_id BETWEEN 20250101 AND 20251231`

### Query Pattern

```sql
-- Get actual date from calendar join
SELECT
    c.date AS trade_date,
    c.year,
    c.quarter,
    s.ticker,
    p.close
FROM fact_stock_prices p
JOIN dim_calendar c ON p.date_id = c.date_id
JOIN dim_security s ON p.security_id = s.security_id
WHERE c.year = 2025
  AND c.is_trading_day = true
```

### Semantic Aliases

When joining, use semantic column aliases in SELECT:
- `c.date AS trade_date` - for securities prices
- `c.date AS fiscal_date` - for financial statements
- `c.date AS report_date` - for earnings reports

### Coverage

- **Range**: 2000-01-01 to 2050-12-31
- **Rows**: ~18,628 dates
- **Self-generating**: No bronze dependency

### Notes

- Foundation model with no dependencies
- Other models link TO temporal via `date_id` FK
- Pre-computed attributes enable efficient filtering
- Trading day flags support securities analysis
