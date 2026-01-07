# Adding a New Data Provider - Checklist

**Purpose**: Step-by-step guide for adding a new data provider (e.g., Chicago, BLS, Yahoo Finance)

---

## Quick Reference: Files to Create/Modify

| Step | File | Action |
|------|------|--------|
| 1 | `datapipelines/providers/{provider}/` | Create directory structure |
| 2 | `configs/pipelines/{provider}_endpoints.json` | Define API endpoints |
| 3 | `configs/storage.json` | Add Bronze table definitions |
| 4 | `datapipelines/providers/{provider}/{provider}_registry.py` | Create endpoint registry |
| 5 | `datapipelines/providers/{provider}/provider.py` | Create provider class |
| 6 | `datapipelines/providers/{provider}/facets/*.py` | Create facet classes |
| 7 | `datapipelines/base/ingestor_engine.py` | Register in `create_engine()` |
| 8 | `scripts/ingest/run_{provider}_ingestion.py` | Create test script |

---

## Step 1: Create Directory Structure

```bash
mkdir -p datapipelines/providers/{provider}/facets
touch datapipelines/providers/{provider}/__init__.py
touch datapipelines/providers/{provider}/provider.py
touch datapipelines/providers/{provider}/{provider}_registry.py
touch datapipelines/providers/{provider}/facets/__init__.py
touch datapipelines/providers/{provider}/facets/{provider}_base_facet.py
```

**Example for Chicago:**
```
datapipelines/providers/chicago/
├── __init__.py
├── provider.py              # ChicagoProvider class
├── chicago_registry.py      # Endpoint rendering
└── facets/
    ├── __init__.py
    ├── chicago_base_facet.py     # Shared facet logic
    ├── unemployment_facet.py     # Endpoint-specific facet
    ├── building_permits_facet.py # Endpoint-specific facet
    └── business_licenses_facet.py
```

---

## Step 2: Define API Endpoints

**File**: `configs/pipelines/{provider}_endpoints.json`

```json
{
  "credentials": {
    "api_keys": [],
    "comment": "Set {PROVIDER}_API_KEYS environment variable"
  },
  "base_urls": {
    "core": "https://data.cityofchicago.org/resource"
  },
  "headers": {
    "Content-Type": "application/json"
  },
  "rate_limit_per_sec": 1.0,

  "endpoints": {
    "unemployment": {
      "base": "core",
      "method": "GET",
      "path_template": "/{dataset_id}.json",
      "required_params": [],
      "default_query": {
        "$limit": 50000
      },
      "response_key": null,
      "default_path_params": {
        "dataset_id": "iqnk-2tcu"
      },
      "comment": "Chicago unemployment statistics"
    },
    "building_permits": {
      "base": "core",
      "method": "GET",
      "path_template": "/{dataset_id}.json",
      "required_params": [],
      "default_query": {
        "$limit": 50000
      },
      "response_key": null,
      "default_path_params": {
        "dataset_id": "ydr8-5enu"
      },
      "comment": "Building permit data"
    }
  }
}
```

---

## Step 3: Add Storage Configuration

**File**: `configs/storage.json` - Add to "tables" section:

```json
{
  "tables": {
    "chicago_unemployment": {
      "root": "bronze",
      "rel": "chicago/unemployment",
      "partitions": ["year"],
      "write_strategy": "upsert",
      "key_columns": ["record_id", "period"],
      "comment": "Chicago unemployment data"
    },
    "chicago_building_permits": {
      "root": "bronze",
      "rel": "chicago/building_permits",
      "partitions": ["issue_year"],
      "write_strategy": "append",
      "key_columns": ["permit_id"],
      "date_column": "issue_date",
      "comment": "Chicago building permits"
    }
  }
}
```

**Key fields:**
- `partitions`: Columns to partition by (from storage.json ONLY - single source of truth)
- `write_strategy`: "upsert" for mutable data, "append" for immutable time-series
- `key_columns`: Unique identifier columns for upsert/dedup
- `date_column`: Required for append strategy

---

## Step 4: Create Registry Class

**File**: `datapipelines/providers/{provider}/{provider}_registry.py`

```python
"""
Registry for {Provider} API endpoints.
"""
from datapipelines.base.registry import BaseRegistry, Endpoint

class ChicagoRegistry(BaseRegistry):
    """Registry for Chicago Data Portal endpoints."""

    def __init__(self, config_path: str = None):
        if config_path is None:
            from utils.repo import get_repo_root
            config_path = get_repo_root() / "configs" / "pipelines" / "chicago_endpoints.json"
        super().__init__(config_path)

    def render(self, endpoint_name: str, **kwargs) -> Endpoint:
        """Render an endpoint with parameters."""
        ep_cfg = self.config["endpoints"][endpoint_name]
        base_url = self.config["base_urls"][ep_cfg["base"]]

        # Build path from template
        path_params = {**ep_cfg.get("default_path_params", {}), **kwargs.get("path_params", {})}
        path = ep_cfg["path_template"].format(**path_params)

        # Build query params
        query = {**ep_cfg.get("default_query", {}), **kwargs.get("query", {})}

        return Endpoint(
            name=endpoint_name,
            url=f"{base_url}{path}",
            method=ep_cfg["method"],
            params=query,
            headers=self.config.get("headers", {}),
            response_key=ep_cfg.get("response_key")
        )
```

---

## Step 5: Create Provider Class

**File**: `datapipelines/providers/{provider}/provider.py`

```python
"""
Chicago Data Portal provider implementation.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Any

from datapipelines.base.provider import BaseProvider, DataType, TickerData, ProviderConfig
from datapipelines.base.http_client import HttpClient
from datapipelines.base.key_pool import ApiKeyPool


# Define provider-specific data types (extend base DataType if needed)
class ChicagoDataType(Enum):
    UNEMPLOYMENT = "unemployment"
    BUILDING_PERMITS = "building_permits"
    BUSINESS_LICENSES = "business_licenses"


class ChicagoProvider(BaseProvider):
    """Provider for Chicago Data Portal API."""

    # Map data types to endpoint names
    ENDPOINT_MAP = {
        ChicagoDataType.UNEMPLOYMENT: "unemployment",
        ChicagoDataType.BUILDING_PERMITS: "building_permits",
        ChicagoDataType.BUSINESS_LICENSES: "business_licenses",
    }

    # Map data types to Bronze table names (must match storage.json)
    TABLE_NAMES = {
        ChicagoDataType.UNEMPLOYMENT: "chicago_unemployment",
        ChicagoDataType.BUILDING_PERMITS: "chicago_building_permits",
        ChicagoDataType.BUSINESS_LICENSES: "chicago_business_licenses",
    }

    # Key columns for upsert (must match storage.json)
    KEY_COLUMNS = {
        ChicagoDataType.UNEMPLOYMENT: ["record_id", "period"],
        ChicagoDataType.BUILDING_PERMITS: ["permit_id"],
        ChicagoDataType.BUSINESS_LICENSES: ["license_id"],
    }

    def __init__(self, config: ProviderConfig, spark):
        super().__init__(config, spark)
        self.registry = None  # Lazy load

    def _setup(self):
        """Initialize registry and HTTP client."""
        from .chicago_registry import ChicagoRegistry
        self.registry = ChicagoRegistry()

        # Get API keys from environment
        import os
        keys = os.environ.get("CHICAGO_API_KEYS", "").split(",")
        keys = [k.strip() for k in keys if k.strip()]

        self.key_pool = ApiKeyPool(keys, cooldown_seconds=60.0)
        self.http = HttpClient(
            rate_limit=self.config.rate_limit,
            max_retries=self.config.max_retries,
            retry_delay=self.config.retry_delay
        )

    def get_supported_data_types(self) -> List[DataType]:
        """Return list of supported data types."""
        return list(ChicagoDataType)

    def fetch_ticker_data(
        self,
        ticker: str = None,  # Not used for Chicago (city-level data)
        data_types: List = None,
        progress_callback=None,
        **kwargs
    ) -> TickerData:
        """Fetch data for specified data types."""
        if self.registry is None:
            self._setup()

        result = TickerData(ticker=ticker or "CHICAGO")

        for dt in (data_types or self.get_supported_data_types()):
            try:
                endpoint_name = self.ENDPOINT_MAP[dt]
                endpoint = self.registry.render(endpoint_name, **kwargs)

                # Add API key if available
                api_key = self.key_pool.next_key()
                if api_key:
                    endpoint.params["$$app_token"] = api_key

                # Fetch data
                response = self.http.request(
                    method=endpoint.method,
                    url=endpoint.url,
                    params=endpoint.params,
                    headers=endpoint.headers
                )

                # Store in result
                setattr(result, dt.value, response.json())

                if progress_callback:
                    progress_callback(ticker, dt, "success", None)

            except Exception as e:
                result.errors.append(f"{dt.value}: {str(e)}")
                if progress_callback:
                    progress_callback(ticker, dt, "error", str(e))

        return result

    def normalize_data(self, ticker_data: TickerData, data_type) -> Any:
        """Normalize raw data to Spark DataFrame using facets."""
        raw_data = getattr(ticker_data, data_type.value, None)
        if raw_data is None:
            return None

        # Import the appropriate facet
        if data_type == ChicagoDataType.UNEMPLOYMENT:
            from .facets.unemployment_facet import UnemploymentFacet
            facet = UnemploymentFacet(self.spark)
        elif data_type == ChicagoDataType.BUILDING_PERMITS:
            from .facets.building_permits_facet import BuildingPermitsFacet
            facet = BuildingPermitsFacet(self.spark)
        else:
            raise ValueError(f"Unknown data type: {data_type}")

        return facet.normalize([[raw_data]])

    def get_bronze_table_name(self, data_type) -> str:
        """Get the Bronze table name for a data type."""
        return self.TABLE_NAMES[data_type]

    def get_key_columns(self, data_type) -> List[str]:
        """Get key columns for upsert."""
        return self.KEY_COLUMNS[data_type]


def create_chicago_provider(api_cfg: Dict, spark) -> ChicagoProvider:
    """Factory function to create ChicagoProvider."""
    config = ProviderConfig(
        name="chicago",
        base_url=api_cfg["base_urls"]["core"],
        rate_limit=api_cfg.get("rate_limit_per_sec", 1.0),
        credentials_env_var="CHICAGO_API_KEYS",
        headers=api_cfg.get("headers", {}),
    )
    return ChicagoProvider(config, spark)
```

---

## Step 6: Create Facet Classes

**File**: `datapipelines/providers/{provider}/facets/{provider}_base_facet.py`

```python
"""
Base facet for Chicago Data Portal.
"""
from datapipelines.facets.base_facet import Facet

class ChicagoBaseFacet(Facet):
    """Base facet for Chicago data transformations."""

    def __init__(self, spark):
        super().__init__(spark)

    def normalize(self, raw_batches):
        """Override in subclass."""
        raise NotImplementedError
```

**File**: `datapipelines/providers/{provider}/facets/unemployment_facet.py`

```python
"""
Facet for Chicago unemployment data.
"""
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, IntegerType
from .chicago_base_facet import ChicagoBaseFacet

class UnemploymentFacet(ChicagoBaseFacet):
    """Normalize Chicago unemployment data."""

    OUTPUT_SCHEMA = StructType([
        StructField("record_id", StringType(), True),
        StructField("period", StringType(), True),
        StructField("year", IntegerType(), True),
        StructField("month", IntegerType(), True),
        StructField("unemployment_rate", DoubleType(), True),
        StructField("labor_force", IntegerType(), True),
        StructField("employed", IntegerType(), True),
        StructField("unemployed", IntegerType(), True),
    ])

    def normalize(self, raw_batches):
        """Transform raw API response to DataFrame."""
        rows = []
        for batch in raw_batches:
            for record in batch:
                rows.append({
                    "record_id": record.get("id"),
                    "period": record.get("period"),
                    "year": int(record.get("year")) if record.get("year") else None,
                    "month": int(record.get("month")) if record.get("month") else None,
                    "unemployment_rate": float(record.get("unemployment_rate")) if record.get("unemployment_rate") else None,
                    "labor_force": int(record.get("labor_force")) if record.get("labor_force") else None,
                    "employed": int(record.get("employed")) if record.get("employed") else None,
                    "unemployed": int(record.get("unemployed")) if record.get("unemployed") else None,
                })

        if not rows:
            return self.spark.createDataFrame([], schema=self.OUTPUT_SCHEMA)

        return self.spark.createDataFrame(rows, schema=self.OUTPUT_SCHEMA)
```

**File**: `datapipelines/providers/{provider}/facets/__init__.py`

```python
"""Chicago facets."""
from .unemployment_facet import UnemploymentFacet
from .building_permits_facet import BuildingPermitsFacet

__all__ = ["UnemploymentFacet", "BuildingPermitsFacet"]
```

---

## Step 7: Register with IngestorEngine

**File**: `datapipelines/base/ingestor_engine.py` - Update `create_engine()`:

```python
def create_engine(
    provider_name: str,
    api_cfg: Dict,
    storage_cfg: Dict,
    spark=None
) -> IngestorEngine:
    """Factory function to create an IngestorEngine for a provider."""
    if provider_name == "alpha_vantage":
        from datapipelines.providers.alpha_vantage.provider import create_alpha_vantage_provider
        provider = create_alpha_vantage_provider(api_cfg, spark)
    elif provider_name == "chicago":
        from datapipelines.providers.chicago.provider import create_chicago_provider
        provider = create_chicago_provider(api_cfg, spark)
    elif provider_name == "bls":
        from datapipelines.providers.bls.provider import create_bls_provider
        provider = create_bls_provider(api_cfg, spark)
    else:
        raise ValueError(f"Unknown provider: {provider_name}")

    return IngestorEngine(provider, storage_cfg)
```

---

## Step 8: Create Test Script

**File**: `scripts/ingest/run_chicago_ingestion.py`

```python
#!/usr/bin/env python
"""
Run Chicago Data Portal ingestion.

Usage:
    python -m scripts.ingest.run_chicago_ingestion
    python -m scripts.ingest.run_chicago_ingestion --endpoints unemployment building_permits
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

from config.logging import setup_logging, get_logger
from orchestration.common.spark_session import get_spark
from datapipelines.base.ingestor_engine import create_engine
from datapipelines.providers.chicago.provider import ChicagoDataType

logger = get_logger(__name__)


def main():
    setup_logging()

    parser = argparse.ArgumentParser(description="Run Chicago Data Portal ingestion")
    parser.add_argument("--endpoints", nargs="+", default=["unemployment"],
                       choices=["unemployment", "building_permits", "business_licenses"],
                       help="Endpoints to ingest")
    args = parser.parse_args()

    # Load configs
    with open(repo_root / "configs" / "pipelines" / "chicago_endpoints.json") as f:
        api_cfg = json.load(f)
    with open(repo_root / "configs" / "storage.json") as f:
        storage_cfg = json.load(f)

    # Initialize Spark
    spark = get_spark("ChicagoIngestion")

    # Create engine
    engine = create_engine("chicago", api_cfg, storage_cfg, spark)

    # Map endpoint names to data types
    data_type_map = {
        "unemployment": ChicagoDataType.UNEMPLOYMENT,
        "building_permits": ChicagoDataType.BUILDING_PERMITS,
        "business_licenses": ChicagoDataType.BUSINESS_LICENSES,
    }
    data_types = [data_type_map[ep] for ep in args.endpoints]

    # Run ingestion (no tickers needed for city-level data)
    results = engine.run(
        tickers=["CHICAGO"],  # Placeholder - Chicago is city-level data
        data_types=data_types,
        batch_size=1,
        auto_compact=True
    )

    print(f"\nIngestion complete!")
    print(f"Tables written: {list(results.tables_written.keys())}")
    print(f"Errors: {results.total_errors}")

    spark.stop()


if __name__ == "__main__":
    main()
```

---

## Checklist Summary

```
[ ] 1. Directory structure created
      datapipelines/providers/{provider}/
      datapipelines/providers/{provider}/facets/

[ ] 2. API config created
      configs/pipelines/{provider}_endpoints.json

[ ] 3. Storage config updated
      configs/storage.json - tables section

[ ] 4. Registry class created
      datapipelines/providers/{provider}/{provider}_registry.py

[ ] 5. Provider class created
      datapipelines/providers/{provider}/provider.py
      - Implements: fetch_ticker_data(), normalize_data()
      - Maps: ENDPOINT_MAP, TABLE_NAMES, KEY_COLUMNS

[ ] 6. Facets created (one per endpoint)
      datapipelines/providers/{provider}/facets/{endpoint}_facet.py
      - Define OUTPUT_SCHEMA
      - Implement normalize()

[ ] 7. Engine factory updated
      datapipelines/base/ingestor_engine.py - create_engine()

[ ] 8. Test script created
      scripts/ingest/run_{provider}_ingestion.py

[ ] 9. Environment variable set
      .env: {PROVIDER}_API_KEYS=your_key_here
```

---

## Key Principles

1. **Partition config in storage.json ONLY** - Never hardcode partitions in provider code
2. **Use get_spark()** - Always use `orchestration.common.spark_session.get_spark()` for Delta Lake support
3. **Write Delta format** - Use `sink.smart_write()` which reads config from storage.json
4. **One facet per endpoint** - Each endpoint should have its own facet class with OUTPUT_SCHEMA
5. **Test early** - Create test script immediately and verify basic data flow

---

## Reference Files

| Component | Reference Implementation |
|-----------|-------------------------|
| Provider | `datapipelines/providers/alpha_vantage/provider.py` |
| Registry | `datapipelines/providers/alpha_vantage/alpha_vantage_registry.py` |
| Facet | `datapipelines/providers/alpha_vantage/facets/securities_prices_facet.py` |
| Engine | `datapipelines/base/ingestor_engine.py` |
| BronzeSink | `datapipelines/ingestors/bronze_sink.py` |
| Storage Config | `configs/storage.json` |
| API Config | `configs/pipelines/alpha_vantage_endpoints.json` |
