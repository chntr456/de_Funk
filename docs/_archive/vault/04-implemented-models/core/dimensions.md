# Core Dimensions

**Calendar dimension schema reference**

---

## dim_calendar

**Purpose**: Master calendar lookup table for all date-based analysis

**Primary Key**: `date`

**Record Count**: ~10,000+ (daily granularity)

---

## Schema

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `date` | date | Calendar date (PK) | `2024-01-15` |
| `year` | int | Calendar year | `2024` |
| `quarter` | int | Quarter (1-4) | `1` |
| `month` | int | Month (1-12) | `1` |
| `month_name` | string | Full month name | `January` |
| `month_abbr` | string | Month abbreviation | `Jan` |
| `week_of_year` | int | ISO week number | `3` |
| `day_of_month` | int | Day of month (1-31) | `15` |
| `day_of_week` | int | Day of week (0=Mon, 6=Sun) | `0` |
| `day_of_week_name` | string | Full day name | `Monday` |
| `day_of_week_abbr` | string | Day abbreviation | `Mon` |
| `day_of_year` | int | Day of year (1-366) | `15` |
| `is_weekend` | boolean | Saturday or Sunday | `false` |
| `is_weekday` | boolean | Monday-Friday | `true` |
| `is_month_start` | boolean | First day of month | `false` |
| `is_month_end` | boolean | Last day of month | `false` |
| `is_quarter_start` | boolean | First day of quarter | `false` |
| `is_quarter_end` | boolean | Last day of quarter | `false` |
| `is_year_start` | boolean | January 1st | `false` |
| `is_year_end` | boolean | December 31st | `false` |
| `days_in_month` | int | Days in the month | `31` |
| `year_month` | string | YYYY-MM format | `2024-01` |
| `year_quarter` | string | YYYY-Q# format | `2024-Q1` |
| `date_str` | string | ISO date string | `2024-01-15` |
| `fiscal_year` | int | Fiscal year | `2024` |
| `fiscal_quarter` | int | Fiscal quarter | `3` |
| `fiscal_month` | int | Fiscal month | `7` |

---

## Usage Examples

### Filter by Date Attributes

```sql
-- Get all Mondays in Q1 2024
SELECT date
FROM core.dim_calendar
WHERE year = 2024
  AND quarter = 1
  AND day_of_week = 0
```

### Join with Fact Table

```sql
-- Stock prices with calendar attributes
SELECT
    p.ticker,
    p.close,
    c.year,
    c.quarter,
    c.month_name,
    c.is_weekend
FROM stocks.fact_stock_prices p
JOIN core.dim_calendar c ON p.trade_date = c.date
WHERE c.year = 2024
```

### Aggregate by Period

```sql
-- Monthly average prices
SELECT
    c.year_month,
    AVG(p.close) as avg_close
FROM stocks.fact_stock_prices p
JOIN core.dim_calendar c ON p.trade_date = c.date
GROUP BY c.year_month
ORDER BY c.year_month
```

### Filter Weekdays Only

```sql
-- Trading days (exclude weekends)
SELECT p.*
FROM stocks.fact_stock_prices p
JOIN core.dim_calendar c ON p.trade_date = c.date
WHERE c.is_weekday = true
```

---

## Fiscal Calendar

The fiscal calendar assumes **July 1 fiscal year start** (common for government/education):

| Calendar Month | Fiscal Month | Fiscal Quarter |
|----------------|--------------|----------------|
| July | 1 | Q1 |
| August | 2 | Q1 |
| September | 3 | Q1 |
| October | 4 | Q2 |
| November | 5 | Q2 |
| December | 6 | Q2 |
| January | 7 | Q3 |
| February | 8 | Q3 |
| March | 9 | Q3 |
| April | 10 | Q4 |
| May | 11 | Q4 |
| June | 12 | Q4 |

**Note**: Fiscal year is the year containing the fiscal year end (June).

---

## Related Documentation

- [Core Overview](overview.md)
- [Cross-Model References](../../02-graph-architecture/cross-model-references.md)
