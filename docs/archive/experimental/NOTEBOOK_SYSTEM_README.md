# Markdown Notebook System for Financial Modeling

## Overview

The Markdown Notebook System provides a document-centric approach to building financial modeling notebooks. Create markdown files with inline filters and exhibits that generate interactive data visualizations in Streamlit.

## Key Features

### 1. **Markdown-First Approach**
- Write notebooks in markdown with inline filters and exhibits
- No code required - use $filter${} and $exhibits${} syntax
- Human-readable format with YAML front matter
- Version-controlled notebook definitions

### 2. **Graph-Based Data Modeling**
- Query backend data models and create relational frameworks
- Subgraph extraction for notebook-specific data
- Cross-model bridges for joining different data sources
- Support for macroeconomic and company profile data in unified exhibits

### 3. **Flexible Measures & Aggregations**
- Simple aggregations (sum, avg, min, max, count, stddev)
- Weighted averages with value and weight columns
- Custom calculations with expressions
- Window functions for time-series analysis (moving averages, lag/lead)
- Variable declarations from dimension tables

### 4. **Dynamic Exhibits**
- Multiple visualization types (line charts, bar charts, scatter plots, tables)
- Interactive user controls
- Notebook-level and exhibit-specific filters
- Responsive layouts with sections and columns

### 5. **Dynamic Database-Driven Filters**
- Filters defined with inline $filter${} syntax
- Options pulled directly from database (no static lists)
- Multi-select, date ranges, sliders, and more
- Automatic SQL WHERE clause generation
- Filter values persist in session state
- Support for multiple operators (in, between, gte, contains, fuzzy)

## Architecture

```
Markdown Notebook File (.md)
    ↓
Markdown Parser (extracts front matter, filters, exhibits)
    ↓
Model Session Initialization (from front matter)
    ↓
Dynamic Filter Rendering (database-driven options)
    ↓
Markdown Renderer (text, collapsible sections)
    ↓
Exhibit Renderer (visualizations with filtered data)
    ↓
DuckDB Backend (10-100x faster than Spark)
```

## File Structure

```
configs/
├── notebooks/
│   ├── stock_analysis.md                    # Markdown notebook with inline filters/exhibits
│   ├── aggregate_stock_analysis.md          # Weighted aggregate indices notebook
│   ├── forecast_analysis.md                 # Time series forecast notebook
│   └── Financial Analysis/
│       └── stock_analysis.md                # Organized in folders
├── models/
│   ├── company.yaml                         # Company model definition
│   └── forecast.yaml                        # Forecast model definition
└── storage.json                             # Storage configuration

src/
├── notebook/
│   ├── __init__.py
│   ├── schema.py                    # YAML schema definitions
│   ├── parser.py                    # YAML parser and validator
│   ├── graph/
│   │   ├── query_engine.py         # Graph query builder
│   │   ├── bridge_manager.py       # Cross-model joins
│   │   └── subgraph.py             # Subgraph representation
│   ├── measures/
│   │   ├── engine.py               # Aggregation engine
│   │   ├── calculator.py           # Expression calculator
│   │   └── window.py               # Window functions
│   ├── filters/
│   │   ├── engine.py               # Filter application
│   │   ├── context.py              # Filter state management
│   │   └── types.py                # Filter type definitions
│   ├── exhibits/
│   │   ├── base.py                 # Base exhibit
│   │   └── ...                     # Exhibit implementations
│   └── api/
│       └── notebook_session.py     # Notebook execution session
└── ui/
    └── notebook_app.py              # Streamlit notebook viewer
```

## Quick Start

### 1. Create a Notebook YAML

Create a file in `configs/notebooks/my_notebook.yaml`:

```yaml
version: "1.0"

notebook:
  id: my_analysis
  title: "My Financial Analysis"
  description: "Analyzing stock performance"

graph:
  models:
    - name: company
      config: configs/models/company.yaml
      nodes:
        - dim_company
        - fact_prices

variables:
  time:
    type: date_range
    default:
      start: "-30d"
      end: "today"
    display_name: "Date Range"

  tickers:
    type: multi_select
    default: ["AAPL", "GOOGL"]
    display_name: "Stocks"

dimensions:
  - id: ticker
    source:
      model: company
      node: dim_company
      column: ticker
    display_name: "Ticker"
    type: string

  - id: trade_date
    source:
      model: company
      node: fact_prices
      column: trade_date
    display_name: "Date"
    type: date

measures:
  - id: avg_price
    source:
      model: company
      node: fact_prices
      column: close
    aggregation: avg
    display_name: "Average Price"
    format: "$#,##0.00"

exhibits:
  - id: price_chart
    type: line_chart
    title: "Price Trend"
    filters:
      time: $time
      tickers: $tickers
    x_axis:
      dimension: trade_date
    y_axis:
      measures:
        - avg_price
    color_by: ticker

layout:
  - section:
      title: "Analysis"
      exhibits:
        - price_chart
```

### 2. Run the Notebook App

```bash
streamlit run src/ui/notebook_app.py
```

### 3. Select Your Notebook

1. Open the Streamlit app in your browser
2. Select your notebook from the sidebar
3. Adjust filters as needed
4. View interactive exhibits

## YAML Notebook Schema

### Notebook Metadata

```yaml
notebook:
  id: unique_id
  title: "Display Title"
  description: "Description of the notebook"
  author: "email@company.com"
  created: "2024-01-01"
  updated: "2024-01-15"
  tags: [tag1, tag2]
```

### Graph Configuration

Define which models and nodes to load:

```yaml
graph:
  models:
    - name: company
      config: configs/models/company.yaml
      nodes:
        - dim_company
        - fact_prices

    - name: macro_economy
      config: configs/models/macro.yaml
      nodes:
        - dim_economic_indicator
        - fact_indicator_values

  # Bridges connect models
  bridges:
    - from: company.fact_prices
      to: macro_economy.fact_indicator_values
      on:
        - trade_date = indicator_date
      type: left
```

### Variables (Filters)

Define notebook-level filters:

```yaml
variables:
  time:
    type: date_range
    default:
      start: "-30d"  # 30 days ago
      end: "today"
    display_name: "Date Range"

  tickers:
    type: multi_select
    source:
      model: company
      node: dim_company
      column: ticker
    default: ["AAPL", "GOOGL"]
    display_name: "Stocks"

  min_volume:
    type: number
    default: 1000000
    display_name: "Minimum Volume"
```

**Supported Variable Types:**
- `date_range`: Start and end dates
- `multi_select`: Multiple values from list
- `single_select`: Single value from list
- `number`: Numeric value
- `text`: Text value
- `boolean`: True/false toggle

### Dimensions

Define attributes from dimension tables:

```yaml
dimensions:
  - id: ticker
    source:
      model: company
      node: dim_company
      column: ticker
    display_name: "Ticker Symbol"
    type: string

  - id: trade_date
    source:
      model: company
      node: fact_prices
      column: trade_date
    display_name: "Date"
    type: date
    format: "YYYY-MM-DD"
```

### Measures

Define calculations and aggregations:

#### Simple Aggregation

```yaml
measures:
  - id: total_volume
    source:
      model: company
      node: fact_prices
      column: volume
    aggregation: sum
    display_name: "Total Volume"
    format: "#,##0"
```

#### Weighted Average

```yaml
measures:
  - id: weighted_avg_price
    type: weighted_average
    value_column:
      model: company
      node: fact_prices
      column: close
    weight_column:
      model: company
      node: fact_prices
      column: volume
    display_name: "Volume-Weighted Avg Price"
    format: "$#,##0.00"
```

#### Custom Calculation

```yaml
measures:
  - id: price_change_pct
    type: calculation
    expression: "(close - open) / open * 100"
    sources:
      close:
        model: company
        node: fact_prices
        column: close
      open:
        model: company
        node: fact_prices
        column: open
    aggregation: avg
    display_name: "Avg Daily Change %"
```

#### Window Function (Moving Average)

```yaml
measures:
  - id: moving_avg_30d
    type: window_function
    source:
      model: company
      node: fact_prices
      column: close
    function: avg
    window:
      partition_by: [ticker]
      order_by: [trade_date]
      rows_between: [-29, 0]  # 30-day window
    display_name: "30-Day Moving Average"
```

### Exhibits

Define visualizations:

#### Metric Cards

```yaml
exhibits:
  - id: price_overview
    type: metric_cards
    title: "Price Overview"
    filters:
      time: $time
      tickers: $tickers
    metrics:
      - measure: avg_close_price
      - measure: total_volume
    layout:
      columns: 4
```

#### Line Chart

```yaml
exhibits:
  - id: price_trend
    type: line_chart
    title: "Price Trends"
    filters:
      time: $time
    x_axis:
      dimension: trade_date
      label: "Date"
    y_axis:
      measures:
        - avg_close_price
        - moving_avg_30d
      label: "Price ($)"
    color_by: ticker
    legend: true
```

#### Bar Chart

```yaml
exhibits:
  - id: volume_analysis
    type: bar_chart
    title: "Trading Volume"
    x_axis:
      dimension: ticker
    y_axis:
      measures:
        - total_volume
    color_by: exchange
    sort:
      by: total_volume
      order: desc
```

#### Data Table

```yaml
exhibits:
  - id: detailed_data
    type: data_table
    title: "Detailed Prices"
    columns:
      - trade_date
      - ticker
      - company_name
      - avg_close_price
      - total_volume
    pagination: true
    page_size: 50
    download: true
    sortable: true
```

**Supported Exhibit Types:**
- `metric_cards`: Summary metrics with comparisons
- `line_chart`: Time-series line charts
- `bar_chart`: Bar/column charts
- `scatter_chart`: Scatter plots
- `dual_axis_chart`: Dual Y-axis charts
- `heatmap`: Correlation heatmaps
- `data_table`: Interactive data tables
- `pivot_table`: Pivot tables with drill-down

### Layout

Define how exhibits are arranged:

```yaml
layout:
  - section:
      title: "Summary Metrics"
      exhibits:
        - price_overview

  - section:
      title: "Trend Analysis"
      exhibits:
        - price_trend
        - volume_analysis
      columns: 2  # Display in 2 columns

  - section:
      title: "Detailed Data"
      exhibits:
        - detailed_data
```

## Advanced Features

### 1. Cross-Model Joins (Bridges)

Connect data from multiple models:

```yaml
graph:
  models:
    - name: company
      nodes: [fact_prices]
    - name: macro_economy
      nodes: [fact_indicator_values]

  bridges:
    - from: company.fact_prices
      to: macro_economy.fact_indicator_values
      on:
        - trade_date = indicator_date
      type: left
```

### 2. Filter Inheritance

Exhibits inherit notebook-level filters and can override them:

```yaml
variables:
  time:
    type: date_range
    default:
      start: "-30d"
      end: "today"

exhibits:
  - id: recent_data
    filters:
      time: $time  # Inherits notebook time filter

  - id: historical_data
    filters:
      time:  # Overrides with custom range
        start: "-1y"
        end: "today"
```

### 3. Dynamic Filter Sources

Populate filter options from dimension tables:

```yaml
variables:
  tickers:
    type: multi_select
    source:
      model: company
      node: dim_company
      column: ticker
      filter:
        - exchange_code in ['NASDAQ', 'NYSE']
    display_name: "US Stocks"
```

### 4. Time Horizons

Use relative time notation:

- `-30d`: 30 days ago
- `-1w`: 1 week ago
- `-6m`: 6 months ago
- `-1y`: 1 year ago
- `today`: Current date
- `ytd`: Year-to-date
- `mtd`: Month-to-date
- `qtd`: Quarter-to-date

## Integration with Existing Pipeline

The notebook system integrates seamlessly with the existing data pipeline:

```
Polygon API
    ↓
Bronze Layer (raw data)
    ↓
CompanyModel.build() → Silver Layer
    ↓
ModelSession
    ↓
NotebookSession → YAML Notebook
    ↓
Streamlit Notebook Viewer
```

### Model Session Integration

```python
from src.orchestration.context import RepoContext
from src.model.api.session import ModelSession
from src.notebook.api.notebook_session import NotebookSession

# Get model session
ctx = RepoContext()
model_session = ModelSession(ctx)

# Create notebook session
notebook_session = NotebookSession(spark, model_session, ctx.repo_root)

# Load notebook
notebook_session.load_notebook("configs/notebooks/stock_analysis.yaml")

# Get exhibit data
df = notebook_session.get_exhibit_data("price_trend")
```

## Best Practices

### 1. Notebook Organization

- **One focus per notebook**: Keep notebooks focused on specific analyses
- **Reusable measures**: Define measures that can be shared across exhibits
- **Clear naming**: Use descriptive IDs and display names
- **Documentation**: Add descriptions to notebooks and exhibits

### 2. Performance Optimization

- **Filter early**: Apply filters at the notebook level when possible
- **Limit dimensions**: Only include necessary dimensions in exhibits
- **Aggregate data**: Use measures instead of raw columns
- **Partition awareness**: Consider data partitioning in time filters

### 3. Filter Design

- **Default values**: Set sensible defaults for filters
- **Time as primary**: Make time the primary filter for most notebooks
- **Progressive disclosure**: Start with common filters, add advanced ones as needed
- **Dynamic sources**: Load filter options from dimension tables for consistency

### 4. Exhibit Design

- **Clear titles**: Use descriptive titles for exhibits
- **Appropriate types**: Choose the right visualization for the data
- **Interactive elements**: Enable interactivity for exploration
- **Consistent formatting**: Use format strings for consistent number display

## Troubleshooting

### Notebook Won't Load

1. Check YAML syntax (use a YAML validator)
2. Verify model references exist
3. Check that all node IDs are valid
4. Ensure dimension and measure sources are correct

### Exhibit Shows No Data

1. Check filter values (may be too restrictive)
2. Verify dimension and measure IDs match definitions
3. Check that required columns exist in source nodes
4. Review filter context in debug mode

### Performance Issues

1. Add indexes to frequently filtered columns
2. Use partitioned reads when possible
3. Consider pre-aggregating data in the model layer
4. Limit the number of exhibits per section

## Future Enhancements

- [ ] Custom component support for advanced visualizations
- [ ] Notebook templates library
- [ ] Export to PDF/Excel
- [ ] Scheduled notebook execution
- [ ] Collaboration features (comments, sharing)
- [ ] Version control integration
- [ ] A/B testing for different notebook configurations
- [ ] Mobile-responsive layouts

## Examples

See the `configs/notebooks/` directory for example notebooks:

- `stock_analysis.yaml`: Basic stock price analysis
- (Add more examples as they're created)

## Support

For questions or issues:
1. Check this documentation
2. Review example notebooks
3. Check the schema design document: `docs/NOTEBOOK_SCHEMA_DESIGN.md`
4. Review inline code documentation

## Contributing

When adding new features:
1. Update schema definitions in `src/notebook/schema.py`
2. Update parser in `src/notebook/parser.py`
3. Add exhibit types in `src/notebook/exhibits/`
4. Update this documentation
5. Add example notebooks demonstrating the feature
