# Alpha Vantage API Reference

**Endpoint documentation and parameters**

---

## Base Configuration

```json
{
  "base_urls": {
    "core": "https://www.alphavantage.co"
  },
  "auth": {
    "type": "query_param",
    "param_name": "apikey"
  }
}
```

---

## Endpoints

### 1. Company Overview (OVERVIEW)

**Purpose**: Company fundamentals, SEC identifiers, sector classification

**Endpoint**: `GET /query?function=OVERVIEW`

| Parameter | Required | Description |
|-----------|----------|-------------|
| `function` | Yes | `OVERVIEW` |
| `symbol` | Yes | Stock ticker (e.g., `AAPL`) |
| `apikey` | Yes | Your API key |

**Response Fields** (key fields):

| Field | Type | Description |
|-------|------|-------------|
| `Symbol` | string | Ticker symbol |
| `Name` | string | Company name |
| `CIK` | string | SEC Central Index Key |
| `Exchange` | string | Exchange code |
| `Sector` | string | GICS sector |
| `Industry` | string | GICS industry |
| `MarketCapitalization` | string | Market cap in USD |
| `SharesOutstanding` | string | Shares outstanding |
| `DividendYield` | string | Dividend yield |
| `52WeekHigh` | string | 52-week high price |
| `52WeekLow` | string | 52-week low price |

**Example Request**:
```
https://www.alphavantage.co/query?function=OVERVIEW&symbol=AAPL&apikey=YOUR_KEY
```

**de_Funk Usage**: `SecuritiesReferenceFacetAV`

---

### 2. Daily Prices (TIME_SERIES_DAILY_ADJUSTED)

**Purpose**: Historical daily OHLCV with dividend/split adjustments

**Endpoint**: `GET /query?function=TIME_SERIES_DAILY_ADJUSTED`

| Parameter | Required | Description |
|-----------|----------|-------------|
| `function` | Yes | `TIME_SERIES_DAILY_ADJUSTED` |
| `symbol` | Yes | Stock ticker |
| `outputsize` | No | `compact` (100 days) or `full` (20+ years) |
| `apikey` | Yes | Your API key |

**Response Structure**:
```json
{
  "Meta Data": {
    "1. Information": "Daily Time Series with Splits and Dividend Events",
    "2. Symbol": "AAPL",
    "3. Last Refreshed": "2024-01-15"
  },
  "Time Series (Daily)": {
    "2024-01-15": {
      "1. open": "150.00",
      "2. high": "152.00",
      "3. low": "149.00",
      "4. close": "151.00",
      "5. adjusted close": "151.00",
      "6. volume": "50000000",
      "7. dividend amount": "0.00",
      "8. split coefficient": "1.0"
    }
  }
}
```

**de_Funk Usage**: `SecuritiesPricesFacetAV`

---

### 3. Listing Status (LISTING_STATUS)

**Purpose**: Bulk discovery of all active/delisted tickers

**Endpoint**: `GET /query?function=LISTING_STATUS`

| Parameter | Required | Description |
|-----------|----------|-------------|
| `function` | Yes | `LISTING_STATUS` |
| `state` | No | `active` or `delisted` |
| `apikey` | Yes | Your API key |

**Response**: CSV format (not JSON)

```csv
symbol,name,exchange,assetType,ipoDate,delistingDate,status
A,Agilent Technologies Inc,NYSE,Stock,1999-11-18,null,Active
AA,Alcoa Corporation,NYSE,Stock,2016-11-01,null,Active
```

**Key Benefit**: One API call returns ALL tickers!

**de_Funk Usage**: `AlphaVantageIngestor.ingest_bulk_listing()`

---

### 4. Global Quote (GLOBAL_QUOTE)

**Purpose**: Real-time quote for a single ticker

**Endpoint**: `GET /query?function=GLOBAL_QUOTE`

| Parameter | Required | Description |
|-----------|----------|-------------|
| `function` | Yes | `GLOBAL_QUOTE` |
| `symbol` | Yes | Stock ticker |
| `apikey` | Yes | Your API key |

**Response Fields**:

| Field | Description |
|-------|-------------|
| `01. symbol` | Ticker |
| `02. open` | Open price |
| `03. high` | High price |
| `04. low` | Low price |
| `05. price` | Current/close price |
| `06. volume` | Volume |
| `07. latest trading day` | Date |
| `08. previous close` | Previous close |
| `09. change` | Price change |
| `10. change percent` | Change % |

---

### 5. Technical Indicators

#### Simple Moving Average (SMA)

**Endpoint**: `GET /query?function=SMA`

| Parameter | Required | Description |
|-----------|----------|-------------|
| `function` | Yes | `SMA` |
| `symbol` | Yes | Stock ticker |
| `interval` | Yes | `daily`, `weekly`, `monthly` |
| `time_period` | Yes | Number of periods (e.g., 20) |
| `series_type` | Yes | `close`, `open`, `high`, `low` |

#### Relative Strength Index (RSI)

**Endpoint**: `GET /query?function=RSI`

| Parameter | Required | Description |
|-----------|----------|-------------|
| `function` | Yes | `RSI` |
| `symbol` | Yes | Stock ticker |
| `interval` | Yes | `daily`, `weekly`, `monthly` |
| `time_period` | Yes | Number of periods (e.g., 14) |
| `series_type` | Yes | `close`, `open`, `high`, `low` |

#### MACD

**Endpoint**: `GET /query?function=MACD`

| Parameter | Required | Description |
|-----------|----------|-------------|
| `function` | Yes | `MACD` |
| `symbol` | Yes | Stock ticker |
| `interval` | Yes | `daily`, `weekly`, `monthly` |
| `series_type` | Yes | `close`, `open`, `high`, `low` |
| `fastperiod` | No | Fast EMA period (default: 12) |
| `slowperiod` | No | Slow EMA period (default: 26) |
| `signalperiod` | No | Signal period (default: 9) |

---

### 6. Symbol Search (SYMBOL_SEARCH)

**Purpose**: Find tickers by company name

**Endpoint**: `GET /query?function=SYMBOL_SEARCH`

| Parameter | Required | Description |
|-----------|----------|-------------|
| `function` | Yes | `SYMBOL_SEARCH` |
| `keywords` | Yes | Search term |
| `apikey` | Yes | Your API key |

**Response**:
```json
{
  "bestMatches": [
    {
      "1. symbol": "AAPL",
      "2. name": "Apple Inc",
      "3. type": "Equity",
      "4. region": "United States",
      "5. marketOpen": "09:30",
      "6. marketClose": "16:00",
      "7. timezone": "UTC-05",
      "8. currency": "USD",
      "9. matchScore": "1.0000"
    }
  ]
}
```

---

## Error Responses

### Rate Limit Exceeded

```json
{
  "Note": "Thank you for using Alpha Vantage! Our standard API call frequency is 5 calls per minute and 500 calls per day. Please visit https://www.alphavantage.co/premium/ if you would like to target a higher API call frequency."
}
```

### Invalid API Key

```json
{
  "Error Message": "Invalid API call. Please retry or visit the documentation (https://www.alphavantage.co/documentation/) for TIME_SERIES_DAILY_ADJUSTED."
}
```

### Invalid Symbol

```json
{
  "Error Message": "Invalid API call. Please retry or visit the documentation."
}
```

---

## Configuration File

**File**: `configs/alpha_vantage_endpoints.json`

```json
{
  "base_urls": {
    "core": "https://www.alphavantage.co"
  },
  "rate_limit": {
    "calls_per_second": 1.0
  },
  "endpoints": {
    "company_overview": {
      "base": "core",
      "method": "GET",
      "path_template": "/query",
      "required_params": ["symbol"],
      "default_query": {
        "function": "OVERVIEW"
      }
    },
    "time_series_daily_adjusted": {
      "base": "core",
      "method": "GET",
      "path_template": "/query",
      "required_params": ["symbol"],
      "default_query": {
        "function": "TIME_SERIES_DAILY_ADJUSTED",
        "outputsize": "compact"
      }
    },
    "listing_status": {
      "base": "core",
      "method": "GET",
      "path_template": "/query",
      "default_query": {
        "function": "LISTING_STATUS",
        "state": "active"
      }
    }
  }
}
```

---

## Related Documentation

- [Terms of Use](terms-of-use.md) - Usage restrictions
- [Rate Limits](rate-limits.md) - Throttling strategies
- [Facets](facets.md) - Data transformations
