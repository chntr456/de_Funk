# Architecture Overview

A high-level introduction to how de_Funk works.

---

## What is de_Funk?

**de_Funk** is a modern financial analytics platform that combines:

- **Automated data ingestion** from financial and economic APIs
- **Dimensional data modeling** for analytics-ready datasets
- **Interactive notebooks** for exploratory analysis
- **High-performance analytics** with DuckDB (10-100x faster than Spark)
- **Time series forecasting** with multiple ML models

---

## Design Principles

### 1. Layered Data Architecture

de_Funk uses a **medallion architecture** (Bronze → Silver → Gold):

```
Raw Data → Normalized Data → Analytics-Ready → Insights
(Bronze)   (Silver)          (Gold/UI)
```

### 2. Declarative Configuration

Models, notebooks, and pipelines are defined in **YAML/Markdown**, not code:

- Models: `configs/models/company.yaml`
- Notebooks: `configs/notebooks/stock_analysis.md`
- Pipelines: Orchestrated via scripts

### 3. Backend Agnostic

The system supports multiple query engines:

- **DuckDB** - Fast analytics (10-100x faster, default for UI)
- **Spark** - Large-scale ETL (optional, for data pipelines)

### 4. Notebook-Driven Analytics

Analysis is done via **Markdown notebooks** with:

- Inline filters (`$filter${...}`)
- Inline exhibits (`$exhibits${...}`)
- YAML front matter for metadata

---

## System Architecture

### High-Level Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                         DATA SOURCES                             │
├─────────────────────────────────────────────────────────────────┤
│  • Polygon API (stock prices, news)                              │
│  • BLS API (economic indicators)                                 │
│  • Chicago Data Portal (municipal finance)                       │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ↓
                    ┌─────────┐
                    │ Facets  │  Transform API responses → DataFrames
                    └────┬────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│                    BRONZE LAYER (Raw Data)                       │
├─────────────────────────────────────────────────────────────────┤
│  • Partitioned Parquet files                                     │
│  • Organized by provider/table                                   │
│  • Path: storage/bronze/{provider}/{table}/                      │
│  • Schema: Facet-normalized                                      │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ↓
                ┌─────────────────┐
                │  Model Builder  │  YAML-driven graph transformations
                └────────┬────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│                 SILVER LAYER (Dimensional Models)                │
├─────────────────────────────────────────────────────────────────┤
│  • Dimensions (dim_company, dim_exchange, dim_calendar)          │
│  • Facts (fact_prices, fact_news, fact_forecasts)                │
│  • Materialized views (prices_with_company)                      │
│  • Path: storage/silver/{model}/{table}/                         │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ↓
                ┌─────────────────┐
                │  Query Engine   │  DuckDB (fast) or Spark (ETL)
                └────────┬────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│                   ANALYTICS & VISUALIZATION                      │
├─────────────────────────────────────────────────────────────────┤
│  • Markdown Notebooks (configs/notebooks/)                       │
│  • Dynamic Filters (date range, tickers, thresholds)             │
│  • Interactive Exhibits (charts, tables, metrics)                │
│  • Streamlit UI (http://localhost:8501)                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Layer Details

### Bronze Layer: Raw Data Storage

**Purpose:** Store raw data from external APIs in a normalized format.

**Characteristics:**
- **Format:** Parquet (columnar, compressed)
- **Organization:** `storage/bronze/{provider}/{table}/`
- **Partitioning:** By date (where applicable)
- **Schema:** Defined by Facets (normalization layer)

**Example structure:**
```
storage/bronze/
├── polygon/
│   ├── prices_daily/
│   │   ├── trade_date=2024-01-01/
│   │   ├── trade_date=2024-01-02/
│   │   └── ...
│   ├── ref_ticker/
│   │   └── data.parquet
│   └── news/
│       ├── publish_date=2024-01-01/
│       └── ...
├── bls/
│   └── employment/
│       └── data.parquet
└── chicago/
    └── budget/
        └── data.parquet
```

**Key features:**
- **Immutable** - Never modified after ingestion
- **Timestamped** - Ingestion metadata preserved
- **Append-only** - Historical data retained
- **Partitioned** - For efficient queries

---

### Silver Layer: Dimensional Models

**Purpose:** Transform Bronze data into analytics-ready dimensional models.

**Characteristics:**
- **Format:** Parquet (same as Bronze)
- **Organization:** `storage/silver/{model}/{table}/`
- **Schema:** YAML-defined (in `configs/models/`)
- **Structure:** Star schema (facts + dimensions)

**Example structure:**
```
storage/silver/
├── company/
│   ├── dims/
│   │   ├── dim_company/
│   │   │   └── data.parquet
│   │   └── dim_exchange/
│   │       └── data.parquet
│   └── facts/
│       ├── fact_prices/
│       │   ├── trade_date=2024-01-01/
│       │   └── ...
│       ├── fact_news/
│       │   └── ...
│       └── prices_with_company/  (materialized view)
│           └── ...
├── forecast/
│   ├── dims/
│   │   └── dim_model/
│   └── facts/
│       └── fact_forecasts/
└── core/
    └── dims/
        └── dim_calendar/  (shared dimension)
```

**Dimensional modeling:**
- **Dimensions** - Descriptive attributes (who, what, where)
  - `dim_company` - Company name, ticker, exchange
  - `dim_exchange` - Exchange name, code
  - `dim_calendar` - Date dimension (shared across models)

- **Facts** - Measurable events (metrics, transactions)
  - `fact_prices` - Daily stock prices and volume
  - `fact_news` - News articles with sentiment
  - `fact_forecasts` - Time series predictions

- **Materialized views** - Pre-joined for performance
  - `prices_with_company` - Prices + company + exchange
  - `news_with_company` - News + company info

**YAML-driven transformations:**

The Silver layer is built using graph-based transformations defined in YAML:

```yaml
# configs/models/company.yaml
graph:
  nodes:
    - id: dim_company
      from: bronze.ref_ticker
      select:
        ticker: ticker
        company_name: name
      derive:
        company_id: "sha1(ticker)"

    - id: fact_prices
      from: bronze.prices_daily
      select:
        trade_date: trade_date
        ticker: ticker
        close: close
        volume: volume

  edges:
    - from: fact_prices
      to: dim_company
      on: ["ticker=ticker"]
      type: many_to_one

  paths:
    - id: prices_with_company
      hops: "fact_prices -> dim_company -> dim_exchange"
```

---

### Query Engine Layer

**Purpose:** Execute fast analytics queries on Silver layer data.

**Options:**

#### DuckDB (Default for Analytics)

- **Speed:** 10-100x faster than Spark for UI queries
- **Deployment:** Embedded in Python process
- **Memory:** Efficient for datasets up to 100GB
- **SQL:** Full SQL support with Parquet backend
- **Integration:** Native Python API

**When to use DuckDB:**
- Interactive analytics (UI queries)
- Adhoc exploration
- Small to medium datasets (<100GB)
- Single-node deployments

#### Spark (Optional for ETL)

- **Speed:** Slower for small queries, faster for large-scale ETL
- **Deployment:** Requires cluster setup
- **Memory:** Distributed processing
- **SQL:** Spark SQL
- **Integration:** PySpark API

**When to use Spark:**
- Large-scale data ingestion (>100GB)
- Complex ETL pipelines
- Distributed processing
- Multi-node clusters

**Backend abstraction:**

The `DataConnection` interface allows switching backends:

```python
# DuckDB connection
ctx = RepoContext.from_repo_root(connection_type="duckdb")

# Spark connection (if needed)
ctx = RepoContext.from_repo_root(connection_type="spark")
```

---

### Analytics & Visualization Layer

**Purpose:** Interactive analytics via Markdown notebooks and Streamlit UI.

**Components:**

#### 1. Markdown Notebooks

Notebooks are defined in **Markdown** with YAML front matter:

```markdown
---
id: stock_analysis
title: Stock Performance Analysis
models: [company]
---

# Stock Analysis

$filter${
  "date_range": {
    "label": "Date Range",
    "type": "date_range",
    "default": ["2024-01-01", "2024-12-31"]
  },
  "tickers": {
    "label": "Tickers",
    "type": "multi_select",
    "source": {"model": "company", "table": "dim_company", "column": "ticker"}
  }
}

$exhibits${
  "price_chart": {
    "type": "line_chart",
    "source": "company.fact_prices",
    "x_axis": "trade_date",
    "y_axis": "close",
    "color_by": "ticker"
  }
}
```

**Key features:**
- **Inline filters** - Define filters directly in markdown
- **Inline exhibits** - Define visualizations inline
- **Dynamic options** - Filter options from database
- **Collapsible sections** - `<details>` for organization

#### 2. Filter System

Filters are automatically generated from notebook definitions:

**Filter types:**
- `date_range` - Start/end date picker
- `multi_select` - Multi-select dropdown
- `single_select` - Single select dropdown
- `number_range` - Min/max numeric input
- `slider` - Slider for numeric ranges
- `text_search` - Text search box

**Dynamic filters:**
- Options loaded from database
- Real-time updates
- Backend-agnostic (works with DuckDB or Spark)

#### 3. Exhibit Types

Visualizations rendered from notebook definitions:

**Available exhibit types:**
- `metric_cards` - KPI cards with icons
- `line_chart` - Time series trends
- `bar_chart` - Categorical comparisons
- `scatter_chart` - Scatter plots
- `dual_axis_chart` - Twin Y-axes
- `heatmap` - 2D heatmap
- `data_table` - Sortable tables with download
- `weighted_aggregate_chart` - Multi-stock indices
- `forecast_chart` - Forecast with confidence intervals

#### 4. Streamlit UI

The web interface provides:

**Navigation:**
- Sidebar notebook browser
- Multi-tab support
- Folder organization

**Filtering:**
- Dynamic filter panel
- Auto-apply on change
- Filter state per notebook

**Visualization:**
- Interactive Plotly charts
- Zoom, pan, hover
- Download charts as PNG

**Theme:**
- Light/dark mode toggle
- Professional color schemes
- Accessible contrast

---

## Component Architecture

### Data Pipeline Components

```
┌──────────────────────────────────────────────────────────────┐
│                    Data Ingestion Pipeline                    │
└──────────────────────────────────────────────────────────────┘

┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Facet     │ →   │  Provider   │ →   │  Ingestor   │
├─────────────┤     ├─────────────┤     ├─────────────┤
│ • Normalize │     │ • API calls │     │ • Batch     │
│ • Schema    │     │ • Auth      │     │ • Partition │
│ • Transform │     │ • Paginate  │     │ • Write     │
└─────────────┘     └─────────────┘     └─────────────┘

                          ↓

                    Bronze Layer
                 (Parquet storage)
```

**Key files:**
- `datapipelines/facets/` - Facet definitions
- `datapipelines/providers/` - API providers (Polygon, BLS, Chicago)
- `datapipelines/ingestors/` - Ingestion orchestration

---

### Model Building Components

```
┌──────────────────────────────────────────────────────────────┐
│                    Model Building Pipeline                    │
└──────────────────────────────────────────────────────────────┘

┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Model YAML  │ →   │   Builder   │ →   │  Silver     │
├─────────────┤     ├─────────────┤     ├─────────────┤
│ • Nodes     │     │ • Graph     │     │ • Dims      │
│ • Edges     │     │ • Joins     │     │ • Facts     │
│ • Paths     │     │ • Derive    │     │ • Views     │
└─────────────┘     └─────────────┘     └─────────────┘

                          ↓

                    Silver Layer
              (Dimensional models)
```

**Key files:**
- `configs/models/` - Model YAML definitions
- `models/implemented/` - Model implementations
- `models/api/session.py` - UniversalSession (query interface)

---

### Session Management

```
┌──────────────────────────────────────────────────────────────┐
│                      Session Architecture                     │
└──────────────────────────────────────────────────────────────┘

┌─────────────────────┐
│  UniversalSession   │  Unified query interface
├─────────────────────┤
│ • Multi-model       │
│ • load_model()      │
│ • get_table()       │
│ • Filter app        │
└──────────┬──────────┘
           │
     ┌─────┴─────┐
     │           │
     ↓           ↓
┌──────────┐ ┌──────────┐
│ DuckDB   │ │  Spark   │  Backend abstraction
│Connection│ │Connection│
└──────────┘ └──────────┘
     │           │
     └─────┬─────┘
           ↓
    Silver Layer
```

**Key files:**
- `models/api/session.py` - UniversalSession
- `core/connection.py` - DataConnection (abstract)
- `core/duckdb_connection.py` - DuckDB implementation

---

### Notebook System

```
┌──────────────────────────────────────────────────────────────┐
│                      Notebook System                          │
└──────────────────────────────────────────────────────────────┘

┌─────────────────┐     ┌──────────────────┐
│ Markdown (.md)  │ →   │  Parser          │
├─────────────────┤     ├──────────────────┤
│ • Front matter  │     │ • Extract meta   │
│ • Filters       │     │ • Parse filters  │
│ • Exhibits      │     │ • Parse exhibits │
└─────────────────┘     └────────┬─────────┘
                                 │
                                 ↓
                        ┌─────────────────┐
                        │ NotebookConfig  │
                        ├─────────────────┤
                        │ • Metadata      │
                        │ • Variables     │
                        │ • Exhibits      │
                        │ • Layout        │
                        └────────┬────────┘
                                 │
                                 ↓
                        ┌─────────────────┐
                        │ NotebookSession │
                        ├─────────────────┤
                        │ • Load notebook │
                        │ • Apply filters │
                        │ • Get exhibit   │
                        │   data          │
                        └─────────────────┘
```

**Key files:**
- `app/notebook/markdown_parser.py` - Markdown parser
- `app/notebook/schema.py` - Type definitions
- `app/notebook/api/notebook_session.py` - Session management
- `app/notebook/filters/` - Filter system

---

### UI Application

```
┌──────────────────────────────────────────────────────────────┐
│                      Streamlit UI                             │
└──────────────────────────────────────────────────────────────┘

┌─────────────────┐     ┌──────────────────┐
│  Sidebar        │     │  Main Content    │
├─────────────────┤     ├──────────────────┤
│ • Navigation    │     │ • Tabs           │
│ • Filters       │     │ • Exhibits       │
│ • Theme toggle  │     │ • Edit mode      │
└─────────────────┘     └──────────────────┘

Components:
├── sidebar.py          - Notebook browser
├── filters.py          - Filter rendering
├── notebook_view.py    - Exhibit orchestration
└── exhibits/
    ├── metric_cards.py
    ├── line_chart.py
    ├── bar_chart.py
    └── data_table.py
```

**Key files:**
- `app/ui/notebook_app_duckdb.py` - Main app
- `app/ui/components/` - Reusable UI components

---

## Technology Stack

### Core Technologies

| Technology | Purpose | Version |
|-----------|---------|---------|
| **Python** | Primary language | 3.8+ |
| **DuckDB** | Analytics engine (default) | 0.9.0+ |
| **PySpark** | ETL engine (optional) | 3.4.0+ |
| **Parquet** | Storage format | via pyarrow |
| **Streamlit** | Web framework | 1.28.0+ |
| **Plotly** | Visualization | 5.17.0+ |

### Data Processing

| Library | Purpose |
|---------|---------|
| **pandas** | DataFrame manipulation |
| **pyarrow** | Parquet I/O |
| **pyyaml** | Configuration parsing |
| **markdown** | Notebook rendering |

### Analytics & ML

| Library | Purpose |
|---------|---------|
| **statsmodels** | ARIMA time series |
| **prophet** | Facebook Prophet forecasting |
| **scikit-learn** | ML models (Random Forest, etc.) |

### External APIs

| API | Purpose | Key Required |
|-----|---------|--------------|
| **Polygon** | Stock prices, news | Yes |
| **BLS** | Economic indicators | Optional |
| **Chicago Portal** | Municipal data | No |

---

## Data Models

de_Funk includes several pre-built models:

### 1. Core Model

**Purpose:** Shared dimensions used across models.

**Tables:**
- `dim_calendar` - Date dimension with calendar attributes

**Location:** `/storage/silver/core/`

---

### 2. Company Model

**Purpose:** Financial market data (stocks, prices, news).

**Dimensions:**
- `dim_company` - Companies (ticker, name, exchange)
- `dim_exchange` - Stock exchanges (NYSE, NASDAQ, etc.)

**Facts:**
- `fact_prices` - Daily stock prices and volume
- `fact_news` - News articles with sentiment

**Materialized views:**
- `prices_with_company` - Prices with company context
- `news_with_company` - News with company context

**Location:** `/storage/silver/company/`

---

### 3. Forecast Model

**Purpose:** Time series forecasting results.

**Dimensions:**
- `dim_model` - Forecast models (ARIMA, Prophet, RF)

**Facts:**
- `fact_forecasts` - Predictions with confidence intervals
- `fact_model_metrics` - Accuracy metrics (MAE, RMSE)

**Location:** `/storage/silver/forecast/`

---

### 4. Macro Model

**Purpose:** Economic indicators from BLS.

**Tables:**
- Employment data
- CPI (inflation)
- Unemployment rates

**Location:** `/storage/silver/macro/`

---

### 5. City Finance Model

**Purpose:** Municipal finance data from Chicago.

**Tables:**
- Budget data
- Revenue/expenses
- Department allocations

**Location:** `/storage/silver/city_finance/`

---

## Key Concepts

### Facets

**Facets** normalize API responses into DataFrames with consistent schemas.

**Example:**
```python
class PricesDailyFacet:
    def transform(self, response):
        return {
            "trade_date": response["t"],
            "ticker": response["T"],
            "open": response["o"],
            "close": response["c"],
            "volume": response["v"]
        }
```

**Purpose:**
- Decouple API format from storage schema
- Consistent naming conventions
- Type safety

---

### Models

**Models** define dimensional schemas and transformations.

**Key sections in model YAML:**
- `schema` - Dimensions and facts (source of truth)
- `measures` - Pre-defined aggregations
- `graph` - Transformation logic (nodes, edges, paths)

**Example:**
```yaml
# configs/models/company.yaml
schema:
  dimensions:
    dim_company:
      path: dims/dim_company
      columns: {ticker: string, company_name: string}
  facts:
    fact_prices:
      path: facts/fact_prices
      columns: {trade_date: date, ticker: string, close: double}

graph:
  nodes:
    - id: dim_company
      from: bronze.ref_ticker
      select: {ticker: ticker, company_name: name}
```

---

### Notebooks

**Notebooks** are Markdown files with inline filters and exhibits.

**Structure:**
```markdown
---
id: notebook_id
title: Notebook Title
models: [company]
---

# Heading

$filter${...}    # Inline filter definitions

$exhibits${...}  # Inline exhibit definitions
```

**Purpose:**
- Declarative analytics
- Version control friendly
- Shareable and reproducible

---

### Universal Session

**UniversalSession** provides a unified query interface across models.

**API:**
```python
session = UniversalSession(connection, storage_cfg, repo_root)

# Load model
session.load_model("company")

# Get table
df = session.get_table("company", "fact_prices")

# Get dimension
dim_df = session.get_dimension_df("company", "dim_company")

# List models
models = session.list_models()  # ['company', 'forecast', 'core']
```

**Purpose:**
- Multi-model queries
- Backend abstraction (DuckDB or Spark)
- Consistent API

---

## Typical Workflows

### 1. Data Ingestion Workflow

```
API → Facet → Bronze Layer → Model Builder → Silver Layer
```

**Steps:**
1. **Configure** - Set API keys in environment
2. **Run pipeline** - `python scripts/run_company_data_pipeline.py --days 30`
3. **Verify** - Check Bronze: `ls storage/bronze/polygon/prices_daily/`
4. **Build Silver** - `python test_build_silver.py`
5. **Verify** - Check Silver: `ls storage/silver/company/facts/fact_prices/`

---

### 2. Analytics Workflow

```
Silver Layer → DuckDB → Notebook → Streamlit UI
```

**Steps:**
1. **Start UI** - `./run_app.sh`
2. **Open notebook** - Click "stock_analysis"
3. **Apply filters** - Date range, tickers
4. **Analyze** - Review charts and metrics
5. **Download** - Export data as CSV

---

### 3. Development Workflow (Add New Dashboard)

```
Create Markdown → Define Filters/Exhibits → Refresh UI
```

**Steps:**
1. **Create** - `configs/notebooks/my_analysis.md`
2. **Define filters** - Inline `$filter${...}`
3. **Define exhibits** - Inline `$exhibits${...}`
4. **Refresh UI** - Reload Streamlit page
5. **Test** - Apply filters, verify results

---

## Performance Characteristics

### DuckDB vs Spark

| Metric | DuckDB | Spark |
|--------|--------|-------|
| **Query latency** | 10-75ms | 500-2000ms |
| **Startup time** | <1s | 5-15s |
| **Memory usage** | Efficient (in-process) | Higher (JVM overhead) |
| **Dataset size** | Up to 100GB | 100GB+ (distributed) |
| **Use case** | Interactive analytics | Large-scale ETL |

**Recommendation:**
- Use **DuckDB** for UI queries (default)
- Use **Spark** for large-scale data pipelines (optional)

---

### Storage Format

**Parquet benefits:**
- **Columnar** - Fast column scans (analytics workloads)
- **Compressed** - Typically 5-10x smaller than CSV
- **Schema** - Built-in schema metadata
- **Partitioned** - Skip irrelevant partitions (date-based)

**Example sizes:**
- CSV: 1GB
- Parquet (uncompressed): 400MB
- Parquet (compressed): 100MB

---

## Security Considerations

### API Keys

**Never commit API keys!**

**Best practices:**
1. Use environment variables: `export POLYGON_API_KEY="..."`
2. Use `.env` files (add to `.gitignore`)
3. Use secrets manager (production)

**Configuration:**
```bash
# Set environment variables
export POLYGON_API_KEY="your_key_here"
export BLS_API_KEY="your_key_here"

# Or use .env file
echo 'POLYGON_API_KEY="your_key_here"' > .env
```

---

### Data Access

**Silver layer is read-only in UI:**
- UI never modifies Silver data
- Bronze layer is immutable
- Pipelines create new files (append-only)

---

## Extensibility

### Adding New Data Sources

1. **Create Facet** - `datapipelines/facets/my_facet.py`
2. **Create Provider** - `datapipelines/providers/my_provider/`
3. **Update pipeline** - Reference new provider
4. **Run ingestion** - Data flows to Bronze

---

### Adding New Models

1. **Create YAML** - `configs/models/my_model.yaml`
2. **Define schema** - Dimensions, facts
3. **Define graph** - Nodes, edges, paths
4. **Build model** - Run model builder
5. **Query data** - Use UniversalSession

---

### Adding New Notebooks

1. **Create Markdown** - `configs/notebooks/my_notebook.md`
2. **Add front matter** - Metadata (id, title, models)
3. **Define filters** - Inline `$filter${...}`
4. **Define exhibits** - Inline `$exhibits${...}`
5. **Refresh UI** - Notebook appears in sidebar

---

## Next Steps

Now that you understand the architecture:

### Learn More

- **[Installation Guide](installation.md)** - Complete setup for production
- **[Quickstart Guide](quickstart.md)** - Get running in 5 minutes
- **[How-To Guides](how-to/README.md)** - Step-by-step tutorials

### Dive Deeper

- **[Models Documentation](../../2-models/README.md)** - Detailed model docs
- **[Architecture Deep Dive](../../3-architecture/README.md)** - Component internals
- **[Development Guide](../../4-development/README.md)** - Extending the platform

---

## Glossary

| Term | Definition |
|------|------------|
| **Bronze Layer** | Raw data from APIs, stored as Parquet |
| **Silver Layer** | Dimensional models (facts + dimensions) |
| **Gold Layer** | Application-specific views (UI, reports) |
| **Facet** | Transform API response → DataFrame |
| **Model** | YAML-defined dimensional schema |
| **Notebook** | Markdown file with filters and exhibits |
| **Exhibit** | Visualization (chart, table, metric) |
| **Filter** | User input for data filtering |
| **Session** | Query interface for data access |
| **DuckDB** | Fast in-memory analytics engine |
| **Spark** | Distributed data processing engine |
| **Parquet** | Columnar storage format |

---

**Continue to:** [Installation Guide](installation.md) →
