# Architecture Refactoring Plan v2

## Problems Identified

### 1. Storage Service is Too Specific
**Current Issue:**
```python
class SilverStorageService:
    def get_dim_company(self, tickers=None) -> DataFrame
    def get_dim_exchange(self) -> DataFrame
    def get_fact_prices(self, start_date, end_date, tickers) -> DataFrame
    def get_prices_with_company(...) -> DataFrame
```

**Problem:** Every new table requires a new method. Not scalable.

### 2. Storage Config Separate from Model
**Current:**
- `configs/storage.json` - defines all table paths
- `configs/models/company.yaml` - defines graph structure
- No connection between them

**Problem:** Model doesn't know where its own data lives.

### 3. UI is Monolithic
**Current:** `notebook_app_duckdb.py` - 800+ lines
- Directory tree rendering
- Filter rendering
- Exhibit rendering
- YAML editing
- Session management
- All mixed together

**Problem:** Hard to maintain, no reusability, violates SRP.

### 4. Old Unused Code Exists
**Deprecated but still present:**
- `src/notebook/api/notebook_session.py` (old)
- `src/notebook/graph/query_engine.py` (old)
- `src/notebook/graph/subgraph.py` (old)
- `src/notebook/measures/engine.py` (old)
- `src/ui/notebook_app.py` (old)
- `src/ui/notebook_app_v2.py` (old)

### 5. No Validation
- No YAML validation
- No check if models exist
- No check if tables exist
- No schema validation

### 6. Data Definition vs UI Specification Mixed
**Current notebook YAML:**
```yaml
dimensions:
  - id: ticker
    source: { model: company, node: dim_company, column: ticker }

measures:
  - id: avg_close_price
    source: { model: company, node: fact_prices, column: close }
    aggregation: avg

exhibits:
  - id: price_overview
    dimensions: [ticker]
    measures: [avg_close_price]
```

**Problem:** Duplicates model schema. Model should be source of truth.

---

## Proposed Solution

### Approach A: Model-Centric (Recommended)

#### 1. Merge Storage into Model Config

**New company.yaml:**
```yaml
model: company
version: 1

# Storage configuration
storage:
  root: storage/silver/company
  format: parquet

# Schema definitions (source of truth)
schema:
  dimensions:
    dim_company:
      path: dims/dim_company
      columns:
        ticker: string
        company_name: string
        exchange_code: string
        company_id: string
      primary_key: [ticker]

    dim_exchange:
      path: dims/dim_exchange
      columns:
        exchange_code: string
        exchange_name: string
      primary_key: [exchange_code]

  facts:
    fact_prices:
      path: facts/fact_prices
      columns:
        trade_date: date
        ticker: string
        open: double
        high: double
        low: double
        close: double
        volume_weighted: double
        volume: long
      partitions: [trade_date]

    prices_with_company:
      path: facts/prices_with_company
      columns:
        trade_date: date
        ticker: string
        company_name: string
        exchange_name: string
        open: double
        high: double
        low: double
        close: double
        volume_weighted: double
        volume: long

# Measures available for this model
measures:
  avg_close_price:
    description: "Average closing price"
    source: fact_prices.close
    aggregation: avg
    format: "$#,##0.00"

  total_volume:
    description: "Total trading volume"
    source: fact_prices.volume
    aggregation: sum
    format: "#,##0"

  max_high:
    description: "Highest price"
    source: fact_prices.high
    aggregation: max
    format: "$#,##0.00"

  min_low:
    description: "Lowest price"
    source: fact_prices.low
    aggregation: min
    format: "$#,##0.00"
```

#### 2. Generic Storage Service

```python
class SilverStorageService:
    """Generic storage service - no table-specific methods."""

    def __init__(self, spark: SparkSession):
        self.spark = spark
        self._cache = {}

    def get_table(
        self,
        model_name: str,
        table_name: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> DataFrame:
        """
        Get any table by name with optional filters.

        Args:
            model_name: Model name (e.g., 'company')
            table_name: Table name (e.g., 'fact_prices')
            filters: Optional filters to apply
        """
        model = self.model_registry.get_model(model_name)
        table_config = model.get_table(table_name)

        path = self._build_path(model, table_config)
        df = self.spark.read.parquet(path)

        if filters:
            df = self._apply_filters(df, filters, table_config)

        return df

    def list_models(self) -> List[str]:
        """List all available models."""
        return self.model_registry.list_models()

    def list_tables(self, model_name: str) -> List[str]:
        """List all tables in a model."""
        model = self.model_registry.get_model(model_name)
        return model.list_tables()

    def get_schema(self, model_name: str, table_name: str) -> Dict:
        """Get schema for a table."""
        model = self.model_registry.get_model(model_name)
        return model.get_table_schema(table_name)
```

#### 3. Model Registry

```python
class ModelRegistry:
    """
    Registry of available models.

    Discovers models from configs/models/*.yaml
    Provides model metadata and validation.
    """

    def __init__(self, models_dir: Path):
        self.models_dir = models_dir
        self.models: Dict[str, ModelConfig] = {}
        self._load_models()

    def _load_models(self):
        """Load all model configs."""
        for yaml_file in self.models_dir.glob("*.yaml"):
            config = yaml.safe_load(yaml_file.read_text())
            model = ModelConfig.from_dict(config)
            self.models[model.name] = model

    def get_model(self, name: str) -> ModelConfig:
        """Get model by name."""
        if name not in self.models:
            raise ValueError(f"Model '{name}' not found. Available: {list(self.models.keys())}")
        return self.models[name]

    def list_models(self) -> List[str]:
        """List all model names."""
        return list(self.models.keys())


class ModelConfig:
    """
    Configuration for a data model.

    Contains:
    - Storage configuration
    - Schema definitions (dims, facts)
    - Available measures
    - Validation rules
    """

    def __init__(self, name: str, storage: Dict, schema: Dict, measures: Dict):
        self.name = name
        self.storage = storage
        self.schema = schema
        self.measures = measures

    def list_tables(self) -> List[str]:
        """List all tables (dims + facts)."""
        dims = list(self.schema.get('dimensions', {}).keys())
        facts = list(self.schema.get('facts', {}).keys())
        return dims + facts

    def get_table(self, table_name: str) -> Dict:
        """Get table configuration."""
        if table_name in self.schema.get('dimensions', {}):
            return self.schema['dimensions'][table_name]
        if table_name in self.schema.get('facts', {}):
            return self.schema['facts'][table_name]
        raise ValueError(f"Table '{table_name}' not found in model '{self.name}'")

    def get_table_schema(self, table_name: str) -> Dict:
        """Get columns for a table."""
        table = self.get_table(table_name)
        return table['columns']

    def list_measures(self) -> List[str]:
        """List available measures."""
        return list(self.measures.keys())

    def get_measure(self, measure_id: str) -> Dict:
        """Get measure definition."""
        if measure_id not in self.measures:
            raise ValueError(f"Measure '{measure_id}' not found. Available: {list(self.measures.keys())}")
        return self.measures[measure_id]
```

#### 4. Simplified Notebook YAML

**New notebook YAML (no schema duplication):**
```yaml
notebook:
  title: "Stock Performance Analysis"
  description: "Analyzing stock prices"

# Just reference the model
models:
  - company

# Variables for filtering
variables:
  time:
    type: date_range
    default:
      start: "2024-01-01"
      end: "2024-01-05"
    display_name: "Date Range"

  tickers:
    type: multi_select
    default: ["AAPL", "GOOGL", "MSFT"]
    display_name: "Stock Tickers"

# Exhibits - reference model's measures directly
exhibits:
  - id: price_overview
    type: metric_cards
    title: "Price Overview"
    source: company.prices_with_company  # Fully qualified
    measures: [avg_close_price, total_volume, max_high, min_low]  # Model knows these
    filters:
      trade_date: $time
      ticker: $tickers

  - id: price_trend
    type: line_chart
    title: "Daily Closing Prices"
    source: company.prices_with_company
    x_axis: trade_date
    y_axis: [avg_close_price]
    color_by: ticker
    filters:
      trade_date: $time
      ticker: $tickers

  - id: detailed_prices
    type: data_table
    title: "Detailed Price Data"
    source: company.prices_with_company
    columns: [trade_date, ticker, company_name, open, high, low, close, volume]
    filters:
      trade_date: $time
      ticker: $tickers

layout:
  - section:
      title: "Summary"
      exhibits: [price_overview]
  - section:
      title: "Trends"
      columns: 1
      exhibits: [price_trend]
  - section:
      title: "Details"
      exhibits: [detailed_prices]
```

**Benefits:**
- No dimension/measure definitions (model has them)
- Just specify what to show and filters
- Model is source of truth
- Easier to maintain

#### 5. Validation Layer

```python
class NotebookValidator:
    """Validates notebook configuration against available models."""

    def __init__(self, model_registry: ModelRegistry):
        self.model_registry = model_registry

    def validate(self, notebook_config: NotebookConfig) -> List[str]:
        """
        Validate notebook configuration.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Check models exist
        for model_name in notebook_config.models:
            if model_name not in self.model_registry.list_models():
                errors.append(f"Model '{model_name}' not found")

        # Check exhibits reference valid tables
        for exhibit in notebook_config.exhibits:
            model_name, table_name = self._parse_source(exhibit.source)

            # Check model exists
            try:
                model = self.model_registry.get_model(model_name)
            except ValueError as e:
                errors.append(str(e))
                continue

            # Check table exists
            if table_name not in model.list_tables():
                errors.append(f"Table '{table_name}' not found in model '{model_name}'")

            # Check measures exist
            for measure_id in exhibit.measures:
                if measure_id not in model.list_measures():
                    errors.append(f"Measure '{measure_id}' not found in model '{model_name}'")

        return errors

    def _parse_source(self, source: str) -> Tuple[str, str]:
        """Parse 'model.table' source string."""
        parts = source.split('.')
        if len(parts) != 2:
            raise ValueError(f"Invalid source format: {source}. Expected 'model.table'")
        return parts[0], parts[1]
```

#### 6. UI Component Structure

```
src/ui/
├── app.py                       # Main entry (50 lines)
├── components/
│   ├── __init__.py
│   ├── sidebar.py               # Sidebar component
│   │   ├── NotebookTree        # Directory tree
│   │   └── FilterPanel         # Filters
│   ├── notebook_view.py         # Notebook viewer
│   │   ├── TabBar              # Tab management
│   │   └── NotebookContent     # Main content area
│   ├── exhibits/
│   │   ├── __init__.py
│   │   ├── base.py             # BaseExhibit
│   │   ├── metric_cards.py     # MetricCardsExhibit
│   │   ├── line_chart.py       # LineChartExhibit
│   │   ├── bar_chart.py        # BarChartExhibit
│   │   └── data_table.py       # DataTableExhibit
│   ├── yaml_editor.py          # YAMLEditor component
│   └── theme.py                # ThemeManager
└── utils/
    ├── __init__.py
    └── session.py              # Session state helpers
```

**Example Component:**
```python
# components/exhibits/metric_cards.py
class MetricCardsExhibit:
    """Renders metric cards exhibit."""

    def __init__(self, exhibit_config, theme):
        self.config = exhibit_config
        self.theme = theme

    def render(self, data: pd.DataFrame):
        """Render metric cards."""
        cols = st.columns(len(self.config.metrics))

        for i, metric_id in enumerate(self.config.metrics):
            with cols[i]:
                self._render_metric_card(data, metric_id)

    def _render_metric_card(self, data: pd.DataFrame, metric_id: str):
        """Render single metric card."""
        if metric_id not in data.columns:
            st.metric(label=metric_id, value="N/A")
            return

        value = data[metric_id].iloc[0]
        formatted = self._format_value(value)

        st.metric(
            label=metric_id.replace('_', ' ').title(),
            value=formatted
        )
```

---

## Comparison: Approach A vs Current

| Aspect | Current | Approach A (Recommended) |
|--------|---------|--------------------------|
| **Storage Config** | Separate storage.json | Merged into model config |
| **Storage Service** | Specific methods per table | Generic `get_table()` |
| **Model Registry** | None | Central registry with validation |
| **Notebook YAML** | Duplicates schema | References model schema |
| **Validation** | None | Full validation layer |
| **UI Structure** | Monolithic (800 lines) | Component-based (50-100 lines each) |
| **Code to Delete** | 0 | ~2000 lines |
| **Maintainability** | Low | High |
| **Extensibility** | Hard (new method per table) | Easy (generic interface) |

---

## Implementation Plan

### Phase 1: Model & Storage (1-2 hours)
1. ✅ Update company.yaml with storage + schema + measures
2. ✅ Create ModelRegistry and ModelConfig classes
3. ✅ Refactor SilverStorageService to be generic
4. ✅ Update NotebookService to use ModelRegistry
5. ✅ Update CompanySilverBuilder to use new model config

### Phase 2: Validation (30 min)
1. ✅ Create NotebookValidator
2. ✅ Integrate validation into NotebookService.load_notebook()
3. ✅ Add error reporting

### Phase 3: Simplify Notebook YAML (30 min)
1. ✅ Update stock_analysis.yaml to new format
2. ✅ Update parser to handle new format
3. ✅ Remove old dimension/measure parsing

### Phase 4: UI Components (2 hours)
1. ✅ Create base component classes
2. ✅ Break down into components (sidebar, exhibits, editor)
3. ✅ Create new app.py as orchestrator
4. ✅ Update theme management

### Phase 5: Cleanup (30 min)
1. ✅ Delete old notebook_session.py
2. ✅ Delete graph/ directory
3. ✅ Delete measures/ directory
4. ✅ Delete old UI files (notebook_app.py, notebook_app_v2.py)
5. ✅ Update imports throughout

---

## Questions for Validation

1. **Model Config Approach**: Do you agree with merging storage + schema + measures into company.yaml?

2. **Generic Storage Service**: Is `get_table(model_name, table_name, filters)` the right interface?

3. **Model Registry**: Should this be singleton or injected?

4. **Notebook YAML Format**: Do you like the simplified format with just model references?

5. **UI Components**: Is the proposed component structure clear?

6. **Graph Visualization**: You mentioned "display graphs of connected pieces" - do you want:
   - Visual graph of data lineage (Bronze → Silver)?
   - Graph of model relationships (fact → dim edges)?
   - Both?

---

## Alternative Approach B: Keep Separate

If you prefer keeping storage.json separate:

**Pros:**
- Storage config reusable across models
- Separation of concerns

**Cons:**
- Model doesn't know where its data lives
- Duplication between storage.json and model.yaml
- Two places to update when adding tables

**Recommendation:** Approach A is better - model should own its storage configuration.

---

## Next Steps

Please review and provide feedback on:
1. Overall approach (Approach A vs alternative)
2. Model config structure
3. UI component breakdown
4. Anything else before I start implementing

Once approved, I'll implement in phases with commits at each phase for review.
