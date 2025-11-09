---
title: "Employment Facts"
tags: [economics/bls, component/model, concept/facts, concept/time-series]
aliases: ["Employment Facts", "fact_employment", "Total Nonfarm Employment", "Job Growth"]
---

# Employment Facts

---

Monthly total nonfarm employment from the Bureau of Labor Statistics, measuring the number of paid employees in the U.S. excluding farm workers, private household employees, and non-profit organization employees.

**Table:** `fact_employment`
**Grain:** One row per series per month
**Storage:** `storage/silver/macro/facts/fact_employment`
**Partitioned By:** `year`

---

## Purpose

---

Total nonfarm employment is a key indicator of economic growth and job market health, tracking the total number of paid jobs in the U.S. economy.

**Use Cases:**
- Economic growth monitoring
- Job creation/loss trends
- Recession identification
- Business cycle analysis
- Labor market health assessment

---

## Schema

---

**Grain:** One row per month

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| **series_id** | string | BLS series identifier | "CES0000000001" |
| **date** | date | First day of month | 2024-11-01 |
| **year** | integer | Year | 2024 |
| **period** | string | BLS period code | "M11" |
| **value** | double | Employment (thousands) | 159,358 |
| **period_name** | string | Human-readable period | "November" |

**Partitioned By:** `year`

---

## Sample Data

---

```
+--------------+------------+------+--------+---------+-------------+
| series_id    | date       | year | period | value   | period_name |
+--------------+------------+------+--------+---------+-------------+
| CES0000000001| 2024-11-01 | 2024 | M11    | 159358  | November    |
| CES0000000001| 2024-10-01 | 2024 | M10    | 159189  | October     |
| CES0000000001| 2024-09-01 | 2024 | M09    | 159021  | September   |
| CES0000000001| 2024-08-01 | 2024 | M08    | 158845  | August      |
+--------------+------------+------+--------+---------+-------------+
```

---

## Data Source

---

**Provider:** Bureau of Labor Statistics (BLS)
**Survey:** Current Employment Statistics (CES)
**Series ID:** `CES0000000001` (Total Nonfarm, Seasonally Adjusted)
**Units:** Thousands of jobs
**API Endpoint:** `/publicAPI/v2/timeseries/data/{series_id}`
**Bronze Table:** `bronze.bls_employment`
**Update Frequency:** Monthly (first Friday of each month)

**Transformation:**
```yaml
from: bronze.bls_employment
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

### Get Employment Data

```python
from models.api.session import UniversalSession
from core.context import RepoContext

ctx = RepoContext.from_repo_root()
session = UniversalSession(ctx.connection, ctx.config_root, ctx.storage_cfg)

# Get employment facts
macro = session.load_model('macro')
employment = macro.get_fact_df('fact_employment').to_pandas()

# Sort by date
employment = employment.sort_values('date')

print(employment.tail(12))  # Last 12 months
```

### Calculate Job Growth

```python
# Month-over-month job change
employment = employment.sort_values('date')
employment['jobs_added'] = employment['value'].diff()

# Year-over-year growth
employment['yoy_growth'] = employment['value'].diff(periods=12)
employment['yoy_growth_pct'] = employment['value'].pct_change(periods=12) * 100

print(employment[['date', 'value', 'jobs_added', 'yoy_growth']].tail(12))
```

### Identify Employment Cycles

```python
# Find peaks and troughs
employment = employment.sort_values('date')

# 6-month moving average
employment['ma_6m'] = employment['value'].rolling(window=6).mean()

# Identify turning points (simplified)
employment['is_peak'] = (employment['value'] > employment['value'].shift(1)) & \
                        (employment['value'] > employment['value'].shift(-1))

employment['is_trough'] = (employment['value'] < employment['value'].shift(1)) & \
                          (employment['value'] < employment['value'].shift(-1))

# Show peaks and troughs
print("Peaks:")
print(employment[employment['is_peak']][['date', 'value']])

print("\nTroughs:")
print(employment[employment['is_trough']][['date', 'value']])
```

### Recession Detection

```python
# Sahm-like rule for employment: 2 consecutive months of negative growth
employment = employment.sort_values('date')
employment['jobs_added'] = employment['value'].diff()

# 2-month sum of job changes
employment['job_change_2m'] = employment['jobs_added'].rolling(window=2).sum()

# Recession signal: sustained job losses
recession_signals = employment[employment['job_change_2m'] < -500]  # 500k jobs lost

print("Potential Recession Periods:")
print(recession_signals[['date', 'value', 'job_change_2m']])
```

### Visualize Employment Trends

```python
import matplotlib.pyplot as plt

# Filter to recent decades
recent = employment[employment['date'] >= '2000-01-01']

# Calculate monthly job changes
recent['jobs_added'] = recent['value'].diff()

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))

# Total employment
ax1.plot(recent['date'], recent['value'], linewidth=2)
ax1.set_title('Total Nonfarm Employment (Thousands)')
ax1.set_ylabel('Employment (thousands)')
ax1.grid(True, alpha=0.3)

# Monthly job changes
ax2.bar(recent['date'], recent['jobs_added'], width=20, alpha=0.7)
ax2.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
ax2.set_title('Monthly Job Changes')
ax2.set_ylabel('Jobs Added (thousands)')
ax2.set_xlabel('Date')
ax2.grid(True, alpha=0.3)

plt.tight_layout()
plt.show()
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

## Employment Coverage

---

### Included Sectors
- **Goods-producing:** Manufacturing, construction, mining
- **Service-providing:** Retail, healthcare, education, finance, hospitality

### Excluded Categories
- Farm workers
- Self-employed (unincorporated)
- Private household workers
- Unpaid family workers
- Active military personnel

---

## Historical Context

---

### Normal Range
- **Typical growth:** 100-200k jobs/month
- **Strong growth:** 200k+ jobs/month
- **Weak growth:** 0-100k jobs/month
- **Job losses:** Negative (recession indicator)

### Historical Extremes
- **COVID-19 Losses:** -20.8M jobs (March-April 2020)
- **Great Recession:** -8.7M jobs (2008-2010)
- **Strongest Recovery:** +4.8M jobs (May 2020, post-COVID bounce)

### Current Levels
- **Pre-COVID (Feb 2020):** 152.5M
- **COVID Low (April 2020):** 130.4M
- **Recovery (2024):** 159M+ (record high)

---

## Design Decisions

---

### Why use total nonfarm?

**Decision:** Track total nonfarm employment (CES0000000001)

**Rationale:**
- **Comprehensive** - Broadest measure of job market
- **Standard** - Most commonly cited employment stat
- **Timely** - Released monthly, quickly available
- **Reliable** - Large sample size, well-established

### Why thousands as unit?

**Decision:** Store values in thousands (not raw count)

**Rationale:**
- **BLS standard** - Native API format
- **Readability** - Easier to interpret (159,358 vs 159,358,000)
- **Precision** - Sufficient for economic analysis
- **Consistency** - Matches BLS publications

---

## Related Documentation

---

### Model Documentation
- [[Macro Model Overview]] - Parent model
- [[Economic Series Dimension]] - Series metadata
- [[Unemployment Facts]] - Unemployment rate
- [[Wages Facts]] - Wage data

### Architecture Documentation
- [[Data Pipeline/BLS]] - API ingestion
- [[Facets/Economics]] - Economic normalization
- [[Bronze Storage]] - Raw BLS data

### External Resources
- [BLS Employment Data](https://www.bls.gov/ces/)
- [Employment Situation Summary](https://www.bls.gov/news.release/empsit.toc.htm)

---

**Tags:** #economics/bls #component/model #concept/facts #concept/time-series

**Last Updated:** 2024-11-08
**Table:** fact_employment
**Grain:** One row per month
