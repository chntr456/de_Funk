---
title: "Polygon.io Integration"
tags: [finance/equities, component/data-pipeline, source/polygon, concept/api]
aliases: ["Polygon Integration", "Polygon API", "Market Data Source"]
---

# Polygon.io Integration

---

Polygon.io provides real-time and historical stock market data for the Company model through a REST API.

**Provider:** Polygon.io
**Documentation:** https://polygon.io/docs
**API Version:** v2 / v3
**Data Coverage:** US equities, real-time and historical

---

## Purpose

---

Polygon.io serves as the primary data source for:
- Daily stock prices (OHLCV)
- Company reference data (tickers, exchanges)
- News articles with sentiment
- Real-time market updates

---

## API Endpoints

---

### 1. Aggregates (Bars) - Price Data

**Endpoint:** `/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from}/{to}`

**Purpose:** Historical OHLCV price data

**Example:**
```
GET /v2/aggs/ticker/AAPL/range/1/day/2024-01-01/2024-11-08
```

**Response:**
```json
{
  "ticker": "AAPL",
  "results": [
    {
      "t": 1704096000000,      // Unix timestamp
      "o": 185.28,              // Open
      "h": 186.42,              // High
      "l": 184.35,              // Low
      "c": 185.92,              // Close
      "v": 48592847,            // Volume
      "vw": 185.64              // Volume weighted
    }
  ]
}
```

**Bronze Table:** `bronze.prices_daily`

---

### 2. Reference Tickers - Company Data

**Endpoint:** `/v3/reference/tickers`

**Purpose:** Company metadata, exchange listings, ticker symbols

**Example:**
```
GET /v3/reference/tickers?market=stocks&active=true
```

**Response:**
```json
{
  "results": [
    {
      "ticker": "AAPL",
      "name": "Apple Inc.",
      "market": "stocks",
      "locale": "us",
      "primary_exchange": "XNAS",
      "type": "CS",
      "active": true,
      "currency_name": "usd"
    }
  ]
}
```

**Bronze Table:** `bronze.ref_ticker`

---

### 3. Exchanges - Reference Data

**Endpoint:** `/v3/reference/exchanges`

**Purpose:** Stock exchange information

**Example:**
```
GET /v3/reference/exchanges?asset_class=stocks
```

**Response:**
```json
{
  "results": [
    {
      "id": 1,
      "type": "exchange",
      "market": "stocks",
      "mic": "XNAS",
      "name": "NASDAQ",
      "tape": "Q"
    }
  ]
}
```

**Bronze Table:** `bronze.exchanges`

---

### 4. Ticker News - News Articles

**Endpoint:** `/v2/reference/news`

**Purpose:** News articles with ticker associations and sentiment

**Example:**
```
GET /v2/reference/news?ticker=AAPL&limit=100
```

**Response:**
```json
{
  "results": [
    {
      "id": "abc123xyz",
      "publisher": {
        "name": "Bloomberg"
      },
      "title": "Apple Announces New MacBook Pro",
      "published_utc": "2024-11-08T14:30:00Z",
      "article_url": "https://...",
      "tickers": ["AAPL"],
      "insights": [
        {
          "ticker": "AAPL",
          "sentiment": "positive",
          "sentiment_reasoning": "Positive product announcement",
          "sentiment_score": 0.75
        }
      ]
    }
  ]
}
```

**Bronze Table:** `bronze.news`

---

## Data Pipeline

---

### Bronze Layer (Raw Ingestion)

**Location:** `storage/bronze/polygon/`

**Tables:**
- `prices_daily` - Raw daily price bars
- `ref_ticker` - Company reference data
- `exchanges` - Exchange reference data
- `news` - News articles with sentiment

**Format:** Parquet (partitioned by date)

**Update Frequency:**
- Prices: Daily after market close
- News: Real-time streaming
- Reference: Weekly

---

### Silver Layer (Dimensional Model)

**Location:** `storage/silver/company/`

**Transformation:** Bronze → Silver via Company model graph

**Process:**
1. Read from Bronze tables
2. Apply facet normalization ([[Facets/Prices]], [[Facets/News]])
3. Build dimensional schema ([[Company Dimension]], [[Price Facts]], [[News Facts]])
4. Write to Silver storage

See [[Company Model Overview]] for complete schema.

---

## Authentication

---

**API Key Required:** Yes

**Configuration:**
```bash
# Environment variable
export POLYGON_API_KEY="your_api_key_here"

# Or in config file
# configs/providers/polygon.yaml
api_key: ${POLYGON_API_KEY}
```

**Rate Limits:**
- Free tier: 5 requests/minute
- Starter tier: 100 requests/minute
- Developer tier: 500 requests/minute

---

## Facet Normalization

---

### Price Facet

**Purpose:** Normalize OHLCV data from Polygon format to canonical schema

**Mapping:**
```yaml
from: polygon.aggregates
to: bronze.prices_daily
fields:
  t → trade_date (convert Unix timestamp to date)
  o → open
  h → high
  l → low
  c → close
  v → volume
  vw → volume_weighted
  ticker → ticker (from request)
```

See [[Facets/Prices]] for detailed normalization logic.

---

### News Facet

**Purpose:** Normalize news articles and sentiment data

**Mapping:**
```yaml
from: polygon.news
to: bronze.news
fields:
  id → article_id
  title → title
  published_utc → publish_date
  publisher.name → source
  insights[].ticker → ticker (explode to multiple rows)
  insights[].sentiment_score → sentiment
```

See [[Facets/News]] for detailed normalization logic.

---

## Provider Implementation

---

**Location:** `models/providers/polygon_provider.py`

**Key Classes:**
- `PolygonProvider` - Main API client
- `PolygonIngestor` - Bronze layer ingestion
- `PriceFacet` - Price data normalization
- `NewsFacet` - News data normalization

**Example:**
```python
from models.providers.polygon_provider import PolygonProvider

# Initialize provider
provider = PolygonProvider(api_key=os.getenv('POLYGON_API_KEY'))

# Fetch price data
prices = provider.get_aggregates(
    ticker='AAPL',
    from_date='2024-01-01',
    to_date='2024-11-08',
    timespan='day'
)

# Fetch news
news = provider.get_news(
    ticker='AAPL',
    limit=100
)
```

---

## Usage Examples

---

### Manual Ingestion

```python
from models.providers.polygon_provider import PolygonProvider
from models.ingestors.bronze_writer import BronzeWriter

# Initialize
provider = PolygonProvider(api_key=os.getenv('POLYGON_API_KEY'))
writer = BronzeWriter(storage_root='storage/bronze/polygon')

# Ingest price data for multiple tickers
tickers = ['AAPL', 'MSFT', 'GOOGL']

for ticker in tickers:
    data = provider.get_aggregates(
        ticker=ticker,
        from_date='2024-01-01',
        to_date='2024-11-08'
    )

    writer.write_prices(data, ticker=ticker)

print("Ingestion complete!")
```

### Backfill Historical Data

```python
from datetime import datetime, timedelta

# Backfill last 2 years
end_date = datetime.now()
start_date = end_date - timedelta(days=730)

for ticker in tickers:
    data = provider.get_aggregates(
        ticker=ticker,
        from_date=start_date.strftime('%Y-%m-%d'),
        to_date=end_date.strftime('%Y-%m-%d')
    )

    writer.write_prices(data, ticker=ticker, mode='overwrite')
```

---

## Data Quality

---

### Coverage

- **Tickers:** ~50,000 US equities (all major exchanges)
- **History:** Most stocks from IPO date
- **Frequency:** Tick-level to daily aggregates
- **Delays:** Real-time (premium) or 15-minute delay (free)

### Reliability

- **Uptime:** 99.9% SLA
- **Data accuracy:** Exchange-quality data
- **Corrections:** Corporate actions adjusted
- **Splits:** Automatically adjusted

### Known Issues

- **Delisted stocks:** Limited historical data
- **Pre-market/after-hours:** Separate endpoints
- **International:** US markets only in base tier

---

## Cost Considerations

---

**Free Tier:**
- 5 API calls/minute
- 2 years historical data
- 15-minute delayed data

**Starter Tier ($29/month):**
- 100 calls/minute
- Full historical data
- Real-time data

**Developer Tier ($99/month):**
- 500 calls/minute
- WebSocket streaming
- Technical indicators

**Recommendation:** Starter tier sufficient for daily batch updates

---

## Related Documentation

---

### Model Documentation
- [[Company Model Overview]] - Data consumer
- [[Price Facts]] - Price schema
- [[News Facts]] - News schema
- [[Company Dimension]] - Company reference

### Architecture Documentation
- [[Data Pipeline/Overview]] - Ingestion architecture
- [[Providers]] - Provider framework
- [[Facets/Prices]] - Price normalization
- [[Facets/News]] - News normalization
- [[Bronze Storage]] - Raw data storage

### External Resources
- [Polygon.io Documentation](https://polygon.io/docs)
- [API Reference](https://polygon.io/docs/stocks/getting-started)
- [Rate Limits](https://polygon.io/pricing)

---

**Tags:** #finance/equities #component/data-pipeline #source/polygon #concept/api

**Last Updated:** 2024-11-08
**Provider:** Polygon.io
**API Version:** v2/v3
