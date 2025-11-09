---
title: "Company Model Overview"
tags: [finance/equities, component/model, source/polygon, status/stable]
aliases: ["Company Model", "Stock Model", "Equities Model"]
dependencies: ["[[Calendar]]"]
architecture_components:
  - "[[Data Pipeline/Polygon]]"
  - "[[Facets/Prices]]"
  - "[[Facets/News]]"
  - "[[Bronze Storage]]"
  - "[[Silver Storage]]"
---

# Company Model - Overview

---

The Company Model provides comprehensive stock market data including daily prices, company information, news sentiment, and pre-built analytics for equity analysis.

**Data Source:** Polygon.io API
**Dependencies:** [[Calendar]]
**Storage:** `storage/silver/company`

---

## Model Components

---

### Dimensions
- **[[Company Dimension]]** - Company profiles with ticker, exchange, market cap
- **[[Exchange Dimension]]** - Stock exchange reference data

### Facts
- **[[Price Facts]]** - Daily OHLCV stock prices
- **[[News Facts]]** - News articles with sentiment analysis

### Measures
- **[[Company Measures]]** - Pre-defined aggregations and weighted indices

### Materialized Analytics
- **prices_with_company** - Prices joined with company and exchange context
- **news_with_company** - News joined with company information

---

## Quick Stats

| Metric | Value |
|--------|-------|
| **Companies** | ~500 tickers |
| **Time Range** | 2010-present |
| **Update Frequency** | Daily |
| **Fact Tables** | 4 (2 base + 2 materialized) |
| **Dimension Tables** | 2 |
| **Pre-built Measures** | 12 |
| **Weighted Indices** | 6 |

---

## Star Schema

---

```
dim_calendar (from Core)
     ↓
fact_prices ───→ dim_company ───→ dim_exchange
     ↓
fact_news ─────→ dim_company
```

**Grain:**
- **fact_prices:** One row per ticker per trading day
- **fact_news:** One row per article per ticker

---

## Key Features

---

### 1. Comprehensive Price Data
- Daily OHLCV (Open, High, Low, Close, Volume)
- Volume-weighted average price (VWAP)
- Partitioned by trade date for fast queries

### 2. News Sentiment Analysis
- Article-level sentiment scores
- Multi-ticker tagging
- Source tracking

### 3. Pre-built Measures
- Market cap proxy calculations
- Average/min/max price aggregations
- Total volume calculations
- VWAP averaging

### 4. Weighted Index Construction
- **Equal weighted** - Simple average across stocks
- **Volume weighted** - Weighted by trading volume
- **Market cap weighted** - Weighted by market capitalization
- **Price weighted** - Weighted by stock price (Dow-style)
- **Volatility weighted** - Inverse volatility (risk-adjusted)
- **Volume deviation weighted** - Unusual trading activity

---

## Data Sources

---

**Provider:** Polygon.io
**API Documentation:** https://polygon.io/docs
**Bronze Tables:** `bronze.prices_daily`, `bronze.news`, `bronze.ref_ticker`, `bronze.exchanges`

**Update Schedule:**
- Prices: Daily (after market close)
- News: Real-time ingestion
- Company metadata: Weekly

See **[[Polygon Integration]]** for detailed API documentation.

---

## Usage Example

---

```python
from models.api.session import UniversalSession
from core.context import RepoContext

ctx = RepoContext.from_repo_root()
session = UniversalSession(ctx.connection, ctx.config_root, ctx.storage_cfg)

# Get company model
company = session.load_model('company')

# Get price data with company context
prices = company.get_fact_df('prices_with_company').to_pandas()

# Filter to specific companies
tech_stocks = prices[prices['ticker'].isin(['AAPL', 'MSFT', 'GOOGL'])]

# Calculate returns
tech_stocks['daily_return'] = tech_stocks.groupby('ticker')['close'].pct_change()

print(tech_stocks.head())
```

---

## Related Documentation

---

### Model Documentation
- [[Company Dimension]] - Company profiles and metadata
- [[Exchange Dimension]] - Stock exchange reference
- [[Price Facts]] - Daily price data schema
- [[News Facts]] - News sentiment schema
- [[Company Measures]] - Aggregations and indices

### Architecture Documentation
- [[Data Pipeline/Polygon]] - API ingestion
- [[Facets/Prices]] - Price normalization
- [[Facets/News]] - News normalization
- [[Bronze Storage]] - Raw data storage
- [[Silver Storage]] - Dimensional storage

### How-To Guides
- [[How to Query Stock Prices]]
- [[How to Calculate Custom Indices]]
- [[How to Analyze News Sentiment]]

---

**Tags:** #finance/equities #component/model #source/polygon #architecture/ingestion-to-analytics

**Last Updated:** 2024-11-08
**Model:** company
**Version:** 1
