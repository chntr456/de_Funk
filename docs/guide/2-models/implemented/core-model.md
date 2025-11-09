---
title: "Core Model"
tags: [reference, component/model, source/generated, status/stable]
aliases: ["Core", "Calendar Model", "Foundation Model"]
created: 2024-11-08
updated: 2024-11-08
status: stable
dependencies: []
used_by:
  - "[[Company Model]]"
  - "[[Forecast Model]]"
  - "[[Macro Model]]"
  - "[[City Finance Model]]"
architecture_components:
  - "[[Storage]]"
  - "[[Models System]]"
  - "[[Bronze Storage]]"
---

# Core Model

---

> **Foundation model providing shared reference data and calendar dimension**

The Core model is the foundational model in de_Funk. It provides shared dimensions and reference data used across all other models, most notably the comprehensive `dim_calendar` dimension with 27 date attributes.

**Configuration:** `/home/user/de_Funk/configs/models/core.yaml`
**Implementation:** `/home/user/de_Funk/models/implemented/core/model.py`

---

## Table of Contents

---

- [Overview](#overview)
- [Schema Overview](#schema-overview)
- [Data Sources](#data-sources)
- [Detailed Schema](#detailed-schema)
- [Calendar Generation Logic](#calendar-generation-logic)
- [Graph Structure](#graph-structure)
- [How-To Guides](#how-to-guides)
- [Usage Examples](#usage-examples)
- [Integration with Other Models](#integration-with-other-models)
- [Design Decisions](#design-decisions)

---

## Overview

---

### Purpose

The Core model serves as the **foundation layer** for all other models in de_Funk. It provides:
- Universal calendar dimension for date-based analysis
- Shared reference data for time intelligence
- Fiscal period calculations
- Weekend/weekday flags for business day filtering

### Key Features

- **Comprehensive Calendar** - 27 date attributes covering all common use cases
- **No Dependencies** - Foundation model with no external dependencies
- **Date Range** - 2000-01-01 to 2050-12-31 (50+ years)
- **Fiscal Year Support** - Configurable fiscal year starting month
- **Holiday Configuration** - Optional holiday definitions
- **Time Intelligence** - Period flags (month start/end, quarter start/end, year start/end)

### Model Characteristics

| Attribute | Value |
|-----------|-------|
| **Model Name** | `core` |
| **Tags** | `shared`, `common`, `dimensions`, `reference` |
| **Dependencies** | None (foundation model) |
| **Storage Root** | `storage/silver/core` |
| **Format** | Parquet |
| **Tables** | 1 (dim_calendar) |
| **Dimensions** | 1 |
| **Facts** | 0 |
| **Measures** | 0 (reference data only) |
| **Update Frequency** | Static (generated once) |

---

## Architecture Components Used

---

This model uses the following architecture components:

### Primary Components

| Component | Purpose | Documentation |
|-----------|---------|---------------|
| **[[Storage/Silver]]** | Stores dimensional calendar data in Parquet format | [[Silver Layer]] |
| **[[Models System/Base Model]]** | Foundation model framework implementation | [[Base Model]] |
| **[[Bronze Storage]]** | Seed data for calendar generation | [[Bronze Layer]] |

### Data Flow

The Core model generates calendar data from seed configuration and writes directly to Silver storage. It serves as the foundation layer for all other models, providing a shared time dimension.

**Flow:** Configuration → Calendar Generation → Silver/core/dims/dim_calendar

See [[MODEL_ARCHITECTURE_MAPPING]] for complete architecture mapping.

---

## Schema Overview

---

### High-Level Summary

The Core model implements a **single shared dimension** pattern with a comprehensive calendar table. All data is generated programmatically and provides the foundation for time-based analysis across all models.

**Quick Reference:**

| Table Type | Count | Purpose |
|------------|-------|---------|
| **Dimensions** | 1 | Date attributes and time intelligence |
| **Facts** | 0 | No transactional data (reference only) |
| **Measures** | 0 | Reference data only |

### Dimensions (Reference Data)

| Dimension | Rows | Primary Key | Purpose |
|-----------|------|-------------|---------|
| **dim_calendar** | ~18,627 | date | Universal calendar with 27 date attributes |

### Calendar Schema Diagram

```
┌─────────────────────────────────────┐
│         dim_calendar                │
│                                     │
│  • 27 date attributes               │
│  • 2000-01-01 to 2050-12-31        │
│  • ~18,627 rows (50+ years)        │
│                                     │
│  Used by ALL other models          │
└─────────────────────────────────────┘
         ↓           ↓           ↓
    ┌────────┐  ┌────────┐  ┌────────┐
    │Company │  │ Macro  │  │Forecast│
    │ Model  │  │ Model  │  │ Model  │
    └────────┘  └────────┘  └────────┘
```

**Relationships:**
- All models can join to `dim_calendar.date` for date-based filtering
- No foreign keys in dim_calendar (standalone dimension)
- Optional relationship (models can work without calendar joins)

---

## Data Sources

---

### Generated Data

**Provider:** Programmatically generated
**Authentication:** None required
**Data Coverage:** 2000-01-01 to 2050-12-31 (configurable)

### Generation Configuration

The calendar is generated using configuration in the YAML file:

```yaml
calendar_config:
  start_date: "2000-01-01"
  end_date: "2050-12-31"
  fiscal_year_start_month: 1  # January (can be changed to July for fiscal year starting in July)

  # Weekend days (1=Monday, 7=Sunday)
  weekend_days: [6, 7]  # Saturday, Sunday

  # Holidays (optional - can be added later)
  holidays:
    - name: "New Year's Day"
      type: "fixed"
      month: 1
      day: 1

    - name: "Independence Day"
      type: "fixed"
      month: 7
      day: 4

    - name: "Christmas Day"
      type: "fixed"
      month: 12
      day: 25
```

### Bronze → Silver Transformation

**Pipeline:** `models/implemented/core/model.py`

```
Python Date Generation
    ↓
Date Range (2000-01-01 to 2050-12-31)
    ↓
Calendar Attributes Calculation
    ├─→ Basic: year, quarter, month, day
    ├─→ Names: month_name, day_of_week_name
    ├─→ ISO: week_of_year
    ├─→ Flags: is_weekend, is_weekday, period flags
    ├─→ Fiscal: fiscal_year, fiscal_quarter
    └─→ Strings: year_month, year_quarter
    ↓
Silver Storage (dimensional model)
    └─→ silver/core/dims/dim_calendar/
```

### Data Quality

- **Completeness:** All dates from 2000-2050 (no gaps)
- **Accuracy:** Algorithmically generated (deterministic)
- **Timeliness:** Static dimension (no updates needed)
- **Consistency:** Schema validated during generation

### Expandability

The Core model can be extended with additional reference dimensions:

**Potential Extensions:**
- Time dimension (hour, minute, second for intraday)
- Holiday dimension (country-specific holidays)
- Fiscal calendar variants (different fiscal year starts)
- Business calendar (trading days only)

---

## Detailed Schema

---

### Dimensions

#### dim_calendar

Universal calendar dimension with rich date attributes for time-based analysis.

**Path:** `storage/silver/core/dims/dim_calendar`
**Primary Key:** `date`
**Grain:** One row per date (2000-01-01 to 2050-12-31)

| Column | Type | Description | Example Values |
|--------|------|-------------|----------------|
| **date** | date | Primary key: YYYY-MM-DD | 2024-11-08 |
| **year** | integer | Calendar year | 2024, 2025 |
| **quarter** | integer | Calendar quarter (1-4) | 1, 2, 3, 4 |
| **month** | integer | Month number (1-12) | 1, 2, ..., 12 |
| **month_name** | string | Full month name | January, February, March |
| **month_abbr** | string | Month abbreviation (3 chars) | Jan, Feb, Mar |
| **week_of_year** | integer | ISO week number (1-53) | 1, 2, ..., 53 |
| **day_of_month** | integer | Day of month (1-31) | 1, 2, ..., 31 |
| **day_of_week** | integer | Day of week (1=Monday, 7=Sunday) | 1, 2, ..., 7 |
| **day_of_week_name** | string | Full day name | Monday, Tuesday, Wednesday |
| **day_of_week_abbr** | string | Day abbreviation (3 chars) | Mon, Tue, Wed |
| **day_of_year** | integer | Day of year (1-366) | 1, 2, ..., 366 |
| **is_weekend** | boolean | True if Saturday or Sunday | true, false |
| **is_weekday** | boolean | True if Monday-Friday | true, false |
| **is_month_start** | boolean | First day of month | true, false |
| **is_month_end** | boolean | Last day of month | true, false |
| **is_quarter_start** | boolean | First day of quarter | true, false |
| **is_quarter_end** | boolean | Last day of quarter | true, false |
| **is_year_start** | boolean | First day of year | true, false |
| **is_year_end** | boolean | Last day of year | true, false |
| **fiscal_year** | integer | Fiscal year (configurable) | 2024, 2025 |
| **fiscal_quarter** | integer | Fiscal quarter (1-4) | 1, 2, 3, 4 |
| **fiscal_month** | integer | Fiscal month (1-12) | 1, 2, ..., 12 |
| **days_in_month** | integer | Number of days in the month | 28, 29, 30, 31 |
| **year_month** | string | YYYY-MM format | 2024-01, 2024-02 |
| **year_quarter** | string | YYYY-Q1 format | 2024-Q1, 2024-Q2 |
| **date_str** | string | YYYY-MM-DD as string | "2024-11-08" |

**Sample Data:**
```
+------------+------+--------+------+------------+-----------+--------------+
|   date     | year | quarter| month| month_name | month_abbr| day_of_month |
+------------+------+--------+------+------------+-----------+--------------+
| 2024-01-01 | 2024 |   1    |  1   | January    | Jan       |      1       |
| 2024-01-02 | 2024 |   1    |  1   | January    | Jan       |      2       |
| 2024-01-15 | 2024 |   1    |  1   | January    | Jan       |     15       |
| 2024-03-31 | 2024 |   1    |  3   | March      | Mar       |     31       |
| 2024-04-01 | 2024 |   2    |  4   | April      | Apr       |      1       |
+------------+------+--------+------+------------+-----------+--------------+

+-------------+-----------------+-------------------+-------------+
| day_of_week | day_of_week_name| day_of_week_abbr  | day_of_year |
+-------------+-----------------+-------------------+-------------+
|     1       | Monday          | Mon               |     1       |
|     2       | Tuesday         | Tue               |     2       |
|     1       | Monday          | Mon               |    15       |
|     7       | Sunday          | Sun               |    91       |
|     1       | Monday          | Mon               |    92       |
+-------------+-----------------+-------------------+-------------+

+------------+-----------+---------------+------------------+
| is_weekend | is_weekday| is_month_start| is_month_end     |
+------------+-----------+---------------+------------------+
|   false    |   true    |     true      |     false        |
|   false    |   true    |     false     |     false        |
|   false    |   true    |     false     |     false        |
|   true     |   false   |     false     |     true         |
|   false    |   true    |     true      |     false        |
+------------+-----------+---------------+------------------+

+------------------+-------------------+----------------+------------------+
| is_quarter_start | is_quarter_end    | is_year_start  | is_year_end      |
+------------------+-------------------+----------------+------------------+
|      true        |     false         |     true       |     false        |
|      false       |     false         |     false      |     false        |
|      false       |     false         |     false      |     false        |
|      false       |     true          |     false      |     false        |
|      true        |     false         |     false      |     false        |
+------------------+-------------------+----------------+------------------+

+-------------+---------------+--------------+---------------+-------------+
| fiscal_year | fiscal_quarter| fiscal_month | days_in_month | year_month  |
+-------------+---------------+--------------+---------------+-------------+
|    2024     |      1        |      1       |     31        | 2024-01     |
|    2024     |      1        |      1       |     31        | 2024-01     |
|    2024     |      1        |      1       |     31        | 2024-01     |
|    2024     |      1        |      3       |     31        | 2024-03     |
|    2024     |      2        |      4       |     30        | 2024-04     |
+-------------+---------------+--------------+---------------+-------------+

+-------------+-------------+
| year_quarter| date_str    |
+-------------+-------------+
| 2024-Q1     | 2024-01-01  |
| 2024-Q1     | 2024-01-02  |
| 2024-Q1     | 2024-01-15  |
| 2024-Q1     | 2024-03-31  |
| 2024-Q2     | 2024-04-01  |
+-------------+-------------+
```

---

## Calendar Generation Logic

---

### Generation Process

The calendar is generated from Bronze seed data with the following transformations:

1. **Date Range Generation** - Create one row per date from 2000-01-01 to 2050-12-31
2. **Calendar Attributes** - Extract year, quarter, month, day attributes
3. **ISO Week Calculation** - Calculate ISO week numbers
4. **Day of Week** - Calculate day of week (1=Monday, 7=Sunday)
5. **Weekend Flags** - Mark Saturday/Sunday as weekends
6. **Period Flags** - Identify month/quarter/year start/end dates
7. **Fiscal Year Calculation** - Calculate fiscal year based on start month
8. **String Formats** - Generate formatted strings (YYYY-MM, YYYY-Q1, etc.)

### Fiscal Year Logic

Fiscal year is calculated based on `fiscal_year_start_month`:

- **fiscal_year_start_month = 1 (January)** - Fiscal year = Calendar year
  - FY 2024: Jan 1, 2024 - Dec 31, 2024
  - fiscal_quarter: 1=Q1 (Jan-Mar), 2=Q2 (Apr-Jun), 3=Q3 (Jul-Sep), 4=Q4 (Oct-Dec)

- **fiscal_year_start_month = 7 (July)** - Fiscal year shifts
  - FY 2024: Jul 1, 2023 - Jun 30, 2024
  - fiscal_quarter: 1=Q1 (Jul-Sep), 2=Q2 (Oct-Dec), 3=Q3 (Jan-Mar), 4=Q4 (Apr-Jun)

```python
# Fiscal year calculation (simplified)
if month >= fiscal_year_start_month:
    fiscal_year = year
else:
    fiscal_year = year - 1

fiscal_month = ((month - fiscal_year_start_month) % 12) + 1
fiscal_quarter = ((fiscal_month - 1) // 3) + 1
```

### Weekend Logic

Weekend days are configurable but default to Saturday (6) and Sunday (7):

```python
is_weekend = day_of_week in [6, 7]
is_weekday = not is_weekend
```

For different regions:
- **US/Europe:** Weekend = Saturday (6), Sunday (7)
- **Middle East:** Weekend = Friday (5), Saturday (6)

### Period Flags

Period start/end flags for easy filtering:

```python
is_month_start = day_of_month == 1
is_month_end = day_of_month == days_in_month

is_quarter_start = (month in [1, 4, 7, 10]) and (day_of_month == 1)
is_quarter_end = (month in [3, 6, 9, 12]) and (day_of_month == days_in_month)

is_year_start = (month == 1) and (day_of_month == 1)
is_year_end = (month == 12) and (day_of_month == 31)
```

---

## Graph Structure

---

The Core model has a simple graph structure with no relationships (it's a standalone reference dimension).

### Nodes

```yaml
nodes:
  - id: dim_calendar
    from: bronze.calendar_seed
    select:
      date: date
      year: year
      quarter: quarter
      month: month
      # ... all 27 columns ...
    tags: [dim, calendar, shared]
    unique_key: [date]
```

### Edges

```yaml
edges: []  # No edges - calendar is a standalone dimension
```

### Paths

```yaml
paths: []  # No paths - no joins needed
```

---

## How-To Guides

---

### How to Filter by Date Range

**Step 1:** Load the core model

```python
from core.context import RepoContext
from models.api.session import UniversalSession

# Initialize
ctx = RepoContext.from_repo_root()
session = UniversalSession(ctx.connection, ctx.config_root, ctx.storage_cfg)

# Load core model
core_model = session.load_model('core')
```

**Step 2:** Get calendar for specific date range

```python
# Get calendar dimension
calendar = core_model.get_dimension_df('dim_calendar')

# Filter for 2024
calendar_2024 = calendar.filter(F.col('year') == 2024).orderBy('date')

print(f"Days in 2024: {calendar_2024.count()}")
# Days in 2024: 366 (leap year)

calendar_2024.select('date', 'month_name', 'day_of_week_name').show(10)
```

**Step 3:** Use with other models

```python
# Load company model
company_model = session.load_model('company')
prices = company_model.get_fact_df('fact_prices')

# Join prices with calendar to add date attributes
prices_with_dates = prices.join(
    calendar,
    prices.trade_date == calendar.date,
    how='left'
)

# Now can filter by day of week
monday_prices = prices_with_dates.filter(F.col('day_of_week') == 1)

# Or by month
jan_prices = prices_with_dates.filter(F.col('month') == 1)
```

---

### How to Get Business Days Only

**Step 1:** Load calendar

```python
# Get calendar
calendar = core_model.get_dimension_df('dim_calendar')
```

**Step 2:** Filter for weekdays

```python
# Get weekdays (Monday-Friday) for 2024
weekdays_2024 = calendar.filter(
    (F.col('year') == 2024) &
    (F.col('is_weekday') == True)
).orderBy('date')

print(f"Weekdays in 2024: {weekdays_2024.count()}")
# Weekdays in 2024: 262

weekdays_2024.select('date', 'day_of_week_name').show(10)
```

**Step 3:** Join with business data

```python
# Get company prices
prices = company_model.get_fact_df('fact_prices')

# Join with weekdays only
prices_weekdays = prices.join(
    weekdays_2024.select('date'),
    prices.trade_date == weekdays_2024.date,
    how='inner'  # Inner join keeps only weekdays
)

# All prices are now weekdays only
print(f"Weekday prices: {prices_weekdays.count()}")
```

---

### How to Calculate Fiscal Year Metrics

**Step 1:** Get calendar with fiscal year

```python
# Get all dates in fiscal year 2024
calendar = core_model.get_dimension_df('dim_calendar')

fy2024 = calendar.filter(F.col('fiscal_year') == 2024)

print(f"Days in FY 2024: {fy2024.count()}")

# Show start and end dates
fy2024.select('date', 'fiscal_year', 'fiscal_quarter', 'fiscal_month') \
    .orderBy('date') \
    .show(5)
```

**Step 2:** Aggregate by fiscal quarter

```python
# Load macro unemployment data
macro_model = session.load_model('macro')
unemployment = macro_model.get_fact_df('fact_unemployment')

# Join with calendar
unemployment_with_fiscal = unemployment.join(
    calendar,
    unemployment.date == calendar.date,
    how='left'
)

# Aggregate by fiscal quarter
fiscal_quarterly = unemployment_with_fiscal.groupBy(
    'fiscal_year',
    'fiscal_quarter'
).agg(
    F.avg('value').alias('avg_unemployment_rate')
).orderBy('fiscal_year', 'fiscal_quarter')

fiscal_quarterly.show()
```

**Step 3:** Compare calendar vs fiscal

```python
# Calendar year average
calendar_avg = unemployment.filter(
    F.year('date') == 2024
).agg(
    F.avg('value').alias('calendar_avg')
).first()['calendar_avg']

# Fiscal year average
fiscal_avg = unemployment_with_fiscal.filter(
    F.col('fiscal_year') == 2024
).agg(
    F.avg('value').alias('fiscal_avg')
).first()['fiscal_avg']

print(f"Calendar Year 2024 Average: {calendar_avg:.2f}%")
print(f"Fiscal Year 2024 Average: {fiscal_avg:.2f}%")
```

---

## Usage Examples

---

### 1. Load Core Model

```python
from core.context import RepoContext
from models.api.session import UniversalSession

# Initialize session
ctx = RepoContext.from_repo_root()
session = UniversalSession(ctx.connection, ctx.config_root, ctx.storage_cfg)

# Load core model
core_model = session.load_model('core')
```

### 2. Get Full Calendar

```python
# Get entire calendar dimension
calendar = core_model.get_dimension_df('dim_calendar')

print(f"Total dates: {calendar.count()}")
# Total dates: 18,627 (2000-01-01 to 2050-12-31)

# Show sample
calendar.orderBy('date').show(10)
```

### 3. Filter by Date Range

```python
# Get specific date range
calendar_2024 = calendar.filter(
    (F.col('date') >= '2024-01-01') &
    (F.col('date') <= '2024-12-31')
)

print(f"Days in 2024: {calendar_2024.count()}")
# Days in 2024: 366 (leap year)
```

### 4. Get Only Weekdays

```python
# Get weekdays (Monday-Friday) for 2024
weekdays_2024 = calendar.filter(
    (F.col('year') == 2024) &
    (F.col('is_weekday') == True)
)

print(f"Weekdays in 2024: {weekdays_2024.count()}")
# Weekdays in 2024: 262
```

### 5. Get Only Weekends

```python
# Get weekends (Saturday-Sunday) for 2024
weekends_2024 = calendar.filter(
    (F.col('year') == 2024) &
    (F.col('is_weekend') == True)
)

print(f"Weekends in 2024: {weekends_2024.count()}")
# Weekends in 2024: 104
```

### 6. Get Fiscal Year Dates

```python
# Get all dates in fiscal year 2024
fy2024 = calendar.filter(F.col('fiscal_year') == 2024)

print(f"Days in FY 2024: {fy2024.count()}")

# Show start and end dates
fy2024.select('date', 'fiscal_year', 'fiscal_quarter', 'fiscal_month') \
    .orderBy('date') \
    .show(5)
```

### 7. Get Quarter Dates

```python
# Get Q1 2024 (Jan-Mar)
q1_2024 = calendar.filter(
    (F.col('year') == 2024) &
    (F.col('quarter') == 1)
)

print(f"Days in Q1 2024: {q1_2024.count()}")
# Days in Q1 2024: 91
```

### 8. Get Month Dates

```python
# Get January 2024
jan_2024 = calendar.filter(
    (F.col('year') == 2024) &
    (F.col('month') == 1)
)

print(f"Days in January 2024: {jan_2024.count()}")
# Days in January 2024: 31
```

### 9. Filter by Period Flags

```python
# Get month-end dates for 2024
month_ends = calendar.filter(
    (F.col('year') == 2024) &
    (F.col('is_month_end') == True)
).orderBy('date')

month_ends.select('date', 'month_name', 'day_of_month', 'days_in_month').show()

# +------------+------------+--------------+---------------+
# |   date     | month_name | day_of_month | days_in_month |
# +------------+------------+--------------+---------------+
# | 2024-01-31 | January    |     31       |      31       |
# | 2024-02-29 | February   |     29       |      29       | (leap year)
# | 2024-03-31 | March      |     31       |      31       |
# | ...
```

### 10. Get Quarter Boundaries

```python
# Get quarter-start dates for 2024
quarter_starts = calendar.filter(
    (F.col('year') == 2024) &
    (F.col('is_quarter_start') == True)
).orderBy('date')

quarter_starts.select('date', 'year_quarter', 'quarter').show()

# +------------+--------------+---------+
# |   date     | year_quarter | quarter |
# +------------+--------------+---------+
# | 2024-01-01 | 2024-Q1      |    1    |
# | 2024-04-01 | 2024-Q2      |    2    |
# | 2024-07-01 | 2024-Q3      |    3    |
# | 2024-10-01 | 2024-Q4      |    4    |
# +------------+--------------+---------+
```

### 11. Join with Fact Tables

```python
# Load company model
company_model = session.load_model('company')
prices = company_model.get_fact_df('fact_prices')

# Join prices with calendar to add date attributes
prices_with_dates = prices.join(
    calendar,
    prices.trade_date == calendar.date,
    how='left'
)

# Now can filter by day of week
monday_prices = prices_with_dates.filter(F.col('day_of_week') == 1)

# Or by month
jan_prices = prices_with_dates.filter(F.col('month') == 1)
```

---

## Integration with Other Models

---

All models in de_Funk depend on the Core model for date-based filtering and analysis.

### Company Model Integration

See [[Company Model]] for integration example.

```yaml
# configs/models/company.yaml
depends_on:
  - core  # Uses shared dim_calendar for time-based queries
```

**Usage:**
```python
# Join prices with calendar
prices_with_calendar = session.query("""
    SELECT
        p.trade_date,
        p.ticker,
        p.close,
        c.day_of_week_name,
        c.year_quarter,
        c.is_month_end
    FROM company.fact_prices p
    LEFT JOIN core.dim_calendar c ON p.trade_date = c.date
    WHERE c.year = 2024
""")
```

### Macro Model Integration

See [[Macro Model]] for integration example.

```yaml
# configs/models/macro.yaml
depends_on:
  - core  # Uses shared dim_calendar for time-based queries
```

**Usage:**
```python
# Join unemployment with calendar
unemployment_with_calendar = session.query("""
    SELECT
        u.date,
        u.value AS unemployment_rate,
        c.year,
        c.year_quarter,
        c.month_name
    FROM macro.fact_unemployment u
    LEFT JOIN core.dim_calendar c ON u.date = c.date
    WHERE c.fiscal_year = 2024
""")
```

### Forecast Model Integration

See [[Forecast Model]] for integration example.

```yaml
# configs/models/forecast.yaml
depends_on:
  - core     # Uses shared dim_calendar for time-based queries
  - company  # Forecast model reads from company for training data
```

**Usage:**
```python
# Filter forecasts by weekdays only
weekday_forecasts = session.query("""
    SELECT
        f.forecast_date,
        f.predicted_close,
        c.day_of_week_name
    FROM forecast.forecast_price f
    LEFT JOIN core.dim_calendar c ON f.forecast_date = c.date
    WHERE c.is_weekday = true
""")
```

### City Finance Model Integration

See [[City Finance Model]] for integration example.

```yaml
# configs/models/city_finance.yaml
depends_on:
  - core  # Uses shared dim_calendar for time-based queries
  - macro # Compare local vs national indicators
```

**Usage:**
```python
# Analyze building permits by quarter
permits_by_quarter = session.query("""
    SELECT
        c.year_quarter,
        COUNT(*) AS permit_count,
        SUM(p.total_fee) AS total_fees
    FROM city_finance.fact_building_permits p
    LEFT JOIN core.dim_calendar c ON p.issue_date = c.date
    GROUP BY c.year_quarter
    ORDER BY c.year_quarter
""")
```

---

## Design Decisions

---

### 1. Date Range: 2000-2050

**Decision:** Generate 50+ years of dates (2000-01-01 to 2050-12-31)

**Rationale:**
- Historical data: 2000-2024 (24 years) covers most financial history
- Future forecasts: 2024-2050 (26 years) covers long-term projections
- Small storage footprint: ~18,627 rows × 27 columns = minimal space

**Trade-offs:**
- Could extend to 1900-2100 with minimal cost
- Balance between completeness and relevance

### 2. 27 Date Attributes

**Decision:** Include 27 comprehensive date attributes

**Rationale:**
- Covers all common use cases without requiring joins
- Pre-computed attributes faster than runtime calculations
- Standardizes date logic across models

**Attributes included:**
- Basic: year, quarter, month, day
- Names: month_name, day_of_week_name
- ISO: week_of_year
- Flags: is_weekend, is_weekday, is_month_start, is_month_end, etc.
- Fiscal: fiscal_year, fiscal_quarter, fiscal_month
- Strings: year_month, year_quarter, date_str

### 3. Fiscal Year Configuration

**Decision:** Make fiscal year start month configurable (default: January)

**Rationale:**
- Different organizations have different fiscal calendars
- US Government: October 1 (month 10)
- Many companies: July 1 (month 7)
- Default to calendar year for simplicity

**Configuration:**
```yaml
fiscal_year_start_month: 1  # January (calendar year)
# Change to 7 for fiscal year starting July 1
```

### 4. Weekend Days: Saturday & Sunday

**Decision:** Default weekend to Saturday (6) and Sunday (7)

**Rationale:**
- Standard for US and most Western countries
- Can be overridden for Middle East (Friday-Saturday)

**Configuration:**
```yaml
weekend_days: [6, 7]  # Saturday, Sunday
# Change to [5, 6] for Middle East (Friday, Saturday)
```

### 5. No Partitioning

**Decision:** Don't partition dim_calendar

**Rationale:**
- Small table (~18,627 rows)
- Frequently joined (need all dates available)
- Partitioning would hurt join performance

### 6. Day of Week: 1=Monday

**Decision:** Use ISO 8601 standard (1=Monday, 7=Sunday)

**Rationale:**
- International standard
- Business week starts Monday
- Consistent with Python/Pandas default

**Alternative:**
- US convention: 0=Sunday, 6=Saturday
- Could add `day_of_week_us` column if needed

### 7. Period Flags vs. Runtime Calculation

**Decision:** Pre-compute all period flags (is_month_start, is_quarter_end, etc.)

**Rationale:**
- Faster queries (no need to calculate)
- Consistent logic across queries
- Minimal storage overhead (boolean columns)

**Alternative:**
- Calculate at query time: `day_of_month = 1` for month start
- Would be slower and inconsistent

### 8. String Formats

**Decision:** Include pre-formatted strings (year_month, year_quarter, date_str)

**Rationale:**
- Common grouping dimensions for charts/reports
- Faster than formatting at query time
- Consistent format across analyses

**Examples:**
- `year_month`: "2024-01", "2024-02"
- `year_quarter`: "2024-Q1", "2024-Q2"
- `date_str`: "2024-11-08"

### 9. No Holiday Flags (Yet)

**Decision:** Holiday configuration defined but not yet implemented

**Rationale:**
- Holidays vary by country and organization
- Fixed holidays easy (New Year, Christmas)
- Floating holidays complex (Easter, Thanksgiving)

**Future enhancement:**
```yaml
holidays:
  - name: "New Year's Day"
    type: "fixed"
    month: 1
    day: 1

  - name: "Thanksgiving"
    type: "floating"
    rule: "4th Thursday of November"
```

### 10. No Time Component

**Decision:** Calendar is date-only (no time/timestamp)

**Rationale:**
- Most analytics at daily grain or higher
- Intraday analysis uses different dimensions
- Keeps calendar simple and focused

**Alternative:**
- Could create separate `dim_time` for intraday
- Would have ~86,400 rows per day (seconds)

---

## Summary

---

The Core model provides the foundation for all date-based analysis in de_Funk:

- **Comprehensive** - 27 attributes cover all common use cases
- **Performant** - Pre-computed attributes for fast queries
- **Flexible** - Configurable fiscal year and weekend definitions
- **Universal** - Used by all other models
- **Standards-Based** - ISO 8601 day of week, standard date formats

By centralizing date logic in a shared dimension, we ensure:
- **Consistency** - Same date attributes across all models
- **Simplicity** - No need to recalculate date attributes
- **Performance** - Efficient joins with small, static dimension

---

## Related Documentation

---

### Model Documentation
- [[Company Model]] - Integration example
- [[Macro Model]] - Economic indicators
- [[Forecast Model]] - ML predictions
- [[City Finance Model]] - Municipal data
- [[Models Framework Overview]] - Framework concepts

### Architecture Documentation
- [[MODEL_ARCHITECTURE_MAPPING]] - Complete architecture mapping
- [[Storage/Silver Layer]] - Silver layer storage strategy
- [[Models System/Base Model]] - Base model framework
- [[Bronze Storage]] - Seed data storage

---

**Tags:** #reference #component/model #source/generated #status/stable #component/storage/silver #component/models-system/base #architecture/foundation #pattern/reference-only

**Last Updated:** 2024-11-08
**Model Version:** 1.0
**Dependencies:** None (foundation model)
**Used By:** All other models
