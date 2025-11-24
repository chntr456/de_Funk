# Alpha Vantage Bronze Tables

**Output table schemas and storage structure**

---

## Tables Overview

| Table | Purpose | Partitions | Source Facet |
|-------|---------|------------|--------------|
| `securities_reference` | Company fundamentals | snapshot_dt, asset_type | SecuritiesReferenceFacetAV |
| `securities_prices_daily` | Daily OHLCV | asset_type, year, month | SecuritiesPricesFacetAV |

---

## securities_reference

**Purpose**: Company reference data with SEC identifiers

**Path**: `storage/bronze/securities_reference/`

**Partitions**: `snapshot_dt`, `asset_type`

### Schema

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `ticker` | string | Stock symbol (PK) | `AAPL` |
| `security_name` | string | Company name | `Apple Inc` |
| `asset_type` | string | Asset classification | `stocks` |
| `cik` | string | SEC Central Index Key (10 digits) | `0000320193` |
| `exchange_code` | string | Exchange | `NASDAQ` |
| `currency` | string | Trading currency | `USD` |
| `sector` | string | GICS sector | `Technology` |
| `industry` | string | GICS industry | `Consumer Electronics` |
| `market_cap` | double | Market capitalization | `2500000000000` |
| `shares_outstanding` | long | Shares outstanding | `15700000000` |
| `pe_ratio` | double | Price/Earnings ratio | `28.5` |
| `dividend_yield` | double | Dividend yield | `0.0055` |
| `eps` | double | Earnings per share | `6.14` |
| `beta` | double | Beta vs market | `1.25` |
| `52_week_high` | double | 52-week high price | `199.62` |
| `52_week_low` | double | 52-week low price | `124.17` |
| `50_day_ma` | double | 50-day moving average | `182.50` |
| `200_day_ma` | double | 200-day moving average | `175.00` |
| `is_active` | boolean | Active trading status | `true` |
| `snapshot_dt` | date | Data snapshot date | `2024-01-15` |
| `last_updated` | timestamp | Ingestion timestamp | `2024-01-15T10:30:00Z` |

### Storage Structure

```
storage/bronze/securities_reference/
└── snapshot_dt=2024-01-15/
    └── asset_type=stocks/
        ├── part-00000.parquet
        └── part-00001.parquet
```

### Query Example

```sql
-- Get latest reference data for a ticker
SELECT *
FROM read_parquet('storage/bronze/securities_reference/snapshot_dt=2024-01-15/asset_type=stocks/*.parquet')
WHERE ticker = 'AAPL'
```

---

## securities_prices_daily

**Purpose**: Historical daily price data (OHLCV)

**Path**: `storage/bronze/securities_prices_daily/`

**Partitions**: `asset_type`, `year`, `month`

### Schema

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `ticker` | string | Stock symbol | `AAPL` |
| `trade_date` | date | Trading date | `2024-01-15` |
| `asset_type` | string | Asset classification | `stocks` |
| `open` | double | Opening price | `150.00` |
| `high` | double | High price | `152.00` |
| `low` | double | Low price | `149.00` |
| `close` | double | Closing price | `151.00` |
| `adjusted_close` | double | Split/dividend adjusted close | `151.00` |
| `volume` | long | Trading volume | `50000000` |
| `volume_weighted` | double | Volume-weighted avg price | `150.75` |
| `dividend_amount` | double | Dividend paid | `0.24` |
| `split_coefficient` | double | Split ratio | `1.0` |
| `transactions` | long | Number of transactions | `450000` |
| `year` | int | Year (partition) | `2024` |
| `month` | int | Month (partition) | `1` |

### Storage Structure

```
storage/bronze/securities_prices_daily/
└── asset_type=stocks/
    └── year=2024/
        ├── month=1/
        │   ├── part-00000.parquet
        │   └── part-00001.parquet
        └── month=2/
            └── part-00000.parquet
```

### Query Example

```sql
-- Get AAPL prices for January 2024
SELECT ticker, trade_date, open, high, low, close, volume
FROM read_parquet('storage/bronze/securities_prices_daily/asset_type=stocks/year=2024/month=1/*.parquet')
WHERE ticker = 'AAPL'
ORDER BY trade_date
```

---

## Partitioning Strategy

### Why This Structure?

**securities_reference**:
- `snapshot_dt`: Track data over time (fundamentals change)
- `asset_type`: Filter to stocks, options, etfs, futures

**securities_prices_daily**:
- `asset_type`: Filter by security type
- `year/month`: Efficient date-range queries, avoids partition sprawl

### Partition Pruning

```sql
-- DuckDB automatically prunes partitions
SELECT * FROM read_parquet('storage/bronze/securities_prices_daily/asset_type=stocks/year=2024/month=1/*.parquet')
-- Only reads January 2024 data, not entire table
```

---

## Data Quality

### Null Handling

API returns `"None"`, `"-"`, `"N/A"` as strings. Facets convert to actual nulls:

```python
cleaned_value = None if value in ["None", "-", "N/A", ""] else value
```

### Type Coercion

All numeric strings converted to proper types:

```python
market_cap = float(response.get("MarketCapitalization", 0)) or None
volume = int(response.get("volume", 0)) or None
```

### Deduplication

Primary keys enforced during normalization:

```python
# securities_reference: unique by ticker
df = df.dropDuplicates(["ticker"])

# securities_prices_daily: unique by ticker + trade_date
df = df.dropDuplicates(["ticker", "trade_date"])
```

---

## Related Documentation

- [Facets](facets.md) - Transformation logic
- [API Reference](api-reference.md) - Source endpoints
- [Bronze Layer](../../06-pipelines/bronze-layer.md) - Storage overview
