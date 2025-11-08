# Models System - Base Model

## Overview

**BaseModel** is the foundation for all domain models. It implements generic graph-building logic driven by YAML configuration, eliminating code duplication.

## Class Structure

```python
# File: models/base/model.py:30-300

class BaseModel:
    """Smart base model with YAML-driven graph building."""

    def __init__(self, connection, storage_cfg, model_cfg, params=None):
        self.connection = connection
        self.storage_cfg = storage_cfg
        self.model_cfg = model_cfg
        self.params = params or {}
        self.model_name = model_cfg.get('model', 'unknown')
        
        # Lazy-loaded caches
        self._dims = None
        self._facts = None
        self._is_built = False
        
        # Storage router
        from models.api.dal import StorageRouter
        self.storage_router = StorageRouter(self.storage_cfg)
        
        # Detect backend
        self._backend = self._detect_backend()

    def build(self):
        """Main graph-building pipeline."""
        self.before_build()  # Extension point
        self._build_nodes()
        self._apply_edges()
        self._materialize_paths()
        self.after_build()   # Extension point
        self._is_built = True

    def before_build(self):
        """Override for custom initialization."""
        pass

    def after_build(self):
        """Override for post-processing."""
        pass
```

## Graph Building Process

### 1. Build Nodes (Load Tables)

```python
def _build_nodes(self):
    """Load all nodes from graph config."""
    graph = self.model_cfg.get('graph', {})
    nodes = graph.get('nodes', [])
    
    dims = {}
    facts = {}
    
    for node in nodes:
        node_id = node['id']
        from_spec = node['from']  # e.g., "bronze.polygon.prices_daily"
        
        # Resolve path using StorageRouter
        path = self.storage_router.resolve(from_spec)
        
        # Load table
        df = self.connection.read_table(path)
        
        # Apply select (column mapping)
        if 'select' in node:
            df = self._select_columns(df, node['select'])
        
        # Categorize as dimension or fact
        if node_id.startswith('dim_'):
            dims[node_id] = df
        else:
            facts[node_id] = df
    
    self._dims = dims
    self._facts = facts
```

### 2. Apply Edges (Relationships)

```python
def _apply_edges(self):
    """Apply edges (foreign key relationships)."""
    graph = self.model_cfg.get('graph', {})
    edges = graph.get('edges', [])
    
    for edge in edges:
        from_node = edge['from']
        to_node = edge['to']
        condition = edge['on']  # e.g., "ticker = ticker"
        
        # Validate relationship exists
        from_df = self._get_node(from_node)
        to_df = self._get_node(to_node)
        
        # Parse condition
        left_col, right_col = self._parse_join_condition(condition)
        
        # Verify columns exist
        if left_col not in from_df.columns:
            raise ValueError(f"Column {left_col} not in {from_node}")
        if right_col not in to_df.columns:
            raise ValueError(f"Column {right_col} not in {to_node}")
```

### 3. Materialize Paths (Joins)

```python
def _materialize_paths(self):
    """Materialize path definitions (pre-joined views)."""
    graph = self.model_cfg.get('graph', {})
    paths = graph.get('paths', [])
    
    for path in paths:
        path_id = path['id']
        from_node = path['from']
        joins = path.get('joins', [])
        
        # Start with base table
        result = self._get_node(from_node)
        
        # Apply each join
        for join_node in joins:
            join_df = self._get_node(join_node)
            
            # Determine join key (from edges)
            join_key = self._find_join_key(from_node, join_node)
            
            # Perform join
            result = result.join(join_df, on=join_key, how='left')
        
        # Cache path
        self._facts[path_id] = result
```

## Table Access Methods

```python
def get_table(self, table_name: str):
    """Get a table by name."""
    if not self._is_built:
        self.build()
    
    # Check dims first
    if table_name in self._dims:
        return self._dims[table_name]
    
    # Check facts
    if table_name in self._facts:
        return self._facts[table_name]
    
    raise ValueError(f"Table {table_name} not found in model {self.model_name}")

def list_tables(self) -> List[str]:
    """List all available tables."""
    if not self._is_built:
        self.build()
    
    return list(self._dims.keys()) + list(self._facts.keys())

def get_dimension_df(self, dim_name: str):
    """Get a dimension table."""
    if not self._is_built:
        self.build()
    
    if dim_name not in self._dims:
        raise ValueError(f"Dimension {dim_name} not found")
    
    return self._dims[dim_name]
```

## Extending BaseModel

### Example: CompanyModel

```python
# File: models/company/model.py

from models.base.model import BaseModel

class CompanyModel(BaseModel):
    """Company model with financial data."""

    def before_build(self):
        """Custom initialization."""
        print(f"Building {self.model_name} model...")

    def after_build(self):
        """Post-processing."""
        # Cache frequently used tables
        self._prices_cached = self.get_table('fact_prices')

    # Domain-specific methods
    def get_prices(self, ticker: str):
        """Get prices for a ticker."""
        prices = self.get_table('fact_prices')
        return self.connection.apply_filters(prices, {'ticker': ticker})

    def get_company_info(self, ticker: str):
        """Get company metadata."""
        companies = self.get_table('dim_companies')
        return self.connection.apply_filters(companies, {'ticker': ticker})
```

**File**: `/home/user/de_Funk/docs/guide/3-architecture/components/models-system/base-model.md`
