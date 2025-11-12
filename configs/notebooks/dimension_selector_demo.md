---
id: dimension_selector_demo
title: Dimension Selector and Collapsible Exhibits Demo
description: Demonstrating dynamic dimension selection and collapsible exhibits
tags: [demo, dimension-selector, collapsible]
models: [company]
author: analyst@company.com
created: 2025-01-01
---

$filter${
  id: trade_date
  type: date_range
  label: Date Range
  operator: between
  default: {start: "2024-01-01", end: "2024-01-05"}
  help_text: Filter by trade date range
}

$filter${
  id: ticker
  label: Stock Tickers
  type: select
  multi: true
  source: {model: company, table: fact_prices, column: ticker}
  help_text: Select stocks to analyze
}

# Dimension Selector and Collapsible Exhibits

This notebook demonstrates two powerful new features:

1. **Dimension Selector** - Dynamically switch between different dimensions (like exchange, sector, ticker) for grouping and coloring
2. **Collapsible Exhibits** - Hide/show exhibits in expandable sections to keep notebooks clean

## Dimension Selector Examples

### Example 1: Line Chart with Dynamic Dimension Selection

Select which dimension to use for coloring the lines. Try switching between different groupings!

$exhibits${
  type: line_chart
  source: company.fact_prices
  x: trade_date
  y: close
  title: Stock Price Trends - Dynamic Grouping
  description: Use the dimension selector to change how data is grouped (auto-join for exchange_name)
  dimension_selector: {
    available_dimensions: [ticker, exchange_name],
    default_dimension: ticker,
    label: "Group By",
    selector_type: radio,
    applies_to: color,
    help_text: "Choose how to group the data"
  }
  interactive: true
  collapsible: true
  collapsible_title: "📈 Price Trends (Click to expand/collapse)"
  collapsible_expanded: true
}

### Example 2: Bar Chart with Dimension Selector

Compare volumes across different groupings. The dimension selector lets you quickly switch perspectives!

$exhibits${
  type: bar_chart
  source: company.fact_prices
  x: ticker
  y: volume
  title: Volume Comparison
  description: Switch dimensions to see volume from different perspectives (auto-join for exchange_name)
  dimension_selector: {
    available_dimensions: [ticker, exchange_name],
    default_dimension: ticker,
    label: "Color By",
    selector_type: selectbox,
    applies_to: color,
    help_text: "Choose coloring dimension"
  }
  interactive: true
  collapsible: true
  collapsible_title: "📊 Volume Analysis"
  collapsible_expanded: false
}

## Collapsible Exhibits

Keep your notebook organized by hiding detailed exhibits until needed.

### Example 3: Collapsible Metric Cards

$exhibits${
  type: metric_cards
  source: company.fact_prices
  metrics: [
    { measure: close, label: "Avg Close", aggregation: avg },
    { measure: volume, label: "Total Volume", aggregation: sum },
    { measure: high, label: "Max High", aggregation: max }
  ]
  collapsible: true
  collapsible_title: "💳 Key Metrics"
  collapsible_expanded: false
}

### Example 4: Combined Features - Measure + Dimension Selectors + Collapsible

This exhibit combines all features:
- Measure selector for choosing which metrics to display
- Dimension selector for choosing how to group data
- Collapsible section to keep things tidy

$exhibits${
  type: line_chart
  source: company.fact_prices
  x: trade_date
  y: close
  title: Advanced Multi-Selector Chart
  description: Use both measure and dimension selectors together (auto-join for exchange_name)
  measure_selector: {
    available_measures: [open, close, high, low],
    default_measures: [close],
    label: "Select Price Measures",
    selector_type: checkbox,
    help_text: "Choose which price metrics to display"
  }
  dimension_selector: {
    available_dimensions: [ticker, exchange_name],
    default_dimension: ticker,
    label: "Group Lines By",
    selector_type: radio,
    applies_to: color,
    help_text: "Choose grouping dimension"
  }
  interactive: true
  collapsible: true
  collapsible_title: "🎯 Advanced Analysis (All Features Combined)"
  collapsible_expanded: true
}

## How to Use

### Dimension Selector

Add a `dimension_selector` to any chart exhibit:

```markdown
dimension_selector: {
  available_dimensions: [ticker, exchange_name, company_name],
  default_dimension: ticker,
  label: "Group By",
  selector_type: radio,
  applies_to: color,
  help_text: "Choose dimension for grouping"
}
```

**Properties:**
- `available_dimensions`: List of dimension columns users can choose from
- `default_dimension`: Which dimension to use initially
- `label`: Label shown above the selector
- `selector_type`: `radio` (horizontal buttons) or `selectbox` (dropdown)
- `applies_to`: Currently supports `color` (for coloring lines/bars)
- `help_text`: Help text shown to users

### Collapsible Exhibits

Make any exhibit collapsible:

```markdown
collapsible: true
collapsible_title: "📊 My Chart Title"
collapsible_expanded: false
```

**Properties:**
- `collapsible`: Set to `true` to make exhibit collapsible
- `collapsible_title`: Title for the collapsible section (defaults to exhibit title)
- `collapsible_expanded`: Whether section starts expanded (`true`) or collapsed (`false`)

## Benefits

**Dimension Selector:**
- Quickly explore data from different perspectives
- No need to create multiple exhibits for different groupings
- Users control how they want to view the data
- Common use cases: switching between ticker, exchange_name, company_name, or other dimension columns
- Note: Available dimensions must exist in your source table (use prices_with_company for exchange data)

**Collapsible Exhibits:**
- Keep notebooks clean and organized
- Hide detailed analysis until needed
- Better user experience for long notebooks
- Focus on key insights, details available on demand

## Example Use Cases

1. **Financial Analysis**: Switch between viewing by ticker, exchange_name, or company_name (requires prices_with_company table)
2. **Regional Sales**: Toggle between country, region, or city views
3. **Product Analytics**: Switch between product, category, or brand groupings
4. **Customer Segmentation**: View by age group, region, or purchase frequency

## Important Notes

**Data Source Requirements:**
- The `fact_prices` table only contains: ticker, trade_date, and pricing metrics
- For exchange information, use `prices_with_company` (materialized view with company and exchange data)
- Available dimensions in `prices_with_company`: ticker, company_name, exchange_name
- Always ensure dimension columns exist in your source table before adding to `available_dimensions`
