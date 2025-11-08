---
title: "Company Model"
tags: [finance/equities, component/model, concept/dimensional-modeling, source/polygon, status/stable]
aliases: ["Company", "Stock Model", "Equity Model"]
created: 2024-11-08
updated: 2024-11-08
status: stable
dependencies:
  - "[[Core Model]]"
used_by:
  - "[[Forecast Model]]"
---

# Company Model

---

> **Financial market and company data from Polygon.io API**

The Company model provides comprehensive financial market data including stock prices, company information, exchange references, and news sentiment. It serves as the primary source for equity analysis and is used by the [[Forecast Model]] for ML training.

**Configuration:** `/home/user/de_Funk/configs/models/company.yaml`
**Implementation:** `/home/user/de_Funk/models/implemented/company/model.py`

---

## Table of Contents

---

- [Overview](#overview)
- [Schema Overview](#schema-overview)
- [Data Sources](#data-sources)
- [Detailed Schema](#detailed-schema)
- [Graph Structure](#graph-structure)
- [Measures](#measures)
- [How-To Guides](#how-to-guides)
- [Usage Examples](#usage-examples)
- [Design Decisions](#design-decisions)
- [Partitioning Strategy](#partitioning-strategy)

---

## Overview

---

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
| **Dependencies** | [[Core Model]] (calendar dimension) |
| **Data Source** | Polygon.io API |
| **Storage Root** | `storage/silver/company` |
| **Format** | Parquet |
| **Tables** | 6 (2 dimensions, 2 facts, 2 materialized views) |
| **Dimensions** | 2 (dim_company, dim_exchange) |
| **Facts** | 4 (fact_prices, fact_news, + 2 materialized) |
| **Measures** | 10 |
| **Update Frequency** | Daily (after market close) |

---

## Schema Overview

---

### High-Level Summary

The Company model implements a **star schema** with company and exchange dimensions connected to price and news facts. All data is sourced from Polygon.io API and partitioned by date for optimal query performance.

**Quick Reference:**

| Table Type | Count | Purpose |
|------------|-------|---------|
| **Dimensions** | 2 | Descriptive attributes (who, what, where) |
| **Facts** | 2 | Measurable events (prices, news) |
| **Materialized Views** | 2 | Pre-joined analytics tables |
| **Measures** | 10 | Pre-defined calculations |

### Dimensions (Who/What)

| Dimension | Rows | Primary Key | Purpose |
|-----------|------|-------------|---------|
| **dim_company** | ~500-5000 | ticker | Company metadata (name, exchange, market cap) |
| **dim_exchange** | ~10-20 | exchange_code | Stock exchange reference data |

### Facts (Events/Transactions)

| Fact | Grain | Partitions | Purpose |
|------|-------|------------|---------|
| **fact_prices** | Daily per ticker | trade_date | OHLC price data, volume, VWAP |
| **fact_news** | Article per ticker | publish_date | News articles with sentiment scores |

### Materialized Views (Analytics)

| View | Purpose | Joins |
|------|---------|-------|
| **prices_with_company** | Price analysis with company context | fact_prices → dim_company → dim_exchange |
| **news_with_company** | News analysis with company context | fact_news → dim_company |

### Star Schema Diagram

```
                    ┌─────────────────┐
                    │  [[Core Model]] │
                    │  dim_calendar   │
                    │  (27 attributes)│
                    └────────┬────────┘
                             │
                             │ (can join on date)
                             │
         ┌──────────────────┴───────────────────┐
         │                                      │
         ↓                                      ↓
┌──────────────────┐                  ┌──────────────────┐
│  fact_prices     │                  │   fact_news      │
│  ───────────────│                  │  ───────────────│
│  trade_date (PK) │                  │  publish_date    │
│  ticker (FK)     │                  │  ticker (FK)     │
│  open, high, low │                  │  article_id      │
│  close, volume   │                  │  title, source   │
│  volume_weighted │                  │  sentiment       │
└────────┬─────────┘                  └────────┬─────────┘
         │                                      │
         │                                      │
         └──────────────────┬───────────────────┘
                            │
                            ↓
                   ┌─────────────────┐
                   │  dim_company    │
                   │  ───────────────│
                   │  ticker (PK)    │
                   │  company_name   │
                   │  exchange_code  │
                   │  market_cap     │
                   └────────┬────────┘
                            │
                            │ (FK: exchange_code)
                            │
                            ↓
                   ┌─────────────────┐
                   │  dim_exchange   │
                   │  ───────────────│
                   │  exchange_code  │
                   │  exchange_name  │
                   └─────────────────┘
```

**Relationships:**
- `fact_prices.ticker` → `dim_company.ticker` (many-to-one)
- `fact_news.ticker` → `dim_company.ticker` (many-to-one)
- `dim_company.exchange_code` → `dim_exchange.exchange_code` (many-to-one)
- `fact_prices.trade_date` → `dim_calendar.date` (optional join to [[Core Model]])
- `fact_news.publish_date` → `dim_calendar.date` (optional join to [[Core Model]])

---

## Data Sources

---

### Polygon.io API

**Provider:** Polygon.io (https://polygon.io)
**Authentication:** API key required (free tier available)
**Rate Limits:** 5 calls/minute (free), unlimited (paid)
**Data Coverage:** US stock markets (NYSE, NASDAQ, AMEX)

### API Endpoints Used

| Endpoint | Purpose | Bronze Table | Update Frequency |
|----------|---------|--------------|------------------|
| `/v3/reference/tickers` | List all tickers | `bronze.ref_all_tickers` | Weekly (snapshots) |
| `/v2/aggs/ticker/{ticker}/range/1/day/{from}/{to}` | Daily OHLC prices | `bronze.prices_daily` | Daily |
| `/v2/reference/exchanges` | Exchange metadata | `bronze.exchanges` | Weekly (snapshots) |
| `/v2/reference/news` | News articles by ticker | `bronze.news` | Daily |

### Bronze → Silver Transformation

**Pipeline:** `datapipelines/providers/polygon/`

```
Polygon API
    ↓
Facets (normalize responses)
    ├─→ RefAllTickersFacet
    ├─→ PricesDailyGroupedFacet
    ├─→ ExchangeFacet
    └─→ NewsByDateFacet
    ↓
Bronze Storage (partitioned Parquet)
    ├─→ bronze/ref_all_tickers/ (partitioned by snapshot_dt)
    ├─→ bronze/prices_daily/ (partitioned by trade_date)
    ├─→ bronze/exchanges/ (partitioned by snapshot_dt)
    └─→ bronze/news/ (partitioned by publish_date)
    ↓
BaseModel.build() (YAML-driven graph transformation)
    ↓
Silver Storage (dimensional model)
    ├─→ silver/company/dims/dim_company/
    ├─→ silver/company/dims/dim_exchange/
    ├─→ silver/company/facts/fact_prices/
    ├─→ silver/company/facts/fact_news/
    ├─→ silver/company/facts/prices_with_company/
    └─→ silver/company/facts/news_with_company/
```

### Data Quality

- **Completeness:** Market days only (excludes weekends/holidays)
- **Accuracy:** Sourced directly from exchanges
- **Timeliness:** Updated daily after market close
- **Consistency:** Schema validated via facets

### Expandability

The Chicago Data Portal provides additional municipal datasets that can connect to economic models:

**Available Datasets:**
- Police reports and crime data
- Building permits and inspections
- Business licenses
- 311 service requests
- Budget and expenditures

**Future Integration:**
- Crime data by community area → economic indicators
- Building permits → real estate development trends
- Business licenses → economic activity

See [[City Finance Model]] for current Chicago data integration.

---

## Detailed Schema

---

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
+------------+--------+--------+--------+--------+--------+-----------------+-----------+
```

#### fact_news

News articles with sentiment analysis.

**Path:** `storage/silver/company/facts/fact_news`
**Partitions:** `publish_date`
**Grain:** One row per article per ticker

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| **publish_date** | date | Article publication date (partition key) | 2024-11-08 |
| **ticker** | string | Related stock ticker (FK to dim_company) | AAPL |
| **article_id** | string | Unique article identifier | abc123def456 |
| **title** | string | Article headline | "Apple Announces Q4 Earnings" |
| **source** | string | News source | "Bloomberg", "Reuters" |
| **sentiment** | double | Sentiment score (-1 to +1) | 0.65 (positive) |

**Sample Data:**
```
+--------------+--------+--------------+--------------------------------+----------+-----------+
| publish_date | ticker | article_id   | title                          | source   | sentiment |
+--------------+--------+--------------+--------------------------------+----------+-----------+
| 2024-11-08   | AAPL   | abc123def456 | Apple Announces Q4 Earnings    | Bloomberg| 0.65      |
| 2024-11-08   | GOOGL  | def456ghi789 | Google Cloud Revenue Surges    | Reuters  | 0.78      |
| 2024-11-08   | TSLA   | ghi789jkl012 | Tesla Deliveries Beat Estimates| CNBC     | 0.82      |
+--------------+--------+--------------+--------------------------------+----------+-----------+
```

### Materialized Views

#### prices_with_company

Prices joined with full company and exchange context.

**Path:** `storage/silver/company/facts/prices_with_company`
**Partitions:** `trade_date`
**Grain:** One row per ticker per trading day (same as fact_prices)

**Purpose:** Pre-joined view for analytics, eliminating need for runtime joins.

**Join Path:** `fact_prices → dim_company → dim_exchange`

#### news_with_company

News articles joined with company information.

**Path:** `storage/silver/company/facts/news_with_company`
**Partitions:** `publish_date`
**Grain:** One row per article per ticker (same as fact_news)

**Purpose:** Pre-joined view for news analysis with company context.

**Join Path:** `fact_news → dim_company`

---

## Graph Structure

---

### Nodes (Tables)

The YAML config defines 4 nodes that transform Bronze → Silver:

```yaml
graph:
  nodes:
    - id: dim_company
      from: bronze.ref_ticker
      select:
        ticker: ticker
        company_name: name
        exchange_code: exchange_code
      derive:
        company_id: "sha1(ticker)"
      unique_key: [ticker]

    - id: dim_exchange
      from: bronze.exchanges
      select:
        exchange_code: code
        exchange_name: name
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

    - id: fact_news
      from: bronze.news
      select:
        publish_date: publish_date
        ticker: ticker
        article_id: article_id
        title: title
        source: source
        sentiment: sentiment
```

### Edges (Relationships)

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

### Paths (Materialized Joins)

```yaml
paths:
  - id: prices_with_company
    hops: "fact_prices -> dim_company -> dim_exchange"
    description: "Prices with full company and exchange context"

  - id: news_with_company
    hops: "fact_news -> dim_company"
    description: "News with company context"
```

---

## Measures

---

### Simple Aggregations

| Measure | Source | Aggregation | Format | Purpose |
|---------|--------|-------------|--------|---------|
| **avg_close_price** | fact_prices.close | avg | $#,##0.00 | Average closing price |
| **total_volume** | fact_prices.volume | sum | #,##0 | Total trading volume |
| **max_high** | fact_prices.high | max | $#,##0.00 | Highest price in period |
| **min_low** | fact_prices.low | min | $#,##0.00 | Lowest price in period |

### Computed Measures

| Measure | Expression | Aggregation | Purpose |
|---------|------------|-------------|---------|
| **market_cap** | close × volume | avg | Market capitalization proxy |
| **avg_vwap** | volume_weighted | avg | Average VWAP |

### Weighted Aggregate Indices

**Purpose:** Calculate multi-stock indices using different weighting methods.

| Measure | Weighting Method | Use Case |
|---------|------------------|----------|
| **equal_weighted_index** | Equal | All stocks same weight (S&P Equal Weight) |
| **volume_weighted_index** | Volume | Weight by liquidity |
| **market_cap_weighted_index** | Market Cap | Weight by company size (S&P 500 style) |
| **price_weighted_index** | Price | Weight by stock price (DJIA style) |
| **volume_deviation_weighted_index** | Volume Deviation | Highlight unusual trading activity |
| **volatility_weighted_index** | Inverse Volatility | Risk-adjusted weighting |

**Example YAML Definition:**
```yaml
measures:
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

---

## How-To Guides

---

### How to Query Stock Prices

**Step 1:** Load the model and session

```python
from core.context import RepoContext
from models.api.session import UniversalSession

# Initialize
ctx = RepoContext.from_repo_root()
session = UniversalSession(ctx.connection, ctx.config_root, ctx.storage_cfg)

# Load company model
company = session.load_model('company')
```

**Step 2:** Get price data with filters

```python
# Filter by ticker and date range
filters = {
    'ticker': ['AAPL', 'GOOGL', 'MSFT'],
    'trade_date': {
        'start': '2024-01-01',
        'end': '2024-11-08'
    }
}

# Get prices
prices = company.get_fact_df('fact_prices', filters=filters)

# Convert to Pandas
df = prices.to_pandas()
print(df.head())
```

**Step 3:** Analyze and visualize

```python
import plotly.express as px

# Create price trend chart
fig = px.line(
    df,
    x='trade_date',
    y='close',
    color='ticker',
    title='Stock Price Trends'
)
fig.show()
```

---

### How to Calculate Weighted Indices

**Step 1:** Get price data for all stocks

```python
# Get all prices for a date range
filters = {
    'trade_date': {
        'start': '2024-10-01',
        'end': '2024-11-08'
    }
}

prices = company.get_fact_df('fact_prices', filters=filters).to_pandas()
```

**Step 2:** Calculate equal-weighted index

```python
# Group by date and calculate equal-weighted average
equal_weighted = prices.groupby('trade_date').agg({
    'close': 'mean'  # Equal weight = simple average
}).reset_index()

equal_weighted.columns = ['trade_date', 'equal_weighted_index']
print(equal_weighted)
```

**Step 3:** Calculate volume-weighted index

```python
# Calculate volume-weighted average price
prices['weighted_price'] = prices['close'] * prices['volume']

volume_weighted = prices.groupby('trade_date').agg({
    'weighted_price': 'sum',
    'volume': 'sum'
}).reset_index()

volume_weighted['volume_weighted_index'] = (
    volume_weighted['weighted_price'] / volume_weighted['volume']
)

print(volume_weighted[['trade_date', 'volume_weighted_index']])
```

**Step 4:** Calculate market-cap weighted index

```python
# Calculate market cap proxy (close * volume)
prices['market_cap'] = prices['close'] * prices['volume']

# Weight by market cap
prices['weighted_price'] = prices['close'] * prices['market_cap']

mcap_weighted = prices.groupby('trade_date').agg({
    'weighted_price': 'sum',
    'market_cap': 'sum'
}).reset_index()

mcap_weighted['market_cap_weighted_index'] = (
    mcap_weighted['weighted_price'] / mcap_weighted['market_cap']
)

print(mcap_weighted[['trade_date', 'market_cap_weighted_index']])
```

---

### How to Analyze News Sentiment

**Step 1:** Get news data

```python
# Get news for specific tickers
filters = {
    'ticker': ['AAPL', 'TSLA'],
    'publish_date': {
        'start': '2024-11-01',
        'end': '2024-11-08'
    }
}

news = company.get_fact_df('fact_news', filters=filters).to_pandas()
```

**Step 2:** Calculate sentiment statistics

```python
# Average sentiment by ticker
sentiment_by_ticker = news.groupby('ticker').agg({
    'sentiment': ['mean', 'std', 'count']
}).reset_index()

print("\nSentiment by Ticker:")
print(sentiment_by_ticker)
```

**Step 3:** Correlate sentiment with price changes

```python
# Get prices for same period
prices_filtered = prices[
    (prices['ticker'].isin(['AAPL', 'TSLA'])) &
    (prices['trade_date'] >= '2024-11-01')
].copy()

# Calculate daily returns
prices_filtered['return'] = prices_filtered.groupby('ticker')['close'].pct_change()

# Join with average daily sentiment
daily_sentiment = news.groupby(['publish_date', 'ticker'])['sentiment'].mean().reset_index()
daily_sentiment.columns = ['trade_date', 'ticker', 'avg_sentiment']

merged = prices_filtered.merge(
    daily_sentiment,
    on=['trade_date', 'ticker'],
    how='left'
)

# Calculate correlation
print("\nCorrelation between sentiment and returns:")
print(merged[['avg_sentiment', 'return']].corr())
```

---

### How to Create a Stock Analysis Notebook

**Step 1:** Create a new markdown file

Create `configs/notebooks/my_stock_analysis.md`:

```markdown
---
title: "My Stock Analysis"
model: company
filters:
  - ticker
  - date_range
---

# My Stock Analysis

## Filters

$filter${
  id: ticker
  label: Select Stocks
  type: select
  multi: true
  source: {model: company, table: dim_company, column: ticker}
  default: ["AAPL", "GOOGL", "MSFT"]
}

$filter${
  id: date_range
  label: Date Range
  type: date_range
  default: {start: 2024-10-01, end: 2024-11-08}
}

## Price Trends

$exhibits${
  type: line_chart
  title: "Stock Price Trends"
  source: company.fact_prices
  x: trade_date
  y: close
  color: ticker
  legend: true
}

## Trading Volume

$exhibits${
  type: bar_chart
  title: "Trading Volume by Stock"
  source: company.fact_prices
  x: ticker
  y: volume
  aggregation: sum
}

## Detailed Data

$exhibits${
  type: data_table
  title: "Price Data"
  source: company.fact_prices
  columns: [trade_date, ticker, open, high, low, close, volume]
  sortable: true
  download: true
}
```

**Step 2:** View in the UI

```bash
streamlit run app/ui/notebook_app_duckdb.py
```

Navigate to "My Stock Analysis" in the sidebar.

---

## Usage Examples

---

### Example 1: Basic Price Query

```python
from models.api.session import UniversalSession
from core.context import RepoContext

# Setup
ctx = RepoContext.from_repo_root()
session = UniversalSession(ctx.connection, ctx.config_root, ctx.storage_cfg)

# Get Apple prices for last 30 days
prices = session.get_table('company', 'fact_prices')
apple_prices = prices.filter(
    (prices['ticker'] == 'AAPL') &
    (prices['trade_date'] >= '2024-10-08')
).to_pandas()

print(apple_prices[['trade_date', 'close', 'volume']])
```

### Example 2: Multi-Stock Comparison

```python
# Compare tech stocks
tickers = ['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA']

filters = {
    'ticker': tickers,
    'trade_date': {'start': '2024-01-01', 'end': '2024-11-08'}
}

company = session.load_model('company')
prices = company.get_fact_df('fact_prices', filters=filters).to_pandas()

# Calculate cumulative returns
prices['return'] = prices.groupby('ticker')['close'].pct_change()
prices['cumulative_return'] = prices.groupby('ticker')['return'].cumsum()

# Plot
import plotly.express as px
fig = px.line(prices, x='trade_date', y='cumulative_return', color='ticker')
fig.show()
```

### Example 3: Cross-Model Analysis (Company + Macro)

```python
# Load both models
company = session.load_model('company')
macro = session.load_model('macro')

# Get stock prices
prices = company.get_fact_df('fact_prices').to_pandas()

# Get unemployment rate
unemployment = macro.get_fact_df('fact_unemployment').to_pandas()

# Join on date
unemployment['trade_date'] = unemployment['date']
merged = prices.merge(unemployment[['trade_date', 'value']], on='trade_date', how='left')
merged.rename(columns={'value': 'unemployment_rate'}, inplace=True)

# Analyze correlation
print(merged[['close', 'unemployment_rate']].corr())
```

See [[Macro Model]] for economic indicators.

### Example 4: Using Materialized Views

```python
# Use pre-joined view (faster than joining at query time)
prices_with_company = session.get_table('company', 'prices_with_company').to_pandas()

# Now you have company_name and exchange_name without joins
print(prices_with_company[['ticker', 'company_name', 'exchange_name', 'close']])

# Filter by exchange
nasdaq_stocks = prices_with_company[prices_with_company['exchange_name'] == 'NASDAQ']
print(f"Average NASDAQ price: ${nasdaq_stocks['close'].mean():.2f}")
```

---

## Design Decisions

---

### Why Partitioning by Date?

**Decision:** Partition fact tables by trade_date/publish_date

**Rationale:**
- Most queries filter by date range
- Enables partition pruning (10-100x faster)
- Aligns with data ingestion pattern (daily updates)
- Reduces I/O for time-based analytics

### Why Materialized Views?

**Decision:** Pre-compute `prices_with_company` and `news_with_company`

**Rationale:**
- Most analytics need company context
- Eliminates runtime join cost
- Trades storage for query speed
- Views auto-rebuild when dimensions change

### Why Multiple Weighted Indices?

**Decision:** Support 6 different weighting methods

**Rationale:**
- Different use cases (equal weight, market cap, volatility)
- Enables index comparison and analysis
- Mirrors real-world indices (S&P 500, DJIA)
- Low computational cost (pre-aggregated)

### Why market_cap_proxy Instead of Real Market Cap?

**Decision:** Use close × volume as market cap proxy

**Rationale:**
- Real market cap requires shares outstanding (not in Polygon daily feed)
- Proxy correlates well with actual market cap
- Available for all tickers daily
- Sufficient for weighted index calculations

**Limitation:** Not accurate for absolute market cap analysis

---

## Partitioning Strategy

---

### fact_prices

**Partition Column:** `trade_date`
**Partition Type:** Date
**Partition Format:** `trade_date=YYYY-MM-DD`

**Storage Layout:**
```
storage/silver/company/facts/fact_prices/
├── trade_date=2024-01-02/
│   └── part-00000.parquet
├── trade_date=2024-01-03/
│   └── part-00000.parquet
...
└── trade_date=2024-11-08/
    └── part-00000.parquet
```

**Query Optimization:**
- Filter: `WHERE trade_date >= '2024-11-01'` → Scans only 8 partitions
- No filter: Scans all ~250 partitions (trading days per year)

### fact_news

**Partition Column:** `publish_date`
**Partition Type:** Date
**Partition Format:** `publish_date=YYYY-MM-DD`

**Storage Layout:** Same as fact_prices

---

## Related Documentation

---

- [[Core Model]] - Shared calendar dimension
- [[Forecast Model]] - Uses company prices for training
- [[Macro Model]] - Economic indicators for correlation analysis
- [[Data Pipeline]] - How data is ingested from Polygon API
- [[Universal Session]] - Cross-model query examples

---

**Tags:** #finance/equities #component/model #concept/dimensional-modeling #source/polygon #status/stable

**Last Updated:** 2024-11-08
**Model Version:** 1.0
**Dependencies:** [[Core Model]]
**Used By:** [[Forecast Model]]
