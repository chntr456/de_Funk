# Proposal 011: Smart Incremental Ingestion

**Status**: Draft
**Created**: 2025-12-04
**Author**: Claude

## Summary

This proposal outlines strategies for reducing redundant API calls during data ingestion by tracking what data has already been fetched.

## Current State (Option C - Implemented)

The current implementation uses Delta Lake MERGE (upsert) to accumulate data across runs:

- **Behavior**: Always calls API, merges results into Bronze
- **Benefit**: Multiple runs accumulate data, no duplicates, idempotent
- **Drawback**: Still makes API calls for data that already exists

## Proposed Enhancements

### Option A: Date-Based Incremental (Recommended)

Track the date range coverage per ticker and only fetch missing dates.

**Implementation**:
1. Create metadata table: `bronze_ingestion_metadata`
   ```
   ticker | table_name | min_date | max_date | last_updated
   ```
2. Before API call, check coverage:
   - If requested range fully covered → skip API call
   - If partially covered → only fetch missing dates
   - If not covered → fetch full range

**Pros**:
- Dramatically reduces API calls for daily refreshes
- Efficient for building historical data incrementally

**Cons**:
- Additional complexity (metadata tracking)
- Need to handle gaps in data

### Option B: Existence Check Before API Call

Query Bronze before each API call to check if data exists.

**Implementation**:
```python
def should_fetch(ticker, date_from, date_to):
    existing = spark.read.format("delta").load(bronze_path)
    coverage = existing.filter(
        (col("ticker") == ticker) &
        (col("trade_date").between(date_from, date_to))
    ).count()
    expected = business_days_between(date_from, date_to)
    return coverage < expected * 0.9  # 90% threshold
```

**Pros**:
- Simple to implement
- Works with current architecture

**Cons**:
- Query overhead before each API call
- May not scale well for large ticker lists

### Option C: Watermark-Based Incremental

Track a single "high watermark" per table and only fetch data after that point.

**Implementation**:
1. After each ingestion, record max date as watermark
2. Next run starts from watermark + 1 day
3. No need to check individual tickers

**Pros**:
- Simplest to implement
- No per-ticker tracking

**Cons**:
- Assumes all tickers have same coverage
- Doesn't handle new tickers well

## Recommendation

Implement **Option A** (Date-Based Incremental) as it provides the best balance of:
- API call reduction (major cost savings for premium tier)
- Flexibility (handles new tickers, backfills, partial coverage)
- Correctness (tracks actual coverage, not assumptions)

## Implementation Plan

1. Create `storage/bronze/metadata/ingestion_coverage` Delta table
2. Add `update_coverage()` method to BronzeSink after successful writes
3. Add `get_missing_ranges()` method to check what needs fetching
4. Modify ingestor to call `get_missing_ranges()` before API calls
5. Add CLI flag `--skip-existing` to enable smart incremental mode

## Open Questions

1. How to handle data corrections from Alpha Vantage?
2. Should we support forced refresh (`--force-refresh`) to re-pull everything?
3. How to handle ticker delistings?

## References

- Delta Lake MERGE documentation
- Alpha Vantage rate limits and pricing
- Current BronzeSink implementation
