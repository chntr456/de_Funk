---
title: "News Facts"
tags: [finance/equities, component/model, concept/facts, concept/sentiment]
aliases: ["News Facts", "fact_news", "Stock News", "News Sentiment"]
---

# News Facts

---

News articles with sentiment analysis, linked to stock tickers for market event tracking and sentiment-based analysis.

**Table:** `fact_news`
**Grain:** One row per article per ticker
**Storage:** `storage/silver/company/facts/fact_news`
**Partitioned By:** `publish_date`

---

## Purpose

---

News facts provide sentiment analysis and article metadata to understand market-moving events and news impact on stock prices.

**Use Cases:**
- Sentiment trend analysis
- Event detection
- News-driven trading signals
- Correlation with price movements
- Topic clustering
- Source analysis

---

## Schema

---

**Grain:** One row per article per ticker (articles can mention multiple tickers)

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| **publish_date** | date | Article publication date | 2024-11-08 |
| **ticker** | string | Related stock ticker | "AAPL" |
| **article_id** | string | Unique article identifier | "abc123..." |
| **title** | string | Article headline | "Apple announces new..." |
| **source** | string | News source/publisher | "Bloomberg" |
| **sentiment** | double | Sentiment score (-1 to +1) | 0.75 |

**Partitioned By:** `publish_date` (year-month partitioning)

---

## Sample Data

---

```
+--------------+--------+-------------+--------------------------------+------------+-----------+
| publish_date | ticker | article_id  | title                          | source     | sentiment |
+--------------+--------+-------------+--------------------------------+------------+-----------+
| 2024-11-08   | AAPL   | abc123...   | Apple announces new MacBook... | Bloomberg  | 0.75      |
| 2024-11-08   | AAPL   | def456...   | iPhone sales decline in Chi... | Reuters    | -0.32     |
| 2024-11-08   | MSFT   | ghi789...   | Microsoft cloud revenue surg...| CNBC       | 0.88      |
| 2024-11-08   | TSLA   | jkl012...   | Tesla faces regulatory scru... | WSJ        | -0.65     |
+--------------+--------+-------------+--------------------------------+------------+-----------+
```

---

## Data Source

---

**Provider:** Polygon.io
**API Endpoint:** `/v2/reference/news`
**Bronze Table:** `bronze.news`
**Update Frequency:** Real-time (continuous ingestion)

**Transformation:**
```yaml
from: bronze.news
select:
  publish_date: publish_date
  ticker: ticker
  article_id: article_id
  title: title
  source: source
  sentiment: sentiment
```

**Multi-Ticker Handling:**
- Articles mentioning multiple tickers create multiple rows
- Same article_id appears for each ticker mentioned
- Enables ticker-specific news filtering

---

## Usage Examples

---

### Get Recent News

```python
from models.api.session import UniversalSession
from core.context import RepoContext

ctx = RepoContext.from_repo_root()
session = UniversalSession(ctx.connection, ctx.config_root, ctx.storage_cfg)

# Get news facts
company = session.load_model('company')
news = company.get_fact_df('fact_news').to_pandas()

# Filter to recent news for specific ticker
aapl_news = news[
    (news['ticker'] == 'AAPL') &
    (news['publish_date'] >= '2024-11-01')
].sort_values('publish_date', ascending=False)

print(aapl_news[['publish_date', 'title', 'source', 'sentiment']].head())
```

### Sentiment Trends

```python
# Daily average sentiment by ticker
sentiment_trends = news.groupby(['ticker', 'publish_date']).agg({
    'sentiment': 'mean',
    'article_id': 'count'  # Number of articles
}).reset_index()

sentiment_trends.columns = ['ticker', 'publish_date', 'avg_sentiment', 'article_count']

# Filter to high-coverage stocks
popular = sentiment_trends[sentiment_trends['article_count'] >= 5]

print(popular.head(10))
```

### Identify Negative News

```python
# Find strongly negative news
negative_news = news[news['sentiment'] < -0.5].copy()

# Group by ticker
negative_by_ticker = negative_news.groupby('ticker').agg({
    'article_id': 'count',
    'sentiment': 'mean'
}).reset_index()

negative_by_ticker.columns = ['ticker', 'negative_article_count', 'avg_negative_sentiment']

print(negative_by_ticker.sort_values('negative_article_count', ascending=False).head())
```

### Source Analysis

```python
# Most active news sources
source_stats = news.groupby('source').agg({
    'article_id': 'nunique',    # Unique articles
    'ticker': 'nunique',         # Stocks covered
    'sentiment': 'mean'          # Average sentiment
}).reset_index()

source_stats.columns = ['source', 'article_count', 'stocks_covered', 'avg_sentiment']

print(source_stats.sort_values('article_count', ascending=False).head(10))
```

### Correlate News with Price Movement

```python
# Get price data
prices = company.get_fact_df('fact_prices').to_pandas()

# Daily price change
prices_sorted = prices.sort_values(['ticker', 'trade_date'])
prices_sorted['price_change_pct'] = prices_sorted.groupby('ticker')['close'].pct_change()

# Daily average sentiment
daily_sentiment = news.groupby(['ticker', 'publish_date']).agg({
    'sentiment': 'mean'
}).reset_index()

# Merge sentiment with next-day price change
merged = daily_sentiment.merge(
    prices_sorted[['ticker', 'trade_date', 'price_change_pct']],
    left_on=['ticker', 'publish_date'],
    right_on=['ticker', 'trade_date'],
    how='inner'
)

# Correlation
correlation = merged.groupby('ticker')[['sentiment', 'price_change_pct']].corr().iloc[0::2, -1]

print("Sentiment-Price Correlation by Ticker:")
print(correlation.sort_values(ascending=False))
```

---

## Relationships

---

### Foreign Keys

- **ticker** → [[Company Dimension]].ticker
- **publish_date** → [[Calendar]].date

### Used By

- **news_with_company** - Materialized view with company context

---

## Sentiment Scoring

---

### Sentiment Scale

**Range:** -1.0 (most negative) to +1.0 (most positive)

**Interpretation:**
- **+0.5 to +1.0** - Strongly positive (bullish)
- **+0.1 to +0.5** - Moderately positive
- **-0.1 to +0.1** - Neutral
- **-0.5 to -0.1** - Moderately negative
- **-1.0 to -0.5** - Strongly negative (bearish)

### Sentiment Calculation

Sentiment scores are provided by Polygon.io using NLP models trained on financial news.

**Factors Considered:**
- Headline language
- Article tone
- Financial keywords (beats, misses, surges, plunges)
- Forward-looking statements

---

## Design Decisions

---

### Why one row per ticker per article?

**Decision:** Duplicate articles across tickers when multiple mentioned

**Rationale:**
- **Simplicity** - Easy ticker filtering without JSON arrays
- **Query performance** - Direct ticker joins
- **Fact table pattern** - Dimensional modeling best practice
- **Aggregation** - Natural grouping by ticker

**Alternative Considered:** Array of tickers in single row
**Why Rejected:** Complex queries, poor join performance

### Why partition by publish_date?

**Decision:** Partition by year-month of publication date

**Rationale:**
- Most queries filter by date range
- Aligns with data ingestion (continuous stream)
- Efficient for recent news queries
- Reduces scan costs

---

## Related Documentation

---

### Model Documentation
- [[Company Model Overview]] - Parent model
- [[Company Dimension]] - Company profiles
- [[Price Facts]] - Price data for correlation
- [[Company Measures]] - Sentiment aggregations

### Architecture Documentation
- [[Data Pipeline/Polygon]] - API ingestion
- [[Facets/News]] - News normalization
- [[Bronze Storage]] - Raw news data
- [[Silver Storage]] - Partitioning strategy

### How-To Guides
- [[How to Analyze News Sentiment]]
- [[How to Detect Market Events]]
- [[How to Correlate News with Prices]]

---

**Tags:** #finance/equities #component/model #concept/facts #concept/sentiment #pattern/star-schema

**Last Updated:** 2024-11-08
**Table:** fact_news
**Grain:** One row per article per ticker
