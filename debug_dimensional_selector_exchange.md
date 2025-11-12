# Debug Query: Dimensional Selector Exchange Data Validation

## Problem Summary
The dimensional selector example notebook uses `source: company.fact_prices` with `available_dimensions: [ticker, exchange]`, but the `exchange` column doesn't exist in `fact_prices`.

## Data Validation Queries

### Query 1: Check fact_prices schema (what columns exist)
This query shows all columns available in the fact_prices table:

```sql
SELECT * FROM read_parquet('storage/silver/company/facts/fact_prices/**/*.parquet') LIMIT 1;
```

**Expected columns:** trade_date, ticker, open, high, low, close, volume_weighted, volume
**Missing:** exchange, exchange_name, exchange_code

### Query 2: Check prices_with_company schema (joined table with exchange)
This query shows all columns in the materialized view that includes exchange data:

```sql
SELECT * FROM read_parquet('storage/silver/company/facts/prices_with_company/**/*.parquet') LIMIT 1;
```

**Expected columns:** trade_date, ticker, company_name, exchange_name, open, high, low, close, volume_weighted, volume

### Query 3: Validate exchange data is available
This query confirms exchange_name values are properly loaded:

```sql
SELECT
    exchange_name,
    COUNT(DISTINCT ticker) as ticker_count,
    COUNT(*) as row_count,
    MIN(trade_date) as earliest_date,
    MAX(trade_date) as latest_date
FROM read_parquet('storage/silver/company/facts/prices_with_company/**/*.parquet')
GROUP BY exchange_name
ORDER BY ticker_count DESC;
```

### Query 4: Sample data with exchange information
This query shows sample records with exchange data:

```sql
SELECT
    trade_date,
    ticker,
    company_name,
    exchange_name,
    close,
    volume
FROM read_parquet('storage/silver/company/facts/prices_with_company/**/*.parquet')
WHERE trade_date BETWEEN '2024-01-01' AND '2024-01-05'
ORDER BY trade_date, ticker
LIMIT 20;
```

## Root Cause
According to `configs/models/company.yaml`:

- **fact_prices** is the base fact table with only pricing metrics and ticker
- **dim_company** contains the exchange_code linking companies to exchanges
- **prices_with_company** is a materialized path: `fact_prices -> dim_company -> dim_exchange`

The exchange information requires a join, which is why it's only available in the `prices_with_company` table.

## Solution
Update the dimensional selector demo notebook (`configs/notebooks/dimension_selector_demo.md`) to use the correct source table:

**Current (broken):**
```yaml
source: company.fact_prices
dimension_selector: {
  available_dimensions: [ticker, exchange]
  ...
}
```

**Fixed:**
```yaml
source: company.prices_with_company
dimension_selector: {
  available_dimensions: [ticker, exchange_name]
  ...
}
```

Note: The dimension should be `exchange_name` (not just `exchange`), which is the actual column name in `prices_with_company`.

## Running These Queries

### Option 1: Using DuckDB CLI
```bash
duckdb storage/silver/company.duckdb
# Then paste any query above
```

### Option 2: Using Python
```python
import duckdb

conn = duckdb.connect('storage/silver/company.duckdb')

# Run any query
result = conn.execute("""
    SELECT
        exchange_name,
        COUNT(DISTINCT ticker) as ticker_count
    FROM read_parquet('storage/silver/company/facts/prices_with_company/**/*.parquet')
    GROUP BY exchange_name
""").fetchdf()

print(result)
```

### Option 3: Direct parquet file check
```python
import duckdb

# Check what columns are in fact_prices
conn = duckdb.connect()
df = conn.execute("""
    DESCRIBE SELECT * FROM read_parquet('storage/silver/company/facts/fact_prices/**/*.parquet')
""").fetchdf()
print("fact_prices columns:")
print(df)

# Check what columns are in prices_with_company
df2 = conn.execute("""
    DESCRIBE SELECT * FROM read_parquet('storage/silver/company/facts/prices_with_company/**/*.parquet')
""").fetchdf()
print("\nprices_with_company columns:")
print(df2)
```
