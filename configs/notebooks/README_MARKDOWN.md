# Markdown Notebooks - User Guide

## Overview

Markdown notebooks provide a modern, document-centric approach to data analysis. They combine:
- **YAML front matter** for configuration and metadata
- **Markdown** for narrative and documentation
- **Embedded exhibits** for visualizations and data tables
- **Collapsible sections** for organizing content
- **Streamlined syntax** for faster authoring

## Why Markdown Notebooks?

### Benefits over Traditional YAML Notebooks

1. **More Readable**: Natural markdown flow with embedded visualizations
2. **Better Documentation**: Write detailed analysis narratives alongside charts
3. **Easier to Author**: Simpler syntax, familiar markdown format
4. **Version Control Friendly**: Human-readable diffs
5. **Collapsible Sections**: Better organization for complex analyses
6. **Streamlined Parameters**: Use `x` and `y` instead of verbose axis configs

## Quick Start

### 1. Create a New Markdown Notebook

Create a file with `.md` extension in `configs/notebooks/`:

```markdown
---
id: my_analysis
title: My Analysis
tags: [tag1, tag2]
models: [company]
---

# Filters

- **Date Range**: trade_date (2024-01-01 to 2024-12-31) [date_range]

# My Analysis

Your analysis narrative here...

$exhibits${
  type: line_chart
  source: company.fact_prices
  x: trade_date
  y: close
}
```

### 2. Open in the App

The app automatically detects `.md` files and renders them appropriately.

## File Structure

### YAML Front Matter (Required)

```markdown
---
id: unique_id
title: Display Title
description: Brief description
tags: [tag1, tag2]
models: [company, macro]
dimensions: [date, ticker]
measures: [close, volume]
author: analyst@company.com
created: 2024-01-01
updated: 2024-01-15
---
```

**Required Fields:**
- `id`: Unique identifier
- `title`: Display title

**Optional Fields:**
- `description`: Brief description
- `tags`: List of tags for categorization
- `models`: Models to initialize (enables model sessions)
- `dimensions`: Available dimensions/fields
- `measures`: Available measures/metrics
- `author`: Author email
- `created`: Creation date
- `updated`: Last update date

### Filters Section (Optional)

Define interactive filters with this format:

```markdown
# Filters

- **Display Name**: column_name (default) [type]
```

**Examples:**

```markdown
# Filters

- **Date Range**: trade_date (2024-01-01 to 2024-01-05) [date_range]
- **Stock Tickers**: ticker (AAPL, GOOGL, MSFT) [multi_select]
- **Min Volume**: volume (0) [number]
- **Show Active**: is_active (true) [boolean]
```

**Filter Types:**
- `date_range`: Date range picker (format: start to end)
- `multi_select`: Multiple selection (comma-separated)
- `single_select`: Single selection
- `number`: Numeric threshold
- `text`: Text input
- `boolean`: Toggle (true/false)

### Markdown Content

Use standard markdown:

```markdown
# Main Header
## Subheader
### Sub-subheader

**Bold text**
*Italic text*
~~Strikethrough~~

- Bullet list
- Item 2

1. Numbered list
2. Item 2

> Blockquote

`inline code`

[Link text](url)

---

Horizontal rule
```

### Collapsible Sections

Use HTML `<details>` tags (rendered as Streamlit expanders):

```markdown
<details>
<summary>Click to expand</summary>

Content here (can include text, exhibits, etc.)

</details>
```

**Note**: These are automatically converted to Streamlit expanders for proper component nesting. Exhibits inside collapsible sections will correctly show/hide when toggling.

### Embedded Exhibits

Use `$exhibits${...}` syntax with YAML config:

```markdown
$exhibits${
  type: line_chart
  source: company.fact_prices
  x: trade_date
  y: close
  color: ticker
  title: "Daily Prices"
}
```

## Exhibit Types & Parameters

### Metric Cards

Display aggregated KPIs:

```markdown
$exhibits${
  type: metric_cards
  source: company.fact_prices
  metrics: [
    { measure: close, label: "Avg Close", aggregation: avg },
    { measure: volume, label: "Total Volume", aggregation: sum },
    { measure: high, label: "Max High", aggregation: max },
    { measure: low, label: "Min Low", aggregation: min }
  ]
}
```

**Aggregations:** `avg`, `sum`, `min`, `max`, `count`

### Line Chart

Time series or continuous data:

```markdown
$exhibits${
  type: line_chart
  source: company.fact_prices
  x: trade_date
  y: close
  color: ticker
  title: "Price Trends"
}
```

**Parameters:**
- `x`: X-axis dimension
- `y`: Y-axis measure
- `color`: Color-by dimension
- `title`: Chart title

### Bar Chart

Categorical comparisons:

```markdown
$exhibits${
  type: bar_chart
  source: company.fact_prices
  x: ticker
  y: volume
  color: ticker
  sort: { by: volume, order: desc }
  title: "Trading Volume"
}
```

**Parameters:**
- `x`: X-axis dimension (categories)
- `y`: Y-axis measure (values)
- `color`: Color-by dimension
- `sort`: Sort config with `by` and `order` (asc/desc)

### Scatter Chart

Correlation analysis:

```markdown
$exhibits${
  type: scatter_chart
  source: company.fact_prices
  x: volume
  y: close
  color: ticker
  size: market_cap
  title: "Price vs Volume"
}
```

**Parameters:**
- `x`: X-axis measure
- `y`: Y-axis measure
- `color`: Color-by dimension
- `size`: Size-by measure (bubble chart)

### Data Table

Raw data display:

```markdown
$exhibits${
  type: data_table
  source: company.fact_prices
  columns: [trade_date, ticker, close, volume]
  download: true
  sortable: true
  pagination: true
  page_size: 50
}
```

**Parameters:**
- `columns`: List of columns to display (optional, shows all if not specified)
- `download`: Enable CSV download
- `sortable`: Enable column sorting
- `pagination`: Enable pagination
- `page_size`: Rows per page

### Weighted Aggregate Chart

Multi-weighting comparison:

```markdown
$exhibits${
  type: weighted_aggregate_chart
  source: company.weighted_aggregates
  aggregate_by: trade_date
  value_measures: [
    equal_weighted_index,
    volume_weighted_index,
    market_cap_weighted_index
  ]
  title: "Index Comparison"
}
```

### Forecast Chart

Time series forecasts with confidence intervals:

```markdown
$exhibits${
  type: forecast_chart
  source: company.forecasts
  x: forecast_date
  y: forecast_value
  color: model_type
  title: "Price Forecasts"
}
```

## Best Practices

### 1. Structure Your Analysis

```markdown
# Executive Summary
Brief overview and key findings

## Data Overview
Describe your data sources and filters

## Analysis
### Trend Analysis
...

### Statistical Analysis
...

## Conclusions
Summarize findings
```

### 2. Use Collapsible Sections for Details

Keep main narrative focused, put detailed charts in collapsible sections:

```markdown
## Key Findings

Main insights here...

<details>
<summary>Detailed Analysis</summary>

Detailed charts and tables here...

</details>
```

### 3. Combine Text and Visualizations

```markdown
The price trend shows a clear upward trajectory:

$exhibits${
  type: line_chart
  source: company.fact_prices
  x: trade_date
  y: close
}

As we can see from the chart above...
```

### 4. Use Descriptive Titles

```markdown
$exhibits${
  type: bar_chart
  source: company.fact_prices
  x: ticker
  y: volume
  title: "Trading Volume by Stock (Last 30 Days)"
}
```

### 5. Document Your Assumptions

```markdown
## Methodology

**Assumptions:**
- Data is filtered to US equities only
- Volume is in millions of shares
- Prices are adjusted for splits and dividends

**Calculations:**
- Market cap = price × outstanding shares
- Volatility = 30-day rolling standard deviation
```

## Migration from YAML Notebooks

### Before (YAML):

```yaml
version: "1.0"
notebook:
  id: analysis
  title: "Stock Analysis"

variables:
  trade_date:
    type: date_range
    default: {start: "2024-01-01", end: "2024-01-05"}
    display_name: "Date Range"

exhibits:
  - id: price_chart
    type: line_chart
    source: "company.fact_prices"
    x_axis:
      dimension: trade_date
    y_axis:
      measure: close
    color_by: ticker

layout:
  - title: "Price Trends"
    exhibits: [price_chart]
```

### After (Markdown):

```markdown
---
id: analysis
title: Stock Analysis
models: [company]
---

# Filters

- **Date Range**: trade_date (2024-01-01 to 2024-01-05) [date_range]

# Stock Analysis

## Price Trends

$exhibits${
  type: line_chart
  source: company.fact_prices
  x: trade_date
  y: close
  color: ticker
}
```

**Benefits:**
- 50% less code
- More readable
- Natural narrative flow
- Easier to maintain

## Tips & Tricks

### Use Emojis for Visual Interest

```markdown
## 📊 Price Analysis
## 💰 Revenue Metrics
## 🎯 Key Insights
```

### Create Tables for Comparisons

```markdown
| Metric | Q1 | Q2 | Q3 |
|--------|-----|-----|-----|
| Revenue | 100M | 120M | 150M |
| Profit | 10M | 15M | 20M |
```

### Add Code Examples

```markdown
### Custom Calculation

The weighted index is calculated as:

```python
index = sum(price[i] * weight[i]) / sum(weight[i])
```
```

### Link to External Resources

```markdown
For more information, see:
- [Company Website](https://company.com)
- [API Documentation](https://docs.company.com/api)
```

## Troubleshooting

### Exhibit Not Rendering

**Problem**: Exhibit shows error or doesn't appear

**Solutions**:
1. Check YAML syntax in exhibit block (indentation, colons, brackets)
2. Verify source format: `model.table` (e.g., `company.fact_prices`)
3. Ensure model is listed in front matter `models:` section
4. Check that columns referenced exist in the source table

### Filters Not Working

**Problem**: Filters don't affect data

**Solutions**:
1. Verify filter format: `- **Name**: column (default) [type]`
2. Ensure column names match table columns exactly
3. Check filter type is correct for data type
4. Make sure filters are applied in the app sidebar

### Markdown Not Rendering

**Problem**: Markdown shows as plain text

**Solutions**:
1. Ensure file extension is `.md`
2. Check YAML front matter is properly closed with `---`
3. Verify no syntax errors in markdown

## Examples

See these example notebooks:
- `stock_analysis.md` - Basic stock analysis with metrics, charts, and tables
- `Financial Analysis/stock_analysis.yaml` - Traditional YAML format for comparison

## Support

For issues or questions:
- Check the docs: `/docs/markdown_notebook_spec.md`
- Review examples in `/configs/notebooks/`
- Report bugs: Contact your platform administrator
