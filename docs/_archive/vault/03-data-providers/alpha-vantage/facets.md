# Alpha Vantage Facets

**Data transformation components for Alpha Vantage API responses**

---

## Overview

Facets normalize raw API responses into standard DataFrame schemas for Bronze storage.

| Facet | API Endpoint | Output Table |
|-------|--------------|--------------|
| `SecuritiesReferenceFacetAV` | OVERVIEW | securities_reference |
| `SecuritiesPricesFacetAV` | TIME_SERIES_DAILY_ADJUSTED | securities_prices_daily |

---

## SecuritiesReferenceFacetAV

**File**: `datapipelines/providers/alpha_vantage/facets/securities_reference_facet.py`

**Purpose**: Transform company fundamentals into reference data

### Input (API Response)

```json
{
  "Symbol": "AAPL",
  "Name": "Apple Inc",
  "CIK": "320193",
  "Exchange": "NASDAQ",
  "Sector": "Technology",
  "Industry": "Consumer Electronics",
  "MarketCapitalization": "2500000000000",
  "SharesOutstanding": "15700000000",
  "DividendYield": "0.0055"
}
```

### Output Schema

| Column | Type | Source | Notes |
|--------|------|--------|-------|
| `ticker` | string | Symbol | Primary key |
| `security_name` | string | Name | Company name |
| `asset_type` | string | Hardcoded | `'stocks'` |
| `cik` | string | CIK | Padded to 10 digits |
| `exchange_code` | string | Exchange | NYSE, NASDAQ, etc. |
| `sector` | string | Sector | GICS sector |
| `industry` | string | Industry | GICS industry |
| `market_cap` | double | MarketCapitalization | Parsed to number |
| `shares_outstanding` | long | SharesOutstanding | Parsed to number |
| `dividend_yield` | double | DividendYield | Parsed to number |
| `pe_ratio` | double | PERatio | |
| `52_week_high` | double | 52WeekHigh | |
| `52_week_low` | double | 52WeekLow | |
| `snapshot_dt` | date | Generated | Ingestion date |
| `last_updated` | timestamp | Generated | Ingestion time |

### CIK Processing

```python
# CIK padded to 10 digits for SEC standard format
cik_expr = (
    when(col("cik").isNotNull(),
         lpad(regexp_extract(col("cik"), r"(\d+)", 1), 10, "0"))
    .cast("string")
)
# "320193" → "0000320193"
```

### Data Cleaning

```python
# Replace API "None"/"-" values with actual nulls
def clean_value(value):
    if value in ["None", "-", "N/A", ""]:
        return None
    return value
```

---

## SecuritiesPricesFacetAV

**File**: `datapipelines/providers/alpha_vantage/facets/securities_prices_facet.py`

**Purpose**: Transform daily price data to OHLCV format

### Input (API Response)

```json
{
  "Meta Data": {
    "2. Symbol": "AAPL"
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

### Output Schema

| Column | Type | Source | Notes |
|--------|------|--------|-------|
| `ticker` | string | Meta Data | From request |
| `trade_date` | date | Key | Date string parsed |
| `asset_type` | string | Hardcoded | `'stocks'` |
| `open` | double | 1. open | |
| `high` | double | 2. high | |
| `low` | double | 3. low | |
| `close` | double | 4. close | |
| `adjusted_close` | double | 5. adjusted close | Split/dividend adjusted |
| `volume` | long | 6. volume | |
| `dividend_amount` | double | 7. dividend amount | |
| `split_coefficient` | double | 8. split coefficient | |
| `volume_weighted` | double | Calculated | close * volume / sum(volume) |
| `year` | int | Extracted | For partitioning |
| `month` | int | Extracted | For partitioning |

### Transformation Logic

```python
def normalize(self, raw_batches):
    records = []
    for batch in raw_batches:
        symbol = batch.get("Meta Data", {}).get("2. Symbol")
        time_series = batch.get("Time Series (Daily)", {})

        for date_str, values in time_series.items():
            records.append({
                "ticker": symbol,
                "trade_date": date_str,
                "open": float(values.get("1. open", 0)),
                "high": float(values.get("2. high", 0)),
                "low": float(values.get("3. low", 0)),
                "close": float(values.get("4. close", 0)),
                "adjusted_close": float(values.get("5. adjusted close", 0)),
                "volume": int(values.get("6. volume", 0)),
                "asset_type": "stocks"
            })

    return self.spark.createDataFrame(records, schema=self.output_schema)
```

### Date Filtering

```python
# Filter to date range if specified
if self.date_from:
    df = df.filter(col("trade_date") >= self.date_from)
if self.date_to:
    df = df.filter(col("trade_date") <= self.date_to)
```

---

## Facet Lifecycle

```
1. Initialize
   facet = SecuritiesPricesFacetAV(spark, tickers=['AAPL', 'MSFT'])

2. Generate Calls
   calls = list(facet.calls())
   # [{'endpoint': 'time_series_daily_adjusted', 'params': {'symbol': 'AAPL'}}, ...]

3. Fetch (by ingestor)
   raw_data = ingestor._fetch_calls(calls)

4. Normalize
   df = facet.normalize(raw_data)

5. Postprocess
   df = facet.postprocess(df)  # Add partitions, clean data

6. Validate
   df = facet.validate(df)  # Type checking

7. Write (partitions from storage.json - single source of truth)
   sink.smart_write(df, table_name)  # Reads partitions from configs/storage.json
```

---

## Usage Example

```python
from datapipelines.providers.alpha_vantage.facets import SecuritiesPricesFacetAV

# Initialize facet
facet = SecuritiesPricesFacetAV(
    spark=spark,
    tickers=['AAPL', 'MSFT', 'GOOGL'],
    date_from='2024-01-01',
    output_size='compact'
)

# Generate API calls
calls = list(facet.calls())
print(f"Generated {len(calls)} API calls")

# After fetching raw data...
df = facet.normalize(raw_batches)
df = facet.postprocess(df)
print(f"Processed {df.count()} price records")
```

---

## Related Documentation

- [API Reference](api-reference.md) - Endpoint details
- [Bronze Tables](bronze-tables.md) - Output schemas
- [Pipelines](../../06-pipelines/facet-system.md) - Facet system overview
