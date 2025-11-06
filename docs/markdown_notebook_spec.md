# Markdown Notebook Specification

## Overview

The markdown notebook format provides a user-friendly, document-centric approach to data analysis. It combines YAML front matter for configuration with markdown for narrative, inline filters, and embedded visualizations.

**Note**: This is the only supported format. YAML notebooks are no longer supported.

## Format Structure

### 1. YAML Front Matter (Properties Section)

```markdown
---
id: unique_notebook_id
title: Notebook Title
description: Brief description of the notebook
tags: [tag1, tag2, tag3]
models: [model1, model2]
dimensions: [dim1, dim2, dim3]
measures: [measure1, measure2, measure3]
author: email@company.com
created: YYYY-MM-DD
updated: YYYY-MM-DD
---
```

**Fields:**
- `id` (required): Unique identifier for the notebook
- `title` (required): Display title
- `description` (optional): Brief description
- `tags` (optional): List of tags for categorization
- `models` (optional): List of models this notebook uses (initializes model sessions)
- `dimensions` (optional): List of dimensions/fields available
- `measures` (optional): List of measures/metrics available
- `author` (optional): Author email
- `created` (optional): Creation date
- `updated` (optional): Last update date

### 2. Filters Section

Filters are defined inline using the `$filter${...}` syntax with database-driven options:

```markdown
$filter${
  id: ticker
  label: Stock Tickers
  type: select
  multi: true
  source: {model: company, table: fact_prices, column: ticker}
  help_text: Select stocks to analyze (loaded from database)
}

$filter${
  id: trade_date
  type: date_range
  label: Date Range
  operator: between
  default: {start: "2024-01-01", end: "2024-01-05"}
  help_text: Filter by trade date range
}

$filter${
  id: volume
  label: Minimum Volume
  type: slider
  min_value: 0
  max_value: 100000000
  step: 1000000
  default: 0
  operator: gte
  help_text: Filter by minimum trading volume
}
```

**Filter Types:**
- `select`: Multi/single select (options from database via `source`)
- `date_range`: Date range picker
- `slider`: Numeric slider with min/max/step
- `number_range`: Min/max numeric inputs
- `text_search`: Text search with contains/fuzzy operators
- `boolean`: Toggle (true/false)

**Key Features:**
- Filters only appear in sidebar (not in notebook view)
- Options pulled dynamically from database via `source` parameter
- Automatic SQL WHERE clause generation
- Support for multiple operators (in, between, gte, contains, etc.)

### 3. Markdown Content

Standard markdown with support for:
- Headers (# ## ### etc.)
- **Bold**, *italic*, ~~strikethrough~~
- Lists (ordered and unordered)
- Links and images
- Code blocks
- Tables
- Blockquotes
- Horizontal rules
- HTML tags (for advanced formatting)

### 4. Collapsible Sections

Use HTML `<details>` tags for collapsible content:

```markdown
<details>
<summary>Click to expand</summary>

Content here can include text, charts, and exhibits.

</details>
```

**Implementation Note**: These tags are parsed and rendered as Streamlit expanders (`st.expander()`) to ensure proper component nesting. Exhibits and other Streamlit elements inside collapsible sections will correctly show/hide when toggling the expander.

### 5. Embedded Exhibits

Exhibits are embedded inline using the `$exhibits${...}` syntax:

```markdown
$exhibits${
  type: line_chart
  source: company.fact_prices
  x: trade_date
  y: close
  color: ticker
  title: "Daily Closing Prices"
}
```

#### Streamlined Exhibit Parameters

**Common Parameters:**
- `type`: Exhibit type (metric_cards, line_chart, bar_chart, scatter_chart, data_table, etc.)
- `source`: Data source in "model.table" format
- `title`: Exhibit title (optional, inferred from context if not provided)
- `description`: Exhibit description

**Axis Parameters (Streamlined):**
- `x`: X-axis dimension/measure (replaces x_axis.dimension)
- `y`: Y-axis measure (replaces y_axis.measure)
- `y2`: Secondary Y-axis measure (for dual-axis charts)
- `color`: Color-by dimension (replaces color_by)
- `size`: Size-by measure (replaces size_by)

**Chart-Specific Parameters:**
- `legend`: Show legend (true/false, default: true)
- `interactive`: Enable interactivity (true/false, default: true)
- `sort`: Sort configuration { by: field, order: asc|desc }
- `scale`: Axis scale (linear, log)

**Metric Cards:**
```markdown
$exhibits${
  type: metric_cards
  source: company.fact_prices
  metrics: [
    { measure: close, label: "Avg Close", aggregation: avg },
    { measure: volume, label: "Total Volume", aggregation: sum }
  ]
}
```

**Line Chart:**
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

**Bar Chart:**
```markdown
$exhibits${
  type: bar_chart
  source: company.fact_prices
  x: ticker
  y: volume
  color: ticker
  sort: { by: volume, order: desc }
}
```

**Scatter Chart:**
```markdown
$exhibits${
  type: scatter_chart
  source: company.fact_prices
  x: volume
  y: close
  color: ticker
  size: market_cap
}
```

**Data Table:**
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

**Weighted Aggregate Chart:**
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

## Example Notebook

```markdown
---
id: stock_analysis
title: Stock Performance Analysis
description: Analyzing stock prices with volume metrics
tags: [stocks, prices, analysis]
models: [company]
dimensions: [trade_date, ticker]
measures: [close, volume, high, low]
author: analyst@company.com
---

# Filters

- **Date Range**: trade_date (2024-01-01 to 2024-01-05) [date_range]
- **Stock Tickers**: ticker (AAPL, GOOGL, MSFT) [multi_select]
- **Min Volume**: volume (0) [number]

# Stock Performance Analysis

This analysis examines stock price trends and trading volumes for selected technology equities over a specified date range.

## Summary Metrics

Key performance indicators for the selected period:

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

## Price Trends

The following chart shows daily closing prices for each stock:

$exhibits${
  type: line_chart
  source: company.fact_prices
  x: trade_date
  y: close
  color: ticker
  title: "Daily Closing Prices"
}

## Volume Analysis

<details>
<summary>Trading Volume Comparison</summary>

Total trading volume by stock for the selected period:

$exhibits${
  type: bar_chart
  source: company.fact_prices
  x: ticker
  y: volume
  color: ticker
  sort: { by: volume, order: desc }
  title: "Trading Volume by Stock"
}

</details>

## Detailed Data

<details>
<summary>View Raw Data</summary>

Complete dataset with all fields:

$exhibits${
  type: data_table
  source: company.fact_prices
  download: true
  sortable: true
  pagination: true
}

</details>
```

## Benefits

1. **User-Friendly**: Natural markdown syntax familiar to analysts
2. **Document-Centric**: Narrative-first approach with embedded visualizations
3. **Streamlined Syntax**: Simpler x/y parameters instead of verbose axis configs
4. **Collapsible Sections**: Organize content hierarchically
5. **YAML Front Matter**: Clear metadata section
6. **Human-Readable Filters**: Intuitive filter definitions
7. **Model Sessions**: Automatic model initialization from front matter
8. **Backward Compatible**: Can convert existing YAML notebooks to markdown

## Implementation Notes

1. **Parser**: Use Python `markdown` library + custom exhibit parser
2. **Exhibit Extraction**: Regex pattern to find `$exhibits${...}` blocks
3. **YAML Parsing**: Standard `yaml.safe_load()` for front matter
4. **Filter Parsing**: Custom regex for filter section
5. **Rendering**: Convert markdown to HTML, replace exhibit placeholders with rendered components
6. **Session Management**: Initialize models listed in front matter on notebook load
