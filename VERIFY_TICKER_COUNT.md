# Ticker Count Verification

## Issue
Only 1,011 tickers in `dim_company`, which seems low.

## Pagination Status
✅ **Pagination IS implemented and working:**
- `_fetch_calls()` automatically follows `next_url` cursors
- Default: `enable_pagination=True` (unlimited pages)
- No `max_pages` limit on ref_all_tickers ingestion
- See: `datapipelines/ingestors/polygon_ingestor.py:30-88`

## Data Flow

```
Polygon API
  ↓ (paginated)
bronze.ref_all_tickers  (ALL tickers from Polygon)
  ↓ (filter: active == True)
bronze.ref_ticker       (1,011 ACTIVE tickers)
  ↓ (OLD: was using ref_ticker)
  ↓ (NEW: now using ref_all_tickers)
dim_company             (Should have more tickers now!)
```

## What to Verify

### 1. Check Bronze ref_all_tickers Count

Run this to see how many tickers Polygon actually returned:

```python
from pyspark.sql import SparkSession

spark = SparkSession.builder.appName("check").getOrCreate()

# Check raw bronze data
df = spark.read.parquet('storage/bronze/ref_all_tickers')

total = df.count()
active = df.filter("active == true").count()
inactive = df.filter("active == false").count()

print(f"Total tickers in ref_all_tickers: {total:,}")
print(f"  Active: {active:,}")
print(f"  Inactive: {inactive:,}")
print()

# Sample data
print("Sample (first 20):")
df.show(20)

print("\nSample inactive tickers:")
df.filter("active == false").show(10)
```

**Expected results:**
- If total ≈ 1,011: Polygon only returns active tickers (API limitation)
- If total >> 1,011: Pagination worked, we have inactive tickers too

### 2. Check Polygon API Directly

Test the API endpoint directly to see what it returns:

```bash
curl "https://api.polygon.io/v3/reference/tickers?apiKey=YOUR_KEY&limit=1000"
```

Look for:
- `count` in response (how many results in this page)
- `next_url` field (indicates more pages available)
- Total available via `results` array

### 3. Check dim_company After Rebuild

After rebuilding silver with the new config:

```python
df = spark.read.parquet('storage/silver/company/dim_company')

total = df.count()
print(f"dim_company count: {total:,}")

# Check for duplicates (should be 0)
ticker_count = df.select("ticker").distinct().count()
duplicates = total - ticker_count
print(f"Duplicates: {duplicates:,}")
```

**Expected:**
- Count should match `ref_all_tickers` count
- Duplicates should be 0 (deduplication working)

## Possible Outcomes

### Outcome A: Polygon API Only Has ~1,000 Active Tickers
If `ref_all_tickers` really has ~1,011 tickers total:
- ✅ Pagination is working correctly
- ✅ This is all the data Polygon provides for your account
- ✅ Using `ref_all_tickers` instead of `ref_ticker` won't help

**Solution:** This is normal for free/starter Polygon accounts

### Outcome B: ref_all_tickers Has 1,000s of Tickers
If `ref_all_tickers` has 5,000+ tickers including inactive ones:
- ✅ Pagination worked!
- ✅ The fix to use `ref_all_tickers` will give you more tickers
- ✅ Rebuild silver to see the full count

**Solution:** Rebuild silver with `--silver-only --yes`

### Outcome C: Pagination Failed
If logs show pagination errors or `next_url` not being followed:
- ❌ Check HTTP client implementation
- ❌ Check API key permissions
- ❌ Check rate limiting

**Solution:** Debug `_fetch_calls()` with logging

## Rebuild Command

After verifying the bronze data:

```bash
# Rebuild just silver layer (keeps bronze)
python scripts/clear_and_refresh.py --silver-only --yes
```

This will:
1. Delete old `dim_company` (1,011 rows)
2. Rebuild from `ref_all_tickers` (all tickers)
3. Apply deduplication (remove duplicates)
4. Show final counts

## Debug Script

Use the investigation script to verify:

```bash
python scripts/investigate_ticker_count.py
```

This checks:
- ✓ Unique tickers in fact_prices
- ✓ Row counts in bronze.ref_ticker
- ✓ Row counts in bronze.ref_all_tickers
- ✓ Duplicates in dimensions
- ✓ Cross-reference between prices and dimensions

## Summary

**Pagination IS working** - the question is what Polygon is actually returning. Check the bronze data to see if:
1. Polygon only provides ~1K tickers (account limitation), OR
2. Polygon provides more but we were using the filtered subset

The fix (using `ref_all_tickers`) should help in case #2.
