# de_Funk System Architecture Design

## Table of Contents
1. [Overview](#overview)
2. [Architecture Principles](#architecture-principles)
3. [High-Level Architecture](#high-level-architecture)
4. [Technology Stack](#technology-stack)
5. [Component Interaction](#component-interaction)
6. [Design Patterns](#design-patterns)
7. [Data Architecture](#data-architecture)
8. [Scalability & Extension](#scalability--extension)

## Overview

de_Funk is a modular analytics platform designed for flexible data ingestion, transformation, modeling, and visualization. The system follows a **layered medallion architecture** (Bronze → Silver → Gold) with pluggable components that support multiple data backends (Spark and DuckDB).

### Core Capabilities

- **Multi-source data ingestion** via provider-agnostic pipelines
- **Dual-backend support** for both heavy (Spark) and lightweight (DuckDB) workloads
- **Model-driven analytics** with YAML-configured data graphs
- **Interactive notebooks** with markdown-based exhibit definitions
- **Dynamic filtering** with folder-based context management
- **Real-time visualization** via Streamlit UI

### Design Philosophy

1. **Separation of Concerns**: Clean boundaries between data ingestion, modeling, and presentation
2. **Configuration over Code**: YAML-driven model definitions and notebook specifications
3. **Backend Agnostic**: Unified API works with both Spark and DuckDB
4. **Extensibility**: Plugin architecture for new data sources, models, and visualizations
5. **Developer Experience**: Minimal boilerplate, clear conventions, comprehensive tooling

## Architecture Principles

### 1. Layered Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Presentation Layer                          │
│         (Streamlit UI, Notebook Renderer, Exhibits)             │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                      Application Layer                          │
│    (Notebook Manager, Filter Engine, Universal Session)         │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                       Domain Layer                              │
│           (Models, Services, Business Logic)                    │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                   Data Access Layer                             │
│      (Storage Router, Connections, Data Providers)              │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                      Storage Layer                              │
│           (Bronze, Silver, Gold Tables)                         │
└─────────────────────────────────────────────────────────────────┘
```

### 2. Medallion Architecture

The system implements a three-tier medallion pattern:

```
Raw Data → Bronze (Landing) → Silver (Curated) → Gold (Business)
           ─────────────────   ──────────────    ────────────────
           - As-is ingestion   - Cleansed       - Aggregated
           - No transforms     - Standardized   - Business metrics
           - Historical        - Conformed      - Ready for BI
           - Immutable         - Quality-checked - Cached views
```

**Bronze Layer** (`storage/bronze/`):
- Raw data from external APIs (Polygon, BLS, Chicago Data Portal)
- Partitioned by date and source
- Immutable append-only storage
- Full historical record

**Silver Layer** (`storage/silver/`):
- Cleaned, standardized, and conformed data
- Foreign keys resolved, dimensions denormalized
- Business rules applied
- Optimized for analytics queries

**Gold Layer** (computed on-demand):
- Aggregated metrics and KPIs
- Notebook-specific views
- Cached for performance
- Ephemeral (regenerated as needed)

### 3. Plugin Architecture

All major components support extension through plugins:

```
Component           Plugin Type              Registration Method
─────────────────────────────────────────────────────────────────
Data Providers      Provider subclass        Registry.register()
Facets              BaseFacet subclass       Auto-discovery
Models              BaseModel subclass       ModelRegistry
Exhibits            BaseExhibit subclass     Type annotation
Filters             FilterProvider           FilterEngine.register()
```

## High-Level Architecture

### System Context Diagram

```
                           ┌─────────────────┐
                           │  External APIs  │
                           │  (Polygon, BLS, │
                           │   Chicago, etc) │
                           └────────┬────────┘
                                    │
                                    │ HTTP/REST
                                    │
                    ┌───────────────▼────────────────┐
                    │    Data Pipeline System        │
                    │  ┌──────────┐  ┌──────────┐   │
                    │  │ Facets   │  │Ingestors │   │
                    │  └──────────┘  └──────────┘   │
                    └───────────────┬────────────────┘
                                    │
                            Parquet │ Files
                                    │
            ┌───────────────────────▼───────────────────────┐
            │          Storage Layer (Medallion)            │
            │  ┌────────┐   ┌─────────┐   ┌──────────┐     │
            │  │ Bronze │ → │ Silver  │ → │   Gold   │     │
            │  └────────┘   └─────────┘   └──────────┘     │
            └───────────────────────┬───────────────────────┘
                                    │
                    ┌───────────────▼────────────────┐
                    │      Models System             │
                    │  ┌──────────────────────────┐  │
                    │  │   UniversalSession       │  │
                    │  ├──────────┬───────────────┤  │
                    │  │ Company  │  Forecast     │  │
                    │  │  Model   │   Model       │  │
                    │  └──────────┴───────────────┘  │
                    └───────────────┬────────────────┘
                                    │
        ┌───────────────────────────┴──────────────────────┐
        │                                                   │
        │                                                   │
┌───────▼────────────┐                          ┌──────────▼────────┐
│  Notebook System   │                          │   UI System       │
│  ┌──────────────┐  │                          │  ┌─────────────┐  │
│  │ Notebook     │  │                          │  │  Streamlit  │  │
│  │ Manager      │  │◄─────────────────────────┤  │    App      │  │
│  ├──────────────┤  │    Filter Context        │  ├─────────────┤  │
│  │ Markdown     │  │                          │  │ Components  │  │
│  │ Parser       │  │                          │  │ (Charts,    │  │
│  ├──────────────┤  │                          │  │  Tables,    │  │
│  │ Filter       │  │                          │  │  Metrics)   │  │
│  │ Engine       │  │                          │  └─────────────┘  │
│  ├──────────────┤  │                          └───────────────────┘
│  │ Exhibits     │  │
│  │ Renderer     │  │
│  └──────────────┘  │
└────────────────────┘
```

### Core Components

The system consists of 6 major subsystems:

1. **Data Pipeline** (`datapipelines/`)
   - Facets: API endpoint definitions
   - Ingestors: Orchestrate data fetching and storage
   - Providers: Source-specific implementations
   - Bronze Storage: Raw data persistence

2. **Core Session** (`core/`)
   - RepoContext: Environment and configuration
   - Connections: Database abstraction (Spark/DuckDB)
   - Filter Engine: Centralized filter application

3. **Models System** (`models/`)
   - BaseModel: YAML-driven graph building
   - UniversalSession: Multi-model session management
   - Model Registry: Dynamic model loading
   - Storage Router: Path resolution across layers

4. **Notebook System** (`app/notebook/`)
   - Notebook Manager: Lifecycle management
   - Markdown Parser: Parse exhibit definitions
   - Filter System: Dynamic filter context
   - Exhibits: Visualization specifications
   - Folder Context: Shared filter state

5. **UI Application** (`app/ui/`)
   - Streamlit App: Main application entry
   - Components: Reusable UI widgets
   - State Management: Session state handling

6. **Storage** (`storage/`)
   - Bronze Layer: Raw data landing zone
   - Silver Layer: Curated analytics tables
   - DuckDB Integration: Lightweight query engine

## Technology Stack

### Backend Technologies

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Data Processing** | Apache Spark (PySpark) | Required for data ingestion and Bronze→Silver transformation |
| **Analytics Engine** | DuckDB | Fast OLAP queries for analytics and UI (10-100x faster than Spark) |
| **Storage Format** | Apache Parquet | Columnar storage with compression |
| **Data Modeling** | YAML Configs | Declarative model definitions |

### Frontend Technologies

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **UI Framework** | Streamlit | Interactive web application |
| **Visualization** | Plotly | Interactive charts and graphs |
| **Data Display** | Pandas | DataFrames for tables and metrics |
| **Markdown** | Python-Markdown | Notebook text rendering |

### Development Tools

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Language** | Python 3.9+ | Primary development language |
| **Dependency Management** | pip/requirements.txt | Package management |
| **Configuration** | JSON/YAML | Declarative configuration |
| **Version Control** | Git | Source code management |

### External Services

| Service | Provider | Purpose |
|---------|----------|---------|
| **Stock Data** | Polygon.io API | Real-time and historical stock prices |
| **Economic Data** | BLS API | Unemployment, CPI, economic indicators |
| **City Data** | Chicago Data Portal | Building permits, public datasets |

## Component Interaction

### Data Ingestion Flow

```
┌─────────────┐
│ External    │
│ API         │
└──────┬──────┘
       │
       │ 1. HTTP Request
       │
┌──────▼──────────────┐
│ Facet               │  (Defines endpoint, parameters, pagination)
│ - PricesDailyFacet  │
└──────┬──────────────┘
       │
       │ 2. Fetch Data
       │
┌──────▼──────────────┐
│ Ingestor            │  (Orchestrates fetching and storage)
│ - PolygonIngestor   │
└──────┬──────────────┘
       │
       │ 3. Write Parquet
       │
┌──────▼──────────────┐
│ Bronze Storage      │  (Raw data landing zone)
│ /bronze/polygon/    │
│   prices/           │
│     date=2024-01-01/│
│       data.parquet  │
└─────────────────────┘
```

### Data Transformation Flow

```
┌─────────────────────┐
│ Bronze Layer        │
│ (Raw Data)          │
└──────┬──────────────┘
       │
       │ 1. Read raw data
       │
┌──────▼──────────────┐
│ Transformation      │  (Cleaning, standardization, joins)
│ Script              │
│ - Data quality      │
│ - Type conversion   │
│ - Dimension lookup  │
└──────┬──────────────┘
       │
       │ 2. Write curated data
       │
┌──────▼──────────────┐
│ Silver Layer        │  (Curated analytics tables)
│ /silver/            │
│   fact_prices       │
│   fact_news         │
│   dim_companies     │
│   dim_calendar      │
└─────────────────────┘
```

### Query Execution Flow

```
┌─────────────────────┐
│ Streamlit UI        │
│ - User selects      │
│   ticker, dates     │
└──────┬──────────────┘
       │
       │ 1. Load notebook
       │
┌──────▼──────────────┐
│ NotebookManager     │  (Parse notebook, prepare exhibits)
│ - Parse markdown    │
│ - Extract filters   │
│ - Build exhibit defs│
└──────┬──────────────┘
       │
       │ 2. Apply filters
       │
┌──────▼──────────────┐
│ FilterEngine        │  (Centralized filter application)
│ - Build SQL filters │
│ - Apply to queries  │
└──────┬──────────────┘
       │
       │ 3. Execute query
       │
┌──────▼──────────────┐
│ UniversalSession    │  (Multi-model data access)
│ - Load model        │
│ - Get table         │
│ - Apply filters     │
└──────┬──────────────┘
       │
       │ 4. Query database
       │
┌──────▼──────────────┐
│ DuckDB/Spark        │  (Query engine)
│ - Read Parquet      │
│ - Apply filters     │
│ - Aggregate data    │
└──────┬──────────────┘
       │
       │ 5. Return results
       │
┌──────▼──────────────┐
│ Exhibit Renderer    │  (Visualize data)
│ - Format data       │
│ - Render chart      │
│ - Display in UI     │
└─────────────────────┘
```

### Model Loading and Access

```
┌─────────────────────┐
│ Application         │
│ - UI or script      │
└──────┬──────────────┘
       │
       │ 1. Create session
       │
┌──────▼──────────────┐
│ UniversalSession    │  (Model-agnostic session)
│ - Load registry     │
│ - Initialize models │
└──────┬──────────────┘
       │
       │ 2. Discover models
       │
┌──────▼──────────────┐
│ ModelRegistry       │  (Dynamic model loading)
│ - List configs      │
│ - Load YAML         │
│ - Instantiate model │
└──────┬──────────────┘
       │
       │ 3. Build model
       │
┌──────▼──────────────┐
│ BaseModel           │  (Generic graph building)
│ - Load nodes        │
│ - Apply edges       │
│ - Materialize paths │
└──────┬──────────────┘
       │
       │ 4. Resolve paths
       │
┌──────▼──────────────┐
│ StorageRouter       │  (Layer-aware path resolution)
│ - Map logical names │
│ - Return file paths │
└──────┬──────────────┘
       │
       │ 5. Read data
       │
┌──────▼──────────────┐
│ Connection          │  (Backend abstraction)
│ - DuckDB or Spark   │
│ - Execute query     │
└─────────────────────┘
```

## Design Patterns

### 1. Repository Pattern

**Purpose**: Abstract data access behind a clean interface

**Implementation**: StorageRouter, UniversalSession

```python
# File: models/api/dal.py:25-60

class StorageRouter:
    """Resolves logical table names to physical storage paths."""

    def get_bronze_path(self, provider: str, dataset: str) -> Path:
        """Map logical name to bronze storage path."""
        bronze_root = Path(self.storage_cfg['roots']['bronze'])
        return bronze_root / provider / dataset

    def get_silver_path(self, table_name: str) -> Path:
        """Map logical name to silver storage path."""
        silver_root = Path(self.storage_cfg['roots']['silver'])
        return silver_root / table_name
```

**Benefits**:
- Decouples business logic from storage details
- Easy to test with mock implementations
- Supports multiple storage backends

### 2. Strategy Pattern

**Purpose**: Select algorithm at runtime based on context

**Implementation**: Connection abstraction (Spark vs DuckDB)

```python
# File: core/connection.py:15-40

class ConnectionFactory:
    """Factory for creating backend-specific connections."""

    @staticmethod
    def create(backend: str, **kwargs):
        if backend == "spark":
            return SparkConnection(kwargs['spark_session'])
        elif backend == "duckdb":
            return DuckDBConnection(kwargs.get('db_path'))
        else:
            raise ValueError(f"Unsupported backend: {backend}")
```

**Benefits**:
- Unified API across different backends
- Easy to add new backends
- Runtime selection based on workload

### 3. Template Method Pattern

**Purpose**: Define algorithm skeleton, allow subclasses to override steps

**Implementation**: BaseModel with extension points

```python
# File: models/base/model.py:200-250

class BaseModel:
    """Base class for all domain models."""

    def build(self):
        """Template method for building model."""
        self.before_build()  # Extension point
        self._build_nodes()
        self._apply_edges()
        self._materialize_paths()
        self.after_build()   # Extension point

    def before_build(self):
        """Override in subclass for custom initialization."""
        pass

    def after_build(self):
        """Override in subclass for post-processing."""
        pass
```

**Benefits**:
- Reusable graph-building logic
- Minimal code in concrete models
- Clear extension points

### 4. Registry Pattern

**Purpose**: Central registration and lookup of components

**Implementation**: ModelRegistry, Provider Registry

```python
# File: models/registry.py:40-80

class ModelRegistry:
    """Central registry for all models."""

    _models: Dict[str, Type[BaseModel]] = {}

    @classmethod
    def register(cls, name: str, model_class: Type[BaseModel]):
        """Register a model class."""
        cls._models[name] = model_class

    @classmethod
    def get(cls, name: str) -> Type[BaseModel]:
        """Retrieve a registered model class."""
        return cls._models.get(name)
```

**Benefits**:
- Decoupled component discovery
- Plugin architecture support
- Easy to extend with new models

### 5. Facade Pattern

**Purpose**: Simplify complex subsystem with unified interface

**Implementation**: UniversalSession

```python
# File: models/api/session.py:60-120

class UniversalSession:
    """Unified session for accessing all models."""

    def __init__(self, connection, storage_cfg, repo_root, models=None):
        self.connection = connection
        self.registry = ModelRegistry()
        self._model_instances = {}

        # Load specified models
        for model_name in (models or []):
            self.load_model(model_name)

    def get_table(self, model_name: str, table_name: str):
        """Unified API to get any table from any model."""
        model = self._model_instances[model_name]
        return model.get_table(table_name)
```

**Benefits**:
- Simple API for complex operations
- Hides multi-model complexity
- Consistent interface

### 6. Builder Pattern

**Purpose**: Construct complex objects step by step

**Implementation**: Exhibit builders, Model builders

```python
# File: app/notebook/exhibits/charts.py:45-90

class ChartExhibit:
    """Builder for chart exhibits."""

    def __init__(self):
        self.data = None
        self.x_axis = None
        self.y_axis = None
        self.chart_type = "line"

    def set_data(self, df):
        self.data = df
        return self

    def set_axes(self, x, y):
        self.x_axis = x
        self.y_axis = y
        return self

    def build(self):
        """Construct final chart configuration."""
        return {
            'data': self.data,
            'x': self.x_axis,
            'y': self.y_axis,
            'type': self.chart_type
        }
```

**Benefits**:
- Fluent API
- Step-by-step configuration
- Immutable result

## Data Architecture

### Model Graph Structure

Each model defines a graph of nodes (tables), edges (relationships), and paths (joins):

```yaml
# File: configs/models/company.yaml

graph:
  nodes:
    # Facts (from bronze)
    - id: fact_prices
      from: bronze.polygon.prices_daily
      select:
        date: date
        ticker: ticker
        open: open
        high: high
        low: low
        close: close
        volume: volume

    # Dimensions (from silver)
    - id: dim_companies
      from: silver.companies

  edges:
    # Relationships
    - from: fact_prices
      to: dim_companies
      on: ticker = ticker

  paths:
    # Materialized views
    - id: prices_with_company
      from: fact_prices
      joins:
        - dim_companies
```

### Dimension Modeling

The system uses **star schema** for optimal query performance:

```
                    ┌────────────────┐
                    │ dim_companies  │
                    │ ─────────────  │
                    │ ticker (PK)    │
                    │ name           │
                    │ sector         │
                    │ industry       │
                    └────────┬───────┘
                             │
                             │
    ┌────────────────┐       │       ┌────────────────┐
    │ dim_calendar   │       │       │ dim_exchanges  │
    │ ──────────────│       │       │ ──────────────│
    │ date (PK)      │       │       │ exchange (PK)  │
    │ year           │       │       │ name           │
    │ quarter        │       │       │ country        │
    │ month          │       │       └────────┬───────┘
    │ day_of_week    │       │                │
    └────────┬───────┘       │                │
             │                │                │
             │                │                │
             │        ┌───────▼────────────────▼──┐
             │        │    fact_prices             │
             │        │    ────────────────────    │
             └────────┤ date (FK)                  │
                      │ ticker (FK)                │
                      ├────────────────────────────┤
                      │ open, high, low, close     │
                      │ volume, vwap               │
                      └────────────────────────────┘
```

**Benefits**:
- Denormalized for query performance
- Single JOIN paths to dimensions
- Pre-aggregated dimension attributes

### Calendar Dimension

Shared calendar dimension for time-based analysis:

```python
# File: models/base/calendar.py:20-60

class CalendarDimension:
    """Shared calendar dimension across all models."""

    @staticmethod
    def generate(start_date, end_date):
        """Generate calendar dimension table."""
        return pd.DataFrame({
            'date': pd.date_range(start_date, end_date),
            'year': lambda x: x['date'].dt.year,
            'quarter': lambda x: x['date'].dt.quarter,
            'month': lambda x: x['date'].dt.month,
            'day_of_week': lambda x: x['date'].dt.dayofweek,
            'week_of_year': lambda x: x['date'].dt.isocalendar().week,
            'is_weekend': lambda x: x['day_of_week'].isin([5, 6])
        })
```

## Scalability & Extension

### Adding New Models

To add a new domain model (e.g., "portfolio"):

1. **Create model directory**:
   ```
   models/portfolio/
   ├── model.py          # PortfolioModel(BaseModel)
   ├── types/            # Data types
   ├── services/         # Business logic
   └── __init__.py
   ```

2. **Create model config**:
   ```yaml
   # configs/models/portfolio.yaml
   model: portfolio
   depends_on:
     - company
   graph:
     nodes:
       - id: fact_positions
         from: silver.positions
   ```

3. **Implement model class**:
   ```python
   # models/portfolio/model.py
   from models.base.model import BaseModel

   class PortfolioModel(BaseModel):
       """Portfolio model for position tracking."""

       def get_positions(self, portfolio_id):
           """Get positions for a portfolio."""
           df = self.get_table('fact_positions')
           return df.filter(f"portfolio_id = '{portfolio_id}'")
   ```

4. **Register in session**:
   ```python
   session = UniversalSession(
       connection=conn,
       storage_cfg=storage,
       repo_root=repo,
       models=['company', 'forecast', 'portfolio']
   )
   ```

**That's it!** The BaseModel handles all graph building automatically.

### Adding New Data Providers

To add a new data source (e.g., "fred" for FRED economic data):

1. **Create provider directory**:
   ```
   datapipelines/providers/fred/
   ├── __init__.py
   ├── fred_ingestor.py
   ├── fred_registry.py
   └── facets/
       ├── __init__.py
       ├── fred_base_facet.py
       └── gdp_facet.py
   ```

2. **Implement base facet**:
   ```python
   # datapipelines/providers/fred/facets/fred_base_facet.py
   from datapipelines.facets.base_facet import BaseFacet

   class FredBaseFacet(BaseFacet):
       """Base facet for FRED API."""

       def get_url(self, **params):
           return f"https://api.stlouisfed.org/fred/{self.endpoint}"
   ```

3. **Implement specific facets**:
   ```python
   # datapipelines/providers/fred/facets/gdp_facet.py
   class GDPFacet(FredBaseFacet):
       endpoint = "series/observations"
       dataset = "gdp"
   ```

4. **Register provider**:
   ```python
   # datapipelines/providers/fred/fred_registry.py
   from datapipelines.base.registry import Registry

   Registry.register('fred', 'gdp', GDPFacet)
   ```

### Adding New Exhibit Types

To add a new visualization type (e.g., "heatmap"):

1. **Create exhibit class**:
   ```python
   # app/notebook/exhibits/heatmap.py
   from .base import BaseExhibit

   class HeatmapExhibit(BaseExhibit):
       exhibit_type = "heatmap"

       def render(self, data):
           """Render heatmap visualization."""
           import plotly.graph_objects as go

           fig = go.Figure(data=go.Heatmap(
               z=data['values'],
               x=data['x_axis'],
               y=data['y_axis']
           ))
           return fig
   ```

2. **Register in renderer**:
   ```python
   # app/notebook/exhibits/renderer.py
   from .heatmap import HeatmapExhibit

   ExhibitRegistry.register('heatmap', HeatmapExhibit)
   ```

3. **Use in notebooks**:
   ```markdown
   ## Correlation Heatmap

   $exhibit${
     "type": "heatmap",
     "query": {
       "model": "company",
       "table": "correlation_matrix"
     }
   }
   ```

### Performance Optimization

**Caching Strategy**:
```python
# Use Streamlit caching for expensive operations
@st.cache_data(ttl=3600)
def get_price_data(ticker, start_date, end_date):
    """Cache price data for 1 hour."""
    return session.get_table('company', 'fact_prices')

@st.cache_resource
def get_universal_session():
    """Cache session for entire Streamlit lifecycle."""
    return UniversalSession(...)
```

**Backend Selection**:
- **Use DuckDB** for notebooks and UI (10-100x faster)
- **Use Spark** for ETL and large-scale transformations

**Query Optimization**:
- Push-down filters to storage layer
- Use partition pruning (date-based partitions)
- Pre-aggregate common metrics

---

## Related Documentation

- [Data Flow Architecture](./data-flow.md)
- [Component Documentation](./components/)
- [Model Development Guide](../2-models/)
- [Development Best Practices](../4-development/)

---

**File**: `/home/user/de_Funk/docs/guide/3-architecture/system-design.md`
**Last Updated**: 2025-11-08
