# Data Ingestion Pipeline - Quick Reference Guide

## Files Generated

1. **DATA_PIPELINE_ARCHITECTURE.md** (55KB, 1,528 lines)
   - Comprehensive deep-dive into all components
   - Detailed class diagrams and data flow
   - Complete examples with line-by-line walkthrough
   - Memory management analysis
   - Optimization opportunities with implementation details

2. **PIPELINE_REPORT_SUMMARY.md** (10KB)
   - Executive summary of key findings
   - Architecture overview
   - High-impact optimization opportunities
   - File references with line counts

3. **PIPELINE_QUICK_REFERENCE.md** (this file)
   - Quick lookup guide for developers
   - Common tasks and patterns
   - Key file locations

---

## Quick Lookup

### I want to understand...

**How the pipeline works end-to-end**
→ Read: DATA_PIPELINE_ARCHITECTURE.md Section 8 (Complete Example)

**Rate limiting implementation**
→ Read: DATA_PIPELINE_ARCHITECTURE.md Section 5 (HTTP Client)

**Facet transformation flow**
→ Read: DATA_PIPELINE_ARCHITECTURE.md Section 3 (Facet Transformations)

**Memory usage and bottlenecks**
→ Read: DATA_PIPELINE_ARCHITECTURE.md Section 9 (Memory Management)

**How to add a new data source**
→ Reference: Alpha Vantage provider implementation (Section 2.1)

**Configuration management**
→ Read: DATA_PIPELINE_ARCHITECTURE.md Section 7 (Configuration)

**Error handling strategies**
→ Read: DATA_PIPELINE_ARCHITECTURE.md Section 12 (Error Handling)

**Partitioning strategy**
→ Read: DATA_PIPELINE_ARCHITECTURE.md Section 6 (Bronze Sink)

---

## Component Quick Reference

### Entry Points

```
scripts/ingest/run_full_pipeline.py
  └─ Main entry point for ingestion pipeline
  └─ Configurable: date ranges, ticker limits, providers
  └─ Command: python -m scripts.ingest.run_full_pipeline --days 30
```

### Core Classes

| Class | Location | Purpose |
|-------|----------|---------|
| AlphaVantageIngestor | `datapipelines/providers/alpha_vantage/` | Orchestrate Alpha Vantage ingestion |
| AlphaVantageRegistry | `datapipelines/providers/alpha_vantage/` | Manage API endpoints |
| HttpClient | `datapipelines/base/http_client.py` | Rate-limited HTTP requests |
| ApiKeyPool | `datapipelines/base/key_pool.py` | Rotate API keys |
| Facet | `datapipelines/facets/base_facet.py` | Transform API → DataFrame |
| SecuritiesReferenceFacetAV | `datapipelines/providers/alpha_vantage/facets/` | Company fundamentals |
| SecuritiesPricesFacetAV | `datapipelines/providers/alpha_vantage/facets/` | Daily OHLCV prices |
| BronzeSink | `datapipelines/ingestors/bronze_sink.py` | Write to Parquet |

### Configuration Files

| File | Purpose | Modified by |
|------|---------|-------------|
| `configs/alpha_vantage_endpoints.json` | API endpoints, rate limits | Developers |
| `configs/storage.json` | Path mappings, partitioning | Developers |
| `.env` | API keys, runtime overrides | Operators |

---

## Common Patterns

### Fetch API data with rate limiting
```python
ingestor = AlphaVantageIngestor(cfg, storage, spark)
raw_batches = ingestor._fetch_calls(calls)  # Sequential, rate-limited
# or
raw_batches = ingestor._fetch_calls_concurrent(calls)  # Concurrent (premium tier only)
```

### Transform API response to DataFrame
```python
facet = SecuritiesPricesFacetAV(spark, tickers=['AAPL'], ...)
df = facet.normalize(raw_batches)       # Normalize
df = facet.postprocess(df)              # Transform
df = facet.validate(df)                 # Validate
```

### Write to Bronze layer
```python
sink = BronzeSink(storage_cfg)
path = sink.write(df, "securities_prices_daily", partitions=["asset_type", "year", "month"])
```

### Handle API errors
```python
for batch in raw_batches:
    for item in batch:
        if "Error Message" in item:
            # Handle error
        elif "Note" in item:
            # Handle rate limit warning
```

---

## Performance Considerations

### Rate Limiting

**Alpha Vantage Free Tier**:
- 5 calls/minute = 0.08333 calls/second
- Min interval: 12 seconds per call
- Daily limit: 500 calls/day

**Alpha Vantage Premium**:
- 75 calls/minute = 1.25 calls/second
- Min interval: 0.8 seconds per call
- Can use concurrent fetching

**Throttle Calculation**:
```
min_interval = 1.0 / configured_rps
sleep_time = max(0, min_interval - time_since_last_request)
```

### Memory Usage

**Peak Memory Points**:
1. Pandas bridge in postprocess (full DataFrame in memory)
2. Union of multiple batch DataFrames
3. Spark lazy evaluation (before write)

**Optimization**:
- Batch write every 10-50 tickers (not all at once)
- Use Spark transformations instead of pandas where possible
- Stream responses instead of buffering

### Partitioning Impact

**Securities Prices**: `asset_type, year, month`
- 4 asset types × 48 months × 4,000 tickers = ~768K partitions max
- Avoids partition sprawl vs daily partitioning (~3M partitions)
- Enables efficient time-range filtering

---

## Debugging Tips

### Check API connectivity
```bash
# Test API key + endpoint
curl "https://www.alphavantage.co/query?function=OVERVIEW&symbol=AAPL&apikey=YOUR_KEY"
```

### Verify configuration
```python
from core.context import RepoContext
ctx = RepoContext.from_repo_root()
print(ctx.config.apis['alpha_vantage'])
```

### Check Bronze data
```bash
# List partitions
find storage/bronze/securities_prices_daily -type d -name "asset_type*" | head -10

# Read Parquet file
spark.read.parquet("storage/bronze/securities_prices_daily/asset_type=stocks/year=2025/month=11").show()
```

### Monitor rate limiting
- Look for "429" responses in logs (rate limit hit)
- Check HTTP client is sleeping (1.0 second intervals for free tier)
- Verify API key rotation in key pool

### Debug facet transformations
1. Check raw_batches: `[item for batch in raw_batches for item in batch][:5]`
2. Check normalize output: `df = facet.normalize(raw_batches); df.printSchema()`
3. Check postprocess output: `pdf = df.toPandas(); pdf.dtypes`
4. Check validate: `df.filter(col("ticker").isNull()).count()`

---

## Architecture Diagram Cheat Sheet

```
REQUEST PATH:
User → run_full_pipeline.py → Orchestrator → Ingestor → Facet + Registry + HttpClient → API

RESPONSE PATH:
API → HttpClient → Facet.normalize() → Facet.postprocess() → BronzeSink.write() → Parquet

MEMORY PATH:
JSON Response → List[List[dict]] → Spark DF → Pandas DF → Spark DF → Parquet file
```

---

## Key Insights

1. **Composable Design**: Easy to add new providers (implement Facet + Registry + Ingestor)
2. **Rate-Aware**: Respects API limits through HttpClient throttling
3. **Error-Resilient**: Continues on partial failures, logs detailed errors
4. **Type-Safe**: NUMERIC_COERCE + SPARK_CASTS prevent type mismatches
5. **Partition-Smart**: Year/month partitioning balances efficiency vs structure size

---

## Related Documentation

- CLAUDE.md - Project overview and conventions
- MODEL_DEPENDENCY_ANALYSIS.md - Model relationships
- FILTER_PUSHDOWN_FIX.md - Query optimization
- TESTING_GUIDE.md - Testing strategy

---

**Last Updated**: November 21, 2025  
**Version**: 1.0
