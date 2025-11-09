---
title: "CPI Facts"
tags: [economics/bls, component/model, concept/facts, concept/time-series, concept/inflation]
aliases: ["CPI Facts", "fact_cpi", "Consumer Price Index", "Inflation"]
---

# CPI Facts

---

Monthly Consumer Price Index (CPI) from the Bureau of Labor Statistics, measuring the average change over time in prices paid by urban consumers for a basket of goods and services.

**Table:** `fact_cpi`
**Grain:** One row per series per month
**Storage:** `storage/silver/macro/facts/fact_cpi`
**Partitioned By:** `year`

---

## Purpose

---

CPI is the primary measure of inflation in the United States, used for adjusting wages, benefits, and tax brackets, as well as economic policy decisions.

**Use Cases:**
- Inflation tracking
- Real vs nominal return calculations
- Federal Reserve policy analysis
- Cost of living adjustments
- Purchasing power analysis

---

## Schema

---

**Grain:** One row per month

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| **series_id** | string | BLS series identifier | "CUUR0000SA0" |
| **date** | date | First day of month | 2024-11-01 |
| **year** | integer | Year | 2024 |
| **period** | string | BLS period code | "M11" |
| **value** | double | CPI index value | 314.243 |
| **period_name** | string | Human-readable period | "November" |

**Partitioned By:** `year`

---

## Sample Data

---

```
+--------------+------------+------+--------+---------+-------------+
| series_id    | date       | year | period | value   | period_name |
+--------------+------------+------+--------+---------+-------------+
| CUUR0000SA0  | 2024-11-01 | 2024 | M11    | 314.243 | November    |
| CUUR0000SA0  | 2024-10-01 | 2024 | M10    | 313.548 | October     |
| CUUR0000SA0  | 2024-09-01 | 2024 | M09    | 312.827 | September   |
| CUUR0000SA0  | 2024-08-01 | 2024 | M08    | 312.198 | August      |
+--------------+------------+------+--------+---------+-------------+
```

---

## Data Source

---

**Provider:** Bureau of Labor Statistics (BLS)
**Survey:** Consumer Price Index
**Series ID:** `CUUR0000SA0` (All Urban Consumers, U.S. city average, All items, Seasonally Adjusted)
**Base Period:** 1982-84 = 100
**API Endpoint:** `/publicAPI/v2/timeseries/data/{series_id}`
**Bronze Table:** `bronze.bls_cpi`
**Update Frequency:** Monthly (mid-month, typically 2nd or 3rd week)

**Transformation:**
```yaml
from: bronze.bls_cpi
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

### Get CPI Data

```python
from models.api.session import UniversalSession
from core.context import RepoContext

ctx = RepoContext.from_repo_root()
session = UniversalSession(ctx.connection, ctx.config_root, ctx.storage_cfg)

# Get CPI facts
macro = session.load_model('macro')
cpi = macro.get_fact_df('fact_cpi').to_pandas()

# Sort by date
cpi = cpi.sort_values('date')

print(cpi.tail(12))  # Last 12 months
```

### Calculate Inflation Rate

```python
# Year-over-year inflation rate
cpi = cpi.sort_values('date')
cpi['inflation_rate'] = cpi['value'].pct_change(periods=12) * 100

# Recent inflation trends
recent = cpi[cpi['date'] >= '2020-01-01']

print(recent[['date', 'value', 'inflation_rate']])
```

### Calculate Month-over-Month Change

```python
# Monthly inflation rate
cpi['mom_change'] = cpi['value'].pct_change() * 100

# Annualized monthly rate
cpi['annualized_mom'] = ((1 + cpi['mom_change']/100)**12 - 1) * 100

print(cpi[['date', 'mom_change', 'annualized_mom']].tail(12))
```

### Adjust for Inflation (Real Values)

```python
# Convert nominal stock prices to real (inflation-adjusted) prices

# Get latest CPI value
latest_cpi = cpi[cpi['date'] == cpi['date'].max()]['value'].values[0]

# Get stock prices
company = session.load_model('company')
prices = company.get_fact_df('fact_prices').to_pandas()

# Merge with monthly CPI
prices['month'] = prices['trade_date'].dt.to_period('M').dt.to_timestamp()
cpi_monthly = cpi[['date', 'value']].rename(columns={'date': 'month', 'value': 'cpi'})

merged = prices.merge(cpi_monthly, on='month', how='left')

# Calculate real price
merged['real_close'] = merged['close'] * (latest_cpi / merged['cpi'])

print(merged[['trade_date', 'ticker', 'close', 'real_close']].head())
```

### Visualize Inflation Trends

```python
import matplotlib.pyplot as plt

# Filter to recent data
recent = cpi[cpi['date'] >= '2000-01-01'].copy()
recent['inflation_rate'] = recent['value'].pct_change(periods=12) * 100

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))

# CPI index
ax1.plot(recent['date'], recent['value'], linewidth=2)
ax1.set_title('Consumer Price Index (CPI-U)')
ax1.set_ylabel('Index (1982-84=100)')
ax1.grid(True, alpha=0.3)

# Inflation rate
ax2.plot(recent['date'], recent['inflation_rate'], linewidth=2, color='red')
ax2.axhline(y=2.0, color='green', linestyle='--', label='2% target')
ax2.set_title('Year-over-Year Inflation Rate')
ax2.set_ylabel('Inflation Rate (%)')
ax2.set_xlabel('Date')
ax2.legend()
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

## CPI Calculation

---

### What CPI Measures

**Basket of Goods:**
- Housing (42%)
- Transportation (16%)
- Food & beverages (14%)
- Medical care (9%)
- Education & communication (6%)
- Recreation (5%)
- Apparel (3%)
- Other (5%)

### Index Interpretation

**Base Period:** 1982-84 = 100

**Example:**
- CPI = 314.243 means prices are 214.2% higher than 1982-84 average
- Price change from 300 to 310 = 3.33% inflation

---

## Historical Context

---

### Normal Range
- **Low:** 0-2% (price stability/deflation risk)
- **Target:** ~2% (Federal Reserve target)
- **Moderate:** 2-4%
- **High:** 4%+ (concerning inflation)

### Historical Extremes
- **1970s Inflation:** Peak of 13.5% (1980)
- **Great Recession:** -2.1% (2009, deflation)
- **COVID-19 Era:** 9.1% (2022, highest since 1981)
- **Recent:** Returned to ~3-4% range (2023-2024)

---

## Design Decisions

---

### Why use CPI-U (All Urban Consumers)?

**Decision:** Track CPI-U series (CUUR0000SA0)

**Rationale:**
- **Most comprehensive** - Covers 93% of U.S. population
- **Standard benchmark** - Most commonly cited
- **Federal Reserve** - Primary inflation measure for policy
- **Media standard** - What news reports

**Alternative:** CPI-W (wage earners) covers only ~29% of population

### Why seasonally adjusted?

**Decision:** Use seasonally adjusted series

**Rationale:**
- **Removes patterns** - Eliminates predictable seasonal fluctuations
- **True trends** - Better year-round comparison
- **Policy-making** - Federal Reserve uses seasonally adjusted
- **Standard practice** - Industry convention

---

## Related Documentation

---

### Model Documentation
- [[Macro Model Overview]] - Parent model
- [[Economic Series Dimension]] - Series metadata
- [[Unemployment Facts]] - Labor market data
- [[Wages Facts]] - Wage data

### Architecture Documentation
- [[Data Pipeline/BLS]] - API ingestion
- [[Facets/Economics]] - Economic normalization
- [[Bronze Storage]] - Raw BLS data

### External Resources
- [BLS CPI Data](https://www.bls.gov/cpi/)
- [CPI FAQ](https://www.bls.gov/cpi/questions-and-answers.htm)
- [Inflation Calculator](https://www.bls.gov/data/inflation_calculator.htm)

---

**Tags:** #economics/bls #component/model #concept/facts #concept/time-series #concept/inflation

**Last Updated:** 2024-11-08
**Table:** fact_cpi
**Grain:** One row per month
