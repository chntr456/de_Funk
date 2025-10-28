# YAML Notebook Schema Design

## Overview

The YAML notebook system provides a declarative way to define financial modeling notebooks with:
- **Graph-based data modeling**: Query backend data models and create relational frameworks
- **Flexible measures**: Support complex aggregations (weighted averages, custom calculations)
- **Dynamic exhibits**: Multiple visualization types with user interactions
- **Sophisticated filters**: Notebook-level and exhibit-level filtering with time defaults
- **API integration**: Pull macroeconomic and company profile data into unified exhibits

## Architecture

```
YAML Notebook File
    ↓
Notebook Parser
    ↓
Graph Query Engine (subgraph extraction from backend)
    ↓
Measure Engine (aggregations, calculations)
    ↓
Filter Engine (time, dimensions, metrics)
    ↓
Exhibit Renderer (Streamlit components)
```

## YAML Notebook Schema

### Complete Example

```yaml
version: 1.0
notebook:
  id: tech_stock_analysis
  title: "Tech Stock Performance Analysis"
  description: "Analyzing FAANG stocks with macroeconomic indicators"
  author: analyst@company.com
  created: 2024-01-01
  updated: 2024-01-15

# Graph defines the data subgraph for this notebook
graph:
  # Models to load (each represents a subgraph)
  models:
    - name: company
      config: configs/models/company.yaml
      nodes:
        - dim_company
        - dim_exchange
        - fact_prices
        - fact_news

    - name: macro_economy
      config: configs/models/macro.yaml
      nodes:
        - dim_economic_indicator
        - fact_indicator_values

  # Bridges between models (cross-model joins)
  bridges:
    - from: company.fact_prices
      to: macro_economy.fact_indicator_values
      on:
        - trade_date = indicator_date
      type: left
      description: "Link stock prices to economic indicators by date"

# Variables define reusable parameters and filters
variables:
  # Time is the default notebook variable
  time:
    type: date_range
    default:
      start: -30d  # 30 days ago
      end: today
    display_name: "Date Range"
    description: "Primary time filter for all exhibits"

  tickers:
    type: multi_select
    source:
      model: company
      node: dim_company
      column: ticker
      filter:
        - exchange_code in ['NASDAQ', 'NYSE']
        - company_name is not null
    default: ['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'META']
    display_name: "Stock Tickers"

  economic_indicators:
    type: multi_select
    source:
      model: macro_economy
      node: dim_economic_indicator
      column: indicator_code
    default: ['GDP', 'INFLATION', 'INTEREST_RATE']
    display_name: "Economic Indicators"

  min_volume:
    type: number
    default: 1000000
    display_name: "Minimum Volume"
    format: "#,##0"

# Dimensions define attributes from dimension tables
dimensions:
  - id: ticker
    source:
      model: company
      node: dim_company
      column: ticker
    display_name: "Ticker Symbol"
    type: string

  - id: company_name
    source:
      model: company
      node: dim_company
      column: company_name
    display_name: "Company Name"
    type: string

  - id: exchange
    source:
      model: company
      node: dim_exchange
      column: exchange_name
    display_name: "Exchange"
    type: string

  - id: trade_date
    source:
      model: company
      node: fact_prices
      column: trade_date
    display_name: "Trade Date"
    type: date
    format: "YYYY-MM-DD"

  - id: indicator_name
    source:
      model: macro_economy
      node: dim_economic_indicator
      column: indicator_name
    display_name: "Indicator"
    type: string

# Measures define calculations and aggregations
measures:
  - id: total_volume
    source:
      model: company
      node: fact_prices
      column: volume
    aggregation: sum
    display_name: "Total Volume"
    format: "#,##0"

  - id: avg_close_price
    source:
      model: company
      node: fact_prices
      column: close
    aggregation: avg
    display_name: "Average Close Price"
    format: "$#,##0.00"

  - id: vwap
    source:
      model: company
      node: fact_prices
      column: volume_weighted
    aggregation: avg
    display_name: "Volume Weighted Average Price"
    format: "$#,##0.00"

  # Weighted average example
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

  # Custom calculation example
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
    format: "#,##0.00%"

  # Window function example
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
    format: "$#,##0.00"

# Exhibits define visualizations and interactions
exhibits:
  - id: price_overview
    type: metric_cards
    title: "Price Overview"
    description: "Key price metrics for selected period"
    filters:
      # Inherits notebook variables by default
      time: $time
      tickers: $tickers
    metrics:
      - measure: avg_close_price
        comparison:
          period: previous
          label: "vs Prior Period"
      - measure: total_volume
      - measure: weighted_avg_price
      - measure: price_change_pct
    layout:
      columns: 4

  - id: price_trend
    type: line_chart
    title: "Price Trends Over Time"
    description: "Daily closing prices with moving averages"
    filters:
      time: $time
      tickers: $tickers
      min_volume: $min_volume
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
    interactive: true
    options:
      show_points: false
      line_width: 2
      grid: true

  - id: volume_analysis
    type: bar_chart
    title: "Trading Volume by Ticker"
    description: "Total volume comparison"
    filters:
      time: $time
      tickers: $tickers
    x_axis:
      dimension: ticker
      label: "Stock"
    y_axis:
      measures:
        - total_volume
      label: "Volume"
    color_by: exchange
    sort:
      by: total_volume
      order: desc

  - id: price_volume_correlation
    type: scatter_chart
    title: "Price vs Volume Correlation"
    filters:
      time: $time
      tickers: $tickers
    x_axis:
      measure: total_volume
      label: "Volume"
      scale: log
    y_axis:
      measure: avg_close_price
      label: "Avg Price ($)"
    color_by: ticker
    size_by: price_change_pct
    interactive: true
    options:
      show_regression: true

  - id: macro_comparison
    type: dual_axis_chart
    title: "Stock Performance vs Economic Indicators"
    description: "Correlating stock prices with macro indicators"
    filters:
      time: $time
      tickers: $tickers
      economic_indicators: $economic_indicators
    x_axis:
      dimension: trade_date
      label: "Date"
    y_axis_left:
      measures:
        - avg_close_price
      label: "Stock Price ($)"
    y_axis_right:
      source:
        model: macro_economy
        node: fact_indicator_values
        column: indicator_value
      aggregation: avg
      label: "Indicator Value"
    color_by: indicator_name
    legend: true

  - id: detailed_data
    type: data_table
    title: "Detailed Price Data"
    filters:
      time: $time
      tickers: $tickers
    columns:
      - dimension: trade_date
      - dimension: ticker
      - dimension: company_name
      - measure: avg_close_price
      - measure: total_volume
      - measure: price_change_pct
    pagination: true
    page_size: 50
    download: true
    sortable: true
    searchable: true

  - id: custom_analysis
    type: custom_component
    title: "Custom Financial Analysis"
    component: components/custom_financial_analysis.py
    filters:
      time: $time
      tickers: $tickers
    params:
      risk_free_rate: 0.045
      market_ticker: 'SPY'

# Layout defines how exhibits are arranged
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
      columns: 2

  - section:
      title: "Advanced Analysis"
      exhibits:
        - price_volume_correlation
        - macro_comparison
      columns: 2

  - section:
      title: "Data Tables"
      exhibits:
        - detailed_data

# Export defines export configurations
exports:
  - id: pdf_report
    type: pdf
    title: "Stock Analysis Report"
    include:
      - price_overview
      - price_trend
      - macro_comparison
    format:
      page_size: letter
      orientation: landscape

  - id: excel_data
    type: excel
    sheets:
      - name: "Prices"
        exhibit: detailed_data
      - name: "Summary"
        exhibit: price_overview
```

## Component Specifications

### 1. Graph Query Engine

**Purpose**: Extract and materialize subgraphs from backend models

**Key Classes**:
- `NotebookGraph`: Represents the notebook's data subgraph
- `GraphQueryBuilder`: Builds Spark SQL queries from graph definitions
- `BridgeManager`: Handles cross-model joins

**Workflow**:
1. Load specified models and nodes
2. Validate bridges between models
3. Build unified query plan
4. Materialize joined dataframe
5. Cache for exhibit rendering

### 2. Measure Engine

**Purpose**: Handle complex calculations and aggregations

**Measure Types**:
- **Simple Aggregation**: `sum`, `avg`, `min`, `max`, `count`, `stddev`
- **Weighted Average**: `weighted_average` with value and weight columns
- **Calculation**: Custom expression with multiple sources
- **Window Function**: Time-series calculations with partitioning
- **Ratio**: Division of two measures
- **Year-over-Year**: Time-based comparisons

**Key Classes**:
- `Measure`: Base measure definition
- `AggregationEngine`: Executes aggregations on Spark DataFrames
- `ExpressionParser`: Parses and validates custom expressions
- `WindowCalculator`: Handles window functions

### 3. Filter Engine

**Purpose**: Apply dynamic filters at notebook and exhibit levels

**Filter Types**:
- **date_range**: Start and end dates with relative notation (`-30d`, `today`)
- **multi_select**: Multiple values from dimension
- **single_select**: Single value from dimension
- **number**: Numeric filter with operators (`>`, `<`, `=`, `between`)
- **text**: Text search/filter
- **boolean**: True/false toggle

**Key Features**:
- Filter inheritance: Exhibits inherit notebook-level variables
- Filter override: Exhibits can override or extend filters
- Dynamic sources: Populate filter options from dimension tables
- Default values: Support view sharing with pre-set filters
- Filter dependencies: Cascade filters based on selections

**Key Classes**:
- `Filter`: Base filter definition
- `FilterContext`: Manages active filter values
- `FilterApplicator`: Applies filters to DataFrames

### 4. Exhibit System

**Purpose**: Render dynamic, interactive visualizations

**Exhibit Types**:
- **metric_cards**: Summary metrics with comparisons
- **line_chart**: Time-series line charts
- **bar_chart**: Bar/column charts
- **scatter_chart**: Scatter plots with sizing
- **dual_axis_chart**: Dual Y-axis charts
- **heatmap**: Correlation heatmaps
- **data_table**: Interactive data tables
- **pivot_table**: Pivot tables with drill-down
- **custom_component**: User-defined Streamlit components

**Key Features**:
- Interactive elements: Click, hover, zoom
- Dynamic updates: Respond to filter changes
- Theming: Consistent styling
- Export: Download charts as images/data
- Responsive: Adapt to screen size

**Key Classes**:
- `Exhibit`: Base exhibit definition
- `ExhibitRenderer`: Renders exhibits in Streamlit
- `ChartBuilder`: Builds Plotly/Altair charts
- `InteractionHandler`: Manages user interactions

## Implementation Plan

### Phase 1: Core Infrastructure
1. Enhanced storage abstraction with graph support
2. Notebook YAML parser and validator
3. Graph query engine
4. Measure engine with aggregations

### Phase 2: Filtering and Variables
1. Filter engine with inheritance
2. Variable resolution system
3. Dynamic filter sources from dimensions

### Phase 3: Exhibit System
1. Base exhibit renderer
2. Individual exhibit types (metrics, charts, tables)
3. Interactive features
4. Layout manager

### Phase 4: UI Integration
1. Streamlit notebook viewer
2. Filter sidebar
3. Exhibit rendering
4. Export functionality

### Phase 5: Advanced Features
1. External API integration (macroeconomic data)
2. Custom components support
3. Notebook sharing and versioning
4. Performance optimization (caching, lazy loading)

## File Structure

```
src/
├── notebook/
│   ├── __init__.py
│   ├── schema.py              # YAML schema definitions
│   ├── parser.py              # YAML parser and validator
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── query_engine.py   # Graph query builder
│   │   ├── bridge_manager.py # Cross-model joins
│   │   └── subgraph.py       # Subgraph extraction
│   ├── measures/
│   │   ├── __init__.py
│   │   ├── engine.py         # Aggregation engine
│   │   ├── calculator.py     # Expression calculator
│   │   └── window.py         # Window functions
│   ├── filters/
│   │   ├── __init__.py
│   │   ├── engine.py         # Filter application
│   │   ├── context.py        # Filter state management
│   │   └── types.py          # Filter type definitions
│   ├── exhibits/
│   │   ├── __init__.py
│   │   ├── base.py           # Base exhibit
│   │   ├── renderer.py       # Exhibit renderer
│   │   ├── metrics.py        # Metric cards
│   │   ├── charts.py         # Chart exhibits
│   │   ├── tables.py         # Table exhibits
│   │   └── layout.py         # Layout manager
│   └── api/
│       ├── __init__.py
│       └── notebook_session.py # Notebook execution session
├── ui/
│   ├── notebook_app.py        # New notebook UI
│   └── components/            # Custom components
configs/
├── notebooks/
│   ├── tech_stock_analysis.yaml
│   ├── portfolio_performance.yaml
│   └── macro_indicators.yaml
```

## Benefits

1. **Declarative**: Define notebooks in YAML without code
2. **Reusable**: Share notebook templates across teams
3. **Flexible**: Support complex financial modeling scenarios
4. **Interactive**: Dynamic filters and visualizations
5. **Scalable**: Graph-based approach supports large datasets
6. **Maintainable**: Clear separation of data, logic, and presentation
7. **Extensible**: Easy to add new exhibit types and measures

## Next Steps

1. Implement core classes (parser, graph engine, measure engine)
2. Create example notebooks for testing
3. Build Streamlit UI with notebook viewer
4. Add external API integration for macroeconomic data
5. Performance testing and optimization
