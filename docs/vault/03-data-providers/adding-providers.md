# Adding New Providers

**How to integrate new data sources into de_Funk**

---

## Overview

Adding a new data provider involves:

1. Create provider directory structure
2. Implement registry (endpoint configuration)
3. Implement facets (data transformation)
4. Implement ingestor (orchestration)
5. Configure endpoints (JSON)
6. Add API keys (environment)
7. Create Bronze table mappings

---

## Step 1: Create Directory Structure

```bash
mkdir -p datapipelines/providers/new_provider/facets
touch datapipelines/providers/new_provider/__init__.py
touch datapipelines/providers/new_provider/new_provider_registry.py
touch datapipelines/providers/new_provider/new_provider_ingestor.py
touch datapipelines/providers/new_provider/facets/__init__.py
touch datapipelines/providers/new_provider/facets/base_facet.py
```

**Structure**:
```
datapipelines/providers/new_provider/
├── __init__.py
├── new_provider_registry.py    # Endpoint configuration
├── new_provider_ingestor.py    # Orchestration
└── facets/
    ├── __init__.py
    ├── base_facet.py           # Base class for provider facets
    └── specific_facet.py       # Specific data transformation
```

---

## Step 2: Implement Registry

The registry loads endpoint configuration and renders API calls.

```python
# datapipelines/providers/new_provider/new_provider_registry.py

from datapipelines.base.registry import BaseRegistry
from pathlib import Path

class NewProviderRegistry(BaseRegistry):
    """Registry for New Provider API endpoints."""

    def __init__(self, config_path: Path = None):
        if config_path is None:
            config_path = Path("configs/new_provider_endpoints.json")
        super().__init__(config_path)

    def render(self, endpoint_name: str, **params):
        """
        Render an endpoint with parameters.

        Returns: (endpoint_config, path, query_params)
        """
        endpoint = self.endpoints.get(endpoint_name)
        if not endpoint:
            raise ValueError(f"Unknown endpoint: {endpoint_name}")

        # Build path from template
        path = endpoint["path_template"].format(**params)

        # Merge default query params with provided params
        query = {**endpoint.get("default_query", {}), **params}

        return endpoint, path, query
```

---

## Step 3: Implement Facet

Facets transform raw API responses into normalized DataFrames.

```python
# datapipelines/providers/new_provider/facets/specific_facet.py

from datapipelines.base.facet import BaseFacet
from pyspark.sql import DataFrame
from pyspark.sql.types import StructType, StructField, StringType, DoubleType
from typing import List, Dict, Iterator

class SpecificFacet(BaseFacet):
    """Transform New Provider API responses."""

    def __init__(self, spark, **params):
        super().__init__(spark)
        self.params = params

    @property
    def output_schema(self) -> StructType:
        """Define output DataFrame schema."""
        return StructType([
            StructField("id", StringType(), False),
            StructField("name", StringType(), True),
            StructField("value", DoubleType(), True),
            StructField("date", StringType(), True),
        ])

    def calls(self) -> Iterator[Dict]:
        """Generate API call specifications."""
        yield {
            "endpoint": "data_endpoint",
            "params": self.params
        }

    def normalize(self, raw_batches: List[Dict]) -> DataFrame:
        """Transform raw API responses to DataFrame."""
        records = []

        for batch in raw_batches:
            # Extract data from API response structure
            data_list = batch.get("data", [])

            for item in data_list:
                records.append({
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "value": float(item.get("value", 0)),
                    "date": item.get("date"),
                })

        return self.spark.createDataFrame(records, schema=self.output_schema)

    def postprocess(self, df: DataFrame) -> DataFrame:
        """Apply post-processing transformations."""
        # Add derived columns, clean data, etc.
        return df

    def validate(self, df: DataFrame) -> DataFrame:
        """Validate DataFrame schema and data quality."""
        # Type checking, null handling, etc.
        return df
```

---

## Step 4: Implement Ingestor

The ingestor orchestrates API calls, rate limiting, and data writing.

```python
# datapipelines/providers/new_provider/new_provider_ingestor.py

from datapipelines.base.ingestor import BaseIngestor
from datapipelines.base.http_client import HttpClient
from .new_provider_registry import NewProviderRegistry
import time

class NewProviderIngestor(BaseIngestor):
    """Orchestrate data ingestion from New Provider."""

    def __init__(self, config, storage_cfg, spark):
        super().__init__(spark)
        self.config = config
        self.storage_cfg = storage_cfg
        self.registry = NewProviderRegistry()
        self.client = HttpClient(
            api_keys=config.get("api_keys", []),
            rate_limit=config.get("rate_limit", {"calls_per_second": 1.0})
        )

    def _fetch_calls(self, calls, response_key=None):
        """Execute API calls with rate limiting."""
        results = []

        for call in calls:
            endpoint, path, query = self.registry.render(
                call["endpoint"],
                **call.get("params", {})
            )

            # Make HTTP request
            url = f"{self.registry.base_url}{path}"
            response = self.client.get(url, params=query)

            # Extract data from response
            data = response.json()
            if response_key:
                for key in response_key.split("."):
                    data = data.get(key, {})

            results.append(data)

            # Rate limiting
            time.sleep(1.0 / self.config.get("rate_limit", {}).get("calls_per_second", 1.0))

        return results

    def ingest_data(self, **params):
        """Run data ingestion pipeline."""
        from .facets.specific_facet import SpecificFacet

        # Initialize facet
        facet = SpecificFacet(self.spark, **params)

        # Generate and execute API calls
        calls = list(facet.calls())
        raw_data = self._fetch_calls(calls)

        # Transform data
        df = facet.normalize(raw_data)
        df = facet.postprocess(df)
        df = facet.validate(df)

        # Write to Bronze (partitions come from storage.json - single source of truth)
        from datapipelines.ingestors.bronze_sink import BronzeSink
        sink = BronzeSink(self.storage_cfg)
        sink.smart_write(df, "new_provider_data")  # Reads partitions from storage.json

        return df
```

---

## Step 5: Configure Endpoints

Create JSON configuration file:

```json
// configs/new_provider_endpoints.json
{
  "base_urls": {
    "core": "https://api.newprovider.com/v1"
  },
  "rate_limit": {
    "calls_per_second": 1.0
  },
  "auth": {
    "type": "header",
    "header_name": "Authorization",
    "prefix": "Bearer "
  },
  "endpoints": {
    "data_endpoint": {
      "base": "core",
      "method": "GET",
      "path_template": "/data/{resource_id}",
      "required_params": ["resource_id"],
      "default_query": {
        "format": "json"
      },
      "response_key": "data"
    },
    "list_endpoint": {
      "base": "core",
      "method": "GET",
      "path_template": "/list",
      "default_query": {
        "limit": 100
      }
    }
  }
}
```

---

## Step 6: Add API Keys

Add to `.env`:

```bash
# New Provider API key
NEW_PROVIDER_API_KEYS=your_api_key_here
```

---

## Step 7: Update Storage Config

Add Bronze table mappings to `configs/storage.json`:

```json
{
  "bronze": {
    "new_provider_data": {
      "path": "storage/bronze/new_provider/data/",
      "partitions": ["date"]
    }
  }
}
```

---

## Step 8: Document Provider

Create documentation in `docs/vault/03-data-providers/new-provider/`:

```
new-provider/
├── overview.md
├── terms-of-use.md
├── api-reference.md
├── facets.md
└── bronze-tables.md
```

---

## Testing

### Unit Test

```python
# tests/unit/test_new_provider_facet.py

def test_normalize():
    """Test facet normalization."""
    facet = SpecificFacet(spark)

    raw_data = [{"data": [{"id": "1", "name": "Test", "value": "100"}]}]
    df = facet.normalize(raw_data)

    assert df.count() == 1
    assert df.columns == ["id", "name", "value", "date"]
```

### Integration Test

```python
# tests/integration/test_new_provider_ingestion.py

def test_ingestion():
    """Test full ingestion pipeline."""
    ingestor = NewProviderIngestor(config, storage, spark)
    df = ingestor.ingest_data(resource_id="test")

    assert df.count() > 0
```

---

## Checklist

- [ ] Directory structure created
- [ ] Registry implemented
- [ ] Facets implemented
- [ ] Ingestor implemented
- [ ] Endpoint config created
- [ ] API keys added to .env
- [ ] Storage config updated
- [ ] Documentation created
- [ ] Terms of use documented
- [ ] Unit tests written
- [ ] Integration tests written

---

## Related Documentation

- [Provider Overview](README.md)
- [Facet System](../06-pipelines/facet-system.md)
- [Bronze Layer](../06-pipelines/bronze-layer.md)
