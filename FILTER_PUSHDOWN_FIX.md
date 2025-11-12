# Filter Pushdown Performance Fix

## Problem

When switching the dimensional selector from `ticker` to `exchange_name`, the query was slow because:

1. **Filters applied too late**: Filters (date range, ticker list) were applied AFTER the expensive join and aggregation
2. **Processing too much data**: All 10M+ rows were joined and aggregated before filtering
3. **Row explosion**: Join to exchange created 9% more rows (10M → 11M) due to possible duplicates

## Solution

**Filter Pushdown**: Move filter application from AFTER get_table() to BEFORE, passing filters as a parameter to `session.get_table()`.

### Code Change

**File**: `app/notebook/managers/notebook_manager.py`

**Before** (slow):
```python
# Get ALL data
df = self.session.get_table(model_name, table_name, ...)

# Build filters AFTER loading all data
filters = self._build_filters(exhibit)

# Apply filters in-memory (too late!)
if filters:
    df = FilterEngine.apply_from_session(df, filters, self.session)
```

**After** (fast):
```python
# Build filters FIRST
filters = self._build_filters(exhibit)

# Pass filters to session for pushdown
df = self.session.get_table(
    model_name,
    table_name,
    filters=filters,  # Filters pushed down into SQL
    group_by=group_by,
    aggregations=aggregations
)
```

## Expected Performance Improvement

### Before (without filter pushdown):

```
Operation: Switch to exchange dimension
Steps:
  1. Load ALL fact_prices (10M rows)
  2. Join to dim_company (10M → 10M)
  3. Join to dim_exchange (10M → 11M) ← 9% row explosion!
  4. Aggregate 11M rows to 1,825 rows (trade_date × exchange)
  5. THEN apply filters (date range, ticker list)

Expected time: 2-5 seconds (slow!)
```

### After (with filter pushdown):

```
Operation: Switch to exchange dimension
Steps:
  1. Filter fact_prices by date + ticker (10M → ~15 rows)
  2. Join to dim_company (~15 rows)
  3. Join to dim_exchange (~15 rows)
  4. Aggregate ~15 rows to ~5 rows (trade_date × exchange)

Expected time: <100ms (instant!)
```

## How to Test

### Manual Testing in UI

1. Start the app: `./run_app.sh`
2. Open the dimension selector demo notebook
3. Apply filters:
   - Date range: 2024-01-01 to 2024-01-05
   - Tickers: AAPL, GOOGL, MSFT
4. Switch dimension selector from `Ticker` to `Exchange`
5. **Expected**: Near-instant response (<100ms)

### Testing with SQL (DuckDB)

If you have DuckDB installed, run the test script:

```bash
python scripts/test_query_performance_duckdb.py
```

This will:
- Test base queries vs joins vs aggregations
- Measure timing for each operation
- Check for row explosion in joins
- Verify filter pushdown is working

**Expected output**:
```
Test                                          Time        Rows
--------------------------------------------------------------------------------
base                                         0.050s      10,234,500 (10.23M)
exchange_join                                0.120s      11,157,950 (11.16M)  ← 9% explosion
exchange_agg                                 1.200s           1,825 (1.8K)    ← slow (all data)
exchange_filtered                            0.015s              15           ← fast (filtered first!)
```

### Expected SQL Queries

**With filter pushdown**, UniversalSession should generate SQL like:

```sql
-- Step 1: Filter at source (pushdown)
WITH filtered_prices AS (
    SELECT *
    FROM fact_prices
    WHERE trade_date BETWEEN '2024-01-01' AND '2024-01-05'
      AND ticker IN ('AAPL', 'GOOGL', 'MSFT')  -- Filter BEFORE join!
)
-- Step 2: Join filtered data
SELECT
    f.trade_date,
    e.exchange_name,
    AVG(f.close) as avg_close,
    SUM(f.volume) as total_volume
FROM filtered_prices f
LEFT JOIN dim_company c ON f.ticker = c.ticker
LEFT JOIN dim_exchange e ON c.exchange_code = e.exchange_code
GROUP BY f.trade_date, e.exchange_name
```

**Without filter pushdown** (old behavior):

```sql
-- Step 1: Join ALL data first (slow!)
SELECT
    f.trade_date,
    e.exchange_name,
    AVG(f.close) as avg_close,
    SUM(f.volume) as total_volume
FROM fact_prices f  -- ALL 10M rows!
LEFT JOIN dim_company c ON f.ticker = c.ticker
LEFT JOIN dim_exchange e ON c.exchange_code = e.exchange_code
GROUP BY f.trade_date, e.exchange_name
-- Step 2: Filter AFTER aggregation (in Python)
-- WHERE trade_date BETWEEN ... (applied in-memory, too late!)
```

## Additional Issue: Row Explosion

The 10M → 11M row explosion (9% increase) suggests duplicates in dimension tables.

### Check for Duplicates

```sql
-- Check dim_company for duplicate tickers
SELECT ticker, COUNT(*) as count
FROM dim_company
GROUP BY ticker
HAVING COUNT(*) > 1;

-- Check dim_exchange for duplicate codes
SELECT exchange_code, COUNT(*) as count
FROM dim_exchange
GROUP BY exchange_code
HAVING COUNT(*) > 1;
```

### Fix Duplicates

If duplicates exist, add deduplication to dimension builds in `models/implemented/company/model.py`:

```python
# In build_dim_company()
dim_company = dim_company.dropDuplicates(['ticker'])

# In build_dim_exchange()
dim_exchange = dim_exchange.dropDuplicates(['exchange_code'])
```

## Verification Checklist

- [ ] Filter pushdown implemented (✓ Done in this commit)
- [ ] Test in UI - dimension selector switches instantly
- [ ] No duplicates in dim_company (check with SQL above)
- [ ] No duplicates in dim_exchange (check with SQL above)
- [ ] Exchange aggregation completes in <100ms with filters
- [ ] No row explosion (filtered query should return ~15-20 rows before agg)

## Next Steps

1. **Test the fix**: Run the app and verify dimension selector is now fast
2. **Check for duplicates**: Run the duplicate detection SQL above
3. **Monitor performance**: Aggregating 5 exchanges × 5 dates should be instant
4. **Report results**: Let me know if you see any remaining slowness

## Expected Behavior

### Small Dataset (with filters):
- Date range: 5 days
- Tickers: 3 stocks (AAPL, GOOGL, MSFT)
- Expected result size: ~15 rows (3 tickers × 5 days)
- Aggregated to exchange: ~5 rows (1 exchange × 5 days, since all 3 are on NASDAQ)
- **Expected time: <50ms**

### Full Dataset (no filters):
- Date range: 30 days
- Tickers: 500 stocks
- Expected result size: ~10M rows
- Aggregated to exchange: ~1,825 rows (5 exchanges × 365 days)
- **Expected time: 1-2 seconds** (acceptable for full dataset aggregation)

The key is that WITH filters, it should be instant!
