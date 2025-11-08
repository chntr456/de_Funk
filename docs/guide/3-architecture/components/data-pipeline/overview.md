# Data Pipeline Component - Overview

## Table of Contents
1. [Introduction](#introduction)
2. [Architecture](#architecture)
3. [Component Responsibilities](#component-responsibilities)
4. [Data Flow](#data-flow)
5. [Provider Registry System](#provider-registry-system)
6. [API Integration Patterns](#api-integration-patterns)
7. [Error Handling & Resilience](#error-handling--resilience)
8. [Usage Examples](#usage-examples)

## Introduction

The **Data Pipeline Component** is responsible for ingesting raw data from external APIs and persisting it to the Bronze layer. It implements a **provider-agnostic architecture** that makes it easy to add new data sources while maintaining consistent patterns for fetching, parsing, and storing data.

### Key Features

- **Multi-provider support**: Polygon, BLS, Chicago Data Portal, extensible to more
- **Automatic pagination**: Handles API pagination transparently
- **Rate limiting**: Built-in rate limiter with API key rotation
- **Retry logic**: Automatic retries with exponential backoff
- **Schema inference**: Flexible schema handling for varying API responses
- **Partitioned storage**: Date and provider-based partitioning for efficient queries

### Design Principles

1. **Separation of Concerns**: Facets define "what to fetch", Ingestors handle "how to fetch"
2. **Configuration over Code**: API endpoints and parameters defined in JSON configs
3. **Fail-safe**: Robust error handling ensures partial failures don't stop entire pipeline
4. **Auditable**: All data includes ingestion metadata for traceability

## Architecture

### Component Structure

```
datapipelines/
├── base/                              # Core abstractions
│   ├── registry.py                    # Central facet registry
│   ├── http_client.py                 # HTTP client with rate limiting
│   ├── key_pool.py                    # API key rotation pool
│   └── __init__.py
│
├── facets/                            # Facet definitions (deprecated location)
│   ├── base_facet.py                  # Base facet class
│   └── polygon/                       # Polygon-specific facets
│       ├── polygon_base_facet.py
│       ├── prices_daily_facet.py
│       ├── ref_tickers_facet.py
│       └── ...
│
├── ingestors/                         # Orchestration logic
│   ├── base_ingestor.py               # Base ingestor interface
│   ├── polygon_ingestor.py            # Polygon implementation
│   ├── bronze_sink.py                 # Bronze layer writer
│   └── polygon_registry.py            # Polygon facet registry
│
└── providers/                         # New provider-based organization
    ├── polygon/                       # Polygon data provider
    │   ├── facets/                    # Polygon facets
    │   ├── polygon_ingestor.py        # Polygon ingestor
    │   └── polygon_registry.py        # Polygon registry
    │
    ├── bls/                           # Bureau of Labor Statistics
    │   ├── facets/
    │   ├── bls_ingestor.py
    │   └── bls_registry.py
    │
    └── chicago/                       # Chicago Data Portal
        ├── facets/
        ├── chicago_ingestor.py
        └── chicago_registry.py
```

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    DATA PIPELINE COMPONENT                      │
└─────────────────────────────────────────────────────────────────┘

┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│   Provider   │         │   Provider   │         │   Provider   │
│   Registry   │         │   Registry   │         │   Registry   │
│  (Polygon)   │         │    (BLS)     │         │  (Chicago)   │
└──────┬───────┘         └──────┬───────┘         └──────┬───────┘
       │                        │                        │
       │  Register facets       │                        │
       │                        │                        │
       ▼                        ▼                        ▼
┌──────────────────────────────────────────────────────────────────┐
│                      Central Registry                            │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐                 │
│  │   Facet    │  │   Facet    │  │   Facet    │                 │
│  │  Registry  │  │  Registry  │  │  Registry  │    ...          │
│  └────────────┘  └────────────┘  └────────────┘                 │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           │  Lookup facet
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                         Ingestor                                 │
│  ┌────────────┐    ┌────────────┐    ┌────────────┐             │
│  │  Facet     │ ─► │   HTTP     │ ─► │  Bronze    │             │
│  │  Executor  │    │  Client    │    │   Sink     │             │
│  └────────────┘    └────────────┘    └────────────┘             │
└──────────────────────────────────────────────────────────────────┘
       │                    │                   │
       │                    │                   │
       ▼                    ▼                   ▼
  ┌─────────┐        ┌──────────┐        ┌──────────┐
  │ Facet   │        │ External │        │  Bronze  │
  │ Defines │        │   API    │        │  Layer   │
  │ Endpoint│        │ (Polygon)│        │ (Parquet)│
  └─────────┘        └──────────┘        └──────────┘
```

## Component Responsibilities

### 1. Facets (What to Fetch)

**Purpose**: Define API endpoint specifications and data extraction logic

**Responsibilities**:
- Define endpoint URL patterns
- Specify query parameters
- Handle API-specific response formats
- Transform raw API responses to standard schema
- Define schema coercion rules

**Key Classes**:
- `BaseFacet`: Abstract base class for all facets
- `PolygonBaseFacet`: Base for Polygon-specific facets
- `PricesDailyFacet`: Daily stock price data
- `RefTickersFacet`: Reference data for tickers

**Example**:
```python
# File: datapipelines/providers/polygon/facets/prices_daily_facet.py

class PricesDailyFacet(PolygonBaseFacet):
    """Daily aggregated price bars."""

    endpoint = "v2/aggs/ticker/{ticker}/range/1/day/{from_date}/{to_date}"
    dataset = "prices_daily"

    # Define numeric coercion to prevent schema conflicts
    NUMERIC_COERCE = {
        "o": "double",    # open
        "h": "double",    # high
        "l": "double",    # low
        "c": "double",    # close
        "v": "long",      # volume
        "vw": "double",   # VWAP
        "t": "long"       # timestamp
    }

    # Final schema enforcement
    SPARK_CASTS = {
        "open": "double",
        "high": "double",
        "low": "double",
        "close": "double",
        "volume": "long",
        "vwap": "double",
        "timestamp": "long"
    }

    def postprocess(self, df):
        """Transform Polygon response to standard schema."""
        return df.select(
            F.col("o").alias("open"),
            F.col("h").alias("high"),
            F.col("l").alias("low"),
            F.col("c").alias("close"),
            F.col("v").alias("volume"),
            F.col("vw").alias("vwap"),
            F.col("t").alias("timestamp")
        )
```

### 2. Ingestors (How to Fetch)

**Purpose**: Orchestrate data fetching and storage

**Responsibilities**:
- Initialize HTTP client with rate limiting
- Execute facets with retry logic
- Handle pagination automatically
- Coordinate writes to Bronze layer
- Aggregate results across batches

**Key Classes**:
- `Ingestor`: Base interface
- `PolygonIngestor`: Polygon implementation
- `BLSIngestor`: BLS implementation
- `ChicagoIngestor`: Chicago Data Portal implementation

**Example**:
```python
# File: datapipelines/ingestors/polygon_ingestor.py:8-20

class PolygonIngestor(Ingestor):
    """Orchestrates Polygon data ingestion."""

    def __init__(self, polygon_cfg, storage_cfg, spark):
        super().__init__(storage_cfg=storage_cfg)
        self.registry = PolygonRegistry(polygon_cfg)
        self.http = HttpClient(
            self.registry.base_urls,
            self.registry.headers,
            self.registry.rate_limit,
            ApiKeyPool(polygon_cfg.get("credentials", {}).get("api_keys", []), 90)
        )
        self.sink = BronzeSink(storage_cfg)
        self.spark = spark
```

### 3. Providers (Provider-Specific Logic)

**Purpose**: Encapsulate all logic for a specific data provider

**Responsibilities**:
- Group related facets
- Configure provider-specific settings
- Implement provider registry
- Handle provider-specific authentication

**Key Providers**:
- **Polygon**: Stock market data (prices, tickers, exchanges, news)
- **BLS**: Economic indicators (unemployment, CPI)
- **Chicago**: City data (building permits, unemployment rates)

**Example**:
```python
# File: datapipelines/providers/polygon/polygon_registry.py

class PolygonRegistry:
    """Registry for all Polygon facets."""

    def __init__(self, config):
        self.config = config
        self.base_urls = config["endpoints"]
        self.headers = config.get("headers", {})
        self.rate_limit = config.get("rate_limit", 5)

    def register_facets(self):
        """Register all Polygon facets."""
        Registry.register("polygon", "prices_daily", PricesDailyFacet)
        Registry.register("polygon", "ref_tickers", RefTickersFacet)
        Registry.register("polygon", "news", NewsByDateFacet)
        # ... more facets
```

### 4. Bronze Sink (Storage)

**Purpose**: Write raw data to Bronze layer with partitioning

**Responsibilities**:
- Partition data by provider, dataset, and date
- Convert to Parquet format
- Add ingestion metadata
- Handle incremental writes

**Example**:
```python
# File: datapipelines/ingestors/bronze_sink.py:25-70

class BronzeSink:
    """Handles writes to Bronze layer."""

    def write(self, provider, dataset, data, partition_keys):
        """Write data to partitioned Bronze storage."""
        # Build output path
        bronze_root = Path(self.storage_cfg['roots']['bronze'])
        output_path = bronze_root / provider / dataset

        # Add partitions
        for key, value in partition_keys.items():
            output_path = output_path / f"{key}={value}"

        # Add metadata
        df = pd.DataFrame(data)
        df['ingestion_timestamp'] = datetime.now()
        df['source_provider'] = provider
        df['source_dataset'] = dataset

        # Write Parquet
        output_path.mkdir(parents=True, exist_ok=True)
        df.to_parquet(output_path / "data.parquet", compression='snappy')
```

## Data Flow

### Ingestion Sequence

```
1. INITIALIZATION
   ┌────────────────┐
   │ Pipeline Script│
   │ - Load config  │
   │ - Create ctx   │
   └────────┬───────┘
            │
            ▼
   ┌────────────────┐
   │ Create Ingestor│
   │ - Registry     │
   │ - HTTP client  │
   │ - Bronze sink  │
   └────────┬───────┘

2. FACET EXECUTION
            │
            │ For each facet
            ▼
   ┌────────────────────┐
   │ Facet              │
   │ - Build URL        │
   │ - Set parameters   │
   └────────┬───────────┘
            │
            ▼
   ┌────────────────────┐
   │ HTTP Client        │
   │ - Rate limit check │
   │ - Rotate API key   │
   │ - Make request     │
   └────────┬───────────┘
            │
            ▼
   ┌────────────────────┐
   │ Response Handler   │
   │ - Parse JSON       │
   │ - Extract data     │
   │ - Handle pagination│
   └────────┬───────────┘

3. DATA PROCESSING
            │
            ▼
   ┌────────────────────┐
   │ Schema Normalization│
   │ - Coerce types     │
   │ - Union batches    │
   │ - Apply transforms │
   └────────┬───────────┘

4. STORAGE
            │
            ▼
   ┌────────────────────┐
   │ Bronze Sink        │
   │ - Partition data   │
   │ - Add metadata     │
   │ - Write Parquet    │
   └────────────────────┘
```

### Code Flow Example

```python
# File: scripts/run_full_pipeline.py:60-120

def run_ingestion():
    # 1. Initialize context
    ctx = RepoContext.from_repo_root()

    # 2. Create ingestor
    ingestor = PolygonIngestor(
        polygon_cfg=ctx.polygon_cfg,
        storage_cfg=ctx.storage,
        spark=ctx.spark
    )

    # 3. Define date range
    start_date = "2024-01-01"
    end_date = "2024-12-31"

    # 4. Run ingestion for specific datasets
    ingestor.run_all(
        start_date=start_date,
        end_date=end_date,
        datasets=['prices_daily', 'ref_tickers'],
        max_tickers=100
    )
```

## Provider Registry System

### Registry Architecture

The registry system provides **dynamic facet discovery and execution**:

```
┌──────────────────────────────────────────────────────────┐
│                   Central Registry                       │
│                                                          │
│  provider_name → dataset_name → FacetClass              │
│                                                          │
│  Examples:                                               │
│    polygon → prices_daily → PricesDailyFacet            │
│    polygon → ref_tickers  → RefTickersFacet             │
│    bls     → unemployment → UnemploymentFacet           │
│    chicago → permits      → BuildingPermitsFacet        │
└──────────────────────────────────────────────────────────┘
```

### Registration Process

```python
# File: datapipelines/base/registry.py:20-60

class Registry:
    """Central facet registry."""

    _facets: Dict[Tuple[str, str], Type[Facet]] = {}

    @classmethod
    def register(cls, provider: str, dataset: str, facet_class: Type[Facet]):
        """Register a facet."""
        key = (provider, dataset)
        cls._facets[key] = facet_class

    @classmethod
    def get(cls, provider: str, dataset: str) -> Type[Facet]:
        """Retrieve a registered facet."""
        key = (provider, dataset)
        if key not in cls._facets:
            raise ValueError(f"No facet registered for {provider}.{dataset}")
        return cls._facets[key]

    @classmethod
    def list_facets(cls, provider: Optional[str] = None) -> List[str]:
        """List all registered facets."""
        if provider:
            return [ds for (p, ds) in cls._facets.keys() if p == provider]
        return [f"{p}.{ds}" for p, ds in cls._facets.keys()]
```

### Provider-Specific Registries

Each provider has its own registry that auto-registers facets:

```python
# File: datapipelines/providers/polygon/polygon_registry.py:30-80

class PolygonRegistry:
    """Polygon-specific facet registry."""

    def __init__(self, config):
        self.config = config
        self._register_all_facets()

    def _register_all_facets(self):
        """Auto-register all Polygon facets."""
        from .facets import (
            PricesDailyFacet,
            RefTickersFacet,
            NewsByDateFacet,
            ExchangeFacet
        )

        Registry.register("polygon", "prices_daily", PricesDailyFacet)
        Registry.register("polygon", "ref_tickers", RefTickersFacet)
        Registry.register("polygon", "news", NewsByDateFacet)
        Registry.register("polygon", "exchanges", ExchangeFacet)
```

## API Integration Patterns

### Pattern 1: Simple GET Request

For APIs with straightforward endpoints:

```python
class SimpleFacet(BaseFacet):
    """Simple GET request without pagination."""

    endpoint = "v1/data/{dataset}"

    def fetch(self, dataset: str):
        url = self.endpoint.format(dataset=dataset)
        response = self.http_client.get(url)
        return response.json()['data']
```

### Pattern 2: Paginated Results

For APIs that return paginated data:

```python
# File: datapipelines/ingestors/polygon_ingestor.py:30-88

def _fetch_calls(self, calls, response_key="results", max_pages=None):
    """Fetch with automatic pagination."""
    batches = []
    for call in calls:
        all_data = []
        next_cursor = None

        while True:
            # Build query with cursor
            query = call["params"].copy()
            if next_cursor:
                query["cursor"] = next_cursor

            # Make request
            response = self.http.request(endpoint, path, query)

            # Extract data
            data = response.get(response_key, [])
            all_data.extend(data)

            # Check for next page
            next_url = response.get("next_url")
            if not next_url:
                break

            # Extract cursor
            next_cursor = self._cursor_from_next(next_url)
            if not next_cursor or (max_pages and page_count >= max_pages):
                break

        batches.append(all_data)
    return batches
```

### Pattern 3: Batch Processing

For APIs that support batch requests:

```python
class BatchFacet(BaseFacet):
    """Batch request facet."""

    endpoint = "v1/batch/tickers"

    def fetch_batch(self, tickers: List[str]):
        """Fetch data for multiple tickers in one request."""
        # Split into batches of 100
        batch_size = 100
        all_results = []

        for i in range(0, len(tickers), batch_size):
            batch = tickers[i:i+batch_size]
            response = self.http_client.post(
                self.endpoint,
                json={'tickers': batch}
            )
            all_results.extend(response.json()['results'])

        return all_results
```

## Error Handling & Resilience

### Retry Logic

```python
# File: datapipelines/base/http_client.py:40-90

class HttpClient:
    """HTTP client with retry logic."""

    def request(self, url, params=None, max_retries=3):
        """Make HTTP request with exponential backoff."""
        for attempt in range(max_retries):
            try:
                # Rate limit check
                self._wait_for_rate_limit()

                # Make request
                response = requests.get(url, params=params, timeout=30)
                response.raise_for_status()

                return response.json()

            except requests.exceptions.Timeout:
                if attempt == max_retries - 1:
                    raise
                wait_time = 2 ** attempt  # Exponential backoff
                time.sleep(wait_time)

            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:  # Rate limit
                    retry_after = int(e.response.headers.get('Retry-After', 60))
                    time.sleep(retry_after)
                else:
                    raise
```

### Rate Limiting

```python
# File: datapipelines/base/http_client.py:100-130

def _wait_for_rate_limit(self):
    """Enforce rate limiting."""
    now = time.time()
    time_since_last = now - self.last_request_time

    min_interval = 1.0 / self.rate_limit  # seconds between requests

    if time_since_last < min_interval:
        sleep_time = min_interval - time_since_last
        time.sleep(sleep_time)

    self.last_request_time = time.time()
```

### API Key Rotation

```python
# File: datapipelines/base/key_pool.py:20-70

class ApiKeyPool:
    """Rotating pool of API keys."""

    def __init__(self, api_keys: List[str], rate_limit_per_key: int):
        self.keys = api_keys
        self.rate_limit = rate_limit_per_key
        self.current_index = 0
        self.request_counts = {key: 0 for key in api_keys}
        self.reset_time = time.time() + 60  # Reset every minute

    def get_key(self) -> str:
        """Get next available API key."""
        # Reset counts if minute elapsed
        if time.time() > self.reset_time:
            self.request_counts = {key: 0 for key in self.keys}
            self.reset_time = time.time() + 60

        # Find key under rate limit
        for _ in range(len(self.keys)):
            key = self.keys[self.current_index]
            if self.request_counts[key] < self.rate_limit:
                self.request_counts[key] += 1
                return key

            # Rotate to next key
            self.current_index = (self.current_index + 1) % len(self.keys)

        # All keys exhausted, wait
        time.sleep(1)
        return self.get_key()
```

## Usage Examples

### Example 1: Ingest Daily Prices

```python
from core.context import RepoContext
from datapipelines.providers.polygon import PolygonIngestor

# Initialize
ctx = RepoContext.from_repo_root()
ingestor = PolygonIngestor(ctx.polygon_cfg, ctx.storage, ctx.spark)

# Ingest last 30 days for specific tickers
ingestor.run_prices_daily(
    start_date="2024-11-01",
    end_date="2024-11-30",
    tickers=['AAPL', 'GOOGL', 'MSFT']
)
```

### Example 2: Ingest Reference Data

```python
# Ingest ticker reference data
ingestor.run_ref_tickers(
    max_tickers=100,
    active_only=True
)
```

### Example 3: Custom Facet

```python
from datapipelines.facets.base_facet import Facet

class CustomFacet(Facet):
    """Custom data facet."""

    NUMERIC_COERCE = {"price": "double", "volume": "long"}

    def postprocess(self, df):
        """Custom transformations."""
        return df.withColumn(
            "price_usd",
            F.col("price") * F.col("exchange_rate")
        )

# Register
Registry.register("custom", "dataset", CustomFacet)
```

---

## Related Documentation

- [Facets](./facets.md)
- [Ingestors](./ingestors.md)
- [Providers](./providers.md)
- [Bronze Storage](./bronze-storage.md)

---

**File**: `/home/user/de_Funk/docs/guide/3-architecture/components/data-pipeline/overview.md`
**Last Updated**: 2025-11-08
