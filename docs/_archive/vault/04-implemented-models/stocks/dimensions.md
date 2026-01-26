# Stocks Dimensions

**Stock reference data schema**

---

## dim_stock

**Purpose**: Stock equity reference dimension

**Primary Key**: `ticker`

**Extends**: `_base.securities._dim_security`

**Record Count**: ~1,000+ (depends on ingestion scope)

---

## Schema

### Inherited Fields (from _base.securities)

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `ticker` | string | Stock symbol (PK) | `AAPL` |
| `security_name` | string | Full security name | `Apple Inc` |
| `asset_type` | string | Asset classification | `stocks` |
| `asset_class` | string | Broader classification | `equity` |
| `exchange_code` | string | Exchange | `NASDAQ` |
| `currency` | string | Trading currency | `USD` |
| `is_active` | boolean | Active trading status | `true` |
| `listing_date` | date | IPO/listing date | `1980-12-12` |
| `delisting_date` | date | Delisting date (if any) | `null` |
| `last_updated` | timestamp | Last data update | `2024-01-15T10:00:00` |

### Stocks-Specific Fields

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `company_id` | string | FK to company.dim_company | `COMPANY_0000320193` |
| `cik` | string | SEC Central Index Key (10 digits) | `0000320193` |
| `stock_type` | string | Stock classification | `common` |
| `shares_outstanding` | long | Current shares outstanding | `15700000000` |
| `market_cap` | double | Latest market capitalization | `2500000000000` |
| `beta` | double | Beta vs SPY (500-day rolling) | `1.25` |
| `sector` | string | GICS sector (denormalized) | `Technology` |
| `industry` | string | GICS industry (denormalized) | `Consumer Electronics` |

### Stock Type Values

| Value | Description |
|-------|-------------|
| `common` | Common stock (default) |
| `preferred` | Preferred stock |
| `adr` | American Depositary Receipt |
| `rights` | Stock rights |
| `units` | Units (stock + warrants) |
| `warrants` | Stock warrants |

---

## Source Mapping

| Column | Bronze Source | Transformation |
|--------|---------------|----------------|
| `ticker` | securities_reference.ticker | Direct |
| `security_name` | securities_reference.security_name | Direct |
| `cik` | securities_reference.cik | Padded to 10 digits |
| `company_id` | Derived | `CONCAT('COMPANY_', cik)` |
| `exchange_code` | securities_reference.exchange_code | Direct |
| `sector` | securities_reference.sector | Direct |
| `industry` | securities_reference.industry | Direct |
| `market_cap` | securities_reference.market_cap | Cast to double |
| `shares_outstanding` | securities_reference.shares_outstanding | Cast to long |

---

## Joins

### To Company

```sql
SELECT s.ticker, c.company_name, c.cik
FROM stocks.dim_stock s
JOIN company.dim_company c ON s.company_id = c.company_id
```

### To Prices

```sql
SELECT d.ticker, d.sector, p.close
FROM stocks.dim_stock d
JOIN stocks.fact_stock_prices p ON d.ticker = p.ticker
WHERE p.trade_date = '2024-01-15'
```

---

## Usage Examples

### Get All Tech Stocks

```sql
SELECT ticker, security_name, market_cap
FROM stocks.dim_stock
WHERE sector = 'Technology'
ORDER BY market_cap DESC
```

### Filter by Exchange

```sql
SELECT ticker, security_name
FROM stocks.dim_stock
WHERE exchange_code = 'NASDAQ'
  AND is_active = true
```

### Market Cap Tiers

```sql
SELECT
    ticker,
    security_name,
    market_cap,
    CASE
        WHEN market_cap >= 200e9 THEN 'Mega Cap'
        WHEN market_cap >= 10e9 THEN 'Large Cap'
        WHEN market_cap >= 2e9 THEN 'Mid Cap'
        WHEN market_cap >= 300e6 THEN 'Small Cap'
        ELSE 'Micro Cap'
    END as cap_tier
FROM stocks.dim_stock
WHERE market_cap IS NOT NULL
ORDER BY market_cap DESC
```

---

## Data Quality Notes

- **CIK**: May be null for non-US stocks or recent IPOs
- **market_cap**: Updated periodically, may lag current price
- **sector/industry**: Denormalized from company for query convenience
- **shares_outstanding**: Point-in-time snapshot

---

## Related Documentation

- [Stocks Overview](overview.md)
- [Facts](facts.md) - Price and technical tables
- [Company Model](../company/) - Entity details
