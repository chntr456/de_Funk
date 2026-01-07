# Proposal 011: IngestorEngine Architecture - Complete Provider Guide

**Status**: Implemented (January 2026)
**Author**: de_Funk Team
**Updated**: January 2026
**Purpose**: Complete guide for adding new data providers to the ingestion pipeline

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Architecture Overview](#architecture-overview)
3. [Creating a New Provider](#creating-a-new-provider)
   - [Step 1: Directory Structure](#step-1-directory-structure)
   - [Step 2: API Endpoints Configuration](#step-2-api-endpoints-configuration)
   - [Step 3: Storage Configuration](#step-3-storage-configuration)
   - [Step 4: Registry Class](#step-4-registry-class)
   - [Step 5: Provider Implementation](#step-5-provider-implementation)
   - [Step 6: Create Facets](#step-6-create-facets)
   - [Step 7: Factory Function](#step-7-factory-function)
   - [Step 8: Register with Engine](#step-8-register-with-engine)
   - [Step 9: Test Script](#step-9-test-script)
4. [Adding Endpoints to Existing Provider](#adding-endpoints-to-existing-provider)
5. [Component Reference](#component-reference)
6. [Reference Implementation: Alpha Vantage](#reference-implementation-alpha-vantage)
7. [Common Patterns](#common-patterns)
8. [Troubleshooting](#troubleshooting)
9. [Session Summary](#session-summary)

---

## Executive Summary

This document is the **complete guide for adding new data providers** to de_Funk's ingestion pipeline.

The IngestorEngine is a **provider-agnostic orchestrator** that handles:
- Batch processing with configurable size
- Rate limiting and API key rotation
- Progress tracking and metrics
- Delta Lake writes with compaction

To add a new provider (e.g., BLS, Yahoo Finance, FRED), follow the steps in this document.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           PROVIDER ARCHITECTURE                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                        CONFIGURATION LAYER                                │   │
│  │  configs/pipelines/{provider}_endpoints.json  ← API endpoints            │   │
│  │  configs/storage.json                         ← Table definitions        │   │
│  │  configs/pipelines/run_config.json            ← Run profiles             │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                      │                                           │
│                                      ▼                                           │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                        PROVIDER LAYER                                     │   │
│  │  datapipelines/providers/{provider}/                                      │   │
│  │    ├── __init__.py                                                        │   │
│  │    ├── provider.py          ← BaseProvider implementation                 │   │
│  │    ├── {provider}_registry.py  ← Endpoint rendering                       │   │
│  │    └── facets/                                                            │   │
│  │        ├── __init__.py                                                    │   │
│  │        ├── {provider}_base_facet.py   ← Shared facet logic               │   │
│  │        ├── {endpoint1}_facet.py       ← Endpoint-specific facet          │   │
│  │        └── {endpoint2}_facet.py       ← Endpoint-specific facet          │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                      │                                           │
│                                      ▼                                           │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                        ENGINE LAYER                                       │   │
│  │  datapipelines/base/                                                      │   │
│  │    ├── provider.py           ← BaseProvider abstract class               │   │
│  │    ├── ingestor_engine.py    ← Generic orchestrator                      │   │
│  │    ├── http_client.py        ← Rate-limited HTTP                         │   │
│  │    ├── key_pool.py           ← API key rotation                          │   │
│  │    ├── registry.py           ← Base endpoint registry                    │   │
│  │    └── metrics.py            ← Performance tracking                      │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                      │                                           │
│                                      ▼                                           │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                        STORAGE LAYER                                      │   │
│  │  datapipelines/ingestors/bronze_sink.py  ← Delta Lake writes             │   │
│  │  storage/bronze/{provider}/              ← Bronze tables                  │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Key Components

| Component | File | Purpose |
|-----------|------|---------|
| **BaseProvider** | `datapipelines/base/provider.py` | Abstract interface all providers implement |
| **IngestorEngine** | `datapipelines/base/ingestor_engine.py` | Generic batch orchestrator |
| **HttpClient** | `datapipelines/base/http_client.py` | Rate-limited HTTP with retries |
| **ApiKeyPool** | `datapipelines/base/key_pool.py` | Rotating API keys with cooldown |
| **BaseRegistry** | `datapipelines/base/registry.py` | Endpoint definition and rendering |
| **BronzeSink** | `datapipelines/ingestors/bronze_sink.py` | Delta Lake writer |
| **DataType** | `datapipelines/base/provider.py` | Enum of data types (PRICES, REFERENCE, etc.) |
| **TickerData** | `datapipelines/base/provider.py` | Container for fetched data |

---

## Creating a New Provider

### Step 1: Directory Structure

Create the provider directory structure:

```bash
mkdir -p datapipelines/providers/{provider}/facets
touch datapipelines/providers/{provider}/__init__.py
touch datapipelines/providers/{provider}/provider.py
touch datapipelines/providers/{provider}/{provider}_registry.py
touch datapipelines/providers/{provider}/facets/__init__.py
touch datapipelines/providers/{provider}/facets/{provider}_base_facet.py
```

**Example for BLS (Bureau of Labor Statistics):**

```
datapipelines/providers/bls/
├── __init__.py
├── provider.py              # BLSProvider class
├── bls_registry.py          # Endpoint rendering
└── facets/
    ├── __init__.py
    ├── bls_base_facet.py    # Shared BLS facet logic
    ├── unemployment_facet.py # Unemployment data facet
    ├── cpi_facet.py         # CPI data facet
    └── employment_facet.py  # Employment data facet
```

---

### Step 2: API Endpoints Configuration

Create `configs/pipelines/{provider}_endpoints.json`:

```json
{
  "credentials": {
    "api_keys": [],
    "comment": "Set {PROVIDER}_API_KEYS environment variable"
  },
  "base_urls": {
    "core": "https://api.bls.gov/publicAPI/v2"
  },
  "headers": {
    "Content-Type": "application/json"
  },
  "rate_limit_per_sec": 0.5,
  "_rate_limit_comment": "BLS allows 500 requests/day, ~0.5/sec safely",

  "endpoints": {
    "series_data": {
      "base": "core",
      "method": "POST",
      "path_template": "/timeseries/data/",
      "required_params": ["seriesid"],
      "default_query": {},
      "response_key": "Results",
      "default_path_params": {},
      "comment": "Fetch time series data for one or more series IDs"
    },
    "unemployment_rate": {
      "base": "core",
      "method": "POST",
      "path_template": "/timeseries/data/",
      "required_params": [],
      "default_query": {
        "seriesid": ["LNS14000000"],
        "startyear": "2020",
        "endyear": "2024"
      },
      "response_key": "Results",
      "default_path_params": {},
      "comment": "National unemployment rate (seasonally adjusted)"
    },
    "cpi_all_urban": {
      "base": "core",
      "method": "POST",
      "path_template": "/timeseries/data/",
      "required_params": [],
      "default_query": {
        "seriesid": ["CUUR0000SA0"],
        "startyear": "2020",
        "endyear": "2024"
      },
      "response_key": "Results",
      "default_path_params": {},
      "comment": "Consumer Price Index - All Urban Consumers"
    }
  }
}
```

**Key Fields:**

| Field | Description |
|-------|-------------|
| `base_urls` | Named base URLs (e.g., "core", "v2") |
| `rate_limit_per_sec` | Max API calls per second |
| `endpoints.{name}.base` | Which base URL to use |
| `endpoints.{name}.method` | HTTP method (GET/POST) |
| `endpoints.{name}.path_template` | URL path with placeholders |
| `endpoints.{name}.required_params` | Required parameters |
| `endpoints.{name}.default_query` | Default query parameters |
| `endpoints.{name}.response_key` | Key to extract data from response |

---

### Step 3: Storage Configuration

Add tables to `configs/storage.json`:

```json
{
  "tables": {
    "bls_unemployment": {
      "root": "bronze",
      "rel": "bls/unemployment",
      "partitions": ["year"],
      "write_strategy": "append",
      "key_columns": ["series_id", "period", "year"],
      "date_column": "period_date",
      "comment": "BLS unemployment rate time series"
    },
    "bls_cpi": {
      "root": "bronze",
      "rel": "bls/cpi",
      "partitions": ["year"],
      "write_strategy": "append",
      "key_columns": ["series_id", "period", "year"],
      "date_column": "period_date",
      "comment": "BLS Consumer Price Index time series"
    },
    "bls_employment": {
      "root": "bronze",
      "rel": "bls/employment",
      "partitions": ["year"],
      "write_strategy": "append",
      "key_columns": ["series_id", "period", "year"],
      "date_column": "period_date",
      "comment": "BLS employment statistics"
    }
  }
}
```

**Write Strategy Rules:**

| Strategy | When to Use | Method Called |
|----------|-------------|---------------|
| `upsert` | Mutable reference data | `BronzeSink.upsert()` |
| `append` | Immutable time-series | `BronzeSink.append_immutable()` |
| `overwrite` | Full refresh | `BronzeSink.write(mode="overwrite")` |

---

### Step 4: Registry Class

Create `datapipelines/providers/{provider}/{provider}_registry.py`:

```python
"""
BLS Registry - Endpoint definitions and request rendering.

Handles BLS-specific request formatting:
- POST requests with JSON body
- API key in request body (registrationkey)
- Multiple series IDs per request
"""

from datapipelines.base.registry import BaseRegistry, Endpoint


class BLSRegistry(BaseRegistry):
    """
    Registry for BLS API endpoints.

    BLS uses POST requests with JSON body containing:
    - seriesid: List of series IDs to fetch
    - startyear/endyear: Date range
    - registrationkey: API key (optional but recommended)
    """

    def __init__(self, config):
        """
        Initialize BLS registry.

        Args:
            config: BLS configuration from bls_endpoints.json
        """
        super().__init__(config)

    def render(self, ep_name, **params):
        """
        Render endpoint with parameters.

        BLS-specific handling:
        - Builds JSON body for POST requests
        - Injects API key into body

        Args:
            ep_name: Endpoint name
            **params: Parameters (seriesid, startyear, endyear)

        Returns:
            Tuple of (Endpoint, path, query_params/body)
        """
        ep_config = self.endpoints.get(ep_name)
        if not ep_config:
            raise ValueError(f"Unknown endpoint: {ep_name}")

        ep = Endpoint(
            name=ep_name,
            base=ep_config["base"],
            method=ep_config["method"],
            path_template=ep_config.get("path_template", ""),
            required_params=ep_config.get("required_params", []),
            default_query=ep_config.get("default_query", {}),
            response_key=ep_config.get("response_key")
        )

        # Build path
        path = ep.path_template or ""

        # BLS uses JSON body for POST, not query params
        body = dict(ep.default_query)
        body.update(params)

        # API key placeholder (injected by HttpClient)
        body['registrationkey'] = '${API_KEY}'

        return ep, path, body
```

---

### Step 5: Provider Implementation

Create `datapipelines/providers/{provider}/provider.py`:

```python
"""
BLS Provider Implementation.

Implements BaseProvider for Bureau of Labor Statistics API.

Endpoints:
- unemployment_rate: National unemployment rate
- cpi_all_urban: Consumer Price Index
- employment: Employment statistics

Usage:
    from datapipelines.providers.bls.provider import create_bls_provider
    provider = create_bls_provider(bls_cfg, spark)
"""

from __future__ import annotations

import threading
from typing import List, Optional, Callable, Any, Dict
from enum import Enum

from datapipelines.base.provider import (
    BaseProvider, TickerData, ProviderConfig, FetchResult
)
from datapipelines.base.http_client import HttpClient
from datapipelines.base.key_pool import ApiKeyPool
from datapipelines.providers.bls.bls_registry import BLSRegistry
from config.logging import get_logger

logger = get_logger(__name__)


class BLSDataType(Enum):
    """BLS-specific data types (maps to series IDs)."""
    UNEMPLOYMENT = "unemployment"
    CPI = "cpi"
    EMPLOYMENT = "employment"


class BLSProvider(BaseProvider):
    """
    BLS implementation of BaseProvider.

    Handles all BLS API interactions including:
    - Unemployment rate (LNS14000000)
    - CPI (CUUR0000SA0)
    - Employment statistics
    """

    # Mapping from data type to endpoint name
    ENDPOINT_MAP = {
        BLSDataType.UNEMPLOYMENT: "unemployment_rate",
        BLSDataType.CPI: "cpi_all_urban",
        BLSDataType.EMPLOYMENT: "series_data",
    }

    # Series IDs for each data type
    SERIES_IDS = {
        BLSDataType.UNEMPLOYMENT: ["LNS14000000"],
        BLSDataType.CPI: ["CUUR0000SA0"],
        BLSDataType.EMPLOYMENT: ["CES0000000001"],
    }

    # Bronze table names
    TABLE_NAMES = {
        BLSDataType.UNEMPLOYMENT: "bls_unemployment",
        BLSDataType.CPI: "bls_cpi",
        BLSDataType.EMPLOYMENT: "bls_employment",
    }

    # Key columns for upsert
    KEY_COLUMNS = {
        BLSDataType.UNEMPLOYMENT: ["series_id", "period", "year"],
        BLSDataType.CPI: ["series_id", "period", "year"],
        BLSDataType.EMPLOYMENT: ["series_id", "period", "year"],
    }

    def __init__(self, config: ProviderConfig, spark=None, bls_cfg: Dict = None):
        self._bls_cfg = bls_cfg or {}
        super().__init__(config, spark)

    def _setup(self) -> None:
        """Setup HTTP client and API key pool."""
        self.registry = BLSRegistry(self._bls_cfg)

        credentials = self._bls_cfg.get("credentials", {})
        api_keys = credentials.get("api_keys", [])
        self.key_pool = ApiKeyPool(api_keys, cooldown_seconds=60.0)

        self.http = HttpClient(
            self.registry.base_urls,
            self.registry.headers,
            self.config.rate_limit,
            self.key_pool
        )

        self._http_lock = threading.Lock()

    def fetch_ticker_data(
        self,
        ticker: str,  # For BLS, this is a series_id
        data_types: List,
        progress_callback: Optional[Callable] = None,
        **kwargs
    ) -> TickerData:
        """
        Fetch data for a series ID.

        Note: BLS uses series_id instead of ticker, but we reuse
        the TickerData structure for compatibility with IngestorEngine.
        """
        result = TickerData(ticker=ticker)

        for data_type in data_types:
            fetch_result = self._fetch_single(ticker, data_type, **kwargs)

            if fetch_result.success:
                result.set_data(data_type, fetch_result.data)
            else:
                result.errors.append(f"{data_type.value}: {fetch_result.error}")

            if progress_callback:
                progress_callback(ticker, data_type, fetch_result.success, fetch_result.error)

        return result

    def _fetch_single(self, series_id: str, data_type, **kwargs) -> FetchResult:
        """Fetch a single series."""
        endpoint = self.ENDPOINT_MAP.get(data_type)
        if not endpoint:
            return FetchResult(
                ticker=series_id,
                data_type=data_type,
                success=False,
                error=f"Unsupported data type: {data_type}"
            )

        try:
            params = {
                "seriesid": [series_id],
                "startyear": kwargs.get("start_year", "2020"),
                "endyear": kwargs.get("end_year", "2024"),
            }

            ep, path, body = self.registry.render(endpoint, **params)

            with self._http_lock:
                # BLS uses POST with JSON body
                payload = self.http.request(ep.base, path, body, ep.method)

            # Extract data using response key
            if ep.response_key:
                data = payload.get(ep.response_key, payload)
            else:
                data = payload

            return FetchResult(
                ticker=series_id,
                data_type=data_type,
                success=True,
                data=data
            )

        except Exception as e:
            return FetchResult(
                ticker=series_id,
                data_type=data_type,
                success=False,
                error=str(e)[:50]
            )

    def normalize_data(self, ticker_data: TickerData, data_type) -> Optional[Any]:
        """Normalize BLS response to Spark DataFrame."""
        from datapipelines.providers.bls.facets import UnemploymentFacet

        series_id = ticker_data.ticker

        try:
            if data_type == BLSDataType.UNEMPLOYMENT:
                raw = ticker_data.reference  # Reuse existing field
                if raw:
                    facet = UnemploymentFacet(self.spark, series_id=series_id)
                    return facet.normalize(raw)

            # Add more data types as needed...

        except Exception as e:
            logger.warning(f"Failed to normalize {data_type} for {series_id}: {e}")

        return None

    def get_bronze_table_name(self, data_type) -> str:
        return self.TABLE_NAMES.get(data_type, f"bls_{data_type.value}")

    def get_key_columns(self, data_type) -> List[str]:
        return self.KEY_COLUMNS.get(data_type, ["series_id", "period", "year"])


def create_bls_provider(bls_cfg: Dict, spark=None) -> BLSProvider:
    """Factory function to create BLSProvider."""
    config = ProviderConfig(
        name="bls",
        base_url="https://api.bls.gov/publicAPI/v2",
        rate_limit=bls_cfg.get("rate_limit_per_sec", 0.5),
        batch_size=10,
        credentials_env_var="BLS_API_KEYS",
        supported_data_types=[]
    )
    return BLSProvider(config=config, spark=spark, bls_cfg=bls_cfg)
```

---

### Step 6: Create Facets

Create a facet for each endpoint. Example: `datapipelines/providers/bls/facets/unemployment_facet.py`:

```python
"""
UnemploymentFacet - Transforms BLS unemployment data to Bronze schema.

BLS Response Format:
{
  "Results": {
    "series": [{
      "seriesID": "LNS14000000",
      "data": [
        {"year": "2024", "period": "M01", "periodName": "January", "value": "3.7"},
        ...
      ]
    }]
  }
}

Bronze Schema:
- series_id: string
- year: int
- period: string (M01-M12)
- period_name: string
- value: double
- period_date: date
- ingestion_timestamp: timestamp
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from pyspark.sql import SparkSession
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType, DoubleType, DateType, TimestampType
)
from datapipelines.providers.bls.facets.bls_base_facet import BLSBaseFacet


class UnemploymentFacet(BLSBaseFacet):
    """Transform BLS unemployment data to Bronze schema."""

    name = "bls_unemployment"

    OUTPUT_SCHEMA = StructType([
        StructField("series_id", StringType(), False),
        StructField("year", IntegerType(), True),
        StructField("period", StringType(), True),
        StructField("period_name", StringType(), True),
        StructField("value", DoubleType(), True),
        StructField("period_date", DateType(), True),
        StructField("ingestion_timestamp", TimestampType(), True),
    ])

    def __init__(self, spark: SparkSession, series_id: str):
        super().__init__(spark)
        self.series_id = series_id

    def normalize(self, raw_data: dict) -> Optional:
        """
        Normalize BLS response to Spark DataFrame.

        Args:
            raw_data: BLS API response (already extracted to Results level)

        Returns:
            Spark DataFrame with normalized data
        """
        if not raw_data:
            return None

        series_list = raw_data.get("series", [])
        if not series_list:
            return None

        series = series_list[0]
        data_points = series.get("data", [])

        if not data_points:
            return None

        now = datetime.now()
        rows = []

        for point in data_points:
            year = int(point.get("year", 0))
            period = point.get("period", "")

            # Parse period to date (assume 1st of month)
            period_date = None
            if period.startswith("M"):
                month = int(period[1:])
                period_date = datetime(year, month, 1).date()

            rows.append({
                "series_id": self.series_id,
                "year": year,
                "period": period,
                "period_name": point.get("periodName"),
                "value": float(point.get("value", 0)),
                "period_date": period_date,
                "ingestion_timestamp": now,
            })

        return self.spark.createDataFrame(rows, schema=self.OUTPUT_SCHEMA)

    def validate(self, df):
        """Validate the DataFrame."""
        from pyspark.sql.functions import col

        null_series = df.filter(col("series_id").isNull()).count()
        if null_series > 0:
            raise ValueError(f"Found {null_series} rows with null series_id")

        return df
```

**Base Facet** (`datapipelines/providers/bls/facets/bls_base_facet.py`):

```python
"""Base facet for BLS data transformations."""

from datapipelines.facets.base_facet import Facet


class BLSBaseFacet(Facet):
    """Base facet for BLS providers."""

    def __init__(self, spark):
        super().__init__(spark)

    @staticmethod
    def parse_period_to_date(year: int, period: str):
        """Convert BLS period (M01-M12) to date."""
        from datetime import datetime

        if not period or not period.startswith("M"):
            return None

        try:
            month = int(period[1:])
            return datetime(year, month, 1).date()
        except (ValueError, IndexError):
            return None
```

**Export facets** in `datapipelines/providers/bls/facets/__init__.py`:

```python
from datapipelines.providers.bls.facets.unemployment_facet import UnemploymentFacet

__all__ = ["UnemploymentFacet"]
```

---

### Step 7: Factory Function

Already included in provider.py (Step 5):

```python
def create_bls_provider(bls_cfg: Dict, spark=None) -> BLSProvider:
    """Factory function to create BLSProvider."""
    config = ProviderConfig(...)
    return BLSProvider(config=config, spark=spark, bls_cfg=bls_cfg)
```

---

### Step 8: Register with Engine

Update `datapipelines/base/ingestor_engine.py`:

```python
def create_engine(
    provider_name: str,
    api_cfg: Dict,
    storage_cfg: Dict,
    spark=None
) -> IngestorEngine:
    """Factory to create IngestorEngine for any provider."""

    if provider_name == "alpha_vantage":
        from datapipelines.providers.alpha_vantage.provider import create_alpha_vantage_provider
        provider = create_alpha_vantage_provider(api_cfg, spark)

    elif provider_name == "bls":
        from datapipelines.providers.bls.provider import create_bls_provider
        provider = create_bls_provider(api_cfg, spark)

    # Add more providers here...

    else:
        raise ValueError(f"Unknown provider: {provider_name}")

    return IngestorEngine(provider, storage_cfg)
```

---

### Step 9: Test Script

Create test script or add to existing pipeline:

```python
# Test BLS provider
from datapipelines.providers.bls.provider import create_bls_provider, BLSDataType
from datapipelines.base.ingestor_engine import IngestorEngine
from orchestration.common.spark_session import get_spark
import json

# Load configs
with open('configs/pipelines/bls_endpoints.json') as f:
    bls_cfg = json.load(f)
with open('configs/storage.json') as f:
    storage_cfg = json.load(f)

# Setup
spark = get_spark(app_name='test_bls')
provider = create_bls_provider(bls_cfg, spark=spark)
engine = IngestorEngine(provider, storage_cfg)

# Run ingestion
results = engine.run(
    tickers=['LNS14000000'],  # Series IDs as 'tickers'
    data_types=[BLSDataType.UNEMPLOYMENT],
    batch_size=5
)

print(f'Completed: {results.completed_tickers}')
print(f'Errors: {results.total_errors}')
spark.stop()
```

---

## Adding Endpoints to Existing Provider

For adding a new endpoint to an existing provider (e.g., adding ETF_PROFILE to Alpha Vantage):

### Checklist

```
[ ] 1. configs/pipelines/{provider}_endpoints.json
      - Add endpoint definition with function, params, response_key

[ ] 2. configs/storage.json
      - Add table with rel path, partitions, key_columns, write_strategy

[ ] 3. datapipelines/base/provider.py
      - Add DataType enum value (if new type)
      - Add field to TickerData dataclass
      - Update set_data() attr_map

[ ] 4. datapipelines/providers/{provider}/facets/{name}_facet.py
      - Create facet class with OUTPUT_SCHEMA
      - Implement normalize() method
      - Implement validate() method

[ ] 5. datapipelines/providers/{provider}/facets/__init__.py
      - Export the new facet

[ ] 6. datapipelines/providers/{provider}/provider.py
      - Add to ENDPOINT_MAP
      - Add to RESPONSE_KEYS
      - Add to TABLE_NAMES
      - Add to KEY_COLUMNS
      - Add handler in normalize_data()
      - Add to supported_data_types in factory function

[ ] 7. Test the endpoint
```

---

## Component Reference

### DataType Enum

Defined in `datapipelines/base/provider.py`:

```python
class DataType(Enum):
    REFERENCE = "reference"
    PRICES = "prices"
    INCOME_STATEMENT = "income"
    BALANCE_SHEET = "balance"
    CASH_FLOW = "cashflow"
    EARNINGS = "earnings"
    OPTIONS = "options"
    ETF_PROFILE = "etf_profile"
```

### TickerData Dataclass

```python
@dataclass
class TickerData:
    ticker: str
    reference: Optional[Any] = None
    prices: Optional[Any] = None
    income_statement: Optional[Any] = None
    balance_sheet: Optional[Any] = None
    cash_flow: Optional[Any] = None
    earnings: Optional[Any] = None
    options: Optional[Any] = None
    errors: List[str] = field(default_factory=list)
```

### ProviderConfig Dataclass

```python
@dataclass
class ProviderConfig:
    name: str                    # Provider name
    base_url: str                # Primary base URL
    rate_limit: float = 1.0      # Calls per second
    max_retries: int = 3
    retry_delay: float = 2.0
    batch_size: int = 20
    credentials_env_var: str = ""
    headers: Dict[str, str] = field(default_factory=dict)
    supported_data_types: List[DataType] = field(default_factory=list)
```

---

## Reference Implementation: Alpha Vantage

See these files for the complete reference implementation:

| File | Lines | Purpose |
|------|-------|---------|
| `datapipelines/providers/alpha_vantage/provider.py` | 612 | Full provider implementation |
| `datapipelines/providers/alpha_vantage/alpha_vantage_registry.py` | 86 | Endpoint rendering |
| `datapipelines/providers/alpha_vantage/facets/alpha_vantage_base_facet.py` | 207 | Base facet |
| `datapipelines/providers/alpha_vantage/facets/securities_prices_facet.py` | 425 | Prices facet |

### Currently Implemented Endpoints

| Provider | Endpoint | DataType | Bronze Table | Status |
|----------|----------|----------|--------------|--------|
| Alpha Vantage | LISTING_STATUS | seed | ticker_seed | ✅ |
| Alpha Vantage | COMPANY_OVERVIEW | REFERENCE | securities_reference | ✅ |
| Alpha Vantage | TIME_SERIES_DAILY_ADJUSTED | PRICES | securities_prices_daily | ✅ |
| Alpha Vantage | INCOME_STATEMENT | INCOME_STATEMENT | income_statements | ✅ |
| Alpha Vantage | BALANCE_SHEET | BALANCE_SHEET | balance_sheets | ✅ |
| Alpha Vantage | CASH_FLOW | CASH_FLOW | cash_flows | ✅ |
| Alpha Vantage | EARNINGS | EARNINGS | earnings | ✅ |
| Alpha Vantage | HISTORICAL_OPTIONS | OPTIONS | historical_options | Partial |
| BLS | series_data | custom | bls_* | Skeleton |
| Chicago | various | custom | chicago_* | Skeleton |

---

## Common Patterns

### Rate Limiting

HttpClient handles rate limiting automatically:

```python
self.http = HttpClient(
    self.registry.base_urls,
    self.registry.headers,
    self.config.rate_limit,  # Calls per second
    self.key_pool
)
```

### API Key Rotation

Keys rotate with cooldown:

```python
self.key_pool = ApiKeyPool(api_keys, cooldown_seconds=60.0)
```

### Batch Processing

```python
results = engine.run(
    tickers=['AAPL', 'MSFT', ...],
    data_types=[DataType.PRICES],
    batch_size=20,
    auto_compact=True  # OPTIMIZE after all batches
)
```

### Compaction Strategy

Delta OPTIMIZE runs ONCE after ALL batches:

```python
if auto_compact and results.tables_written:
    self._compact_tables(results.tables_written, silent)
```

For production, set `auto_compact=False` and schedule compaction separately.

---

## Troubleshooting

### API Rate Limits
```
Error: API limit reached
```
- Check `rate_limit_per_sec` in endpoints config
- Add more API keys to pool
- Reduce batch_size

### Missing Data
```
Error: No data returned
```
- Verify API response format in facet.normalize()
- Check response_key in endpoint config
- Test endpoint manually with curl

### Schema Mismatch
```
Error: Cannot merge schema
```
- Facet output doesn't match existing table
- Delete Bronze table and re-ingest
- Or update facet to match existing schema

### Partition Errors
```
Error: Partition columns don't match
```
- Partitions defined in storage.json only
- Delete existing table if partitions changed
- Never hardcode partitions in provider

---

## Session Summary (January 2026)

### What Was Implemented

1. **IngestorEngine** - Provider-agnostic batch orchestrator
2. **BaseProvider** - Abstract interface for all providers
3. **AlphaVantageProvider** - Complete reference implementation
4. **7+ Facets** - Reference, prices, income, balance, cash flow, earnings, company
5. **Compaction** - Delta OPTIMIZE after all batches
6. **Configuration** - Centralized in storage.json and endpoint configs

### Provider Creation Checklist

```
[ ] 1. Create directory: datapipelines/providers/{provider}/
[ ] 2. Create configs/pipelines/{provider}_endpoints.json
[ ] 3. Add tables to configs/storage.json
[ ] 4. Create {provider}_registry.py (extend BaseRegistry)
[ ] 5. Create provider.py (extend BaseProvider)
[ ] 6. Create facets for each endpoint
[ ] 7. Export facets in facets/__init__.py
[ ] 8. Add factory function create_{provider}_provider()
[ ] 9. Register in ingestor_engine.py create_engine()
[ ] 10. Create test script and verify
```

### Key Files Modified

| File | Purpose |
|------|---------|
| `datapipelines/base/provider.py` | BaseProvider, DataType, TickerData |
| `datapipelines/base/ingestor_engine.py` | Generic orchestrator |
| `datapipelines/base/http_client.py` | Rate-limited HTTP |
| `datapipelines/base/key_pool.py` | API key rotation |
| `datapipelines/base/registry.py` | Base endpoint registry |
| `datapipelines/ingestors/bronze_sink.py` | Delta Lake writes |
| `configs/storage.json` | Table definitions |
| `configs/pipelines/*.json` | API endpoints |

---

**For questions, check logs at `logs/de_funk.log`**
