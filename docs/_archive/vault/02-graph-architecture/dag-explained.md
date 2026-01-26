# How de_Funk Uses DAGs

**Understanding Directed Acyclic Graphs in de_Funk**

---

## What is a DAG?

A **Directed Acyclic Graph (DAG)** is a graph structure where:

- **Directed**: Edges have a direction (A → B, not just A — B)
- **Acyclic**: No cycles (you can't follow edges and return to your starting point)

```
    A
   / \
  ▼   ▼
  B   C
   \ /
    ▼
    D
```

This is a valid DAG: A → B → D and A → C → D. No path leads back to A.

---

## DAGs in de_Funk

de_Funk uses DAGs at **two levels**:

1. **Model Dependency Graph** - Which models depend on which other models
2. **Table Relationship Graph** - How tables within a model relate to each other

---

## Level 1: Model Dependency Graph

### Purpose

Determines the **build order** for models. If model A depends on model B, then B must be built before A.

### Current Model DAG

```
                    ┌─────────────┐
                    │    core     │  (Tier 0)
                    │  (calendar) │
                    └──────┬──────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
         ▼                 ▼                 ▼
   ┌───────────┐    ┌───────────┐    ┌───────────┐
   │  company  │    │   macro   │    │           │  (Tier 1)
   │ (entities)│    │(economics)│    │           │
   └─────┬─────┘    └─────┬─────┘    └───────────┘
         │                │
         │    ┌───────────┤
         │    │           │
         ▼    ▼           ▼
   ┌───────────┐    ┌───────────┐
   │   stocks  │    │city_finance│  (Tier 2)
   │ (prices)  │    │(municipal) │
   └─────┬─────┘    └───────────┘
         │
         ▼
   ┌───────────┐
   │ forecast  │  (Tier 3)
   │(predictions)│
   └───────────┘
```

### How It Works

1. **Declaration**: Each model declares dependencies in YAML:

```yaml
# configs/models/stocks/model.yaml
model: stocks
depends_on:
  - core
  - company
```

2. **Graph Construction**: Framework builds a NetworkX DiGraph:

```python
import networkx as nx

G = nx.DiGraph()
G.add_edge("stocks", "core")
G.add_edge("stocks", "company")
G.add_edge("company", "core")
G.add_edge("forecast", "stocks")
G.add_edge("forecast", "core")
```

3. **Topological Sort**: Determines build order:

```python
build_order = list(nx.topological_sort(G))
# Result: ['core', 'company', 'macro', 'stocks', 'city_finance', 'forecast']
```

4. **Cycle Detection**: If you try to create a cycle, it fails:

```python
G.add_edge("core", "stocks")  # Would create cycle: core → stocks → core
# Raises: nx.NetworkXUnfeasible: Graph contains a cycle
```

### Implementation

Located in `models/api/graph.py`:

```python
class ModelDependencyGraph:
    def __init__(self):
        self.graph = nx.DiGraph()

    def add_model(self, model_name: str, depends_on: list):
        for dep in depends_on:
            self.graph.add_edge(model_name, dep)

    def get_build_order(self) -> list:
        # Reverse topological sort (dependencies first)
        return list(reversed(list(nx.topological_sort(self.graph))))

    def validate_no_cycles(self):
        if not nx.is_directed_acyclic_graph(self.graph):
            cycles = list(nx.simple_cycles(self.graph))
            raise ValueError(f"Circular dependencies detected: {cycles}")
```

---

## Level 2: Table Relationship Graph

### Purpose

Defines how **tables within a model** relate to each other. Used for:

- Validating joins (edges)
- Finding join paths between tables
- Materializing paths (pre-joined views)

### Example Table Graph

For the `stocks` model:

```
┌─────────────────────┐
│bronze.securities_   │
│  prices_daily       │
└──────────┬──────────┘
           │ select/derive
           ▼
┌─────────────────────┐         ┌─────────────────────┐
│  fact_stock_prices  │────────▶│     dim_stock       │
└──────────┬──────────┘ ticker  └──────────┬──────────┘
           │                               │
           │ trade_date                    │ company_id
           ▼                               ▼
┌─────────────────────┐         ┌─────────────────────┐
│  core.dim_calendar  │         │ company.dim_company │
└─────────────────────┘         └─────────────────────┘
```

### How It Works

1. **Node Definition**: Tables are nodes in the graph:

```yaml
graph:
  nodes:
    - id: dim_stock
      from: bronze.securities_reference
      select:
        ticker: ticker
        company_id: company_id

    - id: fact_stock_prices
      from: bronze.securities_prices_daily
      select:
        ticker: ticker
        trade_date: trade_date
        close: close
```

2. **Edge Definition**: Relationships are directed edges:

```yaml
  edges:
    - from: fact_stock_prices
      to: dim_stock
      on: [ticker = ticker]

    - from: fact_stock_prices
      to: core.dim_calendar
      on: [trade_date = date]

    - from: dim_stock
      to: company.dim_company
      on: [company_id = company_id]
```

3. **Path Finding**: Query planner uses graph to find join paths:

```python
# Find path from fact_stock_prices to company.dim_company
path = nx.shortest_path(
    table_graph,
    source='fact_stock_prices',
    target='company.dim_company'
)
# Result: ['fact_stock_prices', 'dim_stock', 'company.dim_company']
```

4. **Path Materialization**: Pre-join tables along a path:

```yaml
paths:
  - id: stock_prices_with_company
    hops: fact_stock_prices -> dim_stock -> company.dim_company
```

### Implementation

The BaseModel builds and uses this graph internally:

```python
class BaseModel:
    def _build_table_graph(self):
        """Build NetworkX graph from YAML edges."""
        self._table_graph = nx.DiGraph()

        for edge in self.config.get('graph', {}).get('edges', []):
            self._table_graph.add_edge(
                edge['from'],
                edge['to'],
                join_keys=edge.get('on', [])
            )

    def _find_join_path(self, source: str, target: str) -> list:
        """Find shortest path between two tables."""
        return nx.shortest_path(self._table_graph, source, target)

    def _materialize_path(self, path_config: dict):
        """Join tables along a path to create materialized view."""
        hops = self._parse_hops(path_config['hops'])

        result_df = self._get_node(hops[0])
        for i in range(1, len(hops)):
            next_node = self._get_node(hops[i])
            edge_data = self._table_graph.get_edge_data(hops[i-1], hops[i])
            result_df = self._join_tables(result_df, next_node, edge_data)

        return result_df
```

---

## Why DAGs Matter

### 1. Build Order Guarantees

Without a DAG, you might try to build `stocks` before `company`:

```
ERROR: Cross-model reference 'company.dim_company' failed
       (company model not built yet)
```

The DAG ensures `company` is always built first.

### 2. No Circular Dependencies

Circular dependencies would cause infinite loops:

```
stocks → company → stocks → company → ...
```

The acyclic property prevents this.

### 3. Efficient Query Planning

The table graph enables intelligent query optimization:

```python
# Without graph: Manual join specification required
df = prices.join(stocks).join(company)

# With graph: Automatic path discovery
df = model.get_enriched('fact_stock_prices', enrich_with=['company.dim_company'])
# Framework figures out: prices → stocks → company
```

### 4. Parallel Execution (Future)

Independent branches can be built in parallel:

```
core builds first
  ↓
company and macro build in parallel (no dependency between them)
  ↓
stocks and city_finance build in parallel
  ↓
forecast builds last
```

---

## Working with DAGs

### Viewing the Model Graph

```python
from models.api.registry import get_model_registry

registry = get_model_registry()
graph = registry.get_dependency_graph()

# Print build order
print(graph.get_build_order())

# Check for cycles
graph.validate_no_cycles()
```

### Viewing a Model's Table Graph

```python
model = registry.get_model("stocks")
model.ensure_built()

# Access internal graph
table_graph = model._table_graph

# List nodes (tables)
print(list(table_graph.nodes()))

# List edges (relationships)
for edge in table_graph.edges(data=True):
    print(f"{edge[0]} → {edge[1]}: {edge[2]}")
```

### Visualizing Graphs

```python
import matplotlib.pyplot as plt
import networkx as nx

# Draw model dependency graph
G = registry.get_dependency_graph().graph
nx.draw(G, with_labels=True, arrows=True)
plt.show()
```

---

## Common DAG Patterns

### Star Schema (Fact-Centered)

```
         dim_A
           ↑
dim_B ← FACT → dim_C
           ↓
         dim_D
```

All edges point from fact to dimensions.

### Snowflake Schema (Hierarchical)

```
         dim_A
           ↑
FACT → dim_B → dim_B_detail
           ↓
         dim_C → dim_C_detail
```

Dimensions can have sub-dimensions.

### Cross-Model References

```
Model A               Model B
┌───────┐            ┌───────┐
│ fact  │───────────▶│  dim  │
└───────┘            └───────┘
```

Facts in one model reference dimensions in another.

---

## Related Documentation

- [Graph Overview](graph-overview.md) - Complete graph architecture
- [Nodes, Edges, Paths](nodes-edges-paths.md) - Detailed component reference
- [Cross-Model References](cross-model-references.md) - Inter-model relationships
- [Dependency Resolution](dependency-resolution.md) - Build order details
