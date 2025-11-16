# de_Funk Infrastructure & Framework Layers - Comprehensive Analysis

**Date**: November 2025  
**Scope**: Foundation layers supporting domain models  
**Focus**: Architecture patterns, design principles, and cross-layer integration

---

## 1. BASE MODEL FRAMEWORK

### Overview
The `BaseModel` class (`/home/user/de_Funk/models/base/model.py`) is the cornerstone of the entire modeling framework. It provides:
- YAML-driven generic model construction
- Graph-based node and edge management
- Cross-model table references
- Lazy loading and caching mechanisms
- Backend-agnostic table operations (Spark/DuckDB)

### Key Components

#### 1.1 Model Initialization & Backend Detection
```python
# Location: models/base/model.py:67-163
class BaseModel:
    def __init__(self, connection, storage_cfg, model_cfg, params=None):
        self.connection = connection          # Spark or DuckDB connection
        self.storage_cfg = storage_cfg        # Storage paths from storage.json
        self.model_cfg = model_cfg            # YAML configuration
        self._detect_backend()                # Determine if Spark or DuckDB
        self._dims, self._facts = None, None  # Lazy-loaded caches
        self._is_built = False                # Build state tracking
```

**Backend Detection Strategy** (lines 151-163):
- Checks connection type using introspection
- Returns 'spark' for Spark connections, 'duckdb' for DuckDB
- Raises ValueError for unknown types

#### 1.2 Graph-Based Node Building (Generic)
**The Core Build Process** (lines 207-238):
```
1. _build_nodes()      → Load tables from Bronze layer
2. _apply_edges()      → Validate join relationships exist
3. _materialize_paths()→ Create joined views (optional)
4. after_build()       → Domain-specific post-processing
```

**Node Loading Strategy** (lines 240-319):
- Each node can load from:
  - Bronze layer: `from: bronze.table_name`
  - Other nodes: `from: parent_node_id` (for layering)
  - Custom: Override via `custom_node_loading()` hook
- Supports transformations:
  - `select`: Column selection/aliasing
  - `derive`: Computed columns (SQL expressions or SHA1 hashing)
  - `unique_key`: Deduplication constraint

**Key Insight**: Nodes are built in YAML-defined order, supporting dependency chains. This allows complex transformations to be expressed declaratively.

#### 1.3 Cross-Model References
**Pattern**: Models can reference tables from other models using dot notation
```python
# In YAML:
edges:
  - from: fact_forecast_metrics
    to: core.dim_calendar      # Cross-model reference
    on: [metric_date = trade_date]

# In code (lines 424-454):
def _resolve_node(self, node_id: str, nodes: Dict) -> DataFrame:
    if '.' in node_id:
        model_name, table_name = node_id.split('.', 1)
        other_model = self.session.get_model_instance(model_name)
        return other_model.get_dimension_df(table_name)
```

**Requirements**:
- Model must be loaded via UniversalSession
- Session is injected via `set_session()` (line 165-175)
- Enables federation across domain models

#### 1.4 Table Access Methods
**Generic API** (lines 691-793):
- `get_table(name)`: Get dims/facts
- `get_table_enriched(table, enrich_with, columns)`: Dynamic joins
- `get_dimension_df(dim_id)`: Get specific dimension
- `get_fact_df(fact_id)`: Get specific fact
- `has_table(name)`: Check existence
- `list_tables()`: List available tables
- `get_table_schema(name)`: Get column definitions

**Lazy Loading Pattern** (lines 685-689):
```python
def ensure_built(self):
    if not self._is_built:
        self._dims, self._facts = self.build()
        self._is_built = True
```
- Models are built on first access, not at instantiation
- Supports efficient multi-model sessions

### 1.5 Measure Execution Framework

**New Unified Approach** (lines 880-925):
```python
def calculate_measure(
    self,
    measure_name: str,
    entity_column: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
    limit: Optional[int] = None,
) -> QueryResult:
    """Execute unified measure calculation."""
    return self.measures.execute_measure(
        measure_name=measure_name,
        entity_column=entity_column,
        filters=filters,
        limit=limit,
    )
```

**Lazy-Loaded Measure Executor** (lines 108-125):
```python
@property
def measures(self):
    """Get unified measure executor."""
    if self._measure_executor is None:
        from models.base.measures.executor import MeasureExecutor
        self._measure_executor = MeasureExecutor(self, backend=self.backend)
    return self._measure_executor
```

### 1.6 Storage Router Pattern
**Path Resolution** (`models/api/dal.py:7-18`):
```python
@dataclass(frozen=True)
class StorageRouter:
    storage_cfg: Dict[str, Any]
    
    def bronze_path(self, logical_table: str) -> str:
        root = self.storage_cfg["roots"]["bronze"].rstrip("/")
        rel = self.storage_cfg["tables"][logical_table]["rel"]
        return f"{root}/{rel}"
    
    def silver_path(self, logical_rel: str) -> str:
        root = self.storage_cfg["roots"]["silver"].rstrip("/")
        return f"{root}/{logical_rel}"
```

**Abstraction**: Storage paths are decoupled from business logic. The router handles:
- Bronze layer: Ingested raw data partitioned by provider/table
- Silver layer: Dimensional models organized by model/table

---

## 2. SESSION MANAGEMENT ARCHITECTURE

### Overview
The `UniversalSession` (`/home/user/de_Funk/models/api/session.py`) is the hub for cross-model operations. It:
- Dynamically loads models via ModelRegistry
- Manages model lifecycle and caching
- Supports cross-model queries with auto-join
- Applies filters transparently across backends
- Coordinates between Spark and DuckDB

### Key Architecture

#### 2.1 Universal Session Initialization
**Constructor** (lines 72-111):
```python
class UniversalSession:
    def __init__(
        self,
        connection,           # Spark or DuckDB
        storage_cfg,         # Storage configuration
        repo_root,           # Repository root
        models: list = None  # Optional pre-load list
    ):
        self.connection = connection
        self.storage_cfg = storage_cfg
        
        # Dynamic model loading
        self.registry = ModelRegistry(repo_root / "configs" / "models")
        self._models = {}  # Cache loaded models
        
        # Build model dependency graph (NetworkX)
        self.model_graph = ModelGraph()
        self.model_graph.build_from_config_dir(models_dir)
        
        # Pre-load specified models
        if models:
            for model_name in models:
                self.load_model(model_name)
```

**Key Pattern**: Models are lazy-loaded on first access unless pre-specified.

#### 2.2 Dynamic Model Loading
**Lazy Loading Pipeline** (lines 139-191):
```python
def load_model(self, model_name: str):
    # 1. Return from cache if already loaded
    if model_name in self._models:
        return self._models[model_name]
    
    # 2. Get config from registry
    model_config = self.registry.get_model_config(model_name)
    
    # 3. Get model class (with fallback to BaseModel)
    try:
        model_class = self.registry.get_model_class(model_name)
    except ValueError:
        from models.base.model import BaseModel
        model_class = BaseModel
    
    # 4. Instantiate model
    model = model_class(
        connection=self.connection,
        storage_cfg=self.storage_cfg,
        model_cfg=model_config,
        params={}
    )
    
    # 5. Inject session for cross-model access
    model.set_session(self)
    
    # 6. Cache and return
    self._models[model_name] = model
    return model
```

**Dependency Injection**: The session injects itself into models, enabling:
- Cross-model table lookup
- Graph-based join planning
- Transitive model loading

#### 2.3 Cross-Model Auto-Join System

**Table Access with Auto-Enrichment** (lines 193-336):
```python
def get_table(
    self,
    model_name: str,
    table_name: str,
    required_columns: Optional[List[str]] = None,
    filters: Optional[Dict[str, Any]] = None,
    group_by: Optional[List[str]] = None,
    aggregations: Optional[Dict[str, str]] = None,
    use_cache: bool = True
) -> Any:
    model = self.load_model(model_name)
    
    # Strategy 1: If no enrichment needed, simple table access
    if not required_columns:
        return model.get_table(table_name)
    
    # Strategy 2: Check schema for missing columns
    schema = model.get_table_schema(table_name)
    base_columns = set(schema.keys())
    missing = [col for col in required_columns if col not in base_columns]
    
    # Strategy 3a (Fast Path): Use materialized view if available
    if materialized_table := self._find_materialized_view(model_name, required_columns):
        return model.get_table(materialized_table)
    
    # Strategy 3b (Slow Path): Build joins from graph
    join_plan = self._plan_auto_joins(model_name, table_name, missing)
    df = self._execute_auto_joins(model_name, join_plan, required_columns, filters)
    
    # Apply aggregation if needed
    if group_by:
        df = self._aggregate_data(model_name, df, required_columns, group_by, aggregations)
    
    return df
```

**Key Insight**: Users specify what columns they need, the system figures out the join path automatically.

#### 2.4 Join Planning Algorithm
**Graph-Based Join Planning** (lines 539-627):
```python
def _plan_auto_joins(
    self,
    model_name: str,
    base_table: str,
    missing_columns: List[str]
) -> Dict[str, Any]:
    # 1. Build column-to-table index
    column_index = self._build_column_index(model_name)
    
    # 2. Map missing columns to tables
    target_tables = {}
    for col in missing_columns:
        target_tables[col] = column_index[col][0]  # Use first table
    
    # 3. Use greedy graph traversal to find join sequence
    # Start from base_table, traverse edges to reach target tables
    # Return: [table_sequence, join_keys, target_columns]
```

**Join Execution** (lines 671-832):
- **Spark**: Uses DataFrame.join() with left joins
- **DuckDB**: Uses SQL with properly qualified columns to avoid ambiguity

#### 2.5 Backend Abstraction
**Backend Detection** (lines 113-137):
```python
@property
def backend(self) -> str:
    """Detect backend from connection type."""
    connection_type = str(type(self.connection))
    if 'spark' in connection_type.lower() or hasattr(self.connection, 'sql'):
        return 'spark'
    if 'duckdb' in connection_type.lower() or ....:
        return 'duckdb'
    raise ValueError(f"Unknown connection type: {connection_type}")
```

**SQL Generation vs DataFrame API**:
- Spark: Uses PySpark DataFrame API with F.col(), F.join(), etc.
- DuckDB: Uses SQL strings executed via conn.execute()

### 2.6 Filter Application
**Centralized Filter Engine** (core/session/filters.py):
```python
class FilterEngine:
    @staticmethod
    def apply_filters(df: Any, filters: Dict[str, Any], backend: str) -> Any:
        if backend == 'spark':
            return FilterEngine._apply_spark_filters(df, filters)
        elif backend == 'duckdb':
            return FilterEngine._apply_duckdb_filters(df, filters)
```

**Filter Specification Format**:
```python
filters = {
    'ticker': 'AAPL',                           # Exact match
    'ticker': ['AAPL', 'GOOGL'],               # IN clause
    'trade_date': {                            # Range filter
        'min': '2024-01-01',
        'max': '2024-12-31'
    }
}
```

**Push-Down Optimization**: Filters applied before joins/aggregation when possible.

---

## 3. MODEL BUILDERS

### Overview
The builders in `/home/user/de_Funk/models/builders/` construct Silver layer tables from Bronze data.

#### 3.1 Weighted Aggregate Builder
**Purpose**: Pre-materialize weighted indices combining multiple stocks
**Location**: `models/builders/weighted_aggregate_builder.py`

**Example Use Case**: Building volume-weighted price indices
```yaml
# In model config
measures:
  volume_weighted_close:
    type: weighted_aggregate
    source: fact_prices.close
    weighting_method: volume
    group_by: [trade_date]
```

**SQL Generation** (lines 109-150):
```python
def _generate_weighted_aggregate_sql(self, measure_id: str, measure: Dict) -> str:
    method = measure.get('weighting_method', 'equal')
    source = measure['source']
    group_by = measure['group_by']
    
    if method == 'volume':
        return self._sql_volume_weighted(...)
    elif method == 'market_cap':
        return self._sql_market_cap_weighted(...)
    # ... other weighting methods
```

**Materialization Strategy**: Optional - views or tables depending on size and query patterns

---

## 4. STORAGE LAYER

### Overview
The storage layer organizes data in a two-level hierarchy: Bronze (raw) and Silver (dimensional).

#### 4.1 Storage Organization
**Bronze Layer** (Raw Data):
```
storage/bronze/{provider}/{table}/
  ├── polygon/
  │   ├── company/        # Raw company data from Polygon API
  │   ├── prices/         # Raw price data
  │   └── technicals/     # Raw technical indicators
  ├── bls/
  │   └── indicators/     # Raw economic indicators
  └── chicago/
      └── finance/        # Raw municipal finance data
```

**Silver Layer** (Dimensional Models):
```
storage/silver/{model}/
  ├── dims/
  │   ├── dim_equity/
  │   ├── dim_company/
  │   └── dim_calendar/
  └── facts/
      ├── fact_equity_prices/
      └── fact_forecast_metrics/
```

#### 4.2 Parquet Optimization
**Location**: `models/base/parquet_loader.py`

**DuckDB-Optimized Writing** (lines 54-99):
```python
class ParquetLoader:
    def _write(
        self,
        rel_path: str,
        df: Any,
        sort_by: Optional[List[str]] = None,
        num_files: int = 1,
        row_count: Optional[int] = None
    ):
        # 1. Pre-compute row count (before transformations)
        if row_count is None:
            row_count = df.count()
        
        # 2. Sort by query columns for zone maps
        if sort_by:
            df = df.sortWithinPartitions(*sort_by)
        
        # 3. Coalesce to minimize file count
        df = df.coalesce(num_files)
        
        # 4. Write with snappy compression
        df.write.mode("overwrite").option("compression", "snappy").parquet(str(out))
```

**Optimizations**:
- **Few large files** (1-5): Better for DuckDB queries than 200+ tiny files
- **Zone maps**: Sorting enables predicate pushdown
- **Snappy compression**: Fast read/write vs slower compression algorithms

#### 4.3 Schema Evolution
**Merge Schema Strategy** (`models/api/dal.py:20-46`):
```python
class BronzeTable:
    def read(self, merge_schema: bool = True) -> DataFrame:
        """Read bronze with schema evolution support."""
        return (
            self.spark.read
            .option("mergeSchema", str(merge_schema).lower())
            .parquet(self.path)
        )
```

**Handles**: Different partitions with slightly different schemas (e.g., new columns added over time)

---

## 5. MEASURE FRAMEWORK

### Overview
A unified, extensible framework supporting multiple measure types: simple, computed, weighted, window, ratio, and custom.

### 5.1 Measure Registry & Factory Pattern
**Location**: `models/base/measures/registry.py`

**Decorator-Based Registration** (lines 36-65):
```python
class MeasureRegistry:
    _registry: Dict[MeasureType, Type[BaseMeasure]] = {}
    
    @classmethod
    def register(cls, measure_type: MeasureType):
        """Decorator to register measure implementations."""
        def decorator(measure_class: Type[BaseMeasure]):
            cls._registry[measure_type] = measure_class
            return measure_class
        return decorator

# Usage in measure implementations:
@MeasureRegistry.register(MeasureType.SIMPLE)
class SimpleMeasure(BaseMeasure):
    ...
```

**Factory Method** (lines 68-117):
```python
@classmethod
def create_measure(cls, config: Dict[str, Any]) -> BaseMeasure:
    """Factory method to create measure from configuration."""
    measure_type_str = config.get('type', 'simple')
    measure_type = MeasureType(measure_type_str)
    measure_class = cls._registry.get(measure_type)
    return measure_class(config)
```

### 5.2 Measure Base Class
**Location**: `models/base/measures/base_measure.py`

**Abstract Contract** (lines 22-92):
```python
class BaseMeasure(ABC):
    """Abstract base for all measure types."""
    
    def __init__(self, config: Dict[str, Any]):
        self.name = config['name']
        self.source = config['source']      # e.g., 'fact_prices.close'
        self.data_type = config.get('data_type', 'double')
        self.auto_enrich = config.get('auto_enrich', False)
    
    @abstractmethod
    def to_sql(self, adapter) -> str:
        """Generate SQL for this measure."""
        pass
    
    def execute(self, adapter, **kwargs):
        """Execute measure using backend adapter."""
        sql = self.to_sql(adapter)
        return adapter.execute_sql(sql)
```

**Design Philosophy**:
- **SQL Generation**: Measures generate SQL (business logic)
- **Backend Agnostic**: SQL executed by adapter (infrastructure)
- **Auto-Enrichment**: Optional automatic table joins for entity columns

### 5.3 Measure Types

**Simple Measure** (Basic Aggregations):
```yaml
avg_close_price:
  type: simple
  source: fact_prices.close
  aggregation: avg
```

**Computed Measure** (Expressions):
```yaml
revenue:
  type: computed
  source: fact_prices.close  # Reference only
  expression: close * volume
  aggregation: sum
```

**Weighted Measure** (Multi-stock Indices):
```yaml
volume_weighted_index:
  type: weighted_aggregate
  source: fact_prices.close
  weighting_method: volume
  group_by: [trade_date]
```

### 5.4 Measure Executor
**Location**: `models/base/measures/executor.py`

**Unified Execution** (lines 73-150):
```python
class MeasureExecutor:
    def execute_measure(
        self,
        measure_name: str,
        entity_column: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        **kwargs
    ):
        # 1. Get measure config from model
        measure_config = self._get_measure_config(measure_name)
        
        # 2. Create measure instance via registry
        measure = MeasureRegistry.create_measure(measure_config)
        
        # 3. Auto-enrichment if needed
        if measure.auto_enrich:
            self._auto_enrich_measure(measure, measure_config, entity_column, filters, kwargs)
        
        # 4. Execute via backend adapter
        result = measure.execute(self.adapter, 
                               entity_column=entity_column,
                               filters=filters,
                               limit=limit,
                               **kwargs)
        
        return result
```

**Backend Adapters**:
- DuckDB: Executes SQL strings
- Spark: Builds DataFrames with Spark SQL functions

---

## 6. MODEL REGISTRY & DISCOVERY

### Overview
The ModelRegistry (`models/registry.py`) discovers and manages all available models.

#### 6.1 Configuration-Driven Discovery
**Scanning** (lines 235-246):
```python
def _load_models(self):
    """Discover all model configurations from YAML files."""
    if not self.models_dir.exists():
        raise ValueError(f"Models directory not found: {self.models_dir}")
    
    for yaml_file in self.models_dir.glob("*.yaml"):
        try:
            config_dict = yaml.safe_load(yaml_file.read_text())
            model = ModelConfig(config_dict)
            self.models[model.name] = model
        except Exception as e:
            print(f"Warning: Failed to load model from {yaml_file}: {e}")
```

#### 6.2 Lazy Model Class Registration
**Auto-Registration** (lines 357-396):
```python
def _try_auto_register(self, model_name: str):
    """Auto-register model class by convention."""
    import importlib
    
    try:
        # Try package import: models.implemented.{model_name}
        package_path = f"models.implemented.{model_name}"
        module = importlib.import_module(package_path)
        class_name = f"{model_name.capitalize()}Model"
        
        if hasattr(module, class_name):
            model_class = getattr(module, class_name)
            self.register_model_class(model_name, model_class)
            return
    except (ImportError, AttributeError):
        pass
    
    # Fall back to direct module import if package import fails
```

**Convention Over Configuration**: Models follow naming patterns (e.g., `forecast.yaml` → `ForecastModel` class)

#### 6.3 Model Configuration
**Class** (lines 40-75):
```python
class ModelConfig:
    """Configuration for a data model."""
    
    def __init__(self, config_dict: Dict):
        self.name = config_dict['model']
        self.version = config_dict.get('version', 1)
        self.storage = config_dict.get('storage', {})
        self._dimensions = {}
        self._facts = {}
        self._load_schema(config_dict.get('schema', {}))
        self._measures = {}
        self._load_measures(config_dict.get('measures', {}))
        self.graph = config_dict.get('graph', {})
```

---

## 7. MODEL GRAPH & DEPENDENCY MANAGEMENT

### Overview
`ModelGraph` (`models/api/graph.py`) uses NetworkX to manage model dependencies and relationships.

#### 7.1 Graph Construction
**From Configs** (lines 63-91):
```python
class ModelGraph:
    def build_from_config_dir(self, config_dir: Path) -> None:
        """Build graph from YAML config directory."""
        # Load all model configs
        for yaml_file in config_dir.glob("*.yaml"):
            config = yaml.safe_load(yaml_file.read_text())
            self._model_configs[config.get('model')] = config
        
        # Build graph from configs
        self._build_graph_from_configs()
        
        # Validate DAG property
        self.validate_no_cycles()
```

**Graph Building** (lines 93-135):
```python
def _build_graph_from_configs(self) -> None:
    """Build NetworkX directed graph."""
    # Add all models as nodes
    for model_name in self._model_configs.keys():
        self.graph.add_node(model_name, type='model')
    
    # Add edges from depends_on
    for model_name, config in self._model_configs.items():
        depends_on = config.get('depends_on', [])
        for dependency in depends_on:
            self.graph.add_edge(model_name, dependency, type='dependency')
    
    # Add cross-model edges from graph.edges
    for model_name, config in self._model_configs.items():
        edges = config.get('graph', {}).get('edges', [])
        for edge in edges:
            if '.' in edge.get('to', ''):
                # Cross-model edge
                self.graph.add_edge(model_name, to_model, 
                                   type='cross_model_edge',
                                   from_table=edge['from'],
                                   to_table=edge['to'])
```

#### 7.2 Relationship Queries
**Direct vs Transitive** (lines 172-212):
```python
def get_dependencies(self, model_name: str, transitive: bool = False) -> Set[str]:
    """Get dependencies for a model."""
    if transitive:
        return set(nx.descendants(self.graph, model_name))  # All reachable
    else:
        return set(self.graph.successors(model_name))       # Direct only
```

#### 7.3 Build Order
**Topological Sort** (lines 255-270):
```python
def get_build_order(self) -> List[str]:
    """Get topological sort for build order."""
    if not nx.is_directed_acyclic_graph(self.graph):
        raise ValueError("Graph contains cycles")
    
    return list(nx.topological_sort(self.graph))
```

**Ensures**: Dependencies are built before dependent models

#### 7.4 Cycle Detection
**DAG Validation** (lines 272-285):
```python
def validate_no_cycles(self) -> None:
    """Validate graph is a DAG."""
    if not nx.is_directed_acyclic_graph(self.graph):
        cycles = list(nx.simple_cycles(self.graph))
        raise ValueError(f"Model dependency graph contains cycles: {cycles}")
```

---

## 8. QUERY PLANNER

### Overview
`GraphQueryPlanner` (`models/api/query_planner.py`) builds dynamic joins within a single model.

#### 8.1 Table-Level Graph
**Construction** (lines 55-94):
```python
class GraphQueryPlanner:
    def __init__(self, model):
        self.model = model
        self.graph = self._build_table_graph()  # NetworkX DiGraph of tables
    
    def _build_table_graph(self) -> nx.DiGraph:
        """Build graph from model's graph.edges."""
        g = nx.DiGraph()
        
        # Add table nodes
        for node in self.model.model_cfg.get('graph', {}).get('nodes', []):
            g.add_node(node['id'], type='dimension' if node['id'].startswith('dim_') else 'fact')
        
        # Add join edges
        for edge in self.model.model_cfg.get('graph', {}).get('edges', []):
            g.add_edge(
                edge['from'],
                edge['to'],
                join_on=edge.get('on', []),
                join_type=edge.get('type', 'left')
            )
        
        return g
```

#### 8.2 Dynamic Join Building
**Enrichment Pattern** (lines 96-144):
```python
def get_table_enriched(
    self,
    table_name: str,
    enrich_with: Optional[List[str]] = None,
    columns: Optional[List[str]] = None
) -> Any:
    """Get table with optional dynamic joins."""
    
    # Fast path: materialized view
    materialized = self._find_materialized_view(table_name, enrich_with)
    if materialized:
        return self.model.get_table(materialized)
    
    # Slow path: dynamic join
    return self._build_dynamic_join(table_name, enrich_with, columns)
```

**Materialized Views Optimization**: Checks for pre-computed joins before building dynamically

---

## 9. CONFIGURATION MANAGEMENT SYSTEM

### Overview
`ConfigLoader` (`config/loader.py`) provides centralized, type-safe configuration management.

#### 9.1 Configuration Precedence
**Hierarchy** (highest to lowest):
1. Explicit parameters (passed to `load()`)
2. Environment variables (from `.env`)
3. Configuration files (JSON/YAML)
4. Default values (in `constants.py`)

#### 9.2 Typed Configuration Models
**Location**: `config/models.py`

**AppConfig** (Top-level):
```python
@dataclass
class AppConfig:
    repo_root: Path
    connection: ConnectionConfig
    storage: Dict                 # From storage.json
    apis: Dict                    # Auto-discovered API configs
    log_level: str
```

**ConnectionConfig**:
```python
@dataclass
class ConnectionConfig:
    type: str                     # "spark" or "duckdb"
    spark: Optional[SparkConfig]
    duckdb: Optional[DuckDBConfig]
```

#### 9.3 Repository Discovery
**Centralized** (`utils/repo.py`):
```python
def get_repo_root(start_path: Optional[Path] = None) -> Path:
    """Find repo root by looking for marker directories."""
    current = Path(start_path) if start_path else Path.cwd()
    
    for parent in [current] + list(current.parents):
        if all((parent / marker).exists() for marker in ['configs/', 'core/', '.git/']):
            return parent
    
    raise ValueError("Repository root not found")
```

**Markers**: `configs/`, `core/`, `.git/` (all must exist)

---

## 10. CROSS-LAYER INTEGRATION

### 10.1 Data Flow Architecture
```
API/Notebooks
    ↓
UniversalSession (Orchestration)
    ├─→ ModelRegistry (Discovery)
    ├─→ ModelGraph (Dependencies)
    └─→ FilterEngine (Backend-agnostic filtering)
        ↓
    Model instances (BaseModel + subclasses)
        ├─→ GraphQueryPlanner (Dynamic joins)
        ├─→ MeasureExecutor (Measure calculations)
        └─→ StorageRouter (Path resolution)
            ↓
    Backend Adapters
        ├─→ Spark: DataFrame API
        └─→ DuckDB: SQL strings
            ↓
    Storage Layer
        ├─→ Bronze: storage/bronze/{provider}/{table}/
        └─→ Silver: storage/silver/{model}/{table}/
```

### 10.2 Design Patterns Used

**1. Lazy Loading**
- Models not built until first access
- Measure executor instantiated on demand
- Query planner created per model instance

**2. Dependency Injection**
- Session injected into models
- Backend adapter injected into measures
- Connection injected into all layers

**3. Factory Pattern**
- MeasureRegistry creates measure instances
- ModelRegistry creates model classes
- BackendAdapter factory for Spark/DuckDB

**4. Adapter Pattern**
- FilterEngine adapts filters for Spark/DuckDB
- Backend adapters abstract SQL vs DataFrame API
- StorageRouter abstracts path resolution

**5. Graph-Based Planning**
- ModelGraph (inter-model dependencies)
- GraphQueryPlanner (intra-model joins)
- Topological sorting for build order

**6. Decorator Pattern**
- @MeasureRegistry.register for measure types
- Hooks in BaseModel: before_build(), after_build(), custom_node_loading()

### 10.3 Backend Abstraction

**Unified Interface**:
```python
# Same code works on both backends
session = UniversalSession(connection, storage_cfg, repo_root)
df = session.get_table('equity', 'fact_equity_prices',
                      required_columns=['ticker', 'close', 'company_name'],
                      filters={'trade_date': {'min': '2024-01-01'}})

result = model.calculate_measure('avg_close_price', 
                                entity_column='ticker',
                                limit=10)
```

**Transparent Execution**:
- Spark: Builds DataFrame operations chain
- DuckDB: Generates and executes SQL
- Filters pushed down in both cases
- Results normalized to backend-independent format

---

## 11. KEY ARCHITECTURAL INSIGHTS

### 11.1 YAML as Source of Truth
- All model definitions are declarative YAML
- No business logic mixed into Python code
- Changes to models don't require code changes

### 11.2 Graph-Centric Design
- Models organized as directed acyclic graphs
- Two levels: Model dependencies + Table edges
- Enables automatic join planning and build ordering

### 11.3 Backend Transparency
- Single codebase works with Spark AND DuckDB
- No if/else for backend selection in business logic
- Adapters handle dialect differences

### 11.4 Lazy Evaluation
- Models built on first access (not at instantiation)
- Measures computed dynamically (not stored)
- Supports efficient multi-model sessions

### 11.5 Extensibility
- Decorator-based measure type registration
- Hook methods for custom node loading and post-processing
- Easy to add new measure types without changing core code

---

## 12. FILE LOCATION REFERENCE

| Purpose | Location |
|---------|----------|
| **Base Model Framework** | `/home/user/de_Funk/models/base/model.py` |
| **Session Management** | `/home/user/de_Funk/models/api/session.py` |
| **Model Registry** | `/home/user/de_Funk/models/registry.py` |
| **Model Graph** | `/home/user/de_Funk/models/api/graph.py` |
| **Query Planner** | `/home/user/de_Funk/models/api/query_planner.py` |
| **Storage Router** | `/home/user/de_Funk/models/api/dal.py` |
| **Filter Engine** | `/home/user/de_Funk/core/session/filters.py` |
| **Measure Registry** | `/home/user/de_Funk/models/base/measures/registry.py` |
| **Measure Base** | `/home/user/de_Funk/models/base/measures/base_measure.py` |
| **Measure Executor** | `/home/user/de_Funk/models/base/measures/executor.py` |
| **Simple Measures** | `/home/user/de_Funk/models/measures/simple.py` |
| **Weighted Builder** | `/home/user/de_Funk/models/builders/weighted_aggregate_builder.py` |
| **Parquet Loader** | `/home/user/de_Funk/models/base/parquet_loader.py` |
| **Config Loader** | `/home/user/de_Funk/config/loader.py` |
| **Repo Discovery** | `/home/user/de_Funk/utils/repo.py` |
| **Repository Context** | `/home/user/de_Funk/core/context.py` |

---

## 13. INTEGRATION EXAMPLES

### 13.1 Building and Querying a Model
```python
from core.context import RepoContext

# 1. Setup context with configuration management
ctx = RepoContext.from_repo_root(connection_type="duckdb")

# 2. Create session with model registry and graph
from models.api.session import UniversalSession
session = UniversalSession(
    connection=ctx.connection,
    storage_cfg=ctx.storage,
    repo_root=ctx.repo,
    models=['equity', 'corporate']  # Pre-load specific models
)

# 3. Get table with auto-enrichment (joins)
df = session.get_table(
    'equity',
    'fact_equity_prices',
    required_columns=['ticker', 'close', 'company_name'],  # Auto-joins!
    filters={'trade_date': {'min': '2024-01-01'}},
    group_by=['ticker'],
    aggregations={'close': 'avg'}
)

# 4. Calculate measures
model = session.get_model_instance('equity')
result = model.calculate_measure(
    'avg_close_price',
    entity_column='ticker',
    limit=10
)
```

### 13.2 Custom Model Implementation
```python
# In models/implemented/equity/model.py
from models.base.model import BaseModel

class EquityModel(BaseModel):
    def custom_node_loading(self, node_id: str, node_config: Dict) -> Optional[DataFrame]:
        # Override specific node loading logic
        if node_id == 'fact_equity_prices':
            # Custom logic for prices
            return None  # Let BaseModel handle it
        return None
    
    def after_build(self, dims, facts):
        # Post-processing after standard build
        # e.g., add synthetic dimensions, validate foreign keys
        return dims, facts
```

---

## 14. PERFORMANCE OPTIMIZATION STRATEGIES

### 14.1 Storage Optimizations
- Parquet with snappy compression
- Few large files (1-5) instead of 200+ tiny files
- Sorting by query columns enables zone maps
- Schema evolution via merge_schema option

### 14.2 Query Optimizations
- Filter pushdown (before joins)
- Materialized views as optional fast path
- Lazy model loading (only build used models)
- Column projection (select only needed columns)

### 14.3 Measure Optimizations
- Pre-materialized weighted aggregates
- Cached measure definitions
- Registry-based measure compilation
- Backend-specific execution (SQL for DuckDB, DataFrame for Spark)

---

## Summary

The de_Funk infrastructure is designed around:
1. **Declarative models** (YAML-driven)
2. **Graph-centric orchestration** (dependencies and joins)
3. **Backend transparency** (Spark/DuckDB agnostic)
4. **Lazy evaluation** (compute on demand)
5. **Extensible architecture** (decorator-based registration)

These layers enable the domain models to focus purely on business logic while the framework handles orchestration, optimization, and cross-model coordination.

