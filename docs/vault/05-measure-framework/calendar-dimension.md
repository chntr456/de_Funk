# Calendar Dimension

**Shared time dimension across all models**

Model: `core`
File: `configs/models/core.yaml`

---

## Overview

The **core** model provides a universal calendar dimension (`dim_calendar`) that serves as the foundation for all time-based analysis across de_Funk.

**Design Pattern**: Foundation model (Tier 0) - all other models depend on it.

---

## dim_calendar Schema

```yaml
dim_calendar:
  columns:
    date: date                    # Primary key
    year: integer
    quarter: integer
    month: integer
    week: integer
    day_of_week: integer
    day_name: string
    month_name: string
    is_weekend: boolean
    is_holiday: boolean
    fiscal_year: integer
    fiscal_quarter: integer
```

---

## Usage Pattern

All models with time-series data join to `core.dim_calendar`:

```yaml
# equity.yaml
edges:
  - from: fact_equity_prices
    to: core.dim_calendar
    on: ["trade_date=date"]
    type: left
```

**Benefits**:
- Consistent time attributes across all models
- Calendar-based filtering (e.g., weekends, quarters)
- Fiscal year calculations
- No duplicate calendar logic in each model

---

## Cross-Model References

All time-based models reference `core.dim_calendar`:

| Model | Fact Table | Join Column | Purpose |
|-------|-----------|-------------|---------|
| equity | fact_equity_prices | trade_date | Stock price dates |
| macro | fact_unemployment | date | Economic indicator dates |
| city_finance | fact_local_unemployment | date | Municipal data dates |
| etf | fact_etf_prices | trade_date | ETF price dates |
| forecast | fact_forecasts | prediction_date | Forecast dates |

---

## Calendar Population

**Build Process**: Calendar is pre-populated during core model build

**Date Range**: Typically covers historical data range + future dates for forecasting

**Example**:
```python
# Core model build generates calendar from 2020-01-01 to 2030-12-31
date_range = pd.date_range(start='2020-01-01', end='2030-12-31', freq='D')
calendar_df = pd.DataFrame({'date': date_range})
# ... add year, quarter, month, etc.
```

---

## Common Filters

**Quarter Filter**:
```sql
WHERE quarter = 2 AND year = 2024
```

**Exclude Weekends**:
```sql
WHERE is_weekend = FALSE
```

**Fiscal Year**:
```sql
WHERE fiscal_year = 2024
```

---

## Related Documentation

- [Core Model](implemented-models.md#core) - Complete core model documentation
- [Dependency Resolution](../02-graph-architecture/dependency-resolution.md) - Tier 0 foundation pattern
- [Cross-Model References](../02-graph-architecture/cross-model-references.md) - How models reference calendar
