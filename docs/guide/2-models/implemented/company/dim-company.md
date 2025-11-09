---
title: "Company Dimension"
tags: [finance/equities, component/model, concept/dimensional-modeling, concept/entity]
aliases: ["Company Dimension", "dim_company", "Company Profiles"]
---

# Company Dimension

---

The Company dimension provides company profiles with ticker symbols, exchange listings, and market capitalization proxies.

**Table:** `dim_company`
**Primary Key:** `ticker`
**Storage:** `storage/silver/company/dims/dim_company`

---

## Purpose

---

Company profiles serve as the central entity dimension for stock market analysis, linking price data, news, and other facts to specific publicly traded companies.

**Use Cases:**
- Filter prices by company
- Join news to company metadata
- Calculate market cap weighted indices
- Track exchange listings
- Identify active vs delisted stocks

---

## Schema

---

**Grain:** One row per ticker symbol

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| **ticker** | string | Stock ticker symbol | "AAPL" |
| **company_name** | string | Company legal name | "Apple Inc." |
| **exchange_code** | string | Exchange listing code | "XNAS" |
| **company_id** | string | SHA1 hash of ticker | "d033e22..." |
| **market_cap_proxy** | double | Latest market cap estimate | 2847392000000.0 |
| **latest_trade_date** | date | Most recent trading date | 2024-11-08 |

---

## Sample Data

---

```
+--------+------------------+---------------+-------------+------------------+-------------------+
| ticker | company_name     | exchange_code | company_id  | market_cap_proxy | latest_trade_date |
+--------+------------------+---------------+-------------+------------------+-------------------+
| AAPL   | Apple Inc.       | XNAS          | d033e22...  | 2.85T            | 2024-11-08        |
| MSFT   | Microsoft Corp.  | XNAS          | 98dce83...  | 2.78T            | 2024-11-08        |
| GOOGL  | Alphabet Inc.    | XNAS          | 3c59dc0...  | 1.72T            | 2024-11-08        |
| TSLA   | Tesla Inc.       | XNAS          | eccbc87...  | 789.2B           | 2024-11-08        |
+--------+------------------+---------------+-------------+------------------+-------------------+
```

---

## Data Source

---

**Provider:** Polygon.io
**API Endpoint:** `/v3/reference/tickers`
**Bronze Table:** `bronze.ref_ticker`
**Update Frequency:** Weekly

**Transformation:**
```yaml
from: bronze.ref_ticker
select:
  ticker: ticker
  company_name: name
  exchange_code: exchange_code
derive:
  company_id: "sha1(ticker)"  # Unique hash identifier
```

---

## Usage Examples

---

### Get Company Information

```python
from models.api.session import UniversalSession
from core.context import RepoContext

ctx = RepoContext.from_repo_root()
session = UniversalSession(ctx.connection, ctx.config_root, ctx.storage_cfg)

# Get company dimension
companies = session.get_table('company', 'dim_company').to_pandas()

# Filter to tech companies
tech = companies[companies['ticker'].isin(['AAPL', 'MSFT', 'GOOGL', 'META'])]

print(tech[['ticker', 'company_name', 'market_cap_proxy']])
```

### Join with Price Data

```python
# Get prices
company_model = session.load_model('company')
prices = company_model.get_fact_df('fact_prices').to_pandas()

# Join with company info
merged = prices.merge(companies, on='ticker')

# Calculate market cap
merged['market_cap'] = merged['close'] * merged['volume']

# Group by company
by_company = merged.groupby('company_name').agg({
    'close': 'mean',
    'volume': 'sum',
    'market_cap': 'mean'
})

print(by_company)
```

### Filter by Exchange

```python
# Get all NASDAQ-listed companies
nasdaq = companies[companies['exchange_code'] == 'XNAS']

print(f"Total NASDAQ companies: {len(nasdaq)}")
print(nasdaq[['ticker', 'company_name']].head(10))
```

---

## Relationships

---

### Used By (Foreign Key References)

- **[[Price Facts]]** - `fact_prices.ticker → dim_company.ticker`
- **[[News Facts]]** - `fact_news.ticker → dim_company.ticker`

### Dependencies

- **[[Exchange Dimension]]** - `dim_company.exchange_code → dim_exchange.exchange_code`
- **[[Calendar]]** - `dim_company.latest_trade_date → dim_calendar.date`

---

## Derived Fields

---

### company_id

**Formula:** `SHA1(ticker)`
**Purpose:** Unique identifier for graph databases and deduplication
**Example:** `SHA1("AAPL")` → `d033e22ae348aeb5660fc2140aec35850c4da997`

### market_cap_proxy

**Formula:** Latest `close * volume` from price data
**Purpose:** Approximate market capitalization for index weighting
**Note:** Not exact market cap (uses volume as share proxy)

---

## Design Decisions

---

### Why ticker as primary key?

**Decision:** Use `ticker` as primary key instead of `company_id`

**Rationale:**
- Ticker is natural key used in all queries
- Human-readable and familiar to analysts
- Direct join to price and news facts
- Consistent with industry standards

### Why include market_cap_proxy?

**Decision:** Store latest market cap estimate in dimension

**Rationale:**
- Enable market-cap weighted index calculations
- Avoid expensive joins for simple filtering (e.g., "large cap stocks")
- Updated during each model build
- Acknowledged as approximate (not authoritative market cap)

---

## Future Enhancements

---

### Planned Additions

- **Sector classification** - GICS industry codes
- **Company size** - Market cap tier (large/mid/small)
- **Country** - Company headquarters location
- **IPO date** - Initial public offering date
- **Delisting tracking** - Historical ticker status

---

## Related Documentation

---

### Model Documentation
- [[Company Model Overview]] - Parent model
- [[Exchange Dimension]] - Exchange reference
- [[Price Facts]] - Daily prices
- [[News Facts]] - News sentiment

### Architecture Documentation
- [[Data Pipeline/Polygon]] - API ingestion
- [[Facets/Ticker]] - Ticker normalization
- [[Bronze Storage]] - Raw ticker data
- [[Silver Storage]] - Dimensional storage

---

**Tags:** #finance/equities #component/model #concept/dimensional-modeling #concept/entity

**Last Updated:** 2024-11-08
**Table:** dim_company
**Grain:** One row per ticker
