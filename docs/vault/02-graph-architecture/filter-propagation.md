# Graph-Based Filter Propagation

**How dimension filters cascade across all connected models**

Related: [DAG Explained](dag-explained.md), [Cross-Model References](cross-model-references.md)

---

## Overview

de_Funk's graph architecture enables **automatic filter propagation** across models. When you apply a filter to a shared dimension (like `dim_calendar`), that filter automatically cascades to all models connected through graph edges.

**Key Concept**: Filters follow the graph edges, not model boundaries.

---

## The Calendar Filter Pattern

`dim_calendar` is the most common example of filter propagation because nearly every model references it for time-based analysis.

### Model Connections to Calendar

```
                        ┌─────────────────┐
                        │   dim_calendar  │
                        │    (core)       │
                        └────────┬────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
        ▼                        ▼                        ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│fact_stock_    │    │fact_forecast  │    │fact_local_    │
│  prices       │    │               │    │unemployment   │
│  (stocks)     │    │  (forecast)   │    │(city_finance) │
└───────────────┘    └───────────────┘    └───────────────┘
        │                        │
        ▼                        ▼
┌───────────────┐    ┌───────────────┐
│  dim_stock    │    │fact_unemployment│
│               │    │    (macro)     │
└───────────────┘    └───────────────┘
```

### How Calendar Filters Propagate

**Step 1: User Sets Date Filter**
```yaml
$filter${
type: date_range
label: Date Range
column: date
source: core.dim_calendar
default:
  start: 2024-01-01
  end: 2024-12-31
}
```

**Step 2: Filter Engine Identifies Connected Tables**
```python
# Filter engine traverses graph edges
connected_tables = graph.find_tables_with_edge_to("core.dim_calendar")
# Returns: [
#   "stocks.fact_stock_prices",
#   "forecast.fact_forecasts",
#   "city_finance.fact_local_unemployment",
#   "macro.fact_unemployment"
# ]
```

**Step 3: Filter Applied to All Connected Tables**
```sql
-- Generated WHERE clauses automatically added to each table:

-- stocks.fact_stock_prices
WHERE trade_date BETWEEN '2024-01-01' AND '2024-12-31'

-- forecast.fact_forecasts
WHERE prediction_date BETWEEN '2024-01-01' AND '2024-12-31'

-- macro.fact_unemployment
WHERE date BETWEEN '2024-01-01' AND '2024-12-31'
```

---

## Filter Propagation Rules

### Rule 1: Filters Follow Edges

Filters only propagate through **defined graph edges**. If two tables aren't connected by an edge, filters don't cross between them.

```yaml
# stocks/graph.yaml - Edge defines filter path
edges:
  - from: fact_stock_prices
    to: core.dim_calendar
    on: ["trade_date=date"]
    type: left
```

**Result**: Date filter on `dim_calendar` automatically applies to `fact_stock_prices` via the `trade_date=date` edge.

---

### Rule 2: Column Mapping Determines Application

The edge's `on` clause determines how the filter is applied:

```yaml
# Edge definition
- from: fact_stock_prices
  to: core.dim_calendar
  on: ["trade_date=date"]  # Maps local column to filter column
```

**Filter Translation**:
- Filter: `dim_calendar.date BETWEEN '2024-01-01' AND '2024-12-31'`
- Applied: `fact_stock_prices.trade_date BETWEEN '2024-01-01' AND '2024-12-31'`

---

### Rule 3: Transitive Propagation

Filters can propagate through multiple hops:

```
dim_calendar → fact_stock_prices → dim_stock → dim_company
```

If you filter `dim_calendar`, the filter reaches `dim_company` through the chain:
1. `dim_calendar` → `fact_stock_prices` (via `trade_date=date`)
2. `fact_stock_prices` → `dim_stock` (via `ticker=ticker`)
3. `dim_stock` → `dim_company` (via `company_id=company_id`)

---

### Rule 4: Filter Pushdown Optimization

For performance, filters are pushed down to the storage layer:

```python
# Without pushdown (slow):
df = read_parquet("storage/silver/stocks/facts/fact_stock_prices/")
df = df.filter(df.trade_date >= '2024-01-01')

# With pushdown (fast):
df = read_parquet(
    "storage/silver/stocks/facts/fact_stock_prices/",
    filters=[("trade_date", ">=", "2024-01-01")]
)
```

---

## Common Filter Patterns

### Pattern 1: Ticker Filter Across Models

When user selects tickers, filter propagates to all ticker-related tables:

```yaml
$filter${
type: multi_select
label: Tickers
column: ticker
source: stocks.dim_stock
}
```

**Propagation**:
```
dim_stock (ticker)
    → fact_stock_prices (ticker)
    → fact_technical_indicators (ticker)
    → fact_forecasts (ticker)
```

---

### Pattern 2: Company Filter to Securities

Company filter cascades down to all securities for that company:

```yaml
$filter${
type: multi_select
label: Companies
column: company_name
source: company.dim_company
}
```

**Propagation**:
```
dim_company (company_id)
    → dim_stock (company_id → ticker)
        → fact_stock_prices (ticker)
```

**Translation**:
1. User selects company "Apple Inc."
2. System finds `company_id = 'COMPANY_0000320193'`
3. Finds stocks with that `company_id` → AAPL
4. Filters all stock facts by `ticker = 'AAPL'`

---

### Pattern 3: Date Range to All Time-Series

Universal date filter for any multi-model analysis:

```yaml
$filter${
type: date_range
label: Analysis Period
column: date
source: core.dim_calendar
propagate_to:
  - stocks.fact_stock_prices:trade_date
  - macro.fact_unemployment:date
  - forecast.fact_forecasts:prediction_date
}
```

---

## Implementation Details

### GraphFilterEngine

**File**: `core/session/graph_filter_engine.py`

```python
class GraphFilterEngine:
    """Propagates filters through model graph."""

    def __init__(self, model_registry, graph):
        self.registry = model_registry
        self.graph = graph

    def propagate_filter(self, filter_spec: dict, source_table: str) -> dict:
        """
        Propagate a filter from source table to all connected tables.

        Args:
            filter_spec: Filter definition (column, operator, value)
            source_table: Table where filter originates (e.g., "core.dim_calendar")

        Returns:
            Dict mapping table names to their translated filters
        """
        translated_filters = {}

        # Find all tables connected to source
        connected = self.graph.get_tables_connected_to(source_table)

        for target_table, edge in connected:
            # Translate filter column using edge mapping
            translated_column = self._translate_column(
                filter_spec['column'],
                edge['on']
            )

            translated_filters[target_table] = {
                'column': translated_column,
                'operator': filter_spec['operator'],
                'value': filter_spec['value']
            }

        return translated_filters

    def _translate_column(self, source_col: str, edge_mapping: list) -> str:
        """Translate column name using edge mapping."""
        for mapping in edge_mapping:
            local, remote = mapping.split('=')
            if remote == source_col:
                return local
        return source_col
```

---

### Filter Application in Queries

**File**: `core/session/universal_session.py`

```python
class UniversalSession:
    def query_with_propagated_filters(
        self,
        sql: str,
        base_filters: dict,
        source_dimension: str
    ):
        """Execute query with filters propagated through graph."""

        # Get tables referenced in query
        tables = self._extract_tables(sql)

        # Propagate filters to all relevant tables
        all_filters = {}
        for filter_spec in base_filters:
            propagated = self.filter_engine.propagate_filter(
                filter_spec,
                source_dimension
            )
            all_filters.update(propagated)

        # Apply filters to query
        filtered_sql = self._apply_filters(sql, all_filters)

        return self.execute(filtered_sql)
```

---

## Notebook Example

### Multi-Model Analysis with Calendar Filter

```markdown
---
id: market-economic-analysis
title: Market and Economic Analysis
models: [stocks, macro, forecast]
---

# Stock Market vs Economic Indicators

$filter${
type: date_range
label: Analysis Period
column: date
source: core.dim_calendar
}

This date filter automatically applies to:
- Stock prices (via trade_date)
- Unemployment data (via date)
- Forecasts (via prediction_date)

$exhibits${
type: line_chart
title: S&P 500 vs Unemployment
sources:
  - stocks.fact_stock_prices
  - macro.fact_unemployment
x: date
y:
  - source: stocks.fact_stock_prices
    column: close
    label: S&P 500
  - source: macro.fact_unemployment
    column: unemployment_rate
    label: Unemployment %
}
```

**Behind the Scenes**:
1. User sets date range to 2024
2. Filter engine propagates to all 3 sources
3. Each table gets WHERE clause with its date column
4. Exhibit renders with synchronized time periods

---

## Debugging Filter Propagation

### Log Filter Paths

```python
# Enable filter propagation logging
import logging
logging.getLogger('de_funk.filter_engine').setLevel(logging.DEBUG)

# Output:
# DEBUG: Filter on core.dim_calendar.date propagating...
# DEBUG:   → stocks.fact_stock_prices.trade_date
# DEBUG:   → macro.fact_unemployment.date
# DEBUG:   → forecast.fact_forecasts.prediction_date
```

### Verify Edge Connections

```python
from models.api.registry import get_model_registry

registry = get_model_registry()
graph = registry.get_combined_graph()

# Find all tables connected to dim_calendar
connected = graph.get_edges_from("core.dim_calendar")
for edge in connected:
    print(f"  → {edge['target']} via {edge['on']}")
```

---

## Best Practices

### 1. Always Define Calendar Edges

Every fact table should have an edge to `dim_calendar`:

```yaml
edges:
  - from: fact_my_data
    to: core.dim_calendar
    on: ["date_column=date"]
    type: left
```

### 2. Use Consistent Column Names

Standardize date column names for easier propagation:
- `trade_date` for market data
- `date` for general time-series
- `prediction_date` for forecasts

### 3. Test Filter Propagation

```python
def test_calendar_filter_propagates():
    """Verify date filter reaches all connected tables."""
    session = UniversalSession()

    # Apply date filter
    filters = [{'column': 'date', 'operator': '>=', 'value': '2024-01-01'}]

    # Query multiple models
    result = session.query("""
        SELECT
            s.trade_date,
            s.close,
            m.unemployment_rate
        FROM stocks.fact_stock_prices s
        JOIN macro.fact_unemployment m ON s.trade_date = m.date
    """, filters=filters)

    # Verify both tables were filtered
    assert result['trade_date'].min() >= '2024-01-01'
```

---

## Related Documentation

- [DAG Explained](dag-explained.md) - Graph structure overview
- [Cross-Model References](cross-model-references.md) - Edge definitions
- [Filter Engine (UI)](../07-ui-system/filter-engine-ui.md) - UI filter widgets
- [Query Planner](query-planner.md) - How joins are resolved
