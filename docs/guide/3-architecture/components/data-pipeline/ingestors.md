# Data Pipeline - Ingestors

## Overview

**Ingestors** orchestrate the data fetching process, coordinating between facets (what to fetch), HTTP clients (how to fetch), and Bronze storage (where to store). They implement the "how to fetch" logic while delegating endpoint definitions to facets.

## Architecture

### Ingestor Hierarchy

```
Ingestor (Abstract Interface)
    │
    ├─► PolygonIngestor
    ├─► BLSIngestor
    └─► ChicagoIngestor
```

## Base Ingestor

```python
# File: datapipelines/ingestors/base_ingestor.py:1-10

class Ingestor(ABC):
    """Abstract base for all ingestors."""

    def __init__(self, storage_cfg):
        self.storage_cfg = storage_cfg

    @abstractmethod
    def run_all(self, **kwargs):
        """Run ingestion for all datasets."""
        pass
```

## Polygon Ingestor Implementation

```python
# File: datapipelines/ingestors/polygon_ingestor.py:8-89

class PolygonIngestor(Ingestor):
    """Polygon data ingestion orchestrator."""

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

    def _fetch_calls(self, calls, response_key="results", max_pages=None, enable_pagination=True):
        """
        Fetch data with automatic pagination.

        Args:
            calls: Iterator of call specs with endpoint and parameters
            response_key: Key in response containing data (default: "results")
            max_pages: Maximum pages per call (default: unlimited)
            enable_pagination: Follow next_url for pagination (default: True)

        Returns:
            List of batches (one batch per call, all pages combined)
        """
        batches = []
        for call in calls:
            # Render endpoint with parameters
            ep, path, q = self.registry.render(call["ep_name"], **call["params"])

            # Collect all pages for this call
            all_data = []
            page_count = 0
            next_cursor = None

            while True:
                # Add cursor to query if paginating
                query = q.copy()
                if next_cursor:
                    query["cursor"] = next_cursor

                # Make HTTP request
                payload = self.http.request(ep.base, path, query, ep.method)

                # Extract data from response
                data = payload.get(response_key, []) or []
                if isinstance(data, list):
                    all_data.extend(data)
                else:
                    all_data.append(data)

                page_count += 1

                # Check pagination
                if not enable_pagination:
                    break

                next_url = payload.get("next_url")
                if not next_url:
                    break  # No more pages

                # Extract cursor from next_url
                next_cursor = self._cursor_from_next(next_url)
                if not next_cursor:
                    break  # Can't parse cursor

                # Check page limit
                if max_pages and page_count >= max_pages:
                    break

            batches.append(all_data)
        return batches
```

## Ingestion Workflows

### Daily Prices Ingestion

```python
def run_prices_daily(self, start_date, end_date, tickers=None, max_tickers=None):
    """
    Ingest daily price data.

    Args:
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        tickers: List of tickers (default: all active)
        max_tickers: Limit number of tickers
    """
    # Get ticker list
    if tickers is None:
        tickers = self._get_active_tickers(max_tickers)

    # Build call specs for each ticker
    calls = [
        {
            "ep_name": "prices_daily",
            "params": {
                "ticker": ticker,
                "from_date": start_date,
                "to_date": end_date
            }
        }
        for ticker in tickers
    ]

    # Fetch data (with pagination)
    batches = self._fetch_calls(calls, response_key="results", enable_pagination=True)

    # Get facet for normalization
    facet_class = Registry.get("polygon", "prices_daily")
    facet = facet_class(self.spark)

    # Normalize to DataFrame
    df = facet.normalize(batches)

    # Write to Bronze
    self.sink.write_partitioned(
        provider="polygon",
        dataset="prices_daily",
        df=df,
        partition_cols=["date"]
    )
```

### Reference Data Ingestion

```python
def run_ref_tickers(self, max_tickers=None, active_only=True):
    """
    Ingest ticker reference data.

    Args:
        max_tickers: Limit number of tickers
        active_only: Only fetch active tickers
    """
    # Build call spec
    calls = [{
        "ep_name": "ref_tickers",
        "params": {
            "active": "true" if active_only else None,
            "limit": max_tickers or 1000
        }
    }]

    # Fetch with pagination
    batches = self._fetch_calls(calls, response_key="results", enable_pagination=True)

    # Normalize
    facet = Registry.get("polygon", "ref_tickers")(self.spark)
    df = facet.normalize(batches)

    # Write to Bronze
    self.sink.write(
        provider="polygon",
        dataset="ref_tickers",
        df=df,
        partition_keys={"ingestion_date": datetime.now().strftime("%Y-%m-%d")}
    )
```

## Error Handling

### Retry with Backoff

```python
def _fetch_with_retry(self, call, max_retries=3):
    """Fetch with exponential backoff."""
    for attempt in range(max_retries):
        try:
            return self._fetch_calls([call])
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"Failed after {max_retries} attempts: {e}")
                raise

            wait_time = 2 ** attempt  # Exponential backoff
            logger.warning(f"Attempt {attempt + 1} failed, retrying in {wait_time}s...")
            time.sleep(wait_time)
```

### Partial Failure Handling

```python
def run_all(self, datasets, **kwargs):
    """Run ingestion with partial failure tolerance."""
    results = {}

    for dataset in datasets:
        try:
            logger.info(f"Ingesting {dataset}...")
            method = getattr(self, f"run_{dataset}")
            method(**kwargs)
            results[dataset] = "success"
        except Exception as e:
            logger.error(f"Failed to ingest {dataset}: {e}")
            results[dataset] = f"failed: {e}"

    # Report results
    successes = sum(1 for r in results.values() if r == "success")
    failures = len(results) - successes

    logger.info(f"Ingestion complete: {successes} succeeded, {failures} failed")
    return results
```

## Best Practices

### 1. Use Pagination

```python
# Good - handles large result sets
batches = self._fetch_calls(calls, enable_pagination=True)

# Bad - may miss data
batches = self._fetch_calls(calls, enable_pagination=False)
```

### 2. Limit Pages for Testing

```python
# Good for testing
batches = self._fetch_calls(calls, max_pages=1)

# Production
batches = self._fetch_calls(calls)  # unlimited
```

### 3. Log Progress

```python
def run_prices_daily(self, tickers, **kwargs):
    total = len(tickers)
    for i, ticker in enumerate(tickers, 1):
        logger.info(f"Processing {ticker} ({i}/{total})")
        # ... fetch and store
```

---

**File**: `/home/user/de_Funk/docs/guide/3-architecture/components/data-pipeline/ingestors.md`
