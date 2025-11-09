---
title: "Unemployment Facts"
tags: [economics/bls, component/model, concept/facts, concept/time-series]
aliases: ["Unemployment Facts", "fact_unemployment", "Unemployment Rate"]
---

# Unemployment Facts

---

Monthly national unemployment rate from the Bureau of Labor Statistics (BLS), measuring the percentage of the civilian labor force that is unemployed and actively seeking employment.

**Table:** `fact_unemployment`
**Grain:** One row per series per month
**Storage:** `storage/silver/macro/facts/fact_unemployment`
**Partitioned By:** `year`

---

## Purpose

---

The unemployment rate is a key indicator of labor market health and economic conditions, used for economic analysis, policy decisions, and market forecasting.

**Use Cases:**
- Economic cycle analysis
- Labor market health monitoring
- Correlation with stock market performance
- Federal Reserve policy prediction
- Recession detection

---

## Schema

---

**Grain:** One row per month

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| **series_id** | string | BLS series identifier | "LNS14000000" |
| **date** | date | First day of month | 2024-11-01 |
| **year** | integer | Year | 2024 |
| **period** | string | BLS period code | "M11" |
| **value** | double | Unemployment rate (%) | 3.7 |
| **period_name** | string | Human-readable period | "November" |

**Partitioned By:** `year`

---

## Sample Data

---

```
+--------------+------------+------+--------+-------+-------------+
| series_id    | date       | year | period | value | period_name |
+--------------+------------+------+--------+-------+-------------+
| LNS14000000  | 2024-11-01 | 2024 | M11    | 3.7   | November    |
| LNS14000000  | 2024-10-01 | 2024 | M10    | 3.8   | October     |
| LNS14000000  | 2024-09-01 | 2024 | M09    | 4.1   | September   |
| LNS14000000  | 2024-08-01 | 2024 | M08    | 3.8   | August      |
+--------------+------------+------+--------+-------+-------------+
```

---

## Data Source

---

**Provider:** Bureau of Labor Statistics (BLS)
**Survey:** Current Population Survey (CPS)
**Series ID:** `LNS14000000` (Civilian Labor Force, 16 years and over, Seasonally Adjusted)
**API Endpoint:** `/publicAPI/v2/timeseries/data/{series_id}`
**Bronze Table:** `bronze.bls_unemployment`
**Update Frequency:** Monthly (first Friday of each month)

**Transformation:**
```yaml
from: bronze.bls_unemployment
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

### Get Unemployment Data

```python
from models.api.session import UniversalSession
from core.context import RepoContext

ctx = RepoContext.from_repo_root()
session = UniversalSession(ctx.connection, ctx.config_root, ctx.storage_cfg)

# Get unemployment facts
macro = session.load_model('macro')
unemployment = macro.get_fact_df('fact_unemployment').to_pandas()

# Sort by date
unemployment = unemployment.sort_values('date')

print(unemployment.tail(12))  # Last 12 months
```

### Calculate Year-over-Year Change

```python
# Sort data
unemployment = unemployment.sort_values('date')

# Calculate YoY change
unemployment['unemployment_yoy'] = unemployment['value'].pct_change(periods=12) * 100

# Recent trends
recent = unemployment[unemployment['date'] >= '2020-01-01']

print(recent[['date', 'value', 'unemployment_yoy']])
```

### Identify Recession Periods

```python
# Sahm Rule: Recession indicator based on unemployment rate
# Triggered when 3-month moving average rises 0.5pp above 12-month low

unemployment = unemployment.sort_values('date')

# 3-month moving average
unemployment['ma_3m'] = unemployment['value'].rolling(window=3).mean()

# 12-month rolling minimum
unemployment['min_12m'] = unemployment['value'].rolling(window=12).min()

# Sahm Rule indicator
unemployment['sahm_rule'] = unemployment['ma_3m'] - unemployment['min_12m']

# Recession signal
recessions = unemployment[unemployment['sahm_rule'] >= 0.5]

print("Recession Signals:")
print(recessions[['date', 'value', 'sahm_rule']])
```

### Visualize Trends

```python
import matplotlib.pyplot as plt

# Filter to recent years
recent = unemployment[unemployment['date'] >= '2000-01-01']

plt.figure(figsize=(12, 6))
plt.plot(recent['date'], recent['value'], linewidth=2)
plt.axhline(y=5.0, color='r', linestyle='--', label='5% threshold')
plt.title('US Unemployment Rate (2000-Present)')
plt.xlabel('Date')
plt.ylabel('Unemployment Rate (%)')
plt.legend()
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.show()
```

### Correlate with Stock Market

```python
# Get stock price data
company = session.load_model('company')
prices = company.get_fact_df('fact_prices').to_pandas()

# Calculate monthly average S&P 500 proxy
sp500 = prices.groupby(prices['trade_date'].dt.to_period('M')).agg({
    'close': 'mean'
}).reset_index()

sp500['date'] = sp500['trade_date'].dt.to_timestamp()

# Merge with unemployment
merged = unemployment.merge(sp500[['date', 'close']], on='date', how='inner')

# Calculate correlation
correlation = merged[['value', 'close']].corr()

print("Unemployment vs Stock Prices Correlation:")
print(correlation)
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

## Unemployment Rate Calculation

---

**Formula:**
```
Unemployment Rate = (Unemployed / Civilian Labor Force) × 100
```

**Where:**
- **Unemployed:** People without jobs who are actively seeking work
- **Civilian Labor Force:** Employed + Unemployed (excludes military, institutionalized)

**Not Counted:**
- Discouraged workers (not actively seeking)
- Part-time for economic reasons (see U-6)
- Marginally attached workers

---

## Historical Context

---

### Normal Range
- **Low:** 3.5-4.0% (full employment)
- **Moderate:** 4.0-6.0%
- **High:** 6.0%+ (recession territory)

### Historical Extremes
- **Lowest:** 2.5% (May 1953)
- **Highest:** 14.7% (April 2020, COVID-19)
- **Great Recession:** 10.0% (October 2009)
- **2008 Financial Crisis:** 9.5% peak

---

## Design Decisions

---

### Why partition by year?

**Decision:** Partition by calendar year

**Rationale:**
- Monthly data frequency
- Annual analysis common
- Efficient range scans
- Aligns with BLS reporting structure

### Why include period field?

**Decision:** Store BLS period code (M01-M12) alongside date

**Rationale:**
- **BLS compatibility** - Native API format
- **Debugging** - Traceable to source
- **Validation** - Cross-check date derivation

---

## Related Documentation

---

### Model Documentation
- [[Macro Model Overview]] - Parent model
- [[Economic Series Dimension]] - Series metadata
- [[CPI Facts]] - Inflation data
- [[Employment Facts]] - Employment data

### Architecture Documentation
- [[Data Pipeline/BLS]] - API ingestion
- [[Facets/Economics]] - Economic normalization
- [[Bronze Storage]] - Raw BLS data

### External Resources
- [BLS Unemployment Data](https://www.bls.gov/cps/)
- [How the Unemployment Rate is Calculated](https://www.bls.gov/cps/cps_htgm.htm)

---

**Tags:** #economics/bls #component/model #concept/facts #concept/time-series

**Last Updated:** 2024-11-08
**Table:** fact_unemployment
**Grain:** One row per month
