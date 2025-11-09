---
title: "Price Facts"
tags: [finance/equities, component/model, concept/facts, concept/time-series]
aliases: ["Price Facts", "fact_prices", "Stock Prices", "OHLCV"]
---

# Price Facts

---

Daily stock price data with open, high, low, close, volume, and volume-weighted average price (VWAP).

**Table:** `fact_prices`
**Grain:** One row per ticker per trading day
**Storage:** `storage/silver/company/facts/fact_prices`
**Partitioned By:** `trade_date`

---

## Purpose

---

Price facts provide comprehensive daily trading data for technical analysis, performance tracking, and index construction.

**Use Cases:**
- Price trend analysis
- Return calculations
- Volatility measurements
- Volume analysis
- Index construction
- Backtesting strategies

---

## Schema

---

**Grain:** One row per ticker per trading day

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| **trade_date** | date | Trading date | 2024-11-08 |
| **ticker** | string | Stock ticker symbol | "AAPL" |
| **open** | double | Opening price | 227.35 |
| **high** | double | Highest price of day | 229.12 |
| **low** | double | Lowest price of day | 226.84 |
| **close** | double | Closing price | 228.45 |
| **volume_weighted** | double | Volume weighted average price (VWAP) | 228.02 |
| **volume** | long | Total shares traded | 48592847 |

**Partitioned By:** `trade_date` (year-month partitioning)

---

## Sample Data

---

```
+------------+--------+--------+--------+--------+--------+-----------------+-----------+
| trade_date | ticker | open   | high   | low    | close  | volume_weighted | volume    |
+------------+--------+--------+--------+--------+--------+-----------------+-----------+
| 2024-11-08 | AAPL   | 227.35 | 229.12 | 226.84 | 228.45 | 228.02          | 48592847  |
| 2024-11-08 | MSFT   | 420.10 | 423.45 | 419.22 | 422.18 | 421.45          | 21483920  |
| 2024-11-08 | GOOGL  | 142.88 | 144.22 | 142.35 | 143.75 | 143.42          | 15782443  |
| 2024-11-07 | AAPL   | 226.12 | 228.45 | 225.88 | 227.92 | 227.34          | 52348291  |
+------------+--------+--------+--------+--------+--------+-----------------+-----------+
```

---

## Data Source

---

**Provider:** Polygon.io
**API Endpoint:** `/v2/aggs/ticker/{ticker}/range/1/day/{from}/{to}`
**Bronze Table:** `bronze.prices_daily`
**Update Frequency:** Daily (after market close)

**Transformation:**
```yaml
from: bronze.prices_daily
select:
  trade_date: trade_date
  ticker: ticker
  open: open
  high: high
  low: low
  close: close
  volume_weighted: volume_weighted
  volume: volume
```

---

## Usage Examples

---

### Get Price Data

```python
from models.api.session import UniversalSession
from core.context import RepoContext

ctx = RepoContext.from_repo_root()
session = UniversalSession(ctx.connection, ctx.config_root, ctx.storage_cfg)

# Get price facts
company = session.load_model('company')
prices = company.get_fact_df('fact_prices').to_pandas()

# Filter to specific ticker and date range
aapl = prices[
    (prices['ticker'] == 'AAPL') &
    (prices['trade_date'] >= '2024-01-01')
]

print(aapl.head())
```

### Calculate Returns

```python
# Daily returns
prices_sorted = prices.sort_values(['ticker', 'trade_date'])
prices_sorted['daily_return'] = prices_sorted.groupby('ticker')['close'].pct_change()

# Cumulative returns
prices_sorted['cum_return'] = prices_sorted.groupby('ticker')['daily_return'].cumsum()

print(prices_sorted[['trade_date', 'ticker', 'close', 'daily_return', 'cum_return']].head(10))
```

### Calculate Volatility

```python
# 30-day rolling volatility
prices_sorted['volatility_30d'] = prices_sorted.groupby('ticker')['daily_return'].transform(
    lambda x: x.rolling(window=30).std()
)

# Filter to recent high volatility stocks
high_vol = prices_sorted[
    (prices_sorted['volatility_30d'] > 0.02) &
    (prices_sorted['trade_date'] == prices_sorted['trade_date'].max())
]

print(high_vol[['ticker', 'close', 'volatility_30d']].sort_values('volatility_30d', ascending=False))
```

### Volume Analysis

```python
# Average volume by ticker
avg_volume = prices.groupby('ticker').agg({
    'volume': 'mean',
    'close': 'mean'
}).reset_index()

avg_volume.columns = ['ticker', 'avg_volume', 'avg_price']

# Find high volume stocks
high_volume = avg_volume[avg_volume['avg_volume'] > 20000000]

print(high_volume.sort_values('avg_volume', ascending=False))
```

### VWAP Analysis

```python
# Compare close to VWAP
prices['close_vs_vwap'] = (prices['close'] - prices['volume_weighted']) / prices['volume_weighted']

# Find stocks trading above VWAP
above_vwap = prices[
    (prices['close_vs_vwap'] > 0.01) &  # More than 1% above VWAP
    (prices['trade_date'] == prices['trade_date'].max())
]

print(above_vwap[['ticker', 'close', 'volume_weighted', 'close_vs_vwap']])
```

---

## Relationships

---

### Foreign Keys

- **ticker** → [[Company Dimension]].ticker
- **trade_date** → [[Calendar]].date

### Used By

- **[[Company Measures]]** - Pre-defined aggregations
- **prices_with_company** - Materialized view with company context

---

## OHLCV Fields

---

### Open
First trade price of the trading day

### High
Highest trade price during the trading day

### Low
Lowest trade price during the trading day

### Close
Last trade price of the trading day (most commonly used for analysis)

### Volume
Total number of shares traded during the day

### Volume Weighted (VWAP)
**Formula:** `Σ(price × volume) / Σ(volume)`
**Purpose:** Average price weighted by trading volume, useful for execution quality

---

## Partitioning Strategy

---

**Partition Column:** `trade_date`
**Partition Format:** Year-month (`year=YYYY/month=MM`)

**Benefits:**
- Fast date range queries
- Efficient backfill operations
- Optimized for time series analysis
- Reduced query costs

**Example Partition Structure:**
```
facts/fact_prices/
  year=2024/month=01/
  year=2024/month=02/
  ...
  year=2024/month=11/
```

---

## Design Decisions

---

### Why include VWAP?

**Decision:** Store volume-weighted average price alongside OHLC

**Rationale:**
- Common benchmark for institutional trading
- More representative than simple average of H+L
- Used in many trading strategies
- Expensive to calculate on-the-fly

### Why partition by trade_date?

**Decision:** Partition by year-month of trade date

**Rationale:**
- Most queries filter by date range
- Enables efficient time series analysis
- Reduces full table scans
- Aligns with data update patterns (daily appends)

---

## Related Documentation

---

### Model Documentation
- [[Company Model Overview]] - Parent model
- [[Company Dimension]] - Company profiles
- [[Exchange Dimension]] - Exchange reference
- [[Company Measures]] - Price aggregations
- [[News Facts]] - News sentiment

### Architecture Documentation
- [[Data Pipeline/Polygon]] - API ingestion
- [[Facets/Prices]] - Price normalization
- [[Bronze Storage]] - Raw price data
- [[Silver Storage]] - Partitioning strategy

### How-To Guides
- [[How to Query Stock Prices]]
- [[How to Calculate Returns]]
- [[How to Build Custom Indices]]

---

**Tags:** #finance/equities #component/model #concept/facts #concept/time-series #pattern/star-schema

**Last Updated:** 2024-11-08
**Table:** fact_prices
**Grain:** One row per ticker per trading day
