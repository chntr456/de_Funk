# Graph Architecture: Current State & Proposed Improvements

## Executive Summary

The framework already has **two graph layers** with partial integration:

1. **ModelGraph** (Inter-Model) - Manages model dependencies, build order
2. **Session Auto-Join** (Intra-Model) - Finds materialized views with required columns

**Gap**: Missing intra-model query planner that uses graph edges for dynamic joins.

---

## Current Architecture

### Layer 1: ModelGraph (Inter-Model Dependencies)

**Location**: `models/api/graph.py`

**Created By**: `UniversalSession.__init__()` at session startup

```python
# In UniversalSession.__init__()
self.model_graph = ModelGraph()
self.model_graph.build_from_config_dir(models_dir)
```

**Scope**: Model-level relationships
- Tracks: `equity → core`, `forecast → company`
- Purpose: Build order, cross-model validation
- Methods:
  - `get_build_order()` - Topological sort
  - `are_related(model_a, model_b)` - Check dependencies
  - `get_join_path(model_a, model_b)` - Find cross-model path
  - `validate_no_cycles()` - DAG validation

**Example Usage**:
```python
# Get build order
session.model_graph.get_build_order()
# → ['core', 'equity', 'forecast']

# Check if models are related
session.model_graph.are_related('equity', 'core')
# → True (equity has edges to core.dim_calendar)

# Get cross-model join path
session.model_graph.get_join_path('forecast', 'company')
# → ['forecast', 'company']
```

**Strengths**:
- ✅ Works across ALL models in platform
- ✅ Prevents circular dependencies
- ✅ Provides build orchestration
- ✅ Visualizes model relationships

**Gaps**:
- ❌ Only tracks model-to-model edges
- ❌ Doesn't track table-to-table edges within a model
- ❌ Not used for runtime query planning

---

### Layer 2: Session Auto-Join (Materialized View Finder)

**Location**: `models/api/session.py` (`_find_materialized_view()`)

**Created By**: Called during `session.get_table()` with `required_columns`

```python
# In UniversalSession.get_table()
view = self._find_materialized_view(model_name, required_columns)
if view:
    return model.get_table(view)  # Use pre-joined view
else:
    return model.get_table(table_name)  # Use base table
```

**Scope**: Find pre-joined tables within a model
- Looks through: All tables in model
- Checks: Which tables have ALL required columns
- Returns: First matching materialized view

**Example Usage**:
```python
# Request columns not in base table
df = session.get_table(
    'equity',
    'fact_equity_prices',
    required_columns=['ticker', 'close', 'company_name']  # company_name not in prices!
)

# System checks:
# 1. fact_equity_prices: has [ticker, close] but NOT company_name
# 2. equity_prices_with_company: has [ticker, close, company_name] ✓
# 3. Returns equity_prices_with_company
```

**Strengths**:
- ✅ Transparent to user
- ✅ Uses materialized views when available
- ✅ Backend-agnostic

**Gaps**:
- ❌ Only works if materialized view exists
- ❌ Doesn't build joins dynamically from graph edges
- ❌ Requires pre-computing all possible joins
- ❌ No query planning - just table lookup

---

## Missing Layer: GraphQueryPlanner (Intra-Model Dynamic Joins)

**What's Needed**: Per-model query planner that uses graph edges for runtime joins

### Proposed Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        UniversalSession                         │
│  - Central orchestrator for all models and queries              │
│  - Creates and manages both graph layers                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌────────────────────────────────────────────────────────┐    │
│  │         ModelGraph (Inter-Model)                       │    │
│  │  - Singleton at session level                          │    │
│  │  - Tracks model dependencies                           │    │
│  │  - Build order & validation                            │    │
│  └────────────────────────────────────────────────────────┘    │
│                           │                                     │
│                           │ used by                             │
│                           ▼                                     │
│  ┌────────────────────────────────────────────────────────┐    │
│  │      WorkspaceGraph (Notebook/UI Scoped)               │    │
│  │  - Subgraph of ModelGraph                              │    │
│  │  - Only models used in current notebook                │    │
│  │  - Lightweight visualization                           │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                 │
│  ┌────────────────────────────────────────────────────────┐    │
│  │    GraphQueryPlanner (Intra-Model, Per-Model)          │    │
│  │  - Created per model instance                          │    │
│  │  - Uses model's graph edges                            │    │
│  │  - Plans joins dynamically                             │    │
│  │  - Falls back to materialized views                    │    │
│  └────────────────────────────────────────────────────────┘    │
│                           ▲                                     │
│                           │ accessed via                        │
│                           │                                     │
│  ┌────────────────────────────────────────────────────────┐    │
│  │            BaseModel (Equity, Company, etc)            │    │
│  │  - Has session reference                               │    │
│  │  - Has query_planner property                          │    │
│  │  - Exposes enriched queries                            │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Implementation

#### 1. Add GraphQueryPlanner to BaseModel

```python
# In models/base/model.py

class BaseModel:
    def __init__(self, connection, storage_cfg, model_cfg, params):
        # ... existing init ...
        self._query_planner = None  # Lazy-loaded

    @property
    def query_planner(self):
        """Get query planner for this model."""
        if self._query_planner is None:
            from models.api.query_planner import GraphQueryPlanner
            self._query_planner = GraphQueryPlanner(self)
        return self._query_planner

    def get_table_enriched(
        self,
        table_name: str,
        enrich_with: List[str] = None,
        columns: List[str] = None
    ):
        """
        Get table with optional enrichment via graph edges.

        Args:
            table_name: Base table name
            enrich_with: List of tables to join (uses graph edges)
            columns: Columns to select (default: all)

        Returns:
            DataFrame with dynamic joins applied

        Example:
            # Get prices enriched with company info
            df = equity_model.get_table_enriched(
                'fact_equity_prices',
                enrich_with=['dim_equity', 'dim_exchange'],
                columns=['ticker', 'close', 'company_name', 'exchange_name']
            )
        """
        return self.query_planner.get_table_enriched(
            table_name, enrich_with, columns
        )
```

#### 2. Create GraphQueryPlanner

```python
# New file: models/api/query_planner.py

class GraphQueryPlanner:
    """
    Intra-model query planner that uses graph edges for dynamic joins.

    Each model instance gets its own query planner.
    Uses the model's graph.edges to plan joins at runtime.
    """

    def __init__(self, model):
        """
        Initialize query planner for a model.

        Args:
            model: BaseModel instance
        """
        self.model = model
        self.graph = self._build_table_graph()

    def _build_table_graph(self):
        """
        Build NetworkX graph from model's graph.edges config.

        Returns:
            nx.DiGraph with table nodes and join edges
        """
        import networkx as nx
        g = nx.DiGraph()

        # Add nodes from schema
        schema = self.model.model_cfg.get('schema', {})
        for dim_name in schema.get('dimensions', {}).keys():
            g.add_node(dim_name, type='dimension')
        for fact_name in schema.get('facts', {}).keys():
            g.add_node(fact_name, type='fact')

        # Add edges from graph.edges config
        graph_config = self.model.model_cfg.get('graph', {})
        for edge in graph_config.get('edges', []):
            from_table = edge['from']
            to_table = edge['to']

            # Skip cross-model edges (handle separately)
            if '.' in to_table:
                continue

            g.add_edge(
                from_table,
                to_table,
                join_on=edge.get('on', []),
                join_type=edge.get('type', 'left'),
                description=edge.get('description', '')
            )

        return g

    def get_table_enriched(
        self,
        table_name: str,
        enrich_with: List[str] = None,
        columns: List[str] = None
    ):
        """
        Get table with dynamic enrichment using graph edges.

        Strategy:
        1. Check if materialized view exists (fast path)
        2. If not, build join dynamically using graph edges
        3. Select only requested columns

        Args:
            table_name: Base table name
            enrich_with: Tables to join
            columns: Columns to select

        Returns:
            DataFrame
        """
        # Fast path: check for materialized view
        if enrich_with and columns:
            materialized = self._find_materialized_view(table_name, enrich_with, columns)
            if materialized:
                return self._read_table(materialized, columns)

        # Slow path: build join dynamically
        if enrich_with:
            return self._build_join(table_name, enrich_with, columns)

        # No enrichment: just read base table
        return self._read_table(table_name, columns)

    def _build_join(
        self,
        base_table: str,
        join_tables: List[str],
        columns: List[str] = None
    ):
        """
        Build join dynamically using graph edges.

        Uses NetworkX to find join path, then executes joins.
        """
        import networkx as nx

        # Start with base table
        df = self.model.get_table(base_table)

        # Join each table in sequence
        for join_table in join_tables:
            # Find path in graph
            try:
                path = nx.shortest_path(self.graph, base_table, join_table)
            except nx.NetworkXNoPath:
                raise ValueError(
                    f"No join path from {base_table} to {join_table}. "
                    f"Add edge to {self.model.model_name}.yaml"
                )

            # Execute joins along path
            for i in range(len(path) - 1):
                left = path[i]
                right = path[i + 1]

                # Get edge metadata
                edge_data = self.graph.edges[left, right]
                join_on = edge_data['join_on']
                join_type = edge_data.get('join_type', 'left')

                # Load right table
                right_df = self.model.get_table(right)

                # Execute join
                df = self._join_dataframes(df, right_df, join_on, join_type)

        # Select columns if specified
        if columns:
            df = self._select_columns(df, columns)

        return df

    def _find_materialized_view(
        self,
        base_table: str,
        join_tables: List[str],
        columns: List[str]
    ) -> Optional[str]:
        """
        Find materialized view that matches join + columns.

        Checks paths in model config to see if any match.
        """
        paths = self.model.model_cfg.get('graph', {}).get('paths', [])

        for path in paths:
            # Parse hops to see if it matches join_tables
            hops = path.get('hops', '')
            if isinstance(hops, str):
                tables_in_path = [t.strip() for t in hops.split('->')]
            else:
                tables_in_path = hops

            # Check if this path matches our join
            if tables_in_path[0] == base_table and set(join_tables).issubset(set(tables_in_path)):
                # This path matches! Check if it has our columns
                path_table = path['id']
                if self._table_has_columns(path_table, columns):
                    return path_table

        return None
```

#### 3. Update UniversalSession to Create WorkspaceGraph

```python
# In models/api/session.py

class UniversalSession:
    def __init__(self, connection, storage_cfg, repo_root, models=None):
        # ... existing init ...

        # Global model graph (all models)
        self.model_graph = ModelGraph()
        self.model_graph.build_from_config_dir(models_dir)

        # Workspace graph (only loaded models - for notebooks/UI)
        self._workspace_graph = None

    @property
    def workspace_graph(self):
        """
        Get workspace graph (subgraph of only loaded models).

        This is useful for notebooks/UI where you only care about
        a handful of models, not all 10+ models in the platform.

        Returns:
            ModelGraph with only loaded models
        """
        if self._workspace_graph is None:
            self._workspace_graph = self._build_workspace_graph()
        return self._workspace_graph

    def _build_workspace_graph(self):
        """Build subgraph of only loaded models."""
        workspace = ModelGraph()

        # Only include loaded models
        loaded_models = list(self._models.keys())

        # Create subgraph
        workspace.graph = self.model_graph.graph.subgraph(loaded_models).copy()
        workspace._model_configs = {
            k: v for k, v in self.model_graph._model_configs.items()
            if k in loaded_models
        }

        return workspace
```

---

## Usage Examples

### Example 1: Build Orchestration (ModelGraph)

```python
# Build all models in correct order
session = UniversalSession(...)

# Get global build order
build_order = session.model_graph.get_build_order()
# → ['core', 'equity', 'corporate', 'forecast']

for model_name in build_order:
    model = session.load_model(model_name)
    model.build()
```

### Example 2: Notebook Visualization (WorkspaceGraph)

```python
# In notebook, only load 2 models
session = UniversalSession(..., models=['equity', 'core'])

# Get workspace graph (only equity + core)
workspace = session.workspace_graph

# Visualize just these 2 models
print(workspace.to_mermaid())
# graph TD
#     equity[equity]
#     core[core]
#     equity -->|depends on calendar| core

# Much cleaner than showing all 10+ models!
```

### Example 3: Dynamic Joins (GraphQueryPlanner)

```python
# Load equity model
equity_model = session.get_model_instance('equity')

# Get prices with company info (dynamic join)
df = equity_model.get_table_enriched(
    'fact_equity_prices',
    enrich_with=['dim_equity', 'dim_exchange'],
    columns=['ticker', 'trade_date', 'close', 'company_name', 'exchange_name']
)

# Planner:
# 1. Checks for materialized view (equity_prices_with_company)
# 2. If exists: read it (fast)
# 3. If not: build join from graph edges (still works!)
```

### Example 4: Measure Auto-Join

```python
# In equity.yaml
measures:
  avg_close_by_exchange:
    source: fact_equity_prices.close
    aggregation: avg
    group_by: [exchange_name]  # Not in fact_equity_prices!
    auto_enrich: true  # NEW FLAG

# System:
# 1. Sees exchange_name not in fact_equity_prices
# 2. Uses GraphQueryPlanner to find path: fact_equity_prices -> dim_equity -> dim_exchange
# 3. Builds join automatically
# 4. Groups by exchange_name
# 5. Returns result

# No materialized view needed!
```

---

## Benefits of Unified Architecture

### 1. **Separation of Concerns**

| Component | Scope | Purpose | When Created |
|-----------|-------|---------|--------------|
| ModelGraph | Global (all models) | Build order, validation | Session init |
| WorkspaceGraph | Notebook (loaded models) | UI visualization | Lazy (on access) |
| GraphQueryPlanner | Per-model | Runtime joins | Lazy (per model) |

### 2. **Flexibility**

- ✅ Materialized views become **optional optimization**
- ✅ System works without pre-computing all joins
- ✅ Fast path when materialized exists
- ✅ Slow path when building dynamically

### 3. **Better Notebook Experience**

```python
# Before: Visualize ALL models (cluttered)
session.model_graph.to_mermaid()  # Shows 10+ models

# After: Visualize only what matters
session.workspace_graph.to_mermaid()  # Shows 2 models
```

### 4. **Measure Auto-Join**

```python
# Measures can reference columns across tables
avg_close_by_exchange:
  source: fact_equity_prices.close
  group_by: [exchange_name]  # System finds it in dim_exchange
  auto_enrich: true
```

---

## Migration Path

### Phase 1: Add GraphQueryPlanner (Non-Breaking)
- Add `query_planner` property to BaseModel
- Create `GraphQueryPlanner` class
- Add `get_table_enriched()` method
- **Existing code continues to work**

### Phase 2: Add WorkspaceGraph (Non-Breaking)
- Add `workspace_graph` property to UniversalSession
- Update notebook UI to use workspace instead of global graph
- **Existing code continues to work**

### Phase 3: Update Measures (Opt-In)
- Add `auto_enrich` flag to measure config
- Measures with flag use GraphQueryPlanner
- Measures without flag work as before
- **Gradual migration**

### Phase 4: Disable Default Materialization (Breaking)
- Change paths from default `materialize: true` to `materialize: false`
- Users explicitly enable for performance-critical views
- **Requires config update**

---

## Implementation Checklist

- [ ] Create `models/api/query_planner.py`
- [ ] Add `query_planner` property to `BaseModel`
- [ ] Add `get_table_enriched()` method to `BaseModel`
- [ ] Add `workspace_graph` property to `UniversalSession`
- [ ] Update `MeasureExecutor` to support `auto_enrich`
- [ ] Update notebook UI to use `workspace_graph`
- [ ] Add `materialize:` config option to YAML schema
- [ ] Update build scripts to respect `materialize` flag
- [ ] Write tests for dynamic joins
- [ ] Document usage patterns

---

## Open Questions

1. **Caching Strategy**: Should GraphQueryPlanner cache built joins in memory?
2. **Cross-Model Joins**: How to handle equity → core.dim_calendar?
3. **Performance**: When to materialize vs build dynamically?
4. **Backwards Compatibility**: How to migrate existing notebooks?

---

## Conclusion

The framework has **excellent foundations**:
- ✅ ModelGraph for inter-model dependencies
- ✅ Session auto-join for materialized view lookup
- ✅ Clean separation between models

**Missing piece**: GraphQueryPlanner for intra-model dynamic joins

**Proposal**: Add GraphQueryPlanner as a **complement** to existing architecture, giving users:
- Fast path: Use materialized views when available
- Slow path: Build joins dynamically from graph
- Best of both worlds: Performance + Flexibility
