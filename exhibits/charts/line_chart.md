---
type: line_chart
category: charts
title: Line Chart
description: Time series visualization with one or more traces
icon: trending-up
version: 1.0.0

# Schema Definition
schema:
  required:
    - type
    - domain
    - x_axis
    - y_axis

  properties:
    x_axis:
      type: object
      required: true
      description: X-axis configuration (typically time dimension)
      properties:
        dimension:
          type: string
          description: Static dimension reference
          example: temporal.dim_calendar.date
        available:
          type: array
          items: string
          description: Dynamic selector options
        default:
          type: string
          description: Default selection (when using available)
        label:
          type: string
          description: Axis label

    y_axis:
      type: object
      required: true
      description: Y-axis configuration (measures)
      properties:
        measure:
          type: string
          description: Static measure reference
          example: securities.stocks.measures.close_price
        available:
          type: array
          items: string
          description: Dynamic selector options
        default:
          type: string | array
          description: Default selection(s)
        multi:
          type: boolean
          default: false
          description: Allow multiple measures
        label:
          type: string
          description: Axis label

    color:
      type: object
      description: Color/grouping dimension
      properties:
        dimension:
          type: string
          description: Static dimension for color grouping
        available:
          type: array
          items: string
          description: Dynamic selector options
        default:
          type: string
          description: Default selection

    options:
      type: object
      description: Plotly-specific options
      properties:
        mode:
          type: string
          enum: [lines, markers, lines+markers]
          default: lines+markers
        fill:
          type: string
          enum: [none, tozeroy, tonexty]
          default: none
        line_width:
          type: number
          default: 2
        marker_size:
          type: number
          default: 6

# Examples
examples:
  basic:
    title: Basic Line Chart
    description: Simple time series with single measure
    code: |
      ```exhibit
      type: line_chart
      domain: stocks

      x_axis:
        dimension: temporal.dim_calendar.date
        label: Date

      y_axis:
        measure: securities.stocks.measures.close_price
        label: Price ($)

      color:
        dimension: securities.stocks.dim_stock.ticker
      ```

  dynamic_selectors:
    title: Dynamic Selectors
    description: User can switch measures and dimensions
    code: |
      ```exhibit
      type: line_chart
      domain: stocks
      title: Stock Analysis

      x_axis:
        available:
          - temporal.dim_calendar.date
          - temporal.dim_calendar.week
          - temporal.dim_calendar.month
        default: temporal.dim_calendar.date

      y_axis:
        available:
          - securities.stocks.measures.close_price
          - securities.stocks.measures.volume
          - securities.stocks.measures.daily_return
        default: securities.stocks.measures.close_price
        multi: true

      color:
        available:
          - securities.stocks.dim_stock.ticker
          - securities.stocks.dim_stock.sector
        default: securities.stocks.dim_stock.ticker
      ```

  with_filters:
    title: With Exhibit Filters
    description: Line chart with custom filters
    code: |
      ```exhibit
      type: line_chart
      domain: stocks
      title: High-Value Stock Trends

      page_filters:
        inherit: true
        ignore: [sector]

      filters:
        - id: min_price
          type: slider
          label: Minimum Price
          source: securities.stocks.fact_stock_prices.close
          min: 0
          max: 1000
          default: 100

      metrics:
        - column: securities.stocks.measures.close_price
          label: Avg Close
          aggregation: avg
          format: "$,.2f"

      x_axis:
        dimension: temporal.dim_calendar.date

      y_axis:
        measure: securities.stocks.measures.close_price

      color:
        dimension: securities.stocks.dim_stock.ticker
      ```
---

# Line Chart

Time series visualization with one or more traces. Ideal for showing trends over time.

## When to Use

- **Trends over time** - Stock prices, metrics, KPIs
- **Multiple series comparison** - Compare multiple tickers, categories
- **Continuous data** - Data that flows naturally from point to point

## Basic Example

```yaml
```exhibit
type: line_chart
domain: stocks

x_axis:
  dimension: temporal.dim_calendar.date

y_axis:
  measure: securities.stocks.measures.close_price

color:
  dimension: securities.stocks.dim_stock.ticker
```
```

## Rendered Output

```
┌─────────────────────────────────────────────────────────┐
│ X-Axis: [Date ▼]   Measures: [Close Price ▼]            │
│ Color By: [Ticker ▼]                                    │
├─────────────────────────────────────────────────────────┤
│                                                         │
│     ●────●                                              │
│    /      \      ●────●                                 │
│   /        \    /      \                                │
│  ●          \●/         \●                              │
│                                                         │
├─────────────────────────────────────────────────────────┤
│ Legend: ● AAPL  ● MSFT  ● GOOGL                        │
└─────────────────────────────────────────────────────────┘
```

## Configuration

### X-Axis (Required)

| Property | Type | Description |
|----------|------|-------------|
| `dimension` | string | Static dimension reference |
| `available` | array | Dynamic selector options |
| `default` | string | Default selection |
| `label` | string | Axis label |

**Static:**
```yaml
x_axis:
  dimension: temporal.dim_calendar.date
  label: Date
```

**Dynamic:**
```yaml
x_axis:
  available:
    - temporal.dim_calendar.date
    - temporal.dim_calendar.week
    - temporal.dim_calendar.month
  default: temporal.dim_calendar.date
```

### Y-Axis (Required)

| Property | Type | Description |
|----------|------|-------------|
| `measure` | string | Static measure reference |
| `available` | array | Dynamic selector options |
| `default` | string/array | Default selection(s) |
| `multi` | boolean | Allow multiple measures |
| `label` | string | Axis label |

**Single Measure:**
```yaml
y_axis:
  measure: securities.stocks.measures.close_price
  label: Price ($)
```

**Multiple Measures:**
```yaml
y_axis:
  available:
    - securities.stocks.measures.close_price
    - securities.stocks.measures.volume
  default: [securities.stocks.measures.close_price]
  multi: true
```

### Color (Optional)

Groups data by dimension, creating separate traces:

```yaml
color:
  dimension: securities.stocks.dim_stock.ticker
```

### Plotly Options

```yaml
options:
  mode: lines+markers    # lines | markers | lines+markers
  fill: none             # none | tozeroy | tonexty
  line_width: 2
  marker_size: 6
```

## Filter Integration

### Inherit Page Filters

```yaml
page_filters:
  inherit: true          # Default - use all page filters
```

### Ignore Specific Filters

```yaml
page_filters:
  inherit: true
  ignore: [sector]       # Don't filter by sector
```

### Add Exhibit-Specific Filters

```yaml
filters:
  - id: min_price
    type: slider
    label: Min Price
    source: securities.stocks.fact_stock_prices.close
    default: 100

  - id: show_weekends
    type: boolean
    label: Include Weekends
    default: false
```

## Metrics Header

Display KPI cards above the chart:

```yaml
metrics:
  - column: securities.stocks.measures.close_price
    label: Avg Close
    aggregation: avg
    format: "$,.2f"

  - column: securities.stocks.measures.volume
    label: Total Volume
    aggregation: sum
    format: ",.0f"
```

## Domain Model References

Use domain model references instead of raw columns:

| Reference | Resolves To |
|-----------|-------------|
| `securities.stocks.measures.close_price` | Measure definition in `domains/securities/securities.stocks.md` |
| `securities.stocks.dim_stock.ticker` | Column in dimension table |
| `temporal.dim_calendar.date` | Cross-domain calendar reference |

## Complete Example

```yaml
```exhibit
id: price-trends
type: line_chart
domain: stocks
title: Stock Price Trends
description: Daily closing prices over time

page_filters:
  inherit: true
  ignore: [sector]

filters:
  - id: min_volume
    type: slider
    label: Min Daily Volume
    source: securities.stocks.fact_stock_prices.volume
    min: 0
    max: 100000000
    default: 1000000

metrics:
  - column: securities.stocks.measures.close_price
    label: Avg Close
    aggregation: avg
    format: "$,.2f"
  - column: securities.stocks.measures.daily_return
    label: Period Return
    aggregation: sum
    format: "+.2%"
    conditional_color: true

x_axis:
  available:
    - temporal.dim_calendar.date
    - temporal.dim_calendar.week
  default: temporal.dim_calendar.date
  label: Date

y_axis:
  available:
    - securities.stocks.measures.close_price
    - securities.stocks.measures.open_price
    - securities.stocks.measures.volume
  default: securities.stocks.measures.close_price
  multi: true
  label: Value

color:
  dimension: securities.stocks.dim_stock.ticker

display:
  height: 450
  show_legend: true
  interactive: true

options:
  mode: lines+markers
  line_width: 2
```
```
