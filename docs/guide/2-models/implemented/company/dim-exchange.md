---
title: "Exchange Dimension"
tags: [finance/equities, component/model, concept/dimensional-modeling, concept/reference]
aliases: ["Exchange Dimension", "dim_exchange", "Stock Exchanges"]
---

# Exchange Dimension

---

The Exchange dimension provides reference data for stock exchanges where companies are listed.

**Table:** `dim_exchange`
**Primary Key:** `exchange_code`
**Storage:** `storage/silver/company/dims/dim_exchange`

---

## Purpose

---

Stock exchanges serve as a reference dimension for filtering and grouping companies by their listing location.

**Use Cases:**
- Filter companies by exchange (NASDAQ, NYSE, etc.)
- Group price aggregations by exchange
- Understand market structure
- Track cross-listing activity

---

## Schema

---

**Grain:** One row per exchange

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| **exchange_code** | string | Exchange MIC code | "XNAS" |
| **exchange_name** | string | Exchange full name | "NASDAQ" |

---

## Sample Data

---

```
+---------------+--------------------------------+
| exchange_code | exchange_name                  |
+---------------+--------------------------------+
| XNAS          | NASDAQ                         |
| XNYS          | New York Stock Exchange        |
| BATS          | BATS Global Markets            |
| ARCX          | NYSE Arca                      |
| XASE          | NYSE American                  |
+---------------+--------------------------------+
```

---

## Data Source

---

**Provider:** Polygon.io
**API Endpoint:** `/v3/reference/exchanges`
**Bronze Table:** `bronze.exchanges`
**Update Frequency:** Weekly (rarely changes)

**Transformation:**
```yaml
from: bronze.exchanges
select:
  exchange_code: code
  exchange_name: name
```

---

## Usage Examples

---

### Get All Exchanges

```python
from models.api.session import UniversalSession
from core.context import RepoContext

ctx = RepoContext.from_repo_root()
session = UniversalSession(ctx.connection, ctx.config_root, ctx.storage_cfg)

# Get exchange dimension
exchanges = session.get_table('company', 'dim_exchange').to_pandas()

print(exchanges)
```

### Filter Companies by Exchange

```python
# Get companies
companies = session.get_table('company', 'dim_company').to_pandas()

# Join with exchanges
merged = companies.merge(exchanges, on='exchange_code')

# Filter to NASDAQ
nasdaq = merged[merged['exchange_code'] == 'XNAS']

print(f"NASDAQ companies: {len(nasdaq)}")
print(nasdaq[['ticker', 'company_name']].head())
```

### Aggregate Prices by Exchange

```python
# Get price data with company and exchange
company_model = session.load_model('company')
prices = company_model.get_fact_df('prices_with_company').to_pandas()

# Group by exchange
by_exchange = prices.groupby('exchange_name').agg({
    'ticker': 'nunique',       # Number of companies
    'volume': 'sum',            # Total volume
    'close': 'mean'             # Average price
})

print(by_exchange)
```

---

## Relationships

---

### Used By (Foreign Key References)

- **[[Company Dimension]]** - `dim_company.exchange_code → dim_exchange.exchange_code`

### Indirect Usage

- **[[Price Facts]]** - Via company dimension
- **[[News Facts]]** - Via company dimension

---

## Exchange Codes (MIC)

---

The **Market Identifier Code (MIC)** is an ISO standard for exchange identification.

**Common Codes:**
- **XNAS** - NASDAQ Stock Market
- **XNYS** - New York Stock Exchange
- **BATS** - BATS Global Markets
- **ARCX** - NYSE Arca (formerly ArcaEx)
- **XASE** - NYSE American (formerly AMEX)

See: [ISO 10383 MIC Codes](https://www.iso20022.org/market-identifier-codes)

---

## Design Decisions

---

### Why separate exchange dimension?

**Decision:** Create dedicated exchange dimension instead of embedding in company

**Rationale:**
- **Normalization** - Avoid repeating exchange names
- **Consistency** - Single source of truth for exchange data
- **Extensibility** - Can add exchange metadata (country, timezone, hours)
- **Clarity** - Clear dimensional modeling pattern

### Why use MIC codes?

**Decision:** Use ISO 10383 MIC codes as primary key

**Rationale:**
- **Standard** - Industry standard identifier
- **Unique** - Globally unique codes
- **Compact** - 4-character codes
- **Polygon compatibility** - Matches Polygon.io API

---

## Future Enhancements

---

### Planned Additions

- **Country** - Exchange country location
- **Timezone** - Exchange timezone for market hours
- **Currency** - Primary trading currency
- **Operating hours** - Market open/close times
- **Market type** - Primary, OTC, derivatives, etc.

---

## Related Documentation

---

### Model Documentation
- [[Company Model Overview]] - Parent model
- [[Company Dimension]] - Company profiles
- [[Price Facts]] - Daily prices

### Architecture Documentation
- [[Data Pipeline/Polygon]] - API ingestion
- [[Bronze Storage]] - Raw exchange data
- [[Silver Storage]] - Dimensional storage

---

**Tags:** #finance/equities #component/model #concept/dimensional-modeling #concept/reference

**Last Updated:** 2024-11-08
**Table:** dim_exchange
**Grain:** One row per exchange
