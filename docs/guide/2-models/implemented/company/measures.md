---
title: "Company Measures"
tags: [finance/equities, component/model, concept/measures, concept/aggregation]
aliases: ["Company Measures", "Stock Measures", "Weighted Indices"]
---

# Company Measures

---

Pre-defined aggregations and weighted index calculations for the Company model, enabling consistent metric definitions across analysis.

---

## Purpose

---

Measures provide standardized calculations for common stock market metrics, eliminating the need to rewrite aggregation logic and ensuring consistency across analyses.

**Use Cases:**
- Portfolio performance tracking
- Index construction
- Comparative analysis
- Risk-adjusted metrics
- Volume analysis

---

## Simple Aggregation Measures

---

### Market Cap Proxy

**Description:** Approximate market capitalization
**Source:** `fact_prices.close`
**Formula:** `close * volume`
**Aggregation:** Average
**Format:** `$#,##0.00`

**Example Usage:**
```python
# Calculate market cap proxy for each ticker
market_caps = prices.groupby('ticker').agg({
    'close': lambda x: (x * prices.loc[x.index, 'volume']).mean()
})
```

---

### Average Close Price

**Description:** Average closing price over period
**Source:** `fact_prices.close`
**Aggregation:** Average
**Format:** `$#,##0.00`

**Example Usage:**
```python
# Average price by ticker
avg_prices = prices.groupby('ticker')['close'].mean()
```

---

### Total Volume

**Description:** Total trading volume
**Source:** `fact_prices.volume`
**Aggregation:** Sum
**Format:** `#,##0`

**Example Usage:**
```python
# Total volume by ticker
total_vol = prices.groupby('ticker')['volume'].sum()
```

---

### Max High

**Description:** Highest price in period
**Source:** `fact_prices.high`
**Aggregation:** Max
**Format:** `$#,##0.00`

**Example Usage:**
```python
# 52-week high
high_52w = prices[prices['trade_date'] >= '2023-11-08'].groupby('ticker')['high'].max()
```

---

### Min Low

**Description:** Lowest price in period
**Source:** `fact_prices.low`
**Aggregation:** Min
**Format:** `$#,##0.00`

**Example Usage:**
```python
# 52-week low
low_52w = prices[prices['trade_date'] >= '2023-11-08'].groupby('ticker')['low'].min()
```

---

### Average VWAP

**Description:** Average volume-weighted average price
**Source:** `fact_prices.volume_weighted`
**Aggregation:** Average
**Format:** `$#,##0.00`

**Example Usage:**
```python
# Average VWAP by ticker
avg_vwap = prices.groupby('ticker')['volume_weighted'].mean()
```

---

## Weighted Index Measures

---

Weighted indices combine multiple stocks into a single aggregate measure using different weighting methodologies.

### Equal Weighted Index

**Description:** Simple average across all stocks
**Source:** `fact_prices.close`
**Weighting:** Equal (1/N for N stocks)
**Group By:** `trade_date`

**Formula:**
```
Index_t = (1/N) × Σ(close_i,t)
```

**Use Case:** Broad market exposure without cap bias

**Example:**
```python
# Equal weighted index
equal_idx = prices.groupby('trade_date')['close'].mean()
```

---

### Volume Weighted Index

**Description:** Weighted by trading volume
**Source:** `fact_prices.close`
**Weighting:** Volume (proportional to daily volume)
**Group By:** `trade_date`

**Formula:**
```
Index_t = Σ(close_i,t × volume_i,t) / Σ(volume_i,t)
```

**Use Case:** Emphasize liquid, actively traded stocks

**Example:**
```python
# Volume weighted index
vol_idx = prices.groupby('trade_date').apply(
    lambda g: (g['close'] * g['volume']).sum() / g['volume'].sum()
)
```

---

### Market Cap Weighted Index

**Description:** Weighted by market capitalization
**Source:** `fact_prices.close`
**Weighting:** Market cap (close × volume proxy)
**Group By:** `trade_date`

**Formula:**
```
Index_t = Σ(close_i,t × marketcap_i) / Σ(marketcap_i)
```

**Use Case:** Track large-cap dominated market (S&P 500 style)

**Example:**
```python
# Market cap weighted index
companies = session.get_table('company', 'dim_company').to_pandas()
merged = prices.merge(companies[['ticker', 'market_cap_proxy']], on='ticker')

mcap_idx = merged.groupby('trade_date').apply(
    lambda g: (g['close'] * g['market_cap_proxy']).sum() / g['market_cap_proxy'].sum()
)
```

---

### Price Weighted Index

**Description:** Weighted by stock price (Dow Jones style)
**Source:** `fact_prices.close`
**Weighting:** Stock price
**Group By:** `trade_date`

**Formula:**
```
Index_t = Σ(close_i,t) / divisor
```

**Use Case:** Traditional index methodology (DJIA)

**Example:**
```python
# Price weighted index (DJIA-style)
divisor = 0.15172752595384  # Example divisor
price_idx = prices.groupby('trade_date')['close'].sum() / divisor
```

---

### Volume Deviation Weighted Index

**Description:** Weighted by unusual trading activity
**Source:** `fact_prices.close`
**Weighting:** Volume deviation from average
**Group By:** `trade_date`

**Formula:**
```
weight_i,t = |volume_i,t - avg_volume_i| / avg_volume_i
Index_t = Σ(close_i,t × weight_i,t) / Σ(weight_i,t)
```

**Use Case:** Emphasize stocks with abnormal trading activity

**Example:**
```python
# Calculate average volume per ticker
avg_vol = prices.groupby('ticker')['volume'].transform('mean')

# Volume deviation
prices['vol_deviation'] = abs(prices['volume'] - avg_vol) / avg_vol

# Volume deviation index
vol_dev_idx = prices.groupby('trade_date').apply(
    lambda g: (g['close'] * g['vol_deviation']).sum() / g['vol_deviation'].sum()
)
```

---

### Volatility Weighted Index

**Description:** Inverse volatility weighted (risk-adjusted)
**Source:** `fact_prices.close`
**Weighting:** Inverse volatility (1 / σ)
**Group By:** `trade_date`

**Formula:**
```
weight_i = 1 / volatility_i
Index_t = Σ(close_i,t × weight_i) / Σ(weight_i)
```

**Use Case:** Risk-parity portfolio construction

**Example:**
```python
# Calculate 30-day volatility
prices_sorted = prices.sort_values(['ticker', 'trade_date'])
prices_sorted['daily_return'] = prices_sorted.groupby('ticker')['close'].pct_change()
prices_sorted['volatility'] = prices_sorted.groupby('ticker')['daily_return'].transform(
    lambda x: x.rolling(30).std()
)

# Inverse volatility weight
prices_sorted['inv_vol_weight'] = 1 / prices_sorted['volatility']

# Volatility weighted index
vol_idx = prices_sorted.groupby('trade_date').apply(
    lambda g: (g['close'] * g['inv_vol_weight']).sum() / g['inv_vol_weight'].sum()
)
```

---

## Measure Configuration

---

All measures are defined in the Company model YAML:

**Location:** `configs/models/company.yaml`

**Example Configuration:**
```yaml
measures:
  avg_close_price:
    description: "Average closing price"
    source: fact_prices.close
    aggregation: avg
    data_type: double
    format: "$#,##0.00"
    tags: [price, average]

  equal_weighted_index:
    description: "Equal weighted price index across stocks"
    type: weighted_aggregate
    source: fact_prices.close
    weighting_method: equal
    group_by: [trade_date]
    data_type: double
    format: "$#,##0.00"
    tags: [index, aggregate, equal_weighted]
```

---

## Usage in Analysis

---

### Using Pre-defined Measures

```python
from models.api.session import UniversalSession
from core.context import RepoContext

ctx = RepoContext.from_repo_root()
session = UniversalSession(ctx.connection, ctx.config_root, ctx.storage_cfg)

# Load company model
company = session.load_model('company')

# Access measure definitions
measures = company.config.measures

# Use measure logic in analysis
avg_close = measures['avg_close_price']
print(f"Measure: {avg_close['description']}")
print(f"Source: {avg_close['source']}")
print(f"Aggregation: {avg_close['aggregation']}")
```

### Building Custom Index

```python
# Get price data
prices = company.get_fact_df('fact_prices').to_pandas()

# Apply equal weighted index logic
equal_weighted = prices.groupby('trade_date')['close'].mean()

# Apply market cap weighted logic
companies = session.get_table('company', 'dim_company').to_pandas()
merged = prices.merge(companies[['ticker', 'market_cap_proxy']], on='ticker')

mcap_weighted = merged.groupby('trade_date').apply(
    lambda g: (g['close'] * g['market_cap_proxy']).sum() / g['market_cap_proxy'].sum()
)

# Compare indices
import matplotlib.pyplot as plt

plt.figure(figsize=(12, 6))
plt.plot(equal_weighted.index, equal_weighted.values, label='Equal Weighted')
plt.plot(mcap_weighted.index, mcap_weighted.values, label='Market Cap Weighted')
plt.legend()
plt.title('Index Comparison')
plt.xlabel('Date')
plt.ylabel('Index Value')
plt.show()
```

---

## Design Decisions

---

### Why pre-define measures?

**Decision:** Define common metrics in model configuration

**Rationale:**
- **Consistency** - Same calculation across all analyses
- **Documentation** - Clear definition of each metric
- **Reusability** - Avoid rewriting aggregation logic
- **Validation** - Single source of truth for calculations

### Why multiple index methodologies?

**Decision:** Provide 6 different weighting schemes

**Rationale:**
- **Flexibility** - Different use cases prefer different weightings
- **Comparison** - Understand impact of weighting choice
- **Research** - Academic and practitioner interest
- **Risk management** - Various risk-adjusted approaches

---

## Related Documentation

---

### Model Documentation
- [[Company Model Overview]] - Parent model
- [[Price Facts]] - Source data for measures
- [[Company Dimension]] - Market cap data

### Architecture Documentation
- [[Models System/Measures]] - Measure framework
- [[Silver Storage]] - Pre-aggregated storage

### How-To Guides
- [[How to Build Custom Indices]]
- [[How to Calculate Risk Metrics]]

---

**Tags:** #finance/equities #component/model #concept/measures #concept/aggregation

**Last Updated:** 2024-11-08
**Total Measures:** 12
**Weighted Indices:** 6
