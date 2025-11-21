# Data Ingestion Pipeline Architecture Report

**Report Date**: November 21, 2025  
**Repository**: de_Funk  
**Focus**: Complete data ingestion pipeline architecture from API to Bronze layer  

---

## Executive Summary

de_Funk implements a **three-tier data ingestion architecture**:
1. **API Providers** - External data sources (Alpha Vantage, BLS, Chicago Data Portal)
2. **Bronze Layer** - Raw ingested data stored as partitioned Parquet files
3. **Silver Layer** - Dimensional models built from Bronze

The pipeline uses a **composable architecture** with:
- **Facets**: Transform API responses to DataFrames
- **Ingestors**: Orchestrate providers + facets + bronze writes
- **Registries**: Manage endpoint definitions and request rendering
- **Sinks**: Handle Parquet write operations

Key optimization: **Sequential rate-limited API calls** with configurable concurrency, supporting both free tier (5 calls/min) and premium tier (75+ calls/min) rate limits.

---

## 1. Pipeline Architecture Overview

### 1.1 High-Level Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR ENTRY POINT                      │
│                    (run_full_pipeline.py)                        │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
        ┌──────────────────────────────────────┐
        │   RepoContext + Configuration         │
        │   - Load API endpoints (JSON)         │
        │   - Load storage paths (JSON)         │
        │   - Initialize Spark session          │
        └──────────────────────────┬────────────┘
                                   │
                                   ▼
            ┌────────────────────────────────────────┐
            │      INGESTOR SELECTION                │
            │  (AlphaVantageIngestor, BLSIngestor)  │
            └──────────────┬─────────────────────────┘
                           │
    ┌──────────────────────┴──────────────────────┐
    │                                             │
    ▼                                             ▼
┌──────────────────────────┐          ┌──────────────────────────┐
│ ingest_reference_data()  │          │   ingest_prices()        │
│ (OVERVIEW endpoint)      │          │ (TIME_SERIES endpoint)   │
└──────────┬───────────────┘          └──────────┬───────────────┘
           │                                     │
    ┌──────┴─────────┐                  ┌───────┴─────────┐
    │                │                  │                 │
    ▼                ▼                  ▼                 ▼
 REGISTRY       FACET               REGISTRY           FACET
 (render)       (calls)             (render)          (calls)
    │                │                  │                 │
    └──────┬─────────┘                  └────────┬────────┘
           │                                      │
           ▼                                      ▼
    ┌─────────────────────────────────────────────────────┐
    │          HTTP CLIENT (rate limited)                 │
    │  - Throttle based on rate_limit_per_sec             │
    │  - API key rotation from key pool                   │
    │  - Retry with exponential backoff (429, 5xx)        │
    │  - Thread-safe request execution                    │
    └──────────────────────────┬──────────────────────────┘
                               │
                ┌──────────────┴──────────────┐
                │                             │
                ▼                             ▼
            API Response              API Response
         (JSON Lists)                (JSON Objects)
                │                             │
    ┌───────────┴──────────────┐             │
    ▼                          ▼             ▼
 Normalize                  Normalize    Normalize
 (Facet.normalize)          (Facet.normalize)
    │                          │             │
    └──────────────┬───────────┴─────────────┘
                   │
                   ▼
          ┌─────────────────────┐
          │ Postprocess         │
          │ (Type coercion,     │
          │  schema casting,    │
          │  validation)        │
          └────────────┬────────┘
                       │
                       ▼
            ┌──────────────────────┐
            │  BRONZE SINK         │
            │  (BronzeSink.write)  │
            │                      │
            │ - Partitioning      │
            │ - Parquet format    │
            │ - Overwrite mode    │
            └────────────┬─────────┘
                         │
                         ▼
        ┌────────────────────────────────┐
        │  BRONZE LAYER (Parquet)        │
        │                                │
        │  storage/bronze/               │
        │  ├── securities_reference/     │
        │  │   ├── snapshot_dt=2025-11-21│
        │  │   │   ├── asset_type=stocks │
        │  │   │   │   └── part-*.parquet│
        │  │   │   └── asset_type=etfs   │
        │  │   └── ...                   │
        │  ├── securities_prices_daily/  │
        │  │   ├── asset_type=stocks     │
        │  │   │   ├── year=2025         │
        │  │   │   │   ├── month=01      │
        │  │   │   │   │   └── part-*.par│
        │  │   │   │   └── month=02      │
        │  │   │   └── ...               │
        │  │   └── ...                   │
        │  └── [other providers]         │
        └────────────────────────────────┘
```

### 1.2 Data Pipeline Orchestration Flow

```python
# STEP 1: Entry Point
run_full_pipeline()
  ├─ Parse command-line arguments
  ├─ Initialize RepoContext (loads config)
  └─ Create Orchestrator(ctx)

# STEP 2: Data Ingestion
Orchestrator.run_company_pipeline()
  ├─ Create ingestor: AlphaVantageIngestor(cfg, storage)
  ├─ Call ingestor.run_all()
  │   └─ Orchestrates reference + prices ingestion
  └─ Returns list of tickers

# STEP 3: Reference Data (Company Fundamentals)
AlphaVantageIngestor.ingest_reference_data(tickers=['AAPL', ...])
  ├─ Create SecuritiesReferenceFacetAV(tickers)
  ├─ Generate calls: [{"ep_name": "company_overview", "params": {"symbol": "AAPL"}}, ...]
  ├─ Fetch calls: _fetch_calls(calls) → raw API responses
  ├─ Normalize: facet.normalize(raw_batches)
  │   └─ Create DataFrame from rows
  ├─ Postprocess: facet.postprocess(df)
  │   └─ Transform Alpha Vantage fields to unified schema
  ├─ Validate: facet.validate(df)
  └─ Write: sink.write(df, "securities_reference", partitions=["snapshot_dt", "asset_type"])

# STEP 4: Price Data
AlphaVantageIngestor.ingest_prices(tickers=['AAPL', ...])
  ├─ Create SecuritiesPricesFacetAV(tickers, date_from, date_to)
  ├─ Generate calls: [{"ep_name": "time_series_daily_adjusted", "params": {"symbol": "AAPL"}}, ...]
  ├─ Fetch calls: _fetch_calls(calls) → raw API responses
  ├─ Normalize: facet.normalize(raw_batches)
  │   └─ Flatten nested time series dict to rows
  ├─ Postprocess: facet.postprocess(df)
  │   └─ Parse dates, rename columns, calculate VWAP
  ├─ Validate: facet.validate(df)
  └─ Write: sink.write(df, "securities_prices_daily", partitions=["asset_type", "year", "month"])
```

---

## 2. Provider Implementations

### 2.1 Alpha Vantage Provider (Primary v2.0)

**Location**: `/datapipelines/providers/alpha_vantage/`

#### Architecture
```
alpha_vantage/
├── alpha_vantage_ingestor.py      # Main orchestration
├── alpha_vantage_registry.py       # Endpoint management
└── facets/
    ├── alpha_vantage_base_facet.py # Base class
    ├── securities_reference_facet.py
    └── securities_prices_facet.py
```

#### AlphaVantageIngestor Class

**Key Methods**:

1. **`__init__(alpha_vantage_cfg, storage_cfg, spark)`**
   - Initializes registry, HTTP client, API key pool, bronze sink
   - Sets up threading lock for thread-safe HTTP requests

2. **`ingest_reference_data(tickers, use_concurrent=False)`**
   - Fetches company fundamentals (OVERVIEW endpoint)
   - One API call per ticker
   - Returns: Path to written bronze table

3. **`ingest_prices(tickers, date_from, date_to, outputsize='full', use_concurrent=False)`**
   - Fetches daily OHLCV (TIME_SERIES_DAILY_ADJUSTED endpoint)
   - Full history in single call per ticker (no pagination)
   - Returns: Path to written bronze table

4. **`ingest_bulk_listing(state='active')`**
   - **Efficient**: Single API call returns ALL tickers (CSV format)
   - Maps to securities_reference schema
   - Returns: (path, tickers_list, ticker_exchanges_dict)

5. **`run_all(tickers, date_from, date_to, use_bulk_listing=False, skip_reference_refresh=False)`**
   - Main orchestration method
   - Supports two modes:
     - **Bulk listing mode**: Discover all tickers in 1 call, filter to US exchanges
     - **Individual ticker mode**: Use provided ticker list

**Rate Limiting Strategy**:
```python
# Free tier: 5 calls/minute = 0.08333 calls/second
# Premium: 75 calls/minute = 1.25 calls/second

# Default: Sequential processing (HttpClient throttles)
_fetch_calls(calls)
  └─ Loop: for each call
      ├─ _throttle() → sleep if needed
      └─ http.request() → fetch API

# Optional: Concurrent with ThreadPoolExecutor
_fetch_calls_concurrent(calls, max_workers=5)
  └─ ThreadPoolExecutor with _http_lock for thread-safe requests
```

**Error Handling**:
- Detects Alpha Vantage error response structures:
  - `{"Information": "...error message..."}` (info message)
  - `{"Error Message": "...error message..."}` (error)
  - `{"Note": "...rate limit message..."}` (rate limit warning)
- Logs failed tickers with detailed error info
- Continues ingestion if partial failures occur

#### AlphaVantageRegistry Class

**Purpose**: Manage endpoint definitions and request rendering

**Configuration Source**: `configs/alpha_vantage_endpoints.json`

**Sample Endpoint Definition**:
```json
{
  "company_overview": {
    "base": "core",
    "method": "GET",
    "path_template": "",
    "required_params": ["symbol"],
    "default_query": {
      "function": "OVERVIEW"
    },
    "response_key": null
  }
}
```

**Rendering Process**:
```python
endpoint, path, query = registry.render("company_overview", symbol="AAPL")

# Returns:
# - endpoint: Endpoint(name, base, method, path_template, required_params, default_query, response_key)
# - path: "" (empty for Alpha Vantage - single base URL)
# - query: {
#     "function": "OVERVIEW",
#     "symbol": "AAPL",
#     "apikey": "${API_KEY}"  # Placeholder for HttpClient
#   }
```

### 2.2 BLS Provider (Bureau of Labor Statistics)

**Location**: `/datapipelines/providers/bls/`

**Key Differences**:
- Uses POST requests with JSON body (not GET query params)
- No pagination (returns all data for period in single response)
- Series-based API (seriesid, startyear, endyear)

**BLSIngestor.run_all()**:
```python
def run_all(self, **kwargs):
    """Fetch economic indicators for specified series."""
    # Supports multiple series IDs (unemployment, CPI, employment, wages)
    # POST body: {"seriesid": [...], "startyear": 2020, "endyear": 2024}
```

### 2.3 Chicago Provider (Socrata API)

**Location**: `/datapipelines/providers/chicago/`

**Key Characteristics**:
- Uses Socrata API (SODA - Socrata Open Data API)
- REST endpoints for different datasets
- Query parameter based filtering

**Datasets**:
- Unemployment rates (by district)
- Building permits
- Business licenses
- Economic indicators

---

## 3. Facet Transformations

### 3.1 Base Facet Class

**Location**: `/datapipelines/facets/base_facet.py`

**Purpose**: Normalize raw API responses to Spark DataFrames

**Key Features**:

1. **Numeric Coercion** (Line 66-94):
   - Pre-coerces numeric fields from mixed types (string/int/float)
   - Maps field names to target types (double, long)
   - Handles type conflicts when unioning batches

2. **Normalization Pipeline** (Line 136-158):
   ```python
   def normalize(self, raw_batches):
       # 1. Coerce numeric fields (_coerce_rows)
       # 2. Create Spark DataFrames from batch rows
       # 3. Union all batches
       # 4. Call postprocess(df) for child-specific transformations
       # 5. Apply final casts (_apply_final_casts)
       # 6. Apply final column set (_apply_final_columns)
   ```

3. **Final Column Enforcement**:
   - Ensures stable column set and order
   - Creates NULL columns for missing fields
   - Casts to final target types

### 3.2 Alpha Vantage Base Facet

**Location**: `/datapipelines/providers/alpha_vantage/facets/alpha_vantage_base_facet.py`

**Purpose**: Clean Alpha Vantage data at Python level (before Spark)

**Key Transformations**:
```python
def normalize(self, raw_batches):
    # Clean invalid markers at Python level
    for batch in raw_batches:
        for item in batch:
            for key, value in item.items():
                if isinstance(value, str):
                    value = value.strip()
                    if value in ("None", "N/A", "-", ""):
                        cleaned_item[key] = None
```

**Why Important**:
- Alpha Vantage returns literal string "None" for missing values
- Uses "N/A" and "-" for unavailable data
- Pandas handles this gracefully with `pd.to_numeric(errors='coerce')`

### 3.3 SecuritiesReferenceFacetAV

**Location**: `/datapipelines/providers/alpha_vantage/facets/securities_reference_facet.py`

**Purpose**: Transform OVERVIEW endpoint to unified reference schema

**Input Schema** (Alpha Vantage OVERVIEW response):
```python
NUMERIC_COERCE = {
    "MarketCapitalization": "long",
    "SharesOutstanding": "long",
    "PERatio": "double",
    "52WeekHigh": "double",
    # ... more fields
}
```

**Key Transformation in postprocess()**:

```python
def postprocess(self, df):
    # Convert to pandas for flexible transformation
    pdf = df.toPandas()
    
    # Map asset types
    def map_asset_type(asset_type):
        if asset_type == "Common Stock": return "stocks"
        elif asset_type in ("ETF", "Mutual Fund"): return "etfs"
        elif "Option" in asset_type: return "options"
        elif "Future" in asset_type: return "futures"
    
    # Transform fields
    result = pd.DataFrame({
        'ticker': pdf['Symbol'],
        'security_name': pdf['Name'],
        'asset_type': pdf['AssetType'].apply(map_asset_type),
        
        # CIK: Pad to 10 digits per SEC standard
        'cik': pdf['CIK'].apply(lambda x: str(x).zfill(10) if pd.notna(x) else None),
        
        # Market data: Use pd.to_numeric for safe conversion
        'shares_outstanding': pd.to_numeric(pdf['SharesOutstanding'], errors='coerce'),
        'market_cap': pd.to_numeric(pdf['MarketCapitalization'], errors='coerce'),
        
        # ... more fields
    })
    
    # Deduplicate by ticker
    result = result.drop_duplicates(subset=['ticker'])
    
    # Convert back to Spark with explicit schema
    return self.spark.createDataFrame(result, schema=self._get_output_schema())
```

**Output Schema**:
```python
FINAL_COLUMNS = [
    ("ticker", "string"),
    ("security_name", "string"),
    ("asset_type", "string"),
    ("cik", "string"),  # SEC Central Index Key
    ("exchange_code", "string"),
    ("market_cap", "double"),
    ("shares_outstanding", "long"),
    ("pe_ratio", "double"),
    ("dividend_yield", "double"),
    # ... 31 columns total
]
```

### 3.4 SecuritiesPricesFacetAV

**Location**: `/datapipelines/providers/alpha_vantage/facets/securities_prices_facet.py`

**Purpose**: Transform TIME_SERIES_DAILY_ADJUSTED to unified prices schema

**Input Structure** (Nested):
```json
{
  "Time Series (Daily)": {
    "2024-01-15": {
      "1. open": "185.00",
      "2. high": "187.50",
      "3. low": "184.25",
      "4. close": "186.75",
      "5. adjusted close": "186.75",
      "6. volume": "52341200",
      "7. dividend amount": "0.0000",
      "8. split coefficient": "1.0"
    },
    "2024-01-14": { ... },
    ...
  }
}
```

**Key Transformation Steps**:

1. **Normalize Override** (handles nested structure):
   ```python
   def normalize(self, raw_batches):
       # Flatten nested date dict to rows
       flattened_batches = []
       for i, batch in enumerate(raw_batches):
           ctx = self._call_contexts[i]  # Get ticker/asset_type
           
           for response_dict in batch:
               # Find time series key ("Time Series (Daily)")
               time_series = response_dict[time_series_key]
               
               # Flatten: one row per date
               for date_str, ohlcv_data in time_series.items():
                   row = {
                       "ticker": ctx["ticker"],
                       "asset_type": ctx["asset_type"],
                       "trade_date": date_str,
                       **ohlcv_data  # Include all OHLCV fields
                   }
                   flattened_rows.append(row)
       
       # Call base normalize() with flattened batches
       return super().normalize(flattened_batches)
   ```

2. **Postprocess** (date parsing, numeric conversion, VWAP calculation):
   ```python
   def postprocess(self, df):
       pdf = df.toPandas()
       
       # Parse dates and extract partition columns
       pdf['trade_date'] = pd.to_datetime(pdf['trade_date'], errors='coerce')
       pdf['year'] = pdf['trade_date'].dt.year
       pdf['month'] = pdf['trade_date'].dt.month
       
       # Rename columns (remove numeric prefixes)
       rename_map = {
           "1. open": "open",
           "2. high": "high",
           "3. low": "low",
           "4. close": "close",
           "5. adjusted close": "adjusted_close",
           # ...
       }
       pdf = pdf.rename(columns=rename_map)
       
       # Convert numeric fields
       numeric_fields = ['open', 'high', 'low', 'close', 'volume', ...]
       for field in numeric_fields:
           pdf[field] = pd.to_numeric(pdf[field], errors='coerce')
       
       # Calculate VWAP (Volume-Weighted Average Price)
       # Approximation: (High + Low + Close) / 3
       pdf['volume_weighted'] = ((pdf['high'] + pdf['low'] + pdf['close']) / 3.0)
       
       # Date range filtering
       if self.date_from:
           pdf = pdf[pdf['trade_date'] >= pd.to_datetime(self.date_from).date()]
       if self.date_to:
           pdf = pdf[pdf['trade_date'] <= pd.to_datetime(self.date_to).date()]
       
       # Data quality filters
       pdf = pdf[
           (pdf['ticker'].notna()) &
           (pdf['close'].notna()) &
           (pdf['close'] > 0) &
           (pdf['trade_date'].notna())
       ]
       
       # Deduplicate by (ticker, trade_date)
       pdf = pdf.drop_duplicates(subset=['ticker', 'trade_date'])
       
       return self.spark.createDataFrame(pdf, schema=self._get_output_schema())
   ```

**Output Schema**:
```python
OUTPUT_SCHEMA = [
    ("trade_date", "date"),
    ("ticker", "string"),
    ("asset_type", "string"),
    ("year", "int"),          # Partition column
    ("month", "int"),         # Partition column
    ("open", "double"),
    ("high", "double"),
    ("low", "double"),
    ("close", "double"),
    ("volume", "double"),
    ("volume_weighted", "double"),
    ("transactions", "long"),  # NULL - not in Alpha Vantage
    ("otc", "boolean"),        # FALSE - not in Alpha Vantage
    ("adjusted_close", "double"),
    ("dividend_amount", "double"),
    ("split_coefficient", "double")
]
```

---

## 4. Ingestor Classes

### 4.1 Base Ingestor

**Location**: `/datapipelines/ingestors/base_ingestor.py`

**Purpose**: Abstract base for all ingestors

```python
class Ingestor(ABC):
    def __init__(self, storage_cfg):
        self.storage_cfg = storage_cfg
    
    @abstractmethod
    def run_all(self, **kwargs):
        """Orchestrate complete ingestion for this provider."""
        pass
```

### 4.2 AlphaVantageIngestor Flow

**Complete Memory Path**:
```
1. API Call (HTTP)
   └─ Response: JSON dict/list in memory

2. _fetch_calls() or _fetch_calls_concurrent()
   └─ Returns: List[List[dict]] (batches of raw API responses)
   └─ Memory: ~50KB per stock reference, ~100KB per 20 years of prices

3. Facet.normalize(raw_batches)
   └─ Pre-coerce numeric fields
   └─ Create Spark DataFrames from batches
   └─ Union batches (merge schemas)
   └─ Call facet.postprocess()

4. Facet.postprocess()
   └─ For REFERENCE: Convert to pandas, transform, convert back to Spark
   └─ For PRICES: Flatten nested dict, convert to pandas, transform back
   └─ Memory: Pandas DataFrame held in memory during transformation

5. Facet.validate()
   └─ Check for data quality issues
   └─ Return validated Spark DataFrame

6. BronzeSink.write()
   └─ Spark handles Parquet write with partitioning
   └─ Data spilled to disk as Parquet
   └─ Partitions created on disk (snapshot_dt, asset_type)
```

**Memory Management Considerations**:

1. **Batching**: API responses fetched in batches (one per ticker)
2. **Pandas Bridge**: Temporary pandas DataFrames during postprocess
3. **Spark Lazy Evaluation**: Spark keeps data lazy until write
4. **Partitioning**: Parquet files partitioned for efficient storage
5. **No Streaming**: All data loaded into memory before write (potential optimization point)

### 4.3 BLS and Chicago Ingestors

Similar structure to AlphaVantageIngestor but with provider-specific:
- Request building (POST bodies for BLS)
- Response key navigation (nested response paths)
- Facet-specific transformations

---

## 5. HTTP Client and Rate Limiting

**Location**: `/datapipelines/base/http_client.py`

### 5.1 HttpClient Class

**Key Attributes**:
```python
class HttpClient:
    def __init__(self, base_urls, headers, rate_limit_per_sec, api_key_pool, safety_factor=0.9, max_retries=6):
        self.configured_rps = float(rate_limit_per_sec or 0.0834)  # Default: Free tier
        self.api_key_pool = api_key_pool
        self.safety = float(safety_factor)
        self.max_retries = int(max_retries)
        self._last_ts = 0.0  # Throttle tracking
```

### 5.2 Rate Limiting Strategy

**Throttle Mechanism**:
```python
def _throttle(self):
    min_interval = 1.0 / self.configured_rps  # e.g., 12 seconds for 5/min
    dt = time.time() - self._last_ts
    if dt < min_interval:
        time.sleep(min_interval - dt)  # Sleep if needed
    self._last_ts = time.time()

def request(self, base_key, path, query, method="GET"):
    backoff_base = 2.0
    for attempt in range(self.max_retries):
        self._throttle()  # Rate limit: sleep if needed
        req, url = self._build_request(base_key, path, query, method)
        
        try:
            return json.loads(urllib.request.urlopen(req, timeout=60).read())
        
        except HTTPError as e:
            # 429 (Rate Limit): Backoff + retry
            if e.code == 429:
                retry_after = e.headers.get("Retry-After")
                wait = float(retry_after) if retry_after else min(120.0, backoff_base ** attempt)
                time.sleep(wait)
                continue
            
            # 5xx (Server Error): Retry with backoff
            if 500 <= e.code < 600:
                time.sleep(min(60.0, backoff_base ** attempt))
                continue
            
            # 4xx (Client Error): Fail
            raise RuntimeError(f"HTTP {e.code}: {url}")
```

### 5.3 API Key Pool

**Location**: `/datapipelines/base/key_pool.py`

**Purpose**: Rotate API keys to distribute rate limit across multiple keys

```python
class ApiKeyPool:
    def __init__(self, keys, cooldown_seconds=60.0):
        self.keys = deque(keys or [])      # Round-robin queue
        self.cooldown = cooldown_seconds    # Cooldown per key
        self.last_used = {}                 # Track last use time

    def next_key(self):
        if not self.keys:
            return None
        
        now = time.time()
        k = self.keys[0]
        
        # If key is in cooldown, rotate to next
        if k in self.last_used and (now - self.last_used[k]) < self.cooldown:
            self.keys.rotate(-1)
            k = self.keys[0]
        
        self.last_used[k] = now
        self.keys.rotate(-1)  # Move to back
        return k
```

**Example Usage**:
```python
# Alpha Vantage: 5 calls/min = 0.08333 calls/sec
# With 2 API keys:
# - Key A: cooldown 60 sec, can use every 60 sec
# - Key B: cooldown 60 sec, can use every 60 sec
# - Effective: 2 calls/min instead of 5, or rotate keys more smartly

key_pool = ApiKeyPool(["KEY_A", "KEY_B"], cooldown_seconds=60.0)

# Successive calls rotate keys:
key1 = key_pool.next_key()  # Returns KEY_A
key2 = key_pool.next_key()  # Returns KEY_B (KEY_A still in cooldown)
key3 = key_pool.next_key()  # Returns KEY_B again (KEY_A still in cooldown)
```

---

## 6. Bronze Sink and Parquet Writing

**Location**: `/datapipelines/ingestors/bronze_sink.py`

### 6.1 BronzeSink Class

```python
class BronzeSink:
    def __init__(self, storage_cfg):
        self.cfg = storage_cfg  # From storage.json
    
    def _table_cfg(self, table):
        return self.cfg["tables"][table]
    
    def _path(self, table, partitions):
        """Build full path: storage/bronze/{table}/partition_key=value/..."""
        base = Path(self.cfg["roots"]["bronze"]) / self._table_cfg(table)["rel"]
        for k, v in (partitions or {}).items():
            base = base / f"{k}={v}"
        return base
    
    def write(self, df, table, partitions=None):
        """
        Write DataFrame to bronze with partitioning.
        
        Args:
            df: Spark DataFrame
            table: Table name (e.g., "securities_reference")
            partitions: List of partition columns (e.g., ["snapshot_dt", "asset_type"])
        
        Returns:
            Path to written table
        """
        table_cfg = self._table_cfg(table)
        base_path = Path(self.cfg["roots"]["bronze"]) / table_cfg["rel"]
        
        # Add snapshot_dt if needed
        if partitions and "snapshot_dt" in partitions:
            from datetime import date
            if "snapshot_dt" not in df.columns:
                df = df.withColumn("snapshot_dt", lit(date.today().isoformat()))
        
        # Write with partitioning
        if partitions:
            df.write.mode("overwrite").partitionBy(*partitions).parquet(str(base_path))
        else:
            df.write.mode("overwrite").parquet(str(base_path))
        
        return str(base_path)
```

### 6.2 Partitioning Strategy

**Securities Reference**:
```
storage/bronze/securities_reference/
├── snapshot_dt=2025-11-21/
│   ├── asset_type=stocks/
│   │   ├── part-00000.parquet
│   │   └── part-00001.parquet
│   ├── asset_type=etfs/
│   │   └── part-00000.parquet
│   └── asset_type=options/
│       └── part-00000.parquet
└── snapshot_dt=2025-11-20/
    └── asset_type=stocks/
        └── part-00000.parquet
```

**Why These Partitions?**:
- **snapshot_dt**: Allows time-series of reference data snapshots
- **asset_type**: Filters by securities category (stocks, etfs, options, futures)

**Securities Prices Daily**:
```
storage/bronze/securities_prices_daily/
├── asset_type=stocks/
│   ├── year=2025/
│   │   ├── month=01/
│   │   │   ├── part-00000.parquet
│   │   │   └── part-00001.parquet
│   │   ├── month=02/
│   │   │   └── part-00000.parquet
│   │   └── ...
│   ├── year=2024/
│   │   ├── month=01/
│   │   │   └── part-00000.parquet
│   │   └── ...
│   └── ...
├── asset_type=etfs/
│   └── year=2025/
│       └── ...
└── asset_type=futures/
    └── ...
```

**Why Year/Month (not trade_date)?**:
- Avoids **partition sprawl**: 3,000+ partitions for multi-year history with daily partitioning
- Year/month: ~4,000 tickers × 48 months × 4 asset types = ~768K partitions (still manageable)
- Enables efficient pruning by time range
- Compressed partition directory structure

---

## 7. Configuration Management

### 7.1 Configuration Loading

**Entry Point**: `config/loader.py` (ConfigLoader)

```python
from config import ConfigLoader

loader = ConfigLoader()
config = loader.load()  # Auto-discover repo root

# Type-safe access
print(config.connection.type)      # "duckdb" or "spark"
print(config.repo_root)
print(config.models_dir)
print(config.apis)                 # Auto-discovered API configs
```

### 7.2 API Endpoint Configuration

**Alpha Vantage**: `configs/alpha_vantage_endpoints.json`

```json
{
  "credentials": {
    "api_keys": [],
    "comment": "Set ALPHA_VANTAGE_API_KEYS environment variable"
  },
  "base_urls": {
    "core": "https://www.alphavantage.co/query"
  },
  "rate_limit_per_sec": 1.0,
  "endpoints": {
    "company_overview": {
      "base": "core",
      "method": "GET",
      "path_template": "",
      "required_params": ["symbol"],
      "default_query": {
        "function": "OVERVIEW"
      },
      "response_key": null
    },
    "time_series_daily_adjusted": { ... },
    "listing_status": { ... }
  }
}
```

### 7.3 Storage Configuration

**File**: `configs/storage.json`

```json
{
  "roots": {
    "bronze": "storage/bronze",
    "silver": "storage/silver"
  },
  "tables": {
    "securities_reference": {
      "root": "bronze",
      "rel": "securities_reference",
      "partitions": ["snapshot_dt", "asset_type"]
    },
    "securities_prices_daily": {
      "root": "bronze",
      "rel": "securities_prices_daily",
      "partitions": ["asset_type", "year", "month"]
    }
  }
}
```

---

## 8. Data Flow - Complete Example

### 8.1 Ingesting Apple Stock Prices

```bash
# Command
python -m scripts.ingest.run_full_pipeline --days 30

# Step 1: Initialize
ctx = RepoContext.from_repo_root()
  └─ Load alpha_vantage_endpoints.json
  └─ Load storage.json
  └─ Initialize Spark session

# Step 2: Create Ingestor
ingestor = AlphaVantageIngestor(
    alpha_vantage_cfg=config.apis['alpha_vantage'],
    storage_cfg=config.storage,
    spark=spark_session
)

# Step 3: Ingest Prices
ingestor.ingest_prices(
    tickers=['AAPL'],
    date_from='2025-10-22',
    date_to='2025-11-21',
    adjusted=True,
    outputsize='full'
)

# Step 3a: Create Facet
facet = SecuritiesPricesFacetAV(
    spark,
    tickers=['AAPL'],
    date_from='2025-10-22',
    date_to='2025-11-21',
    adjusted=True,
    outputsize='full'
)

# Step 3b: Generate API Calls
calls = list(facet.calls())
# Returns: [{
#   "ep_name": "time_series_daily_adjusted",
#   "params": {
#     "symbol": "AAPL",
#     "outputsize": "full"
#   }
# }]

# Step 3c: Fetch from API
endpoint, path, query = registry.render(
    "time_series_daily_adjusted",
    symbol="AAPL",
    outputsize="full"
)
# endpoint = Endpoint(name="time_series_daily_adjusted", base="core", ...)
# path = ""
# query = {
#   "function": "TIME_SERIES_DAILY_ADJUSTED",
#   "outputsize": "full",
#   "datatype": "json",
#   "symbol": "AAPL",
#   "apikey": "${API_KEY}"
# }

# HTTP Request
http_client._throttle()  # Sleep if needed to respect rate limit
api_key = key_pool.next_key()  # Get next API key
url = "https://www.alphavantage.co/query?function=TIME_SERIES_DAILY_ADJUSTED&..."
response = urllib.request.urlopen(url)

# Response (truncated):
response_json = {
    "Meta Data": { ... },
    "Time Series (Daily)": {
        "2025-11-21": {
            "1. open": "250.50",
            "2. high": "252.75",
            "3. low": "249.30",
            "4. close": "251.80",
            "5. adjusted close": "251.80",
            "6. volume": "40123456",
            "7. dividend amount": "0.0000",
            "8. split coefficient": "1.0"
        },
        "2025-11-20": { ... },
        ...
    }
}

# Step 3d: Normalize (Facet)
raw_batches = [[response_json]]

# Flatten nested structure
flattened_rows = [
    {
        "ticker": "AAPL",
        "asset_type": "stocks",
        "trade_date": "2025-11-21",
        "1. open": "250.50",
        "2. high": "252.75",
        ...
    },
    {
        "ticker": "AAPL",
        "asset_type": "stocks",
        "trade_date": "2025-11-20",
        ...
    },
    ...
]

# Coerce numeric fields
for row in flattened_rows:
    row["1. open"] = float(row["1. open"])  # "250.50" → 250.5
    row["6. volume"] = float(row["6. volume"])  # "40123456" → 40123456.0

# Create Spark DataFrame
df = spark.createDataFrame(flattened_rows, schema=get_input_schema())

# Step 3e: Postprocess (Facet)
pdf = df.toPandas()  # Convert to pandas for flexible transformation

# Parse dates
pdf['trade_date'] = pd.to_datetime(pdf['trade_date'])
pdf['year'] = pdf['trade_date'].dt.year  # 2025
pdf['month'] = pdf['trade_date'].dt.month  # 11

# Rename columns
rename_map = {
    "1. open": "open",
    "2. high": "high",
    "3. low": "low",
    "4. close": "close",
    "5. adjusted close": "adjusted_close",
    "6. volume": "volume",
    ...
}
pdf = pdf.rename(columns=rename_map)

# Convert numeric fields
for field in ['open', 'high', 'low', 'close', 'volume', ...]:
    pdf[field] = pd.to_numeric(pdf[field], errors='coerce')

# Calculate VWAP
pdf['volume_weighted'] = ((pdf['high'] + pdf['low'] + pdf['close']) / 3.0)

# Date range filtering
pdf = pdf[pdf['trade_date'] >= pd.to_datetime('2025-10-22').date()]
pdf = pdf[pdf['trade_date'] <= pd.to_datetime('2025-11-21').date()]

# Data quality filters
pdf = pdf[(pdf['ticker'].notna()) & (pdf['close'] > 0)]

# Deduplicate
pdf = pdf.drop_duplicates(subset=['ticker', 'trade_date'])

# Convert back to Spark DataFrame
df_final = spark.createDataFrame(pdf, schema=_get_output_schema())

# Step 3f: Validate (Facet)
assert df_final.filter(col("ticker").isNull()).count() == 0
assert df_final.filter(col("high") < col("low")).count() == 0

# Step 3g: Write to Bronze (BronzeSink)
base_path = Path("storage/bronze/securities_prices_daily")
df_final.write \
    .mode("overwrite") \
    .partitionBy("asset_type", "year", "month") \
    .parquet(str(base_path))

# Result on Disk:
# storage/bronze/securities_prices_daily/
# ├── asset_type=stocks/
# │   └── year=2025/
# │       └── month=11/
# │           ├── part-00000.parquet
# │           └── part-00001.parquet
# └── (other asset types)

# Returns: "storage/bronze/securities_prices_daily"
```

---

## 9. Memory Management and Optimization Opportunities

### 9.1 Current Memory Path

```
1. Raw API Response (~50-500KB per ticker)
   └─ Held in memory as JSON dict/list

2. Facet._fetch_calls()
   └─ List[List[dict]] batches
   └─ Memory: Proportional to # tickers × response size

3. Facet.normalize()
   └─ Create Spark DataFrames from batches
   └─ Union batches in memory
   └─ Call postprocess()

4. Postprocess (Pandas Bridge)
   └─ Convert entire DF to pandas
   └─ Perform transformations
   └─ Convert back to Spark
   └─ Memory: 2-3x size of original DataFrame

5. BronzeSink.write()
   └─ Spark handles write (lazy)
   └─ Data spilled to Parquet
```

### 9.2 Bottlenecks and Solutions

**Current Issue 1: Pandas Bridge in Postprocess**
```python
# Current (memory-intensive for large DataFrames)
def postprocess(self, df):
    pdf = df.toPandas()  # FULL DataFrame to pandas
    # ... transformations ...
    return self.spark.createDataFrame(pdf, ...)
```

**Solution**: Use Spark transformations where possible:
```python
def postprocess_optimized(self, df):
    df = df.withColumn("year", year(col("trade_date")))
    df = df.withColumn("open", col("1. open").cast(DoubleType()))
    # ... etc
```

**Current Issue 2: No Streaming**
```python
# Current: Fetch all tickers sequentially, write in one go
ingestor.ingest_prices(tickers=['AAPL', 'MSFT', 'GOOGL', ...])
# All ~500 tickers held in memory before write

# API Response Memory:
# 500 tickers × 20 years × 252 trading days × ~100 bytes = 250MB per fetch
```

**Solution**: Implement Streaming/Batch Write:
```python
def ingest_prices_streaming(self, tickers, batch_size=10):
    """Ingest in batches, write after each batch."""
    for i in range(0, len(tickers), batch_size):
        batch_tickers = tickers[i:i+batch_size]
        
        # Fetch batch
        raw_batches = self._fetch_calls(...)
        df = facet.normalize(raw_batches)
        df = facet.postprocess(df)
        
        # Write batch immediately
        self.sink.write(df, "securities_prices_daily", partitions=...)
        
        # Memory released after write
```

**Current Issue 3: Duplicate Code in Error Handling**
```python
# Current: Error checking repeated in ingest_reference_data and ingest_prices
if "Information" in item and len(item) == 1:
    error_count += 1
    ...
```

**Solution**: Extract to base class method:
```python
def _check_api_errors(self, raw_batches, tickers):
    """Check for Alpha Vantage error responses."""
    errors = {}
    for i, batch in enumerate(raw_batches):
        for item in batch:
            if self._is_error_response(item):
                errors[tickers[i]] = self._extract_error_msg(item)
    return errors
```

---

## 10. Class Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      BaseRegistry                            │
│  (render endpoint definitions to HTTP requests)             │
│                                                              │
│  - render(ep_name, **params) → (Endpoint, path, query)     │
│  - headers, base_urls, rate_limit_per_sec                   │
│  - endpoints dict with defaults                             │
└────────────┬──────────────────────────────────┬──────────────┘
             │                                  │
             ▼                                  ▼
┌──────────────────────────────┐    ┌──────────────────────────────┐
│   AlphaVantageRegistry       │    │     BLSRegistry              │
│   (Alpha Vantage specific)   │    │     (BLS specific)           │
│                              │    │                              │
│  - render() override         │    │  - render() override         │
│  - Handles API key placement │    │  - Handles POST bodies       │
└──────────────────────────────┘    └──────────────────────────────┘


┌──────────────────────────────────────────────────────────────┐
│                        Facet                                 │
│  (Normalize API responses to Spark DataFrames)              │
│                                                              │
│  - NUMERIC_COERCE: type mapping                             │
│  - SPARK_CASTS: final type casts                            │
│  - FINAL_COLUMNS: stable column set                         │
│  - normalize(raw_batches) → DataFrame                       │
│  - postprocess(df) → transformed DataFrame                  │
│  - validate(df) → validated DataFrame                       │
└───────────┬──────────────────────────────────┬──────────────┘
            │                                  │
            ▼                                  ▼
┌─────────────────────────────────┐  ┌────────────────────────────┐
│    AlphaVantageFacet            │  │   BLSFacet                │
│                                 │  │                            │
│  - normalize() override          │  │  - normalize() override    │
│  - Cleans invalid markers        │  │  - Handles nested keys     │
└────────┬────────────────────────┘  └────────────────────────────┘
         │
    ┌────┴────┬────────────────────────────────┐
    │          │                                │
    ▼          ▼                                ▼
SecRef    SecPrices          [other AV facets]


┌──────────────────────────────────────────────────────────────┐
│                        Ingestor                              │
│  (Orchestrate provider + facet + sink)                      │
│                                                              │
│  @abstractmethod run_all(**kwargs)                          │
│  - storage_cfg: config dict                                 │
└───────────┬──────────────────────────────────┬──────────────┘
            │                                  │
            ▼                                  ▼
┌──────────────────────────────┐    ┌──────────────────────────────┐
│  AlphaVantageIngestor        │    │     BLSIngestor              │
│                              │    │                              │
│  - registry: AvRegistry      │    │  - registry: BLSRegistry     │
│  - key_pool: ApiKeyPool      │    │  - key_pool: ApiKeyPool      │
│  - http: HttpClient          │    │  - http: HttpClient          │
│  - sink: BronzeSink          │    │  - sink: BronzeSink          │
│                              │    │                              │
│  - ingest_reference_data()   │    │  - run_all() -> fetch BLS    │
│  - ingest_prices()           │    │                              │
│  - ingest_bulk_listing()     │    │                              │
│  - run_all()                 │    │                              │
└──────────────────────────────┘    └──────────────────────────────┘


┌──────────────────────────────────────────────────────────────┐
│                      HttpClient                              │
│  (Make HTTP requests with rate limiting)                    │
│                                                              │
│  - request(base, path, query, method) → JSON response       │
│  - request_text(base, path, query, method) → text           │
│  - _throttle() → enforce rate limit                         │
│  - _build_request() → construct urllib.Request              │
│  - Handles 429, 5xx retries with backoff                    │
│  - Thread-safe request execution                            │
│                                                              │
│  - rate_limit_per_sec: 0.08333 (free) to 1.25 (premium)   │
│  - api_key_pool: ApiKeyPool for key rotation                │
└──────────────────────────────────────────────────────────────┘


┌──────────────────────────────────────────────────────────────┐
│                      ApiKeyPool                              │
│  (Rotate API keys to distribute rate limit)                │
│                                                              │
│  - keys: deque of API keys                                  │
│  - cooldown_seconds: 60 (free tier needs long cooldown)     │
│  - next_key() → next available key (with cooldown check)    │
│  - Avoids hammering single key                              │
└──────────────────────────────────────────────────────────────┘


┌──────────────────────────────────────────────────────────────┐
│                      BronzeSink                              │
│  (Write Spark DataFrames to Parquet)                        │
│                                                              │
│  - write(df, table, partitions) → path                      │
│  - _path(table, partitions) → full path with partitions     │
│  - Partitions: snapshot_dt, asset_type, year, month         │
│  - Mode: overwrite (fresh write)                            │
│  - Format: Parquet (columnar, compressed)                   │
└──────────────────────────────────────────────────────────────┘


┌──────────────────────────────────────────────────────────────┐
│                   Orchestrator                               │
│  (High-level pipeline orchestration)                        │
│                                                              │
│  - ctx: RepoContext (config, Spark, storage paths)          │
│  - run_company_pipeline() → orchestrate full ingestion      │
│    1. Create ingestor (AlphaVantageIngestor)                │
│    2. Call ingestor.run_all() → ingest to bronze            │
│    3. Load model config                                     │
│    4. Build silver layer (CompanyModel)                     │
│    5. Return analytics table                                │
└──────────────────────────────────────────────────────────────┘
```

---

## 11. Configuration and Environment

### 11.1 Environment Variables

```bash
# API Keys
ALPHA_VANTAGE_API_KEYS=key1,key2,key3  # Comma-separated for rotation
BLS_API_KEYS=bls_api_key
CHICAGO_API_KEYS=chicago_token

# Connection
CONNECTION_TYPE=duckdb  # or 'spark'

# Logging
LOG_LEVEL=DEBUG

# Spark Config
SPARK_DRIVER_MEMORY=8g
SPARK_EXECUTOR_MEMORY=8g
SPARK_SHUFFLE_PARTITIONS=400

# DuckDB Config
DUCKDB_DATABASE_PATH=storage/duckdb/analytics.db
DUCKDB_MEMORY_LIMIT=8GB
DUCKDB_THREADS=8
```

### 11.2 Configuration Files

```
configs/
├── storage.json                    # Bronze/silver paths
├── alpha_vantage_endpoints.json    # AV API endpoints
├── bls_endpoints.json              # BLS API endpoints
├── chicago_endpoints.json          # Chicago API endpoints
└── models/                         # YAML model definitions
```

---

## 12. Error Handling Strategy

### 12.1 API Error Detection

**Alpha Vantage Error Response Structures**:
```json
// Information message
{
  "Information": "Thank you for using Alpha Vantage! Our standard API call frequency is 5 calls per minute and 500 calls per day."
}

// Error message
{
  "Error Message": "Invalid API call. Please retry or visit the documentation."
}

// Rate limit note
{
  "Note": "Thank you for using Alpha Vantage! Our standard API call frequency is 5 calls per minute."
}
```

**Ingestor Error Detection**:
```python
error_count = 0
error_details = []

for i, batch in enumerate(raw_batches):
    for item in batch:
        if isinstance(item, dict):
            ticker = tickers[i] if i < len(tickers) else "UNKNOWN"
            
            if "Information" in item and len(item) == 1:
                error_count += 1
                error_details.append({"ticker": ticker, "type": "INFO", "message": item['Information']})
            elif "Error Message" in item:
                error_count += 1
                error_details.append({"ticker": ticker, "type": "ERROR", "message": item['Error Message']})
            elif "Note" in item:
                error_count += 1
                error_details.append({"ticker": ticker, "type": "NOTE", "message": item['Note']})

if error_count > 0:
    print(f"⚠ Warning: {error_count} API responses contained errors")
    # Continue ingestion if partial failure (not all tickers failed)
    if error_count < len(raw_batches):
        print("Continuing with successful responses...")
```

### 12.2 HTTP Error Handling

```python
# In HttpClient.request()
try:
    response = urllib.request.urlopen(req, timeout=60)
except HTTPError as e:
    if e.code == 429:  # Rate limit exceeded
        retry_after = e.headers.get("Retry-After")
        wait = float(retry_after) if retry_after else 2 ** attempt
        time.sleep(wait)
        continue  # Retry
    
    elif 500 <= e.code < 600:  # Server error
        time.sleep(2 ** attempt)
        continue  # Retry
    
    else:  # Client error (4xx)
        raise RuntimeError(f"HTTP {e.code}: {url} :: body={body}")

except URLError:  # Network error
    time.sleep(2 ** attempt)
    continue  # Retry
```

---

## 13. Summary and Key Insights

### 13.1 Architecture Strengths

1. **Composable Design**: Facets + Registries + Ingestors are loosely coupled
2. **Rate Limiting**: Built-in throttling respects API limits
3. **Error Resilience**: Continues on partial failures
4. **Partitioning**: Smart partitioning for query efficiency
5. **Type Safety**: NUMERIC_COERCE and SPARK_CASTS prevent type mismatches

### 13.2 Current Limitations

1. **Memory Usage**: Pandas bridge in postprocess loads full DataFrames
2. **No Streaming**: All data buffered before write
3. **Synchronous**: Sequential API calls (optional concurrency with caveats)
4. **Pandas Dependency**: Postprocess logic tied to pandas

### 13.3 Optimization Opportunities

1. **Batch Streaming**: Write batches of tickers as they complete
2. **Spark-Only Transforms**: Replace pandas bridge with Spark SQL
3. **Adaptive Concurrency**: Use concurrency when rate limits allow
4. **Incremental Writes**: Append-only or merge-on-read for updates
5. **Response Streaming**: Stream large responses instead of buffering

---

## Appendix: File Reference

```
datapipelines/
├── base/
│   ├── registry.py              # BaseRegistry (endpoint rendering)
│   ├── http_client.py           # HttpClient (HTTP + rate limiting)
│   └── key_pool.py              # ApiKeyPool (API key rotation)
├── facets/
│   └── base_facet.py            # Facet base class
├── ingestors/
│   ├── base_ingestor.py         # Ingestor abstract base
│   ├── bronze_sink.py           # Write to Parquet
│   └── company_ingestor.py      # Polygon-based ingestor
└── providers/
    ├── alpha_vantage/
    │   ├── alpha_vantage_ingestor.py      # Main orchestration
    │   ├── alpha_vantage_registry.py      # Endpoint definitions
    │   └── facets/
    │       ├── alpha_vantage_base_facet.py
    │       ├── securities_reference_facet.py
    │       └── securities_prices_facet.py
    ├── bls/
    │   ├── bls_ingestor.py
    │   ├── bls_registry.py
    │   └── facets/
    │       ├── bls_base_facet.py
    │       ├── unemployment_facet.py
    │       └── cpi_facet.py
    └── chicago/
        ├── chicago_ingestor.py
        ├── chicago_registry.py
        └── facets/
            ├── chicago_base_facet.py
            └── [specific facets]

scripts/
└── ingest/
    └── run_full_pipeline.py     # Entry point

orchestration/
├── orchestrator.py              # High-level orchestration
└── common/
    └── spark_session.py         # Spark initialization

config/
├── loader.py                    # ConfigLoader
├── models.py                    # Typed config dataclasses
└── constants.py                 # Default values

configs/
├── storage.json                 # Path configuration
├── alpha_vantage_endpoints.json # AV API endpoints
├── bls_endpoints.json           # BLS endpoints
└── chicago_endpoints.json       # Chicago endpoints
```

---

**End of Report**
