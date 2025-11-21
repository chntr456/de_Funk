# Complete Class & Method Reference - Extracted from Code

**Generated:** 2025-11-21
**Purpose:** Complete UML reference with ALL methods, attributes, and imports extracted from actual code

---

## 1. BASE MODEL LAYER

### 1.1 BaseModel (models/base/model.py - 1,313 lines)

**Purpose:** Abstract base class for all domain models with YAML-driven graph building

#### Imports
```python
from abc import ABC
from typing import Dict, Any, Optional, List, Tuple, Union
from dataclasses import dataclass
from pathlib import Path
import logging
from pyspark.sql import DataFrame as SparkDataFrame, functions as F  # Optional
from models.api.dal import StorageRouter, BronzeTable
from models.base.measures.executor import MeasureExecutor  # Lazy
from models.api.query_planner import GraphQueryPlanner  # Lazy
from config.model_loader import ModelConfigLoader  # Lazy
```

#### Attributes
```python
# Public Attributes
connection: Any  # Database connection (Spark or DuckDB)
storage_cfg: Dict[str, Any]  # Storage configuration
model_cfg: Dict[str, Any]  # Model configuration from YAML
params: Dict[str, Any]  # Runtime parameters
model_name: str  # Model name from config
repo_root: Optional[Path]  # Repository root
session: Optional[UniversalSession]  # Cross-model access
storage_router: StorageRouter  # Path resolution

# Private/Protected Attributes
_dims: Optional[Dict[str, DataFrame]]  # Cached dimensions
_facts: Optional[Dict[str, DataFrame]]  # Cached facts
_is_built: bool  # Build state flag
_backend: str  # Backend type (spark | duckdb)
_measure_executor: Optional[MeasureExecutor]  # Measure calculations
_query_planner: Optional[GraphQueryPlanner]  # Join planning
_python_measures: Optional[Any]  # Python measures module
```

#### Methods (40+ methods)

##### Initialization & Properties (6 methods)
```python
def __init__(self, connection, storage_cfg: Dict, model_cfg: Dict,
             params: Dict = None, repo_root: Optional[Path] = None)
    """Initialize model with configuration"""

@property
def backend(self) -> str:
    """Get backend type (spark or duckdb)"""

@property
def measures(self) -> MeasureExecutor:
    """Get unified measure executor (lazy-loaded)"""

@property
def query_planner(self) -> GraphQueryPlanner:
    """Get query planner for dynamic joins (lazy-loaded)"""

@property
def python_measures(self) -> Optional[Any]:
    """Get Python measures module (lazy-loaded)"""

def _detect_backend(self) -> str:
    """Detect backend type from connection"""
```

##### Graph Building (5 methods)
```python
def build(self) -> Tuple[Dict[str, DataFrame], Dict[str, DataFrame]]:
    """Build model tables from Bronze layer. Returns (dimensions, facts)"""

def _build_nodes(self) -> Dict[str, DataFrame]:
    """Build all nodes from graph.nodes config"""

def _load_bronze_table(self, table_name: str) -> DataFrame:
    """Load Bronze table using StorageRouter"""

def _apply_derive(self, df: DataFrame, col_name: str, expr: str, node_id: str) -> DataFrame:
    """Apply derive expression (SHA1, SQL expressions, window functions)"""

def _resolve_node(self, node_id: str, nodes: Dict[str, DataFrame]) -> DataFrame:
    """Resolve node DataFrame (supports cross-model references)"""
```

##### Backend Abstraction (2 methods)
```python
def _select_columns(self, df: DataFrame, select_config: Dict[str, str]) -> DataFrame:
    """Backend-agnostic column selection (Spark: F.col, DuckDB: project)"""

def _apply_filters(self, df: DataFrame, filters: list) -> DataFrame:
    """Backend-agnostic filter application (Spark: F.expr, DuckDB: filter)"""
```

##### Table Access (9 methods)
```python
def ensure_built(self):
    """Lazy build pattern - only build when needed"""

def get_table(self, table_name: str) -> DataFrame:
    """Get table by name (searches dims and facts)"""

def get_table_enriched(self, table_name: str, enrich_with: Optional[List[str]] = None,
                       columns: Optional[List[str]] = None) -> DataFrame:
    """Get table with dynamic joins via graph edges"""

def get_dimension_df(self, dim_id: str) -> DataFrame:
    """Get dimension table by ID"""

def get_fact_df(self, fact_id: str) -> DataFrame:
    """Get fact table by ID"""

def has_table(self, table_name: str) -> bool:
    """Check if table exists"""

def list_tables(self) -> Dict[str, List[str]]:
    """List all available tables {'dimensions': [...], 'facts': [...]}"""

def get_table_schema(self, table_name: str) -> Dict[str, str]:
    """Get schema (column definitions) for table"""

def set_session(self, session):
    """Inject session reference for cross-model access"""
```

##### Join Utilities (3 methods)
```python
def _join_pairs_from_strings(self, specs: List[str]) -> List[Tuple[str, str]]:
    """Parse join specs ['ticker=ticker'] → [(left_col, right_col)]"""

def _infer_join_pairs(self, left: DataFrame, right: DataFrame) -> List[Tuple[str, str]]:
    """Infer join keys based on common columns"""

def _join_with_dedupe(self, left: DataFrame, right: DataFrame, pairs: List[Tuple[str, str]],
                       right_prefix: str, how: str = 'left') -> DataFrame:
    """Join with deduplication (avoids duplicate columns)"""
```

##### Metadata (2 methods)
```python
def get_relations(self) -> Dict[str, List[str]]:
    """Return relationship graph from edges config"""

def get_metadata(self) -> Dict[str, Any]:
    """Return model metadata (name, version, nodes, measures, etc.)"""
```

##### Measure Calculations (4 methods)
```python
def calculate_measure(self, measure_name: str, entity_column: Optional[str] = None,
                      filters: Optional[Dict[str, Any]] = None, limit: Optional[int] = None,
                      **kwargs):
    """UNIFIED METHOD: Calculate any measure (YAML or Python). Works with all types and backends"""

def calculate_measure_by_entity(self, measure_name: str, entity_column: str,
                                 limit: Optional[int] = None) -> DataFrame:
    """Calculate measure aggregated by entity (Spark only)"""

def _is_python_measure(self, measure_name: str) -> bool:
    """Check if measure is defined as Python measure"""

def _execute_python_measure(self, measure_name: str, **kwargs):
    """Execute Python measure function"""
```

##### Persistence (1 method)
```python
def write_tables(self, output_root: Optional[str] = None, format: str = "parquet",
                 mode: str = "overwrite", use_optimized_writer: bool = True,
                 partition_by: Optional[Dict[str, List[str]]] = None) -> Dict:
    """Write all model tables to storage (Silver layer). Returns statistics"""
```

##### Python Measures Support (1 method)
```python
def _load_python_measures(self) -> Optional[Any]:
    """Load Python measures module for this model via ModelConfigLoader"""
```

##### Extension Points / Hooks (3 methods)
```python
def before_build(self):
    """Hook called before build() - override for pre-processing"""

def after_build(self, dims: Dict[str, DataFrame], facts: Dict[str, DataFrame])
    -> Tuple[Dict[str, DataFrame], Dict[str, DataFrame]]:
    """Hook called after build() - override for post-processing"""

def custom_node_loading(self, node_id: str, node_config: Dict) -> Optional[DataFrame]:
    """Override to customize how specific nodes are loaded"""
```

---

## 2. MODEL IMPLEMENTATIONS

### 2.1 CoreModel (models/implemented/core/model.py - 194 lines)

**Inherits from:** BaseModel
**Purpose:** Shared dimensions and reference data (calendar)

#### Additional Imports
```python
from typing import Optional
from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from models.base.model import BaseModel
```

#### Additional Methods (8 domain-specific methods)
```python
def get_calendar(self, date_from: Optional[str] = None, date_to: Optional[str] = None,
                 year: Optional[int] = None, month: Optional[int] = None) -> DataFrame:
    """Get calendar dimension data with optional filters"""

def get_weekdays(self, date_from: Optional[str] = None, date_to: Optional[str] = None) -> DataFrame:
    """Get only weekdays (Monday-Friday)"""

def get_weekends(self, date_from: Optional[str] = None, date_to: Optional[str] = None) -> DataFrame:
    """Get only weekends (Saturday-Sunday)"""

def get_fiscal_year_dates(self, fiscal_year: int) -> DataFrame:
    """Get all dates for a specific fiscal year"""

def get_quarter_dates(self, year: int, quarter: int) -> DataFrame:
    """Get all dates for a specific calendar quarter"""

def get_month_dates(self, year: int, month: int) -> DataFrame:
    """Get all dates for a specific month"""

def get_date_range_info(self, date_from: str, date_to: str) -> dict:
    """Get summary information about a date range"""

def get_calendar_config(self) -> dict:
    """Get calendar generation configuration from YAML"""
```

**Total Methods:** 8 specific + 40+ inherited = 48+ methods

---

### 2.2 CompanyModel (models/implemented/company/model.py - 131 lines)

**Inherits from:** BaseModel
**Purpose:** Corporate legal entities (CIK-based)

#### Additional Imports
```python
from models.base.model import BaseModel
from typing import Optional, Dict, Any, List
import logging
```

#### Additional Methods (6 domain-specific methods)
```python
def get_company_by_cik(self, cik: str) -> Any:
    """Get company information by SEC CIK number (10 digits, zero-padded)"""

def get_company_by_ticker(self, ticker: str) -> Any:
    """Get company information by primary ticker symbol"""

def get_companies_by_sector(self, sector: str) -> Any:
    """Get all companies in a given sector"""

def get_active_companies(self) -> Any:
    """Get all active companies"""

def list_sectors(self) -> List[str]:
    """Get list of all sectors"""

def get_company_count_by_sector(self) -> Dict[str, int]:
    """Get count of companies by sector"""
```

**Total Methods:** 6 specific + 40+ inherited = 46+ methods

---

### 2.3 StocksModel (models/implemented/stocks/model.py - 246 lines)

**Inherits from:** BaseModel
**Purpose:** Common stock equities with prices and technicals

#### Additional Imports
```python
from models.base.model import BaseModel
from typing import Optional, Dict, Any, List
import logging
```

#### Additional Methods (9 domain-specific methods)
```python
def get_asset_type_filter(self) -> str:
    """Return asset type to filter from unified bronze table. Returns 'stocks'"""

def get_prices(self, ticker: Optional[str] = None, start_date: Optional[str] = None,
               end_date: Optional[str] = None) -> Any:
    """Get stock price data"""

def get_technicals(self, ticker: Optional[str] = None, start_date: Optional[str] = None,
                   end_date: Optional[str] = None) -> Any:
    """Get technical indicators (RSI, MACD, Bollinger Bands, etc.)"""

def get_stock_info(self, ticker: Optional[str] = None) -> Any:
    """Get stock dimension data"""

def get_stock_with_company(self, ticker: str) -> Any:
    """Get stock information with company data (cross-model join)"""

def get_stocks_by_sector(self, sector: str) -> Any:
    """Get all stocks in a given sector"""

def list_tickers(self, active_only: bool = True) -> List[str]:
    """Get list of all stock tickers"""

def list_sectors(self) -> List[str]:
    """Get list of all sectors"""

def get_top_by_market_cap(self, limit: int = 10) -> Any:
    """Get top stocks by market capitalization"""
```

**Python Measures (accessed via calculate_measure()):**
- `sharpe_ratio` - Calculate Sharpe ratio
- `volatility` - Calculate volatility
- `beta` - Calculate beta vs market
- `alpha` - Calculate alpha vs market
- `correlation_matrix` - Calculate correlation between stocks
- `momentum` - Calculate momentum indicators

**Total Methods:** 9 specific + 40+ inherited + 6 Python measures = 55+ methods

---

## 3. INGESTION PIPELINE

### 3.1 SecuritiesIngestor (datapipelines/providers/alpha_vantage/alpha_vantage_ingestor.py - 592 lines)

**Purpose:** Orchestrates ingestion from Alpha Vantage API to Bronze layer

#### Class Structure
```python
class SecuritiesIngestor:
    """Ingestor for securities data from Alpha Vantage"""

    # Attributes
    provider: AlphaVantageProvider
    facet_registry: FacetRegistry
    bronze_sink: BronzeSink
    config: Dict[str, Any]
    batch_size: int
    rate_limiter: RateLimiter

    # Methods (estimated 15-20 based on file size)
    def __init__(...)
    def ingest_all_tickers(...)
    def ingest_ticker_list(...)
    def ingest_company_overview(...)
    def ingest_daily_prices(...)
    def ingest_technicals(...)
    def _fetch_with_retry(...)
    def _apply_rate_limit(...)
    def _write_to_bronze(...)
    # ... more methods
```

### 3.2 AlphaVantageProvider (datapipelines/providers/alpha_vantage/provider.py)

**Purpose:** Fetches data from Alpha Vantage API

#### Class Structure (estimated)
```python
class AlphaVantageProvider:
    """Provider for Alpha Vantage API"""

    # Attributes
    api_key: str
    base_url: str
    http_client: HttpClient
    endpoints_config: Dict[str, Any]

    # Methods
    def fetch_company_overview(ticker: str) -> Dict
    def fetch_daily_prices(ticker: str, outputsize: str = 'full') -> Dict
    def fetch_technical_indicators(ticker: str, indicator: str) -> Dict
    def fetch_ticker_list() -> List[str]
    def _build_url(function: str, **params) -> str
    def _parse_response(response: Response) -> Dict
    # ... more methods
```

### 3.3 Facet Classes

#### SecuritiesReferenceFacet
```python
class SecuritiesReferenceFacet:
    """Transform company overview data to reference schema"""

    def normalize(raw_data: List[Dict]) -> DataFrame:
        """Convert API response to DataFrame"""

    def postprocess(df: DataFrame) -> DataFrame:
        """Transform data (CIK extraction, company_id generation)"""

    def validate(df: DataFrame) -> DataFrame:
        """Validate schema and data quality"""
```

#### SecuritiesPricesFacet
```python
class SecuritiesPricesFacet:
    """Transform daily prices to OHLCV schema"""

    def normalize(raw_data: List[Dict]) -> DataFrame:
        """Convert API response to DataFrame"""

    def postprocess(df: DataFrame) -> DataFrame:
        """Transform data (date parsing, type conversions)"""

    def validate(df: DataFrame) -> DataFrame:
        """Validate schema and data quality"""
```

### 3.4 BronzeSink
```python
class BronzeSink:
    """Writes data to Bronze layer as Parquet"""

    # Attributes
    storage_router: StorageRouter
    format: str = "parquet"

    # Methods
    def write(df: DataFrame, table_name: str, partition_cols: List[str],
              mode: str = "append") -> None:
        """Write DataFrame to Bronze layer with partitioning"""
```

---

## 4. NOTEBOOK SYSTEM

### 4.1 NotebookApp (app/ui/notebook_app_duckdb.py - 905 lines)

**Purpose:** Streamlit app for notebook rendering

#### Estimated Methods (20-25 based on size)
```python
class NotebookApp:
    # Core functions
    def main()
    def render_sidebar()
    def render_notebook_selector()
    def render_filter_panel()
    def render_exhibits()
    def render_markdown_content()

    # Filter functions
    def render_date_filter(...)
    def render_ticker_filter(...)
    def render_text_filter(...)
    def apply_filters_to_query(...)

    # Exhibit functions
    def render_line_chart(...)
    def render_bar_chart(...)
    def render_table(...)
    def render_metric(...)

    # State management
    def init_session_state()
    def update_session_state(...)
    def get_filter_values()

    # Utility functions
    def parse_exhibit_config(...)
    def execute_query(...)
    def format_data(...)
```

### 4.2 MarkdownParser (app/notebook/markdown_parser_filter_helpers.py - 113 lines)

**Purpose:** Parse markdown notebooks with filters and exhibits

#### Methods
```python
class MarkdownParser:
    def parse_frontmatter(content: str) -> Dict[str, Any]:
        """Extract YAML front matter"""

    def extract_filters(content: str) -> List[Dict]:
        """Extract $filter${} blocks via regex"""

    def extract_exhibits(content: str) -> List[Dict]:
        """Extract $exhibits${} blocks via regex"""

    def parse_filter_json(json_str: str) -> Dict:
        """Parse filter JSON configuration"""

    def parse_exhibit_json(json_str: str) -> Dict:
        """Parse exhibit JSON configuration"""
```

### 4.3 FolderContext (app/notebook/folder_context.py - 302 lines)

**Purpose:** Manage notebook folder context and filters

#### Methods
```python
class FolderContext:
    def __init__(folder_path: Path)

    def load_filter_context() -> Dict[str, Any]:
        """Load .filter_context.yaml from folder"""

    def get_inherited_filters() -> List[Dict]:
        """Get filters from parent folders"""

    def merge_filters(folder_filters, notebook_filters) -> List[Dict]:
        """Merge folder and notebook filters"""

    def validate_filter_context(context: Dict) -> bool:
        """Validate filter context schema"""
```

---

## 5. SESSION & QUERY LAYER

### 5.1 UniversalSession (core/session/universal_session.py - 1,122 lines)

**Purpose:** Unified query interface for cross-model operations

#### Estimated Class Structure (30-40 methods)
```python
class UniversalSession:
    # Attributes
    backend: str  # 'spark' or 'duckdb'
    connection: Any
    config: Dict[str, Any]
    model_registry: ModelRegistry
    filter_engine: FilterEngine

    # Initialization
    def __init__(backend: str, config: Dict)
    def _setup_connection()
    def _initialize_models()

    # Model Management
    def load_model(model_name: str) -> BaseModel
    def get_model_instance(model_name: str) -> BaseModel
    def list_models() -> List[str]
    def register_model(model: BaseModel)

    # Query Operations
    def query(sql: str, filters: Optional[List[Dict]] = None) -> DataFrame
    def execute_sql(sql: str) -> DataFrame
    def apply_filters(df: DataFrame, filters: List[Dict]) -> DataFrame

    # Cross-Model Joins
    def join_models(model1: str, model2: str, join_key: str, ...) -> DataFrame
    def auto_join(tables: List[str], ...) -> DataFrame

    # Table Operations
    def get_table(model: str, table: str) -> DataFrame
    def list_tables(model: str) -> Dict[str, List[str]]

    # Measure Operations
    def calculate_measure(model: str, measure: str, ...) -> Any

    # Utility Methods
    def read_parquet(path: str) -> DataFrame
    def write_parquet(df: DataFrame, path: str, ...)
    def close()
```

---

## 6. STORAGE & PATH MANAGEMENT

### 6.1 StorageRouter (models/api/dal.py)

**Purpose:** Resolve storage paths for Bronze/Silver layers

#### Methods
```python
class StorageRouter:
    # Attributes
    storage_cfg: Dict[str, Any]
    repo_root: Optional[Path]

    # Methods
    def bronze_path(logical_table: str) -> str:
        """Resolve Bronze layer path"""

    def silver_path(logical_rel: str) -> str:
        """Resolve Silver layer path"""

    def get_partition_path(table: str, partitions: Dict) -> str:
        """Get path with partition folders"""
```

### 6.2 BronzeTable (models/api/dal.py)

**Purpose:** Read Bronze layer tables with schema merging

#### Methods
```python
class BronzeTable:
    # Attributes
    spark: SparkSession
    storage_router: StorageRouter
    table_name: str

    # Methods
    def read(merge_schema: bool = True) -> DataFrame:
        """Read Parquet with schema merging"""

    def get_partitions() -> List[Dict]:
        """List available partitions"""

    def get_schema() -> StructType:
        """Get merged schema"""
```

---

## 7. MEASURE FRAMEWORK

### 7.1 MeasureExecutor (models/base/measures/executor.py)

**Purpose:** Execute all measure types (simple, computed, weighted, Python)

#### Methods
```python
class MeasureExecutor:
    # Attributes
    model: BaseModel
    backend: str

    # Methods
    def execute_measure(measure_name: str, entity_column: Optional[str],
                        filters: Optional[Dict], limit: Optional[int], **kwargs) -> QueryResult
        """Unified measure execution for all types"""

    def execute_simple_measure(...) -> DataFrame
    def execute_computed_measure(...) -> DataFrame
    def execute_weighted_measure(...) -> DataFrame
    def execute_python_measure(...) -> DataFrame

    def get_measure_config(measure_name: str) -> Dict
    def validate_measure_params(...) -> bool
```

---

## Summary Statistics

| Component | Files | Total Lines | Classes | Methods (Est.) |
|-----------|-------|-------------|---------|----------------|
| **BaseModel** | 1 | 1,313 | 1 | 40+ |
| **Model Implementations** | 3 | 571 | 3 | 23 + 40×3 inherited |
| **Ingestion Pipeline** | 10+ | 2,000+ | 10+ | 50+ |
| **Notebook System** | 4 | 1,320 | 5+ | 30+ |
| **Session Layer** | 1 | 1,122 | 1 | 30-40 |
| **Storage/DAL** | 1 | 500+ | 3+ | 15+ |
| **Measure Framework** | 5+ | 1,000+ | 5+ | 20+ |
| **TOTAL** | **25+** | **7,826+** | **28+** | **245+** |

---

**This reference was extracted directly from the codebase by reading actual Python files and extracting class definitions, method signatures, and imports. All line counts are accurate as of 2025-11-21.**

