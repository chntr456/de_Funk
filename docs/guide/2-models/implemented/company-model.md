# Company Model

> **Financial market and company data from Polygon.io API**

The Company model provides comprehensive financial market data including stock prices, company information, exchange references, and news sentiment. It serves as the primary source for equity analysis and is used by the Forecast model for ML training.

**Configuration:** `/home/user/de_Funk/configs/models/company.yaml`
**Implementation:** `/home/user/de_Funk/models/implemented/company/model.py`

---

## Table of Contents

- [Overview](#overview)
- [Schema](#schema)
- [Data Sources](#data-sources)
- [Graph Structure](#graph-structure)
- [Measures](#measures)
- [Usage Examples](#usage-examples)
- [Design Decisions](#design-decisions)
- [Partitioning Strategy](#partitioning-strategy)

---

## Overview

### Purpose

The Company model provides:
- Daily stock price data (OHLC, volume, VWAP)
- Company and ticker reference data
- Stock exchange information
- News articles with sentiment analysis
- Weighted market indices (equal, volume, market cap, price)
- Pre-computed analytical views

### Key Features

- **Rich Price Data** - Open, High, Low, Close, Volume, VWAP
- **Company Metadata** - Ticker, name, exchange, market cap proxy
- **News Sentiment** - Article-level sentiment scoring
- **Materialized Views** - Pre-joined analytics tables
- **10 Measures** - Includes 6 weighted aggregate indices
- **Graph Structure** - Clear relationships between facts and dimensions

### Model Characteristics

| Attribute | Value |
|-----------|-------|
| **Model Name** | `company` |
| **Tags** | `equities`, `polygon`, `us` |
| **Dependencies** | `core` (calendar dimension) |
| **Data Source** | Polygon.io API |
| **Storage Root** | `storage/silver/company` |
| **Format** | Parquet |
| **Tables** | 6 (2 dimensions, 2 facts, 2 materialized views) |
| **Dimensions** | 2 (dim_company, dim_exchange) |
| **Facts** | 4 (fact_prices, fact_news, + 2 materialized) |
| **Measures** | 10 |
| **Update Frequency** | Daily (after market close) |

---

## Schema

### Dimensions

#### dim_company

Company dimension with ticker, exchange info, and market cap proxy.

**Path:** `storage/silver/company/dims/dim_company`
**Primary Key:** `ticker`
**Grain:** One row per ticker

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| **ticker** | string | Stock ticker symbol (primary key) | AAPL, GOOGL, MSFT |
| **company_name** | string | Official company name | Apple Inc., Alphabet Inc. |
| **exchange_code** | string | Stock exchange code (FK to dim_exchange) | XNAS, XNYS |
| **company_id** | string | SHA1 hash of ticker (surrogate key) | a94a8fe5ccb... |
| **market_cap_proxy** | double | Approximate market cap (close × volume) | 2850000000000.0 |
| **latest_trade_date** | date | Most recent trading date for ticker | 2024-11-08 |

**Sample Data:**
```
+--------+-----------------+---------------+------------------+------------------+------------------+
| ticker | company_name    | exchange_code | company_id       | market_cap_proxy | latest_trade_date|
+--------+-----------------+---------------+------------------+------------------+------------------+
| AAPL   | Apple Inc.      | XNAS          | a94a8fe5ccb...   | 2850000000000.0  | 2024-11-08       |
| GOOGL  | Alphabet Inc.   | XNAS          | 7c211433f02...   | 1720000000000.0  | 2024-11-08       |
| MSFT   | Microsoft Corp. | XNAS          | d3d9446802a...   | 2680000000000.0  | 2024-11-08       |
| TSLA   | Tesla, Inc.     | XNAS          | 4e07408562b...   | 685000000000.0   | 2024-11-08       |
+--------+-----------------+---------------+------------------+------------------+------------------+
```

#### dim_exchange

Stock exchange reference dimension.

**Path:** `storage/silver/company/dims/dim_exchange`
**Primary Key:** `exchange_code`
**Grain:** One row per exchange

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| **exchange_code** | string | Exchange code (primary key) | XNAS, XNYS |
| **exchange_name** | string | Full exchange name | NASDAQ, NYSE |

**Sample Data:**
```
+---------------+------------------------------------+
| exchange_code | exchange_name                      |
+---------------+------------------------------------+
| XNAS          | NASDAQ                             |
| XNYS          | New York Stock Exchange            |
| ARCX          | NYSE Arca                          |
| BATS          | Cboe BZX Exchange                  |
+---------------+------------------------------------+
```

### Facts

#### fact_prices

Daily stock prices with OHLC data and volume.

**Path:** `storage/silver/company/facts/fact_prices`
**Partitions:** `trade_date`
**Grain:** One row per ticker per trading day

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| **trade_date** | date | Trading date (partition key) | 2024-11-08 |
| **ticker** | string | Stock ticker (FK to dim_company) | AAPL |
| **open** | double | Opening price in USD | 225.50 |
| **high** | double | Highest price during day | 227.85 |
| **low** | double | Lowest price during day | 224.30 |
| **close** | double | Closing price in USD | 226.95 |
| **volume_weighted** | double | Volume weighted average price (VWAP) | 226.12 |
| **volume** | long | Trading volume (number of shares) | 52847392 |

**Sample Data:**
```
+------------+--------+--------+--------+--------+--------+-----------------+-----------+
| trade_date | ticker | open   | high   | low    | close  | volume_weighted | volume    |
+------------+--------+--------+--------+--------+--------+-----------------+-----------+
| 2024-11-08 | AAPL   | 225.50 | 227.85 | 224.30 | 226.95 | 226.12          | 52847392  |
| 2024-11-08 | GOOGL  | 168.25 | 170.30 | 167.80 | 169.75 | 169.05          | 28456213  |
| 2024-11-08 | MSFT   | 418.30 | 421.50 | 416.90 | 420.25 | 419.40          | 24567890  |
| 2024-11-07 | AAPL   | 223.80 | 225.60 | 222.95 | 225.10 | 224.55          | 48923456  |
+------------+--------+--------+--------+--------+--------+-----------------+-----------+
```

#### fact_news

News articles by ticker with sentiment scores.

**Path:** `storage/silver/company/facts/fact_news`
**Partitions:** `publish_date`
**Grain:** One row per article

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| **publish_date** | date | Article publication date (partition key) | 2024-11-08 |
| **ticker** | string | Stock ticker (FK to dim_company) | AAPL |
| **article_id** | string | Unique article identifier | art_abc123xyz |
| **title** | string | Article headline | "Apple Announces Record Earnings" |
| **source** | string | News source | Bloomberg, Reuters, CNBC |
| **sentiment** | double | Sentiment score (-1.0 to 1.0) | 0.75 (positive) |

**Sample Data:**
```
+--------------+--------+---------------+----------------------------------+------------+-----------+
| publish_date | ticker | article_id    | title                            | source     | sentiment |
+--------------+--------+---------------+----------------------------------+------------+-----------+
| 2024-11-08   | AAPL   | art_abc123    | Apple Announces Record Earnings  | Bloomberg  |  0.75     |
| 2024-11-08   | AAPL   | art_def456    | iPhone Sales Beat Expectations   | Reuters    |  0.82     |
| 2024-11-08   | GOOGL  | art_ghi789    | Google Cloud Revenue Grows 30%   | CNBC       |  0.68     |
| 2024-11-07   | TSLA   | art_jkl012    | Tesla Faces Production Delays    | WSJ        | -0.45     |
+--------------+--------+---------------+----------------------------------+------------+-----------+
```

### Materialized Views

#### prices_with_company

Prices joined with company and exchange info (canonical analytics view).

**Path:** `storage/silver/company/facts/prices_with_company`
**Partitions:** `trade_date`
**Tags:** `canonical`, `analytics`, `materialized`

| Column | Type | Description |
|--------|------|-------------|
| **trade_date** | date | Trading date |
| **ticker** | string | Stock ticker |
| **company_name** | string | Company name (from dim_company) |
| **exchange_name** | string | Exchange name (from dim_exchange) |
| **open** | double | Opening price |
| **high** | double | High price |
| **low** | double | Low price |
| **close** | double | Closing price |
| **volume_weighted** | double | VWAP |
| **volume** | long | Trading volume |

**Graph Path:** `fact_prices → dim_company → dim_exchange`

#### news_with_company

News joined with company info.

**Path:** `storage/silver/company/facts/news_with_company`
**Partitions:** `publish_date`
**Tags:** `news`, `analytics`, `materialized`

| Column | Type | Description |
|--------|------|-------------|
| **publish_date** | date | Publication date |
| **ticker** | string | Stock ticker |
| **company_name** | string | Company name (from dim_company) |
| **article_id** | string | Article ID |
| **title** | string | Article title |
| **source** | string | News source |
| **sentiment** | double | Sentiment score |

**Graph Path:** `fact_news → dim_company`

---

## Data Sources

### Polygon.io API

The Company model sources data from Polygon.io, a financial market data provider.

**API Endpoints Used:**
1. **Ticker Reference** - `/v3/reference/tickers`
   - Provides company metadata
   - Maps to `dim_company`

2. **Exchange Reference** - `/v3/reference/exchanges`
   - Provides exchange metadata
   - Maps to `dim_exchange`

3. **Aggregates (Bars)** - `/v2/aggs/ticker/{ticker}/range/1/day/{from}/{to}`
   - Daily OHLC, volume, VWAP
   - Maps to `fact_prices`

4. **News Articles** - `/v2/reference/news`
   - News articles with sentiment
   - Maps to `fact_news`

### Bronze Layer Mapping

| Bronze Table | API Source | Silver Table |
|--------------|------------|--------------|
| `bronze.ref_ticker` | Ticker Reference | `dim_company` |
| `bronze.exchanges` | Exchange Reference | `dim_exchange` |
| `bronze.prices_daily` | Aggregates (Daily) | `fact_prices` |
| `bronze.news` | News Articles | `fact_news` |

### Data Transformations

#### dim_company
```python
# From Bronze
bronze.ref_ticker
  .select(
    ticker=ticker,
    company_name=name,
    exchange_code=exchange_code
  )
  .derive(
    company_id="sha1(ticker)"  # Surrogate key
  )
```

#### fact_prices
```python
# From Bronze
bronze.prices_daily
  .select(
    trade_date=trade_date,
    ticker=ticker,
    open=open,
    high=high,
    low=low,
    close=close,
    volume_weighted=volume_weighted,
    volume=volume
  )
  .partition_by(trade_date)  # Daily partitions
```

### Update Frequency

- **Daily Updates** - After US market close (4:00 PM ET)
- **Historical Backfill** - Available back to 2004
- **Real-time** - 15-minute delay (free tier), real-time (paid tier)

---

## Graph Structure

### ASCII Diagram

```
                    ┌─────────────────────┐
                    │   dim_exchange      │
                    │                     │
                    │  • exchange_code    │
                    │  • exchange_name    │
                    │                     │
                    └──────────┬──────────┘
                               │
                               │ exchange_code
                               │
                    ┌──────────▼──────────┐
                    │   dim_company       │◄──────────────┐
                    │                     │               │
                    │  • ticker (PK)      │               │
                    │  • company_name     │               │ ticker
                    │  • exchange_code    │               │
                    │  • company_id       │               │
                    │  • market_cap_proxy │               │
                    │                     │               │
                    └──────────┬──────────┘               │
                               │                          │
                               │ ticker                   │
                               │                          │
        ┌──────────────────────┼──────────────────────────┘
        │                      │
        │ ticker               │ ticker
        │                      │
┌───────▼───────────┐  ┌───────▼───────────┐
│   fact_prices     │  │   fact_news       │
│                   │  │                   │
│  • trade_date     │  │  • publish_date   │
│  • ticker         │  │  • ticker         │
│  • open           │  │  • article_id     │
│  • high           │  │  • title          │
│  • low            │  │  • source         │
│  • close          │  │  • sentiment      │
│  • volume_weighted│  │                   │
│  • volume         │  └───────────────────┘
│                   │
│  Partitioned by   │
│  trade_date       │
└───────────────────┘

Materialized Paths:
  1. prices_with_company: fact_prices → dim_company → dim_exchange
  2. news_with_company:   fact_news → dim_company

Legend:
  ┌─────┐
  │     │  = Table (dimension or fact)
  └─────┘

  ──▶    = Foreign key relationship (many-to-one)
```

### Nodes

```yaml
nodes:
  - id: dim_company
    from: bronze.ref_ticker
    select:
      ticker: ticker
      company_name: name
      exchange_code: exchange_code
    derive:
      company_id: "sha1(ticker)"
    tags: [dim, entity, company]
    unique_key: [ticker]

  - id: dim_exchange
    from: bronze.exchanges
    select:
      exchange_code: code
      exchange_name: name
    tags: [dim, ref, exchange]
    unique_key: [exchange_code]

  - id: fact_prices
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
    tags: [fact, prices]

  - id: fact_news
    from: bronze.news
    select:
      publish_date: publish_date
      ticker: ticker
      article_id: article_id
      title: title
      source: source
      sentiment: sentiment
    tags: [fact, news]
```

### Edges

```yaml
edges:
  - from: fact_prices
    to: dim_company
    on: ["ticker=ticker"]
    type: many_to_one
    description: "Prices belong to a company"

  - from: dim_company
    to: dim_exchange
    on: ["exchange_code=exchange_code"]
    type: many_to_one
    description: "Company lists on an exchange"

  - from: fact_news
    to: dim_company
    on: ["ticker=ticker"]
    type: many_to_one
    description: "News articles about a company"
```

### Paths

```yaml
paths:
  - id: prices_with_company
    hops: "fact_prices -> dim_company -> dim_exchange"
    description: "Prices with full company and exchange context"
    tags: [canonical, analytics]

  - id: news_with_company
    hops: "fact_news -> dim_company"
    description: "News with company context"
    tags: [news, analytics]
```

---

## Measures

The Company model defines 10 measures: 4 simple aggregates and 6 weighted indices.

### Simple Measures

#### market_cap
Market capitalization proxy (close × volume)

```yaml
market_cap:
  description: "Market capitalization proxy (close * volume)"
  type: computed
  source: fact_prices.close
  expression: "close * volume"
  aggregation: avg
  data_type: double
  format: "$#,##0.00"
  tags: [market, valuation, aggregate]
```

**Usage:**
```python
# Top 10 companies by market cap
top_companies = company_model.calculate_measure_by_entity(
    'market_cap',
    'ticker',
    limit=10
)
```

#### avg_close_price
Average closing price

```yaml
avg_close_price:
  source: fact_prices.close
  aggregation: avg
  data_type: double
  format: "$#,##0.00"
  tags: [price, average]
```

#### total_volume
Total trading volume

```yaml
total_volume:
  source: fact_prices.volume
  aggregation: sum
  data_type: long
  format: "#,##0"
  tags: [volume, total]
```

#### max_high
Highest price in period

```yaml
max_high:
  source: fact_prices.high
  aggregation: max
  data_type: double
  format: "$#,##0.00"
  tags: [price, max]
```

#### min_low
Lowest price in period

```yaml
min_low:
  source: fact_prices.low
  aggregation: min
  data_type: double
  format: "$#,##0.00"
  tags: [price, min]
```

#### avg_vwap
Average volume weighted average price

```yaml
avg_vwap:
  source: fact_prices.volume_weighted
  aggregation: avg
  data_type: double
  format: "$#,##0.00"
  tags: [price, vwap]
```

### Weighted Aggregate Measures

These measures create multi-stock indices using different weighting schemes.

#### equal_weighted_index
Equal weighted price index across stocks

```yaml
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

**Logic:** Each stock has equal weight (1/N)

```
Index = (Price_AAPL + Price_GOOGL + Price_MSFT) / 3
```

#### volume_weighted_index
Volume weighted price index

```yaml
volume_weighted_index:
  description: "Volume weighted price index across stocks"
  type: weighted_aggregate
  source: fact_prices.close
  weighting_method: volume
  group_by: [trade_date]
  data_type: double
  format: "$#,##0.00"
  tags: [index, aggregate, volume_weighted]
```

**Logic:** Weight by trading volume

```
Weight_AAPL = Volume_AAPL / (Volume_AAPL + Volume_GOOGL + Volume_MSFT)
Index = (Price_AAPL × Weight_AAPL) + (Price_GOOGL × Weight_GOOGL) + ...
```

#### market_cap_weighted_index
Market cap weighted price index

```yaml
market_cap_weighted_index:
  description: "Market cap weighted price index across stocks"
  type: weighted_aggregate
  source: fact_prices.close
  weighting_method: market_cap
  group_by: [trade_date]
  data_type: double
  format: "$#,##0.00"
  tags: [index, aggregate, market_cap_weighted]
```

**Logic:** Weight by market capitalization (similar to S&P 500)

```
MarketCap_AAPL = Close_AAPL × Volume_AAPL
Weight_AAPL = MarketCap_AAPL / Total_MarketCap
Index = (Price_AAPL × Weight_AAPL) + (Price_GOOGL × Weight_GOOGL) + ...
```

#### price_weighted_index
Price weighted index (similar to DJIA)

```yaml
price_weighted_index:
  description: "Price weighted index across stocks"
  type: weighted_aggregate
  source: fact_prices.close
  weighting_method: price
  group_by: [trade_date]
  data_type: double
  format: "$#,##0.00"
  tags: [index, aggregate, price_weighted]
```

**Logic:** Weight by stock price (similar to Dow Jones)

```
Index = (Price_AAPL + Price_GOOGL + Price_MSFT) / Divisor
```

#### volume_deviation_weighted_index
Volume deviation weighted index (unusual activity)

```yaml
volume_deviation_weighted_index:
  description: "Volume deviation weighted index (unusual activity)"
  type: weighted_aggregate
  source: fact_prices.close
  weighting_method: volume_deviation
  group_by: [trade_date]
  data_type: double
  format: "$#,##0.00"
  tags: [index, aggregate, volume_deviation]
```

**Logic:** Weight by volume deviation from average (highlights unusual activity)

```
Deviation_AAPL = |Volume_today - AvgVolume_30d| / AvgVolume_30d
Weight_AAPL = Deviation_AAPL / Total_Deviation
```

#### volatility_weighted_index
Inverse volatility weighted index (risk-adjusted)

```yaml
volatility_weighted_index:
  description: "Inverse volatility weighted index (risk-adjusted)"
  type: weighted_aggregate
  source: fact_prices.close
  weighting_method: volatility
  group_by: [trade_date]
  data_type: double
  format: "$#,##0.00"
  tags: [index, aggregate, volatility_weighted]
```

**Logic:** Weight inversely by volatility (low volatility = higher weight)

```
Volatility_AAPL = StdDev(Returns_30d)
Weight_AAPL = (1 / Volatility_AAPL) / Sum(1 / Volatility)
```

---

## Usage Examples

### 1. Load Company Model

```python
from core.context import RepoContext
from models.api.session import UniversalSession

# Initialize session
ctx = RepoContext.from_repo_root()
session = UniversalSession(ctx.connection, ctx.config_root, ctx.storage_cfg)

# Load company model
company_model = session.load_model('company')
```

### 2. Get Company Dimension

```python
# Get all companies
companies = company_model.get_dimension_df('dim_company')
companies.show(10)

# Filter for specific tickers
aapl = companies.filter(F.col('ticker') == 'AAPL')
aapl.show()
```

### 3. Get Stock Prices

```python
# Get all prices
prices = company_model.get_fact_df('fact_prices')

# Filter by date range
prices_2024 = prices.filter(
    (F.col('trade_date') >= '2024-01-01') &
    (F.col('trade_date') <= '2024-12-31')
)

# Filter by ticker
aapl_prices = prices.filter(F.col('ticker') == 'AAPL')
```

### 4. Get Prices with Company Context

```python
# Use materialized view
prices_with_company = session.get_table('company', 'prices_with_company')

prices_with_company.filter(F.col('trade_date') == '2024-11-08').show()

# +------------+--------+---------------+---------------+--------+-------+
# | trade_date | ticker | company_name  | exchange_name | close  | volume|
# +------------+--------+---------------+---------------+--------+-------+
# | 2024-11-08 | AAPL   | Apple Inc.    | NASDAQ        | 226.95 |52847k |
# | 2024-11-08 | GOOGL  | Alphabet Inc. | NASDAQ        | 169.75 |28456k |
# +------------+--------+---------------+---------------+--------+-------+
```

### 5. Calculate Average Price by Ticker

```python
# Using measure calculation
avg_prices = company_model.calculate_measure_by_entity(
    'avg_close_price',
    'ticker',
    limit=10
)

avg_prices.show()

# +--------+-----------------+
# | ticker | avg_close_price |
# +--------+-----------------+
# | AAPL   |          186.42 |
# | GOOGL  |          142.35 |
# | MSFT   |          382.18 |
# +--------+-----------------+
```

### 6. Calculate Market Cap

```python
# Top 10 by market cap
top_market_cap = company_model.calculate_measure_by_entity(
    'market_cap',
    'ticker',
    limit=10
)

top_market_cap.show()
```

### 7. Get News with Sentiment

```python
# Get all news
news = company_model.get_fact_df('fact_news')

# Filter by ticker and date
aapl_news = news.filter(
    (F.col('ticker') == 'AAPL') &
    (F.col('publish_date') >= '2024-11-01')
)

# Get positive news (sentiment > 0.5)
positive_news = news.filter(F.col('sentiment') > 0.5)
positive_news.show()
```

### 8. Analyze Price Trends

```python
from pyspark.sql import functions as F, Window

# Calculate daily returns
prices = company_model.get_fact_df('fact_prices')

window_spec = Window.partitionBy('ticker').orderBy('trade_date')

returns = prices.withColumn(
    'prev_close',
    F.lag('close').over(window_spec)
).withColumn(
    'daily_return',
    (F.col('close') - F.col('prev_close')) / F.col('prev_close')
)

# Get top daily movers
top_movers = returns.filter(
    F.col('trade_date') == '2024-11-08'
).orderBy(F.desc('daily_return')).limit(10)

top_movers.select('ticker', 'close', 'daily_return').show()
```

### 9. Calculate Moving Averages

```python
from pyspark.sql import Window

# 30-day moving average
window_30d = Window.partitionBy('ticker').orderBy('trade_date').rowsBetween(-29, 0)

prices_with_ma = prices.withColumn(
    'ma_30',
    F.avg('close').over(window_30d)
)

# Filter for AAPL
aapl_with_ma = prices_with_ma.filter(F.col('ticker') == 'AAPL')
aapl_with_ma.select('trade_date', 'close', 'ma_30').show()
```

### 10. Join with Calendar

```python
# Load core model
core_model = session.load_model('core')
calendar = core_model.get_dimension_df('dim_calendar')

# Join prices with calendar
prices_with_dates = prices.join(
    calendar,
    prices.trade_date == calendar.date,
    how='left'
)

# Get Monday prices only
monday_prices = prices_with_dates.filter(F.col('day_of_week') == 1)

# Analyze by month
monthly_stats = prices_with_dates.groupBy('year_month', 'ticker').agg(
    F.avg('close').alias('avg_close'),
    F.sum('volume').alias('total_volume')
)
monthly_stats.show()
```

### 11. Cross-Model Analysis: Prices + Macro

```python
# Load macro model
macro_model = session.load_model('macro')
unemployment = macro_model.get_fact_df('fact_unemployment')

# Join prices with unemployment rate
prices_monthly = prices.groupBy(
    F.date_trunc('month', 'trade_date').alias('month'),
    'ticker'
).agg(
    F.avg('close').alias('avg_close')
)

unemployment_monthly = unemployment.select(
    F.date_trunc('month', 'date').alias('month'),
    F.col('value').alias('unemployment_rate')
)

combined = prices_monthly.join(unemployment_monthly, on='month', how='left')
combined.show()
```

---

## Design Decisions

### 1. Partition by Date

**Decision:** Partition fact_prices by `trade_date` and fact_news by `publish_date`

**Rationale:**
- Most queries filter by date range
- Partition pruning improves performance
- Daily partitions balance between too many/too few

**Performance Impact:**
```python
# Without partitioning: Full table scan
prices.filter(F.col('trade_date') == '2024-11-08')  # Scans all files

# With partitioning: Only scans relevant partition
prices.filter(F.col('trade_date') == '2024-11-08')  # Scans 1 partition
```

### 2. Include VWAP

**Decision:** Include `volume_weighted` (VWAP) column in fact_prices

**Rationale:**
- VWAP is common metric for institutional traders
- Provided by Polygon API (no calculation needed)
- More accurate than simple average of OHLC

### 3. Market Cap Proxy

**Decision:** Use `close × volume` as market cap proxy in dim_company

**Rationale:**
- True market cap requires shares outstanding (not always available)
- Proxy is "good enough" for relative comparisons
- Updates automatically with price data

**Limitations:**
- Not actual market cap
- Volume varies daily (use average)

### 4. Materialized Views

**Decision:** Create `prices_with_company` and `news_with_company` materialized views

**Rationale:**
- Common join pattern (fact → dim_company → dim_exchange)
- Pre-joining improves query performance
- Denormalized format easier for analysts

**Trade-off:**
- Storage: ~3x larger than normalized
- Updates: Must rebuild when dim_company changes

### 5. SHA1 Company ID

**Decision:** Generate surrogate key using `sha1(ticker)`

**Rationale:**
- Consistent, deterministic ID
- Useful for graph databases
- Avoids auto-increment issues

### 6. No Intraday Data

**Decision:** Daily grain only (no intraday prices)

**Rationale:**
- Most analytics at daily level or higher
- Intraday requires different storage strategy
- Reduces data volume significantly

**Future Enhancement:**
- Add `fact_prices_intraday` for minute-level bars

### 7. News Sentiment

**Decision:** Include pre-computed sentiment score

**Rationale:**
- Polygon provides sentiment analysis
- Enables correlation with price movements
- Saves computation time

**Alternative:**
- Could run own NLP sentiment analysis
- Would require more infrastructure

### 8. 10 Measures Including Weighted Indices

**Decision:** Pre-define 10 measures including 6 weighted indices

**Rationale:**
- Weighted indices are complex calculations
- Common use case: portfolio/market analysis
- Standardizes index calculation logic

**Index Types Chosen:**
- Equal weighted: Simple benchmark
- Volume weighted: Liquidity focus
- Market cap weighted: S&P 500 style
- Price weighted: DJIA style
- Volume deviation: Unusual activity
- Volatility weighted: Risk-adjusted

---

## Partitioning Strategy

### fact_prices Partitioning

```
storage/silver/company/facts/fact_prices/
├── trade_date=2024-01-01/
│   └── part-00000.parquet
├── trade_date=2024-01-02/
│   └── part-00000.parquet
├── trade_date=2024-01-03/
│   └── part-00000.parquet
...
```

**Benefits:**
- Query filtering: Only reads relevant dates
- Update pattern: Append new date partition
- Deletion: Easy to drop old partitions

**Query Examples:**
```python
# Scans 1 partition
prices.filter(F.col('trade_date') == '2024-11-08')

# Scans 7 partitions
prices.filter(
    (F.col('trade_date') >= '2024-11-01') &
    (F.col('trade_date') <= '2024-11-07')
)
```

### fact_news Partitioning

```
storage/silver/company/facts/fact_news/
├── publish_date=2024-01-01/
├── publish_date=2024-01-02/
...
```

Same strategy as fact_prices.

### Dimension Tables: No Partitioning

```
storage/silver/company/dims/dim_company/
└── part-00000.parquet

storage/silver/company/dims/dim_exchange/
└── part-00000.parquet
```

**Rationale:**
- Small tables (hundreds to thousands of rows)
- Fully scanned for joins
- Partitioning would hurt performance

---

## Summary

The Company model provides comprehensive financial market data with:

- **Rich Schema** - 6 tables (2 dims, 2 facts, 2 materialized views)
- **Quality Data** - From Polygon.io API with daily updates
- **10 Measures** - Including 6 weighted market indices
- **Graph Structure** - Clear relationships with materialized paths
- **Performance** - Date-partitioned facts for fast queries
- **Integration** - Dependency on Core model for date intelligence

This model serves as the foundation for equity analysis and feeds the Forecast model for ML predictions.

---

**Next Steps:**
- See [Forecast Model](forecast-model.md) for ML predictions on company data
- See [Macro Model](macro-model.md) for economic indicators
- See [Overview](../overview.md) for framework concepts

---

**Related Documentation:**
- [Models Framework Overview](../overview.md)
- [Core Model](core-model.md)
- [Graph Building](../overview.md#graph-building)
- [Measures](../overview.md#measures)
