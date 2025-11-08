# Data Pipeline - Providers

## Overview

**Providers** encapsulate all logic for a specific external data source. Each provider bundles its facets, ingestor, and registry into a cohesive module.

## Provider Structure

```
datapipelines/providers/{provider_name}/
├── __init__.py
├── {provider}_ingestor.py      # Provider-specific ingestor
├── {provider}_registry.py      # Facet registry
└── facets/                     # All facets for this provider
    ├── __init__.py
    ├── {provider}_base_facet.py # Base facet
    └── *.py                     # Specific facets
```

## Implemented Providers

### 1. Polygon (Financial Data)

```
datapipelines/providers/polygon/
├── polygon_ingestor.py
├── polygon_registry.py
└── facets/
    ├── polygon_base_facet.py
    ├── prices_daily_facet.py
    ├── prices_daily_grouped_facet.py
    ├── ref_ticker_facet.py
    ├── ref_all_tickers_facet.py
    ├── exchange_facet.py
    └── news_by_date_facet.py
```

**Data Types**:
- Daily stock prices (OHLCV)
- Intraday aggregates
- Ticker reference data
- Exchange information
- News articles

**Example Usage**:
```python
from datapipelines.providers.polygon import PolygonIngestor

ingestor = PolygonIngestor(polygon_cfg, storage_cfg, spark)
ingestor.run_prices_daily(start_date="2024-01-01", end_date="2024-12-31")
```

### 2. BLS (Economic Data)

```
datapipelines/providers/bls/
├── bls_ingestor.py
├── bls_registry.py
└── facets/
    ├── bls_base_facet.py
    ├── unemployment_facet.py
    └── cpi_facet.py
```

**Data Types**:
- Unemployment rates
- Consumer Price Index (CPI)
- Labor force statistics

**Example Usage**:
```python
from datapipelines.providers.bls import BLSIngestor

ingestor = BLSIngestor(bls_cfg, storage_cfg, spark)
ingestor.run_unemployment(start_year=2020, end_year=2024)
```

### 3. Chicago Data Portal

```
datapipelines/providers/chicago/
├── chicago_ingestor.py
├── chicago_registry.py
└── facets/
    ├── chicago_base_facet.py
    ├── building_permits_facet.py
    └── unemployment_rates_facet.py
```

**Data Types**:
- Building permits
- City unemployment rates
- Public datasets

**Example Usage**:
```python
from datapipelines/providers.chicago import ChicagoIngestor

ingestor = ChicagoIngestor(chicago_cfg, storage_cfg, spark)
ingestor.run_building_permits(start_date="2024-01-01")
```

## Adding a New Provider

### Step 1: Create Provider Directory

```bash
mkdir -p datapipelines/providers/fred/facets
touch datapipelines/providers/fred/__init__.py
touch datapipelines/providers/fred/facets/__init__.py
```

### Step 2: Implement Base Facet

```python
# datapipelines/providers/fred/facets/fred_base_facet.py

from datapipelines.facets.base_facet import Facet

class FredBaseFacet(Facet):
    """Base facet for FRED API."""

    base_url = "https://api.stlouisfed.org/fred"
    api_key_param = "api_key"

    def __init__(self, spark, api_key, **kwargs):
        super().__init__(spark, **kwargs)
        self.api_key = api_key

    def build_url(self, endpoint, **params):
        """Build URL with API key."""
        params[self.api_key_param] = self.api_key
        return f"{self.base_url}/{endpoint}", params
```

### Step 3: Implement Specific Facets

```python
# datapipelines/providers/fred/facets/gdp_facet.py

class GDPFacet(FredBaseFacet):
    """US GDP data from FRED."""

    endpoint = "series/observations"
    dataset = "gdp"
    series_id = "GDP"

    SPARK_CASTS = {
        "date": "date",
        "value": "double"
    }

    def postprocess(self, df):
        """Transform FRED response."""
        return df.select(
            F.to_date(F.col("date")).alias("date"),
            F.col("value").cast("double").alias("gdp")
        )
```

### Step 4: Create Registry

```python
# datapipelines/providers/fred/fred_registry.py

from datapipelines.base.registry import Registry
from .facets.gdp_facet import GDPFacet
from .facets.unemployment_facet import UnemploymentFacet

class FredRegistry:
    """Registry for FRED facets."""

    @classmethod
    def register_all(cls):
        """Register all FRED facets."""
        Registry.register("fred", "gdp", GDPFacet)
        Registry.register("fred", "unemployment", UnemploymentFacet)
```

### Step 5: Implement Ingestor

```python
# datapipelines/providers/fred/fred_ingestor.py

from datapipelines.ingestors.base_ingestor import Ingestor
from .fred_registry import FredRegistry

class FredIngestor(Ingestor):
    """FRED data ingestor."""

    def __init__(self, fred_cfg, storage_cfg, spark):
        super().__init__(storage_cfg)
        self.config = fred_cfg
        self.spark = spark
        FredRegistry.register_all()

    def run_gdp(self, start_date, end_date):
        """Ingest GDP data."""
        facet = Registry.get("fred", "gdp")(self.spark, api_key=self.config["api_key"])

        # Fetch data
        data = facet.fetch(start_date=start_date, end_date=end_date)

        # Normalize
        df = facet.normalize([data])

        # Write to Bronze
        self.sink.write(
            provider="fred",
            dataset="gdp",
            df=df
        )
```

### Step 6: Configure Provider

```json
// configs/fred_endpoints.json

{
  "base_url": "https://api.stlouisfed.org/fred",
  "credentials": {
    "api_key": "YOUR_API_KEY"
  },
  "rate_limit": 120,
  "datasets": {
    "gdp": {
      "series_id": "GDP",
      "frequency": "quarterly"
    },
    "unemployment": {
      "series_id": "UNRATE",
      "frequency": "monthly"
    }
  }
}
```

## Provider Configuration

### Polygon Configuration

```json
// configs/polygon_endpoints.json

{
  "endpoints": {
    "base": "https://api.polygon.io",
    "reference": "https://api.polygon.io"
  },
  "credentials": {
    "api_keys": ["key1", "key2", "key3"]
  },
  "rate_limit": 5,
  "default_params": {
    "adjusted": "true",
    "sort": "asc"
  }
}
```

### BLS Configuration

```json
// configs/bls_endpoints.json

{
  "base_url": "https://api.bls.gov/publicAPI/v2",
  "credentials": {
    "api_key": "YOUR_API_KEY"
  },
  "rate_limit": 25,
  "series": {
    "unemployment": "LNS14000000",
    "cpi": "CUUR0000SA0"
  }
}
```

## Best Practices

### 1. Provider Isolation

Each provider should be self-contained:
```python
# Good - provider encapsulates all logic
from datapipelines.providers.polygon import PolygonIngestor

# Bad - mixing provider internals
from datapipelines.providers.polygon.facets import PricesFacet
from datapipelines.providers.bls.facets import UnemploymentFacet
```

### 2. Configuration Management

Use provider-specific configs:
```python
# Good
polygon_cfg = load_config("configs/polygon_endpoints.json")
ingestor = PolygonIngestor(polygon_cfg, ...)

# Bad - hardcoded values
ingestor = PolygonIngestor(api_key="hardcoded", ...)
```

### 3. Error Handling

Implement provider-specific error handling:
```python
class PolygonIngestor(Ingestor):
    def handle_error(self, error):
        """Handle Polygon-specific errors."""
        if "rate limit" in str(error).lower():
            logger.warning("Rate limit hit, rotating API key")
            self.http.rotate_key()
        else:
            raise
```

---

**File**: `/home/user/de_Funk/docs/guide/3-architecture/components/data-pipeline/providers.md`
