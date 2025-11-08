# de_Funk Data Flow Architecture

## Table of Contents
1. [Overview](#overview)
2. [Bronze Layer Ingestion Flow](#bronze-layer-ingestion-flow)
3. [Silver Layer Transformation Flow](#silver-layer-transformation-flow)
4. [Query Execution Flow](#query-execution-flow)
5. [Filter Application Flow](#filter-application-flow)
6. [Complete Pipeline Diagrams](#complete-pipeline-diagrams)
7. [Data Lineage](#data-lineage)
8. [Performance Considerations](#performance-considerations)

## Overview

de_Funk implements a **medallion architecture** with three data layers, each serving a specific purpose in the analytics pipeline. Data flows from external APIs through Bronze (raw) to Silver (curated) to Gold (business) layers, with each transformation adding value and structure.

### Data Flow Principles

1. **Unidirectional Flow**: Data flows forward through layers (Bronze → Silver → Gold)
2. **Immutable Bronze**: Raw data is never modified after ingestion
3. **Idempotent Transforms**: Silver transformations can be rerun safely
4. **On-Demand Gold**: Business metrics computed at query time
5. **Layer Isolation**: Each layer has clear boundaries and responsibilities

### Architecture Overview

```
External APIs ──► Bronze Layer ──► Silver Layer ──► Gold Layer ──► Applications
(Raw Data)        (Landing Zone)   (Curated)        (Business)     (UI/Reports)
```

## Bronze Layer Ingestion Flow

### End-to-End Ingestion Process

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        BRONZE INGESTION PIPELINE                        │
└─────────────────────────────────────────────────────────────────────────┘

1. CONFIGURATION LOADING
   ┌───────────────────────┐
   │ Pipeline Script       │
   │ run_full_pipeline.py  │
   └──────────┬────────────┘
              │
              │ Load configs
              ▼
   ┌───────────────────────┐
   │ RepoContext           │
   │ - storage.json        │
   │ - polygon_endpoints   │
   └──────────┬────────────┘

2. REGISTRY INITIALIZATION
              │
              │ Initialize
              ▼
   ┌───────────────────────┐
   │ Provider Registry     │
   │ - Polygon facets      │
   │ - BLS facets          │
   │ - Chicago facets      │
   └──────────┬────────────┘

3. INGESTOR CREATION
              │
              │ Create ingestor
              ▼
   ┌───────────────────────┐
   │ PolygonIngestor       │
   │ - API client          │
   │ - Bronze sink         │
   │ - Retry logic         │
   └──────────┬────────────┘

4. FACET EXECUTION (for each dataset)
              │
              │ For each ticker/date
              ▼
   ┌───────────────────────┐
   │ Facet                 │
   │ PricesDailyFacet      │
   ├───────────────────────┤
   │ - Build URL           │
   │ - Set parameters      │
   │ - Handle pagination   │
   └──────────┬────────────┘
              │
              │ HTTP GET
              ▼
   ┌───────────────────────┐
   │ External API          │
   │ api.polygon.io        │
   └──────────┬────────────┘
              │
              │ JSON response
              ▼
   ┌───────────────────────┐
   │ Response Parser       │
   │ - Extract data        │
   │ - Validate schema     │
   │ - Add metadata        │
   └──────────┬────────────┘

5. BRONZE STORAGE
              │
              │ Write parquet
              ▼
   ┌───────────────────────────────────────┐
   │ Bronze Layer                          │
   │ storage/bronze/polygon/               │
   │   prices_daily/                       │
   │     ticker=AAPL/                      │
   │       date=2024-01-01/                │
   │         data.parquet                  │
   │           - open, high, low, close    │
   │           - volume, vwap              │
   │           - transactions              │
   │           - ingestion_timestamp       │
   └───────────────────────────────────────┘
```

### Detailed Ingestion Sequence

**Step 1: Pipeline Initialization**

```python
# File: scripts/run_full_pipeline.py:45-80

def main():
    # Initialize repository context
    ctx = RepoContext.from_repo_root()

    # Load storage configuration
    storage_cfg = ctx.storage

    # Create ingestor with configuration
    ingestor = PolygonIngestor(storage_cfg)

    # Define date range
    start_date = datetime.date(2024, 1, 1)
    end_date = datetime.date(2024, 12, 31)

    # Run ingestion
    ingestor.run_all(
        start_date=start_date,
        end_date=end_date,
        datasets=['prices_daily', 'ref_tickers']
    )
```

**Step 2: Facet Registration**

```python
# File: datapipelines/providers/polygon/polygon_registry.py:20-50

class PolygonRegistry:
    """Registry for Polygon data facets."""

    @classmethod
    def register_facets(cls):
        """Register all Polygon facets."""
        Registry.register(
            provider='polygon',
            dataset='prices_daily',
            facet_class=PricesDailyFacet
        )
        Registry.register(
            provider='polygon',
            dataset='ref_tickers',
            facet_class=RefTickersFacet
        )
        # ... more facets
```

**Step 3: Data Fetching**

```python
# File: datapipelines/facets/polygon/prices_daily_facet.py:30-80

class PricesDailyFacet(PolygonBaseFacet):
    """Facet for daily aggregate price bars."""

    endpoint = "v2/aggs/ticker/{ticker}/range/1/day/{from_date}/{to_date}"
    dataset = "prices_daily"

    def fetch(self, ticker: str, from_date: str, to_date: str):
        """Fetch daily prices for a ticker."""
        url = self.get_url(ticker=ticker, from_date=from_date, to_date=to_date)

        # Handle pagination
        all_results = []
        next_url = url

        while next_url:
            response = self.http_client.get(next_url)
            data = response.json()

            all_results.extend(data.get('results', []))

            # Check for next page
            next_url = data.get('next_url')

        return all_results
```

**Step 4: Bronze Storage**

```python
# File: datapipelines/ingestors/bronze_sink.py:25-70

class BronzeSink:
    """Handles writing data to Bronze layer."""

    def write(self, provider: str, dataset: str, data: List[Dict], partition_keys: Dict):
        """Write data to Bronze with partitioning."""
        # Determine output path
        bronze_root = Path(self.storage_cfg['roots']['bronze'])
        output_path = bronze_root / provider / dataset

        # Add partition columns
        for key, value in partition_keys.items():
            output_path = output_path / f"{key}={value}"

        # Convert to DataFrame
        df = pd.DataFrame(data)

        # Add metadata
        df['ingestion_timestamp'] = datetime.now()
        df['source_provider'] = provider
        df['source_dataset'] = dataset

        # Write as Parquet
        output_path.mkdir(parents=True, exist_ok=True)
        df.to_parquet(
            output_path / "data.parquet",
            compression='snappy',
            index=False
        )
```

### Bronze Layer Structure

```
storage/bronze/
├── polygon/                          # Provider name
│   ├── prices_daily/                 # Dataset name
│   │   ├── ticker=AAPL/              # Partition by ticker
│   │   │   ├── date=2024-01-01/      # Partition by date
│   │   │   │   └── data.parquet
│   │   │   ├── date=2024-01-02/
│   │   │   │   └── data.parquet
│   │   │   └── ...
│   │   ├── ticker=GOOGL/
│   │   │   └── ...
│   │   └── ...
│   ├── ref_tickers/
│   │   └── ingestion_date=2024-01-01/
│   │       └── data.parquet
│   └── news/
│       └── ...
├── bls/
│   ├── unemployment/
│   └── cpi/
└── chicago/
    ├── building_permits/
    └── unemployment_rates/
```

### Ingestion Metadata

Each Bronze record includes metadata for traceability:

```python
{
    "ticker": "AAPL",
    "date": "2024-01-01",
    "open": 184.22,
    "high": 186.88,
    "low": 183.89,
    "close": 185.64,
    "volume": 48874900,

    # Metadata
    "ingestion_timestamp": "2024-01-02T08:15:30",
    "source_provider": "polygon",
    "source_dataset": "prices_daily",
    "api_version": "v2",
    "request_id": "abc123..."
}
```

## Silver Layer Transformation Flow

### ETL Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     SILVER TRANSFORMATION PIPELINE                      │
└─────────────────────────────────────────────────────────────────────────┘

1. READ BRONZE DATA
   ┌───────────────────────┐
   │ Bronze Layer          │
   │ Parquet files         │
   └──────────┬────────────┘
              │
              │ Read with Spark (required for transformation)
              ▼
   ┌───────────────────────┐
   │ Raw DataFrame         │
   │ (untransformed)       │
   └──────────┬────────────┘

2. DATA QUALITY & CLEANSING
              │
              │ Apply transformations
              ▼
   ┌───────────────────────────────────────┐
   │ Data Quality Rules                    │
   ├───────────────────────────────────────┤
   │ - Remove duplicates                   │
   │ - Handle nulls                        │
   │ - Validate data types                 │
   │ - Check business rules                │
   │ - Flag anomalies                      │
   └──────────┬────────────────────────────┘
              │
              │ Cleansed data
              ▼
   ┌───────────────────────┐
   │ Clean DataFrame       │
   └──────────┬────────────┘

3. STANDARDIZATION
              │
              │ Conform schema
              ▼
   ┌───────────────────────────────────────┐
   │ Schema Standardization                │
   ├───────────────────────────────────────┤
   │ - Rename columns                      │
   │ - Convert types (string → date)       │
   │ - Normalize formats                   │
   │ - Add calculated fields               │
   └──────────┬────────────────────────────┘

4. DIMENSION ENRICHMENT
              │
              │ Join dimensions
              ▼
   ┌───────────────────────────────────────┐
   │ Dimension Lookup                      │
   ├───────────────────────────────────────┤
   │ - Join company metadata               │
   │ - Join calendar attributes            │
   │ - Resolve foreign keys                │
   │ - Denormalize for performance         │
   └──────────┬────────────────────────────┘

5. BUSINESS LOGIC
              │
              │ Apply rules
              ▼
   ┌───────────────────────────────────────┐
   │ Business Rules                        │
   ├───────────────────────────────────────┤
   │ - Calculate derived fields            │
   │ - Apply business classifications      │
   │ - Compute aggregates                  │
   │ - Generate surrogate keys             │
   └──────────┬────────────────────────────┘

6. WRITE SILVER DATA
              │
              │ Write optimized format
              ▼
   ┌───────────────────────────────────────┐
   │ Silver Layer                          │
   │ storage/silver/                       │
   │   fact_prices/                        │
   │     date=2024-01/                     │
   │       data.parquet                    │
   │         - All price data              │
   │         - Company metadata            │
   │         - Calendar attributes         │
   │         - Computed fields             │
   └───────────────────────────────────────┘
```

### Transformation Example: Prices ETL

```python
# File: orchestration/silver/build_fact_prices.py:30-120

def build_fact_prices(spark, storage_cfg):
    """Transform Bronze prices to Silver fact table."""

    # Step 1: Read Bronze data
    bronze_path = f"{storage_cfg['roots']['bronze']}/polygon/prices_daily"
    raw_prices = spark.read.parquet(bronze_path)

    # Step 2: Data Quality
    clean_prices = (
        raw_prices
        # Remove duplicates
        .dropDuplicates(['ticker', 'date'])
        # Filter out invalid data
        .filter(F.col('close') > 0)
        .filter(F.col('volume') > 0)
        # Handle nulls
        .fillna({'vwap': F.col('close')})
    )

    # Step 3: Standardization
    standardized = clean_prices.select(
        F.col('date').cast('date').alias('date'),
        F.upper(F.col('ticker')).alias('ticker'),
        F.col('open').cast('double'),
        F.col('high').cast('double'),
        F.col('low').cast('double'),
        F.col('close').cast('double'),
        F.col('volume').cast('bigint'),
        F.col('vwap').cast('double'),
        F.col('transactions').cast('integer')
    )

    # Step 4: Dimension Enrichment
    # Join company dimension
    companies = spark.read.parquet(f"{storage_cfg['roots']['silver']}/dim_companies")
    enriched = standardized.join(
        companies.select('ticker', 'name', 'sector', 'industry'),
        on='ticker',
        how='left'
    )

    # Join calendar dimension
    calendar = spark.read.parquet(f"{storage_cfg['roots']['silver']}/dim_calendar")
    enriched = enriched.join(
        calendar.select('date', 'year', 'quarter', 'month', 'day_of_week'),
        on='date',
        how='left'
    )

    # Step 5: Business Logic
    final = enriched.withColumn(
        # Calculate price change
        'price_change', F.col('close') - F.col('open')
    ).withColumn(
        # Calculate percent change
        'price_change_pct', (F.col('close') - F.col('open')) / F.col('open') * 100
    ).withColumn(
        # Compute price range
        'price_range', F.col('high') - F.col('low')
    ).withColumn(
        # Add processing timestamp
        'etl_timestamp', F.current_timestamp()
    )

    # Step 6: Write to Silver
    silver_path = f"{storage_cfg['roots']['silver']}/fact_prices"
    (
        final
        .write
        .mode('overwrite')
        .partitionBy('year', 'month')  # Partition by time for query performance
        .parquet(silver_path)
    )

    return final
```

### Silver Layer Structure

```
storage/silver/
├── fact_prices/                      # Fact tables
│   ├── year=2024/
│   │   ├── month=1/
│   │   │   └── data.parquet
│   │   ├── month=2/
│   │   │   └── data.parquet
│   │   └── ...
│   └── ...
├── fact_news/
│   └── ...
├── fact_forecasts/
│   └── ...
├── dim_companies/                    # Dimension tables
│   └── data.parquet
├── dim_calendar/
│   └── data.parquet
├── dim_sectors/
│   └── data.parquet
└── dim_exchanges/
    └── data.parquet
```

### Silver Table Schema

**fact_prices** (Price bars with enrichments):
```
Columns:
  date: date                          # Trading date
  ticker: string                      # Stock symbol (FK)

  # Price data
  open: double
  high: double
  low: double
  close: double
  volume: bigint
  vwap: double
  transactions: integer

  # Calculated fields
  price_change: double
  price_change_pct: double
  price_range: double

  # Dimension attributes (denormalized)
  company_name: string
  sector: string
  industry: string
  year: integer
  quarter: integer
  month: integer
  day_of_week: integer

  # Metadata
  etl_timestamp: timestamp
```

## Query Execution Flow

### Notebook-Based Query Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        QUERY EXECUTION PIPELINE                         │
└─────────────────────────────────────────────────────────────────────────┘

1. USER INTERACTION
   ┌───────────────────────┐
   │ Streamlit UI          │
   │ - Select notebook     │
   │ - Set filters         │
   │ - Choose ticker       │
   └──────────┬────────────┘
              │
              │ Load notebook
              ▼

2. NOTEBOOK LOADING
   ┌───────────────────────────────────────┐
   │ NotebookManager                       │
   ├───────────────────────────────────────┤
   │ - Parse markdown file                 │
   │ - Extract exhibits                    │
   │ - Load filter definitions             │
   │ - Initialize folder context           │
   └──────────┬────────────────────────────┘
              │
              │ Parsed exhibits
              ▼

3. EXHIBIT PREPARATION
   ┌───────────────────────────────────────┐
   │ Exhibit Definitions                   │
   ├───────────────────────────────────────┤
   │ $exhibit${                            │
   │   "type": "line_chart",               │
   │   "query": {                          │
   │     "model": "company",               │
   │     "table": "fact_prices",           │
   │     "measures": ["close", "volume"]   │
   │   }                                   │
   │ }                                     │
   └──────────┬────────────────────────────┘
              │
              │ For each exhibit
              ▼

4. FILTER CONTEXT RESOLUTION
   ┌───────────────────────────────────────┐
   │ FilterEngine                          │
   ├───────────────────────────────────────┤
   │ - Merge global filters                │
   │ - Apply folder-level filters          │
   │ - Apply exhibit-level filters         │
   │ - Build SQL predicates                │
   └──────────┬────────────────────────────┘
              │
              │ Filter expressions
              ▼

5. MODEL & TABLE RESOLUTION
   ┌───────────────────────────────────────┐
   │ UniversalSession                      │
   ├───────────────────────────────────────┤
   │ - Load requested model                │
   │ - Get table definition                │
   │ - Resolve storage path                │
   └──────────┬────────────────────────────┘
              │
              │ Table metadata
              ▼

6. QUERY BUILDING
   ┌───────────────────────────────────────┐
   │ Query Builder                         │
   ├───────────────────────────────────────┤
   │ SELECT close, volume                  │
   │ FROM silver.fact_prices               │
   │ WHERE ticker = 'AAPL'                 │
   │   AND date >= '2024-01-01'            │
   │   AND date <= '2024-12-31'            │
   │ ORDER BY date                         │
   └──────────┬────────────────────────────┘
              │
              │ SQL query
              ▼

7. DATABASE EXECUTION
   ┌───────────────────────────────────────┐
   │ DuckDB / Spark                        │
   ├───────────────────────────────────────┤
   │ - Read Parquet files                  │
   │ - Apply partition pruning             │
   │ - Execute filters                     │
   │ - Perform aggregations                │
   │ - Return results                      │
   └──────────┬────────────────────────────┘
              │
              │ DataFrame
              ▼

8. DATA POST-PROCESSING
   ┌───────────────────────────────────────┐
   │ Result Processing                     │
   ├───────────────────────────────────────┤
   │ - Convert to Pandas                   │
   │ - Format dates                        │
   │ - Apply frontend filters              │
   │ - Sort/limit results                  │
   └──────────┬────────────────────────────┘
              │
              │ Formatted data
              ▼

9. VISUALIZATION RENDERING
   ┌───────────────────────────────────────┐
   │ Exhibit Renderer                      │
   ├───────────────────────────────────────┤
   │ - Create Plotly chart                 │
   │ - Apply styling                       │
   │ - Add interactivity                   │
   │ - Render to UI                        │
   └───────────────────────────────────────┘
```

### Query Example: Price Chart

```python
# File: app/notebook/api/notebook_session.py:180-240

def execute_exhibit(self, exhibit: Exhibit):
    """Execute query for an exhibit."""

    # Step 1: Get model and table
    model_name = exhibit.query.get('model', 'company')
    table_name = exhibit.query.get('table')

    # Step 2: Load model if needed
    if model_name not in self.manager.session.models:
        self.manager.session.load_model(model_name)

    # Step 3: Get base table
    df = self.manager.session.get_table(model_name, table_name)

    # Step 4: Apply filters
    filter_context = self.manager.folder_context_manager.get_current_context()
    df = self.filter_engine.apply_filters(df, filter_context)

    # Step 5: Select measures
    measures = exhibit.query.get('measures', [])
    if measures:
        df = df.select(measures)

    # Step 6: Apply aggregations
    if exhibit.query.get('group_by'):
        group_cols = exhibit.query['group_by']
        agg_spec = exhibit.query.get('aggregations', {})
        df = df.groupBy(group_cols).agg(agg_spec)

    # Step 7: Convert to Pandas
    pdf = df.toPandas()

    # Step 8: Return data
    return pdf
```

## Filter Application Flow

### Hierarchical Filter System

de_Funk implements a **three-tier filter hierarchy**:

```
Global Filters (Application-wide)
    │
    ├─► Folder Filters (Notebook folder)
    │       │
    │       ├─► Exhibit Filters (Individual exhibit)
    │       │       │
    │       │       └─► Final Query
    │       │
    │       └─► Exhibit Filters
    │               │
    │               └─► Final Query
    │
    └─► Folder Filters
            │
            └─► ...
```

### Filter Merging and Application

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        FILTER APPLICATION FLOW                          │
└─────────────────────────────────────────────────────────────────────────┘

1. FILTER COLLECTION
   ┌───────────────────────────────────────┐
   │ Global Filters (from UI)              │
   ├───────────────────────────────────────┤
   │ ticker: ['AAPL', 'GOOGL']             │
   │ date_range: ['2024-01-01', ...]       │
   └──────────┬────────────────────────────┘
              │
              │ Merge
              ▼
   ┌───────────────────────────────────────┐
   │ Folder Filters (from folder context)  │
   ├───────────────────────────────────────┤
   │ sector: 'Technology'                  │
   │ min_volume: 1000000                   │
   └──────────┬────────────────────────────┘
              │
              │ Merge
              ▼
   ┌───────────────────────────────────────┐
   │ Exhibit Filters (from exhibit def)    │
   ├───────────────────────────────────────┤
   │ measure: 'close'                      │
   │ aggregation: 'avg'                    │
   └──────────┬────────────────────────────┘

2. FILTER NORMALIZATION
              │
              │ Normalize
              ▼
   ┌───────────────────────────────────────┐
   │ FilterContext                         │
   ├───────────────────────────────────────┤
   │ {                                     │
   │   "dimensions": {                     │
   │     "ticker": ["AAPL", "GOOGL"],      │
   │     "sector": ["Technology"]          │
   │   },                                  │
   │   "date_range": {                     │
   │     "start": "2024-01-01",            │
   │     "end": "2024-12-31"               │
   │   },                                  │
   │   "measures": {                       │
   │     "volume": {"min": 1000000}        │
   │   }                                   │
   │ }                                     │
   └──────────┬────────────────────────────┘

3. SQL PREDICATE BUILDING
              │
              │ Build SQL
              ▼
   ┌───────────────────────────────────────┐
   │ FilterEngine                          │
   ├───────────────────────────────────────┤
   │ WHERE ticker IN ('AAPL', 'GOOGL')     │
   │   AND sector = 'Technology'           │
   │   AND date >= '2024-01-01'            │
   │   AND date <= '2024-12-31'            │
   │   AND volume >= 1000000               │
   └──────────┬────────────────────────────┘

4. QUERY EXECUTION
              │
              │ Apply to query
              ▼
   ┌───────────────────────────────────────┐
   │ Database Query                        │
   ├───────────────────────────────────────┤
   │ SELECT date, ticker, close            │
   │ FROM silver.fact_prices               │
   │ WHERE ticker IN ('AAPL', 'GOOGL')     │
   │   AND sector = 'Technology'           │
   │   AND date >= '2024-01-01'            │
   │   AND date <= '2024-12-31'            │
   │   AND volume >= 1000000               │
   │ ORDER BY date                         │
   └──────────┬────────────────────────────┘
              │
              │ Execute
              ▼
   ┌───────────────────────────────────────┐
   │ Filtered Results                      │
   └───────────────────────────────────────┘
```

### Filter Context Manager

```python
# File: app/notebook/folder_context.py:40-100

class FolderFilterContextManager:
    """Manages filter contexts per notebook folder."""

    def __init__(self, notebooks_root: Path):
        self.notebooks_root = notebooks_root
        self._contexts: Dict[str, FilterContext] = {}
        self._current_folder: Optional[str] = None

    def switch_folder(self, notebook_path: Path):
        """Switch to folder context for a notebook."""
        # Determine folder (relative to notebooks_root)
        try:
            rel_path = notebook_path.relative_to(self.notebooks_root)
            folder_key = str(rel_path.parent) if rel_path.parent != Path('.') else 'root'
        except ValueError:
            folder_key = 'root'

        # Switch current context
        self._current_folder = folder_key

        # Initialize context if not exists
        if folder_key not in self._contexts:
            self._contexts[folder_key] = FilterContext()

        return self._contexts[folder_key]

    def get_current_context(self) -> FilterContext:
        """Get current folder's filter context."""
        if self._current_folder is None:
            return FilterContext()  # Empty context

        return self._contexts.get(self._current_folder, FilterContext())

    def update_filter(self, dimension: str, values: List[str]):
        """Update filter in current folder context."""
        context = self.get_current_context()
        context.dimensions[dimension] = values

    def clear_filters(self):
        """Clear all filters in current folder."""
        context = self.get_current_context()
        context.clear()
```

### Filter Precedence Rules

1. **Exhibit filters override folder filters**
2. **Folder filters override global filters**
3. **Date range filters use intersection (narrowest range wins)**
4. **Measure filters use union (all constraints applied)**
5. **Dimension filters use intersection (all values must match)**

## Complete Pipeline Diagrams

### Full End-to-End Data Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                       COMPLETE DE_FUNK DATA PIPELINE                            │
└─────────────────────────────────────────────────────────────────────────────────┘

External APIs              Bronze Layer          Silver Layer         Application
─────────────              ────────────          ────────────         ───────────

┌──────────────┐
│ Polygon API  │──┐
└──────────────┘  │
                  │
┌──────────────┐  │  Ingest    ┌────────────┐   Transform  ┌────────────┐
│ BLS API      │──┼────────►   │   Bronze   │──────────►   │   Silver   │
└──────────────┘  │   (Raw)    │  Landing   │  (Cleanse)   │  Curated   │
                  │            └────────────┘              └──────┬─────┘
┌──────────────┐  │                                               │
│ Chicago API  │──┘                                               │
└──────────────┘                                                  │
                                                                  │
                                                          ┌───────▼────────┐
                                                          │  UniversalSess │
                                                          │  - Load models │
                                                          │  - Query data  │
                                                          └───────┬────────┘
                                                                  │
                                                      ┌───────────┴───────────┐
                                                      │                       │
                                              ┌───────▼────────┐    ┌────────▼───────┐
                                              │ Notebook System│    │  Streamlit UI  │
                                              │ - Parse .md    │    │  - Filters     │
                                              │ - Render charts│    │  - Interactive │
                                              └────────────────┘    └────────────────┘

Timeline:
─────────
T0: API calls (seconds to minutes)
T1: Bronze write (milliseconds)
T2: Silver transform (minutes to hours, scheduled)
T3: Query execution (milliseconds with DuckDB)
T4: UI render (milliseconds)
```

### Scheduled vs On-Demand Operations

```
SCHEDULED (Batch)                       ON-DEMAND (Interactive)
─────────────────                       ───────────────────────

Daily 6:00 AM                           User Action
    │                                       │
    ├─► Ingest new data                     ├─► Select notebook
    │   (Polygon, BLS, Chicago)             │
    │   └─► Write to Bronze                 ├─► Set filters
    │                                       │
    ├─► Transform to Silver                 ├─► Load data
    │   (Cleanse, enrich)                   │   (Read from Silver)
    │   └─► Overwrite Silver tables         │
    │                                       ├─► Apply filters
    ├─► Run forecasts (optional)            │   (FilterEngine)
    │   └─► Write to Silver                 │
    │                                       ├─► Render exhibits
Weekly Sunday 2:00 AM                       │   (Charts, tables)
    │                                       │
    ├─► Full historical refresh             └─► Display in UI
    │   (90 days of data)
    │
    └─► Archive old data
```

## Data Lineage

### Tracking Data Through Layers

Each record maintains lineage metadata through the pipeline:

```
┌─────────────────────────────────────────────────────────────┐
│                    DATA LINEAGE TRACKING                    │
└─────────────────────────────────────────────────────────────┘

Bronze Record (Raw API Response)
────────────────────────────────
{
  "ticker": "AAPL",
  "date": "2024-01-01",
  "close": 185.64,

  # Bronze metadata
  "ingestion_timestamp": "2024-01-02T08:15:30",
  "source_provider": "polygon",
  "source_dataset": "prices_daily",
  "api_request_id": "abc123",
  "partition_date": "2024-01-01"
}
        │
        │ Transform
        ▼
Silver Record (Curated)
───────────────────────
{
  "ticker": "AAPL",
  "date": "2024-01-01",
  "close": 185.64,
  "price_change": 1.42,
  "price_change_pct": 0.77,

  # Silver metadata
  "etl_timestamp": "2024-01-02T10:30:00",
  "etl_job_id": "silver_prices_20240102",
  "source_layer": "bronze",
  "source_provider": "polygon",
  "quality_score": 100
}
        │
        │ Query
        ▼
Gold Record (Business View)
───────────────────────────
{
  "ticker": "AAPL",
  "company_name": "Apple Inc.",
  "date": "2024-01-01",
  "close": 185.64,
  "52_week_high": 199.62,
  "52_week_low": 164.08,
  "percentile_rank": 85.3,

  # Gold metadata
  "computed_timestamp": "2024-01-02T14:45:00",
  "computation_method": "rolling_window",
  "cache_key": "aapl_metrics_20240101"
}
```

## Performance Considerations

### Query Optimization Strategies

**1. Partition Pruning**

```python
# Good: Uses date partition
df = spark.read.parquet("silver/fact_prices") \
    .filter("date >= '2024-01-01' AND date <= '2024-01-31'")

# Only reads January 2024 partition
# Performance: ~100x faster than full scan
```

**2. Predicate Pushdown**

```python
# Good: Filter pushed to storage layer
df = spark.read.parquet("silver/fact_prices") \
    .filter("ticker = 'AAPL'") \
    .select("date", "close")

# Filter applied during read, not after
# Performance: ~10x faster
```

**3. Column Pruning**

```python
# Good: Only reads needed columns
df = spark.read.parquet("silver/fact_prices") \
    .select("date", "close", "volume")

# Parquet only reads 3 columns, not all 20+
# Performance: ~5x faster
```

**4. DuckDB for Analytics**

```python
# Use DuckDB instead of Spark for notebooks
# Performance: 10-100x faster for OLAP queries
# Memory: Uses ~1/10th the memory
```

### Caching Strategy

```python
# Cache expensive computations
@st.cache_data(ttl=3600)  # 1 hour TTL
def get_price_history(ticker, start_date, end_date):
    """Cached price data."""
    return session.get_table('company', 'fact_prices')

@st.cache_resource  # Cache for entire session
def get_universal_session():
    """Cached database connection."""
    return UniversalSession(...)
```

### Storage Format Optimization

```python
# Parquet with compression
df.write \
    .mode('overwrite') \
    .option('compression', 'snappy') \  # Fast compression
    .partitionBy('year', 'month') \      # Time-based partitions
    .parquet(output_path)

# Result: 10x smaller files, 5x faster queries
```

---

## Related Documentation

- [System Design](./system-design.md)
- [Component Documentation](./components/)
- [Pipeline Guide](../../../PIPELINE_GUIDE.md)

---

**File**: `/home/user/de_Funk/docs/guide/3-architecture/data-flow.md`
**Last Updated**: 2025-11-08
