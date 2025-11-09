---
title: "Wages Facts"
tags: [economics/bls, component/model, concept/facts, concept/time-series]
aliases: ["Wages Facts", "fact_wages", "Average Hourly Earnings", "Wage Growth"]
---

# Wages Facts

---

Monthly average hourly earnings for all employees in the total private sector from the Bureau of Labor Statistics, measuring wage trends and income growth.

**Table:** `fact_wages`
**Grain:** One row per series per month
**Storage:** `storage/silver/macro/facts/fact_wages`
**Partitioned By:** `year`

---

## Purpose

---

Average hourly earnings track wage growth and income trends, key indicators of worker purchasing power and inflation pressures.

**Use Cases:**
- Wage growth analysis
- Real income calculations
- Inflation expectations
- Consumer spending forecasts
- Labor market tightness assessment

---

## Schema

---

**Grain:** One row per month

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| **series_id** | string | BLS series identifier | "CES0500000003" |
| **date** | date | First day of month | 2024-11-01 |
| **year** | integer | Year | 2024 |
| **period** | string | BLS period code | "M11" |
| **value** | double | Hourly earnings ($) | 35.42 |
| **period_name** | string | Human-readable period | "November" |

**Partitioned By:** `year`

---

## Sample Data

---

```
+--------------+------------+------+--------+-------+-------------+
| series_id    | date       | year | period | value | period_name |
+--------------+------------+------+--------+-------+-------------+
| CES0500000003| 2024-11-01 | 2024 | M11    | 35.42 | November    |
| CES0500000003| 2024-10-01 | 2024 | M10    | 35.36 | October     |
| CES0500000003| 2024-09-01 | 2024 | M09    | 35.28 | September   |
| CES0500000003| 2024-08-01 | 2024 | M08    | 35.21 | August      |
+--------------+------------+------+--------+-------+-------------+
```

---

## Data Source

---

**Provider:** Bureau of Labor Statistics (BLS)
**Survey:** Current Employment Statistics (CES)
**Series ID:** `CES0500000003` (Average Hourly Earnings - Total Private, Seasonally Adjusted)
**Units:** U.S. dollars
**API Endpoint:** `/publicAPI/v2/timeseries/data/{series_id}`
**Bronze Table:** `bronze.bls_wages`
**Update Frequency:** Monthly (first Friday of each month)

**Transformation:**
```yaml
from: bronze.bls_wages
select:
  series_id: series_id
  date: date
  year: year
  period: period
  value: value
  period_name: period_name
```

---

## Usage Examples

---

### Get Wage Data

```python
from models.api.session import UniversalSession
from core.context import RepoContext

ctx = RepoContext.from_repo_root()
session = UniversalSession(ctx.connection, ctx.config_root, ctx.storage_cfg)

# Get wages facts
macro = session.load_model('macro')
wages = macro.get_fact_df('fact_wages').to_pandas()

# Sort by date
wages = wages.sort_values('date')

print(wages.tail(12))  # Last 12 months
```

### Calculate Wage Growth

```python
# Year-over-year wage growth
wages = wages.sort_values('date')
wages['wage_growth_yoy'] = wages['value'].pct_change(periods=12) * 100

# Month-over-month growth
wages['wage_growth_mom'] = wages['value'].pct_change() * 100

print(wages[['date', 'value', 'wage_growth_yoy', 'wage_growth_mom']].tail(12))
```

### Calculate Real Wages (Inflation-Adjusted)

```python
# Get CPI data
cpi = macro.get_fact_df('fact_cpi').to_pandas()

# Merge wages with CPI
merged = wages.merge(cpi[['date', 'value']], on='date', suffixes=('_wage', '_cpi'))

# Latest CPI for normalization
latest_cpi = merged['value_cpi'].max()

# Calculate real wages
merged['real_wage'] = merged['value_wage'] * (latest_cpi / merged['value_cpi'])

# Real wage growth
merged = merged.sort_values('date')
merged['real_wage_growth'] = merged['real_wage'].pct_change(periods=12) * 100

print(merged[['date', 'value_wage', 'real_wage', 'real_wage_growth']].tail(12))
```

### Compare to Inflation

```python
import matplotlib.pyplot as plt

# Merge with CPI
merged = wages.merge(cpi[['date', 'value']], on='date', suffixes=('', '_cpi'))

# Calculate growth rates
merged = merged.sort_values('date')
merged['wage_growth'] = merged['value'].pct_change(periods=12) * 100
merged['inflation_rate'] = merged['value_cpi'].pct_change(periods=12) * 100

# Real wage growth
merged['real_wage_growth'] = merged['wage_growth'] - merged['inflation_rate']

# Plot
recent = merged[merged['date'] >= '2010-01-01']

plt.figure(figsize=(12, 6))
plt.plot(recent['date'], recent['wage_growth'], label='Nominal Wage Growth', linewidth=2)
plt.plot(recent['date'], recent['inflation_rate'], label='Inflation Rate', linewidth=2)
plt.plot(recent['date'], recent['real_wage_growth'], label='Real Wage Growth', linewidth=2, linestyle='--')
plt.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
plt.title('Wage Growth vs Inflation')
plt.ylabel('Year-over-Year Growth (%)')
plt.xlabel('Date')
plt.legend()
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.show()
```

### Calculate Annual Salary Equivalent

```python
# Estimate annual salary (assuming 2080 hours/year)
wages['annual_salary_equiv'] = wages['value'] * 2080

print(wages[['date', 'value', 'annual_salary_equiv']].tail(12))
```

---

## Relationships

---

### Foreign Keys

- **series_id** → [[Economic Series Dimension]].series_id
- **date** → [[Calendar]].date

### Used By

- **economic_indicators_wide** - Materialized view with all indicators

---

## Wage Calculation

---

### What is Measured

**Average Hourly Earnings:**
- Total private sector wages / total hours worked
- Covers all production and nonsupervisory employees
- **Excludes:** Benefits, bonuses, commissions (base wage only)

### Coverage

**Included:**
- Production workers (manufacturing)
- Non-supervisory workers (services)
- Hourly and salaried employees

**Excluded:**
- Supervisors above working level
- Self-employed
- Farm workers
- Government employees

---

## Historical Context

---

### Normal Range
- **Typical growth:** 2-4% annually
- **Strong growth:** 4%+ (tight labor market)
- **Weak growth:** 0-2% (slack labor market)
- **Declining:** Negative (rare, recession)

### Recent Trends
- **Pre-COVID (2019):** ~$28/hour
- **COVID Era (2020-2021):** Rapid growth (composition effect)
- **Inflation Era (2022-2023):** Nominal growth strong, real wages lagged
- **Current (2024):** ~$35/hour

### Key Insights
- **COVID paradox:** Wages appeared to surge (low-wage job losses)
- **Inflation lag:** Wages typically trail inflation
- **Real wages:** Often stagnant despite nominal growth

---

## Design Decisions

---

### Why total private sector?

**Decision:** Track total private (CES0500000003) not all employees

**Rationale:**
- **Consistency** - Excludes volatile government wages
- **Representative** - Covers ~83% of workforce
- **Historical** - Longer data series
- **Comparable** - Standard benchmark

### Why exclude benefits?

**Decision:** Track cash wages only (BLS standard)

**Rationale:**
- **Timely** - Available monthly (benefits lag)
- **Comparable** - Consistent measurement
- **Simplicity** - Easy to understand
- **Standard** - What BLS reports

**Note:** Total compensation (wages + benefits) available in separate BLS series

---

## Related Documentation

---

### Model Documentation
- [[Macro Model Overview]] - Parent model
- [[Economic Series Dimension]] - Series metadata
- [[CPI Facts]] - Inflation for real wage calculations
- [[Employment Facts]] - Job market context

### Architecture Documentation
- [[Data Pipeline/BLS]] - API ingestion
- [[Facets/Economics]] - Economic normalization
- [[Bronze Storage]] - Raw BLS data

### External Resources
- [BLS Wage Data](https://www.bls.gov/ces/)
- [Real Earnings Summary](https://www.bls.gov/news.release/realer.toc.htm)

---

**Tags:** #economics/bls #component/model #concept/facts #concept/time-series

**Last Updated:** 2024-11-08
**Table:** fact_wages
**Grain:** One row per month
