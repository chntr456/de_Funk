---
title: "Calendar Dimension"
tags: [reference, component/model, concept/dimensional-modeling, concept/time-intelligence]
aliases: ["Calendar", "Date Dimension", "dim_calendar", "Time Dimension"]
---

# Calendar Dimension

---

The Calendar dimension provides comprehensive date attributes for time-based analysis across all models. It serves as the foundation for temporal queries and time intelligence.

**Table:** `dim_calendar`
**Primary Key:** `date`
**Storage:** `storage/silver/core/dims/dim_calendar`

---

## Purpose

---

The calendar dimension enables:
- **Date filtering** - Query by date ranges, fiscal periods
- **Time aggregation** - Group by week, month, quarter, year
- **Business logic** - Weekday/weekend, month-end, fiscal periods
- **Cross-model joins** - Consistent time dimension across all models

**Used By:** ALL models (Company, Forecast, Macro, City Finance)

---

## Schema

---

**Grain:** One row per day
**Range:** 2000-01-01 to 2050-12-31 (50 years)
**Total Rows:** ~18,250 dates

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| **date** | date | Calendar date (PK) | 2024-11-08 |
| **year** | integer | Calendar year | 2024 |
| **quarter** | integer | Calendar quarter (1-4) | 4 |
| **month** | integer | Month number (1-12) | 11 |
| **month_name** | string | Full month name | "November" |
| **month_abbr** | string | Month abbreviation | "Nov" |
| **week_of_year** | integer | ISO week number (1-53) | 45 |
| **day_of_month** | integer | Day of month (1-31) | 8 |
| **day_of_week** | integer | Day of week (1=Mon, 7=Sun) | 5 |
| **day_of_week_name** | string | Full day name | "Friday" |
| **day_of_week_abbr** | string | Day abbreviation | "Fri" |
| **day_of_year** | integer | Day of year (1-366) | 313 |
| **is_weekend** | boolean | Saturday or Sunday | false |
| **is_weekday** | boolean | Monday through Friday | true |
| **is_month_start** | boolean | First day of month | false |
| **is_month_end** | boolean | Last day of month | false |
| **is_quarter_start** | boolean | First day of quarter | false |
| **is_quarter_end** | boolean | Last day of quarter | false |
| **is_year_start** | boolean | First day of year | false |
| **is_year_end** | boolean | Last day of year | false |
| **fiscal_year** | integer | Fiscal year (configurable) | 2024 |
| **fiscal_quarter** | integer | Fiscal quarter (1-4) | 2 |
| **fiscal_month** | integer | Fiscal month (1-12) | 5 |
| **days_in_month** | integer | Number of days in month | 30 |
| **year_month** | string | YYYY-MM format | "2024-11" |
| **year_quarter** | string | YYYY-Q# format | "2024-Q4" |
| **date_str** | string | Date as string | "2024-11-08" |

**Total Attributes:** 27 date-related columns

---

## Sample Data

---

```
+------------+------+---------+-------+------------+------------+
| date       | year | quarter | month | month_name | day_of_week|
+------------+------+---------+-------+------------+------------+
| 2024-11-08 | 2024 | 4       | 11    | November   | 5          |
| 2024-11-09 | 2024 | 4       | 11    | November   | 6          |
| 2024-11-10 | 2024 | 4       | 11    | November   | 7          |
+------------+------+---------+-------+------------+------------+

+-------------+------------+-----------+-------------+----------------+
| is_weekend  | is_weekday | is_month_start | fiscal_year | year_quarter |
+-------------+------------+----------------+-------------+--------------+
| false       | true       | false          | 2024        | 2024-Q4      |
| true        | false      | false          | 2024        | 2024-Q4      |
| true        | false      | false          | 2024        | 2024-Q4      |
+-------------+------------+----------------+-------------+--------------+
```

---

## Calendar Generation

---

**Source:** Generated from seed configuration
**Configuration:** `configs/models/core.yaml`

```yaml
calendar_config:
  start_date: "2000-01-01"
  end_date: "2050-12-31"
  fiscal_year_start_month: 1  # January (standard calendar year)
  weekend_days: [6, 7]  # Saturday=6, Sunday=7
```

**Generation Process:**
1. Create date range from start to end
2. Calculate all date attributes
3. Apply fiscal year rules
4. Mark weekends and special dates
5. Write to Bronze then Silver

**Bronze Table:** `bronze.calendar_seed`
**Transformation:** Enrichment with calculated attributes

---

## Fiscal Year Configuration

---

**Default:** Fiscal year = Calendar year (starts January 1)

**Customizable:** Change `fiscal_year_start_month` in config
- **January (1):** Standard calendar year
- **July (7):** US Federal fiscal year
- **October (10):** Many corporate fiscal years

**Fiscal Logic:**
- If month >= fiscal_start_month: fiscal_year = calendar_year
- If month < fiscal_start_month: fiscal_year = calendar_year - 1

**Example (July start):**
- 2024-08-15: fiscal_year = 2024, fiscal_quarter = 1
- 2024-06-15: fiscal_year = 2023, fiscal_quarter = 4

---

## Usage Examples

---

### Filter by Date Range

```python
from models.api.session import UniversalSession
from core.context import RepoContext

ctx = RepoContext.from_repo_root()
session = UniversalSession(ctx.connection, ctx.config_root, ctx.storage_cfg)

# Get last 30 days
calendar = session.get_table('core', 'dim_calendar')
recent = calendar.filter(
    calendar['date'] >= '2024-10-09'
).to_pandas()

print(recent[['date', 'day_of_week_name', 'is_weekend']])
```

### Filter by Weekdays Only

```python
# Get all weekdays in November 2024
weekdays = calendar.filter(
    (calendar['year'] == 2024) &
    (calendar['month'] == 11) &
    (calendar['is_weekday'] == True)
).to_pandas()

print(f"Weekdays in November 2024: {len(weekdays)}")
```

### Filter by Fiscal Quarter

```python
# Get Q4 fiscal dates
q4 = calendar.filter(
    (calendar['fiscal_year'] == 2024) &
    (calendar['fiscal_quarter'] == 4)
).to_pandas()

print(q4[['date', 'fiscal_month', 'quarter']].head())
```

### Month-End Analysis

```python
# Get all month-end dates in 2024
month_ends = calendar.filter(
    (calendar['year'] == 2024) &
    (calendar['is_month_end'] == True)
).to_pandas()

print("Month-end dates in 2024:")
print(month_ends[['date', 'month_name']])
```

### Join with Price Data

```python
# Join calendar with stock prices
company = session.load_model('company')
prices = company.get_fact_df('fact_prices').to_pandas()

# Add day of week
prices_with_cal = prices.merge(
    calendar[['date', 'day_of_week_name', 'is_weekend']].to_pandas(),
    left_on='trade_date',
    right_on='date',
    how='left'
)

# Average volume by day of week
avg_volume_by_day = prices_with_cal.groupby('day_of_week_name')['volume'].mean()
print(avg_volume_by_day)
```

### Time Series Gaps

```python
# Find missing dates in price data
all_dates = set(calendar.filter(
    (calendar['is_weekday'] == True) &
    (calendar['date'] >= '2024-01-01')
).to_pandas()['date'])

price_dates = set(prices[prices['ticker'] == 'AAPL']['trade_date'])

missing = all_dates - price_dates
print(f"Missing trading days: {sorted(missing)}")
```

---

## Relationships

---

### Used By (Join Keys)

All models can join to calendar via date columns:

- **[[Company Model]]** - `fact_prices.trade_date`, `fact_news.publish_date`
- **[[Forecast Model]]** - `fact_forecasts.forecast_date`, `fact_forecasts.prediction_date`
- **[[Macro Model]]** - `fact_unemployment.date`, `fact_cpi.date`
- **[[City Finance Model]]** - `fact_local_unemployment.date`, `fact_building_permits.issue_date`

**Join Pattern:**
```sql
SELECT *
FROM fact_prices p
JOIN dim_calendar c ON p.trade_date = c.date
WHERE c.is_weekday = true
  AND c.fiscal_quarter = 4
```

---

## Design Decisions

---

### Why 50-Year Range?

**Decision:** 2000-2050 date range

**Rationale:**
- Covers historical analysis (20+ years back)
- Supports long-term forecasting (25+ years forward)
- Small table size (~18K rows)
- Avoids regeneration for decades

### Why 27 Attributes?

**Decision:** Comprehensive date attribute set

**Rationale:**
- Eliminates runtime calculations
- Supports diverse analytics needs
- Fiscal year flexibility
- Business logic pre-computed
- Minimal storage cost

### Why Calendar Year Default for Fiscal?

**Decision:** Fiscal year = Calendar year by default

**Rationale:**
- Most intuitive for users
- Easy to customize if needed
- Matches most data sources
- Simple configuration change

---

## Future Enhancements

---

### Planned Additions

- **Holiday dimension** - US federal holidays, market holidays
- **Business day calculations** - Working day counts, lags
- **Week start configuration** - Configurable week start day
- **Custom calendar types** - 4-4-5 retail calendar, ISO 8601

### Geography Integration

**Future:** Add geographic time zones
- **UTC offsets** - Time zone conversions
- **Daylight saving** - DST transitions
- **Regional calendars** - Country-specific holidays

See [[Geography]] (planned) for geographic extensions.

---

## Related Documentation

---

### Model Documentation
- [[Core Model Overview]] - Parent model
- [[Geography]] - Planned geographic dimension
- [[Company Model]] - Primary consumer
- [[Macro Model]] - Economic time series

### Architecture Documentation
- [[Bronze Storage]] - Calendar seed data
- [[Silver Storage]] - Calendar dimension storage
- [[Models System/Base]] - Dimension building

### How-To Guides
- [[How to Use Calendar Dimension]] - Filtering and joins
- [[How to Filter by Fiscal Periods]] - Fiscal year queries
- [[How to Create a Model]] - Using calendar in your model

---

**Tags:** #reference #component/model #concept/dimensional-modeling #concept/time-intelligence #architecture/foundation

**Last Updated:** 2024-11-08
**Table:** dim_calendar
**Grain:** One row per day (18,250 rows for 2000-2050)
