# Auto-Join Enhancement: Smart Graph Traversal at Query Time

## Problem Statement

Currently, users must know which materialized table to use to access certain dimensions. This is brittle and requires knowledge of the internal data model.

### Current Behavior (Brittle)

```yaml
# This FAILS because exchange_name doesn't exist in fact_prices
$exhibits${
  type: line_chart
  source: company.fact_prices
  dimension_selector: {
    available_dimensions: [ticker, exchange_name]  # ❌ exchange_name not in fact_prices
  }
}

# User must know to use prices_with_company instead
$exhibits${
  type: line_chart
  source: company.prices_with_company  # ✅ Has exchange_name
  dimension_selector: {
    available_dimensions: [ticker, exchange_name]
  }
}
```

### Issues with Current Approach

1. **User must know the schema** - Which tables have which columns?
2. **Must understand materialized paths** - What is `prices_with_company`? Why not just `fact_prices`?
3. **Tight coupling** - Exhibits are coupled to specific materialized views
4. **Graph underutilized** - We define edges and paths in YAML but only use them at build time
5. **Not extensible** - Adding new dimensions requires creating new materialized tables

## Proposed Solution: Auto-Join at Query Time

### How It Should Work

```yaml
# User specifies the BASE table they want
$exhibits${
  type: line_chart
  source: company.fact_prices
  dimension_selector: {
    available_dimensions: [ticker, exchange_name]  # System auto-joins to get exchange_name
  }
}
```

**System behavior:**
1. User requests `source: company.fact_prices` with dimension `exchange_name`
2. System detects `exchange_name` not in `fact_prices` schema
3. System looks at graph definition to find path to `exchange_name`:
   - Check all edges from `fact_prices`
   - Find: `fact_prices -> dim_company -> dim_exchange` (which has `exchange_name`)
4. System automatically performs joins at query time
5. Returns data with requested dimensions

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│ Exhibit Definition                                      │
│  source: company.fact_prices                           │
│  dimensions: [ticker, exchange_name, company_name]     │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│ Storage Service / Notebook Session                      │
│  get_exhibit_data(exhibit_id)                          │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│ NEW: Smart Source Resolver                              │
│  1. Parse source (model.table)                         │
│  2. Get requested columns from exhibit config          │
│  3. Check which columns exist in source table          │
│  4. For missing columns, find join path via graph      │
│  5. Build SQL/DataFrame with auto-joins                │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│ Graph Traversal Engine                                  │
│  - Find shortest path from source to target column     │
│  - Build join sequence                                 │
│  - Return join metadata (tables, keys, order)          │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│ Query Builder (DuckDB / Spark)                          │
│  - Construct SQL with LEFT JOINs                       │
│  - Apply filters                                        │
│  - Return result DataFrame                             │
└─────────────────────────────────────────────────────────┘
```

## Implementation Approach

### Phase 1: Column-to-Table Mapping

Build a reverse index from the model config:

```python
class SmartSourceResolver:
    def __init__(self, model_registry):
        self.model_registry = model_registry
        self.column_index = self._build_column_index()

    def _build_column_index(self) -> Dict[str, List[Tuple[str, str]]]:
        """
        Build index: column_name -> [(model, table), ...]

        Returns:
            {
                'exchange_name': [('company', 'dim_exchange'), ('company', 'prices_with_company')],
                'ticker': [('company', 'fact_prices'), ('company', 'dim_company'), ...],
                ...
            }
        """
        index = {}
        for model_name in self.model_registry.list_models():
            model = self.model_registry.get_model(model_name)
            for table_name in model.list_tables():
                schema = model.get_table_schema(table_name)
                for column_name in schema.keys():
                    if column_name not in index:
                        index[column_name] = []
                    index[column_name].append((model_name, table_name))
        return index
```

### Phase 2: Graph Path Finding

Extend the existing `ModelGraph` to find paths at the table level:

```python
class ModelGraph:
    def find_column_path(
        self,
        source_model: str,
        source_table: str,
        target_column: str
    ) -> Optional[List[str]]:
        """
        Find shortest path from source table to a table containing target column.

        Args:
            source_model: Starting model (e.g., 'company')
            source_table: Starting table (e.g., 'fact_prices')
            target_column: Column we need (e.g., 'exchange_name')

        Returns:
            List of table names to join through, or None if no path exists
            Example: ['fact_prices', 'dim_company', 'dim_exchange']
        """
        # 1. Find all tables that have target_column
        # 2. Use graph edges to find shortest path from source_table to any target table
        # 3. Return the join sequence
        pass
```

### Phase 3: Auto-Join Query Builder

Build the actual query with joins:

```python
class AutoJoinQueryBuilder:
    def build_query(
        self,
        base_table: str,
        required_columns: List[str],
        join_path: List[str],
        filters: Dict[str, Any]
    ) -> str:
        """
        Build SQL query with automatic joins.

        Args:
            base_table: Starting table
            required_columns: Columns needed in result
            join_path: Sequence of tables to join
            filters: Filter conditions

        Returns:
            SQL query string
        """
        # Build LEFT JOIN chain
        # Apply filters
        # Select only required columns
        pass
```

### Phase 4: Integration with NotebookSession

Modify `NotebookSession.get_exhibit_data()`:

```python
def get_exhibit_data(self, exhibit_id: str) -> Any:
    # ... existing code ...

    # NEW: Instead of simple get_table(), use smart resolver
    resolver = SmartSourceResolver(self.model_registry)

    # Extract required columns from exhibit
    required_columns = self._extract_required_columns(exhibit)

    # Resolve source with auto-joins
    df = resolver.get_table_with_auto_joins(
        model_name=model_name,
        table_name=table_name,
        required_columns=required_columns,
        filters=filters
    )

    return df
```

## Benefits

### For Users
- **Simpler mental model** - Just specify the base fact table and dimensions needed
- **No need to understand materialized views** - System figures it out
- **More flexible** - Can request any dimension combination without pre-building views
- **Better error messages** - "Column X requires joining through Y, Z tables"

### For System
- **Graph is actually utilized** - We defined edges for a reason!
- **Fewer materialized views needed** - On-demand joins reduce storage
- **More maintainable** - Changes to schema don't break exhibits
- **Better performance insights** - Can log which auto-joins are slow and materialize those

## Performance Considerations

### When to Use Auto-Joins vs Materialized Views

**Auto-Joins Good For:**
- Interactive notebooks with changing requirements
- Exploratory analysis
- Infrequent dimension combinations
- Development and prototyping

**Materialized Views Good For:**
- Common query patterns (e.g., 95% of queries need company + exchange)
- Large-scale aggregations
- Complex multi-hop joins (3+ tables)
- Production dashboards with fixed schemas

### Optimization Strategy

1. **Start with auto-joins** - Let users work flexibly
2. **Monitor query patterns** - Log which auto-joins are used frequently
3. **Selective materialization** - Create materialized views for hot paths
4. **Transparent fallback** - If materialized view exists, use it instead of auto-join

## Example: DuckDB Implementation

```python
class DuckDBAutoJoiner:
    def get_table_with_auto_joins(
        self,
        model_name: str,
        table_name: str,
        required_columns: List[str],
        filters: Dict[str, Any] = None
    ):
        # Get base table schema
        schema = self.model_registry.get_table_schema(model_name, table_name)
        base_columns = set(schema.keys())

        # Find missing columns
        missing = [col for col in required_columns if col not in base_columns]

        if not missing:
            # No auto-join needed - direct table access
            return self.get_table(model_name, table_name, filters)

        # Find join paths for missing columns
        model = self.model_registry.get_model(model_name)
        graph_config = model.model_cfg.get('graph', {})

        join_sequence = self._find_join_sequence(
            source_table=table_name,
            required_columns=missing,
            graph_config=graph_config
        )

        # Build SQL with joins
        sql = self._build_join_sql(
            base_table=f"{model_name}.{table_name}",
            join_sequence=join_sequence,
            required_columns=required_columns,
            filters=filters
        )

        return self.connection.conn.execute(sql).fetchdf()
```

## Migration Path

### Phase 1: Implement in Parallel
- Keep existing materialized views working
- Add auto-join capability as opt-in
- Users can choose: `source: company.fact_prices` (auto-join) or `source: company.prices_with_company` (materialized)

### Phase 2: Document & Test
- Update documentation with auto-join examples
- Performance testing to validate auto-join vs materialized performance
- Identify which paths should stay materialized

### Phase 3: Gradual Migration
- Update example notebooks to use simpler sources where appropriate
- Keep complex aggregations on materialized views
- Add query planner that chooses best strategy

## Open Questions

1. **Cache auto-joined results?** Should we cache the joined DataFrames in memory?
2. **Ambiguous paths?** If multiple join paths exist to get a column, which to choose?
3. **Cross-model auto-joins?** Should this work across models (e.g., company -> macro)?
4. **SQL generation vs DataFrame API?** DuckDB can use SQL, Spark might need DataFrame API
5. **Circular dependencies?** How to handle if graph has cycles?

## References

- Similar to **dbt's ref() function** - resolves dependencies automatically
- Similar to **Looker's join logic** - defines relationships, queries traverse them
- Similar to **GraphQL** - request what you need, system figures out how to get it

## Next Steps

1. ✅ Document the enhancement proposal (this file)
2. Create proof-of-concept for DuckDB backend
3. Test performance: auto-join vs materialized views
4. Implement column index builder
5. Implement graph path finder
6. Integrate with NotebookSession
7. Update dimension_selector to validate columns exist (via auto-join or direct)
8. Write tests for various join scenarios
9. Update documentation with new patterns

## Status

- **Status**: Proposed
- **Priority**: High (major UX improvement)
- **Complexity**: Medium (leverages existing graph infrastructure)
- **Impact**: High (simplifies all notebook definitions)
