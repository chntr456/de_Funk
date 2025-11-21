# Data Ingestion Pipeline Architecture - Executive Summary

**Report Location**: `docs/DATA_PIPELINE_ARCHITECTURE.md`  
**Report Size**: 1,528 lines  
**Date**: November 21, 2025

## Key Findings

### Architecture Overview
- **3-tier system**: API Providers → Bronze Layer (Parquet) → Silver Layer (Models)
- **Composable design**: Facets + Registries + Ingestors + Sinks
- **Rate-limited**: Respects API limits (5 calls/min for free tier, 75+ for premium)
- **Error-resilient**: Continues on partial failures, logs detailed error info

### Component Structure

```
Run Pipeline (Entry)
    └─ RepoContext (Config + Spark)
        └─ Ingestor (Provider)
            ├─ Registry (Endpoint definitions)
            ├─ HttpClient (Rate-limited HTTP)
            ├─ Facet (API → DataFrame)
            └─ BronzeSink (Write to Parquet)
```

### Providers

1. **Alpha Vantage** (Primary v2.0)
   - Company fundamentals (OVERVIEW endpoint)
   - Daily OHLCV prices (TIME_SERIES_DAILY_ADJUSTED)
   - Bulk ticker listing (LISTING_STATUS)
   - Rate limit: 5 calls/min (free), 75 calls/min (premium)

2. **BLS** (Bureau of Labor Statistics)
   - Uses POST with JSON body
   - Economic indicators (unemployment, CPI, etc.)
   - No pagination (returns all data in one call)

3. **Chicago** (Socrata API)
   - Municipal finance data
   - Building permits, business licenses, etc.
   - Query parameter filtering

### Facet Transformations

**Base Facet** (`facets/base_facet.py`):
- Numeric coercion (string/int/float → double/long)
- DataFrame creation from batches
- Final schema enforcement
- Pipeline: normalize() → postprocess() → validate()

**Alpha Vantage Facet**:
- Cleans invalid markers ("None", "N/A", "-") to NULL
- Handles mixed API response types

**SecuritiesReferenceFacetAV**:
- Transform OVERVIEW to unified schema
- CIK padding (10 digits per SEC standard)
- Maps asset types (stocks, etfs, options, futures)
- Uses pandas for flexible type conversion

**SecuritiesPricesFacetAV**:
- Flattens nested time series dict to rows
- Parses dates, extracts year/month for partitioning
- Calculates VWAP (high + low + close)/3
- Handles missing fields gracefully

### Rate Limiting & HTTP

**HttpClient** (`base/http_client.py`):
- Throttles to configured rate: `1.0 / rate_limit_per_sec`
- Exponential backoff for 429/5xx errors
- 6 max retries with configurable backoff
- Thread-safe with urllib (no async)

**ApiKeyPool** (`base/key_pool.py`):
- Round-robin key rotation
- Per-key cooldown tracking
- Avoids hammering single key

**Example**: With 2 keys + 60sec cooldown:
- Key A used → rotated to back
- Key B used → Key A still cooling, so Key B used again
- Spreads load across multiple keys

### Memory Path

```
API Response (JSON)
    └─ _fetch_calls() → List[List[dict]]
        └─ Facet.normalize() → Create Spark DF + postprocess()
            └─ Postprocess: Pandas bridge (full DF in memory)
                └─ Validate DF
                    └─ BronzeSink.write() → Parquet to disk
```

**Bottleneck**: Pandas postprocess loads entire DataFrame in memory

### Partitioning Strategy

**Securities Reference**:
```
bronze/securities_reference/
├── snapshot_dt=2025-11-21/
│   ├── asset_type=stocks/
│   ├── asset_type=etfs/
│   └── asset_type=options/
```
**Why**: Time-series snapshots + asset type filtering

**Securities Prices**:
```
bronze/securities_prices_daily/
├── asset_type=stocks/
│   ├── year=2025/
│   │   ├── month=01/
│   │   ├── month=02/
│   │   └── ...
│   └── year=2024/
```
**Why**: Avoids partition sprawl (year/month vs daily = ~260MB vs 1GB+ structure)

### Configuration

**Loading**: `config/ConfigLoader` (type-safe, auto-discovery)

**API Configs**: `configs/*_endpoints.json`
- Endpoint definitions
- Base URLs, headers, rate limits
- Required/optional params
- Response key navigation

**Storage**: `configs/storage.json`
- Bronze/silver root paths
- Table mappings
- Partition definitions

### Data Flow - Complete Example

**Ingest Apple prices** (1,000+ lines detailed walkthrough in report):

1. Create facet → Generate API calls
2. HTTP request with rate limiting
3. Get nested time series response
4. Flatten rows, coerce numerics
5. Convert to pandas, transform schema
6. Calculate VWAP, filter by date range
7. Deduplicate, validate data quality
8. Write to Parquet with year/month partitioning

---

## Optimization Opportunities

### Current Issues

1. **Memory Usage**: Pandas bridge loads full DataFrames into memory
   - **Solution**: Use Spark transformations where possible

2. **No Streaming**: All tickers fetched before write
   - **Solution**: Batch write after each 10-50 tickers

3. **Synchronous Only**: Sequential API calls (concurrency available but risky for free tier)
   - **Solution**: Adaptive concurrency based on tier detection

4. **Duplicate Error Handling**: Error checking repeated across methods
   - **Solution**: Extract to base class `_check_api_errors()`

5. **Pandas Dependency**: Postprocess tied to pandas (tight coupling)
   - **Solution**: Consider Spark SQL or PySpark functions alternative

### High-Impact Improvements (Priority Order)

1. **Batch Streaming** (Quick win)
   - Write every 10 tickers instead of all at once
   - Reduces peak memory by 10x
   - Implementation: 20 lines of code

2. **Spark-Only Transforms** (Medium effort)
   - Replace pandas bridge with Spark SQL
   - Eliminates postprocess memory spike
   - Implementation: Rewrite 3 facet classes

3. **Incremental Writes** (Longer term)
   - Append-only or merge-on-read updates
   - Handles daily/weekly refresh cleanly
   - Implementation: Requires schema versioning

---

## Key Files Reference

### Core Pipeline
- `scripts/ingest/run_full_pipeline.py` - Entry point
- `orchestration/orchestrator.py` - High-level orchestration
- `datapipelines/ingestors/base_ingestor.py` - Abstract base

### Alpha Vantage
- `datapipelines/providers/alpha_vantage/alpha_vantage_ingestor.py` (593 lines)
- `datapipelines/providers/alpha_vantage/alpha_vantage_registry.py` (86 lines)
- `datapipelines/providers/alpha_vantage/facets/securities_reference_facet.py` (388 lines)
- `datapipelines/providers/alpha_vantage/facets/securities_prices_facet.py` (407 lines)

### Infrastructure
- `datapipelines/base/http_client.py` - HTTP + rate limiting (124 lines)
- `datapipelines/base/key_pool.py` - API key rotation (24 lines)
- `datapipelines/facets/base_facet.py` - Facet base class (162 lines)
- `datapipelines/ingestors/bronze_sink.py` - Parquet writing (58 lines)

### Configuration
- `configs/storage.json` - Path mappings
- `configs/alpha_vantage_endpoints.json` - AV endpoints
- `config/loader.py` - ConfigLoader (type-safe)

---

## Class Diagram Summary

```
┌────────────────────────────────────────┐
│         BaseRegistry                   │
│  - render(ep_name) → (endpoint, path, query)
└────────────┬───────────────────────────┘
             │
         ┌───┴────┬──────────────┐
         ▼        ▼              ▼
   AlphaVantage BLS Chicago
   Registry    Registry Registry


┌────────────────────────────────────────┐
│           Facet                        │
│  - normalize(raw_batches) → DF        │
│  - postprocess(df) → transformed      │
│  - validate(df) → validated           │
└────────────┬───────────────────────────┘
             │
         ┌───┴─────┬──────────────────┐
         ▼         ▼                  ▼
   SecRef SecPrice [Other Facets]
   FacetAV FacetAV


┌────────────────────────────────────────┐
│          Ingestor                      │
│  - run_all(**kwargs)                  │
└────────────┬───────────────────────────┘
             │
         ┌───┴───────────┬──────────────┐
         ▼               ▼              ▼
   AlphaVantage BLS Chicago
   Ingestor    Ingestor Ingestor

Components:
- registry: Registry (endpoint definitions)
- key_pool: ApiKeyPool (API key rotation)
- http: HttpClient (rate-limited requests)
- sink: BronzeSink (Parquet writes)
```

---

## Testing & Validation

The report includes:
- Complete data flow walkthrough for Apple stock prices
- Memory management analysis
- Rate limiting calculations
- Error handling patterns
- Configuration precedence rules

---

## Appendix

The full 1,528-line report in `docs/DATA_PIPELINE_ARCHITECTURE.md` includes:

1. **13 main sections** with detailed documentation
2. **10+ code examples** showing actual pipeline flow
3. **Complete class diagrams** with relationships
4. **Error handling patterns** and API response structures
5. **Configuration examples** for all 3 providers
6. **Memory optimization opportunities** with implementation suggestions
7. **File reference appendix** with location and line counts

---

**Report Generated**: November 21, 2025  
**Total Content**: 1,528 lines across 13 sections  
**Coverage**: API layer, Bronze layer, configuration, error handling, optimization opportunities
