---
title: Exhibit Types Reference
description: Documentation for all de_Funk exhibit types
version: 1.0.0

categories:
  - name: charts
    description: Interactive visualizations using Plotly.js
    types: [line_chart, bar_chart, scatter_chart, area_chart, heatmap, pie_chart]

  - name: tables
    description: Tabular data displays
    types: [data_table, pivot_table, great_table]

  - name: metrics
    description: KPI and metric displays
    types: [metric_cards]

common_properties:
  id:
    type: string
    required: true
    description: Unique identifier for this exhibit

  domain:
    type: string
    required: true
    description: Primary domain model (e.g., stocks, company)

  title:
    type: string
    required: false
    description: Display title above the exhibit

  description:
    type: string
    required: false
    description: Subtitle or description text

  page_filters:
    type: object
    required: false
    default: { inherit: true }
    description: Controls inheritance from page-level filters
    properties:
      inherit:
        type: boolean
        default: true
        description: Whether to inherit filters from frontmatter
      ignore:
        type: array
        items: string
        description: List of filter IDs to ignore

  filters:
    type: array
    required: false
    description: Exhibit-specific filters (render inside exhibit)
    items:
      type: object
      properties:
        id: { type: string, required: true }
        type: { type: string, required: true, enum: [select, date_range, date, number_range, slider, boolean] }
        label: { type: string }
        source: { type: string, required: true }
        default: { type: any }

  metrics:
    type: array
    required: false
    description: KPI cards to display in exhibit header
    items:
      type: object
      properties:
        id: { type: string }
        column: { type: string, required: true }
        label: { type: string }
        aggregation: { type: string, enum: [sum, avg, min, max, count] }
        format: { type: string }

  display:
    type: object
    required: false
    description: Display options
    properties:
      height: { type: number, default: 400 }
      show_legend: { type: boolean, default: true }
      show_filters: { type: boolean, default: true }
      show_metrics: { type: boolean, default: true }
      interactive: { type: boolean, default: true }
---

# Exhibit Types Reference

This folder contains documentation for all de_Funk exhibit types. Each exhibit type has its own markdown file with:

1. **YAML frontmatter** - Schema definition (required/optional fields, types, defaults)
2. **Markdown body** - Documentation, examples, and usage guidelines

## How to Use

In your Obsidian notes, use code blocks with the exhibit type:

```yaml
```exhibit
type: line_chart          # The exhibit type
domain: stocks            # Primary domain model
# ... type-specific options
```
```

## Categories

### Charts (`exhibits/charts/`)

Interactive visualizations powered by Plotly.js:

| Type | Description | Best For |
|------|-------------|----------|
| `line_chart` | Time series lines | Trends over time |
| `bar_chart` | Categorical bars | Comparisons |
| `scatter_chart` | X-Y scatter plot | Correlations |
| `area_chart` | Filled area | Cumulative trends |
| `heatmap` | 2D color matrix | Density/patterns |
| `pie_chart` | Proportional slices | Part-of-whole |

### Tables (`exhibits/tables/`)

Tabular data displays:

| Type | Description | Best For |
|------|-------------|----------|
| `data_table` | Interactive table | Raw data exploration |
| `pivot_table` | Grouped pivot | Aggregated summaries |
| `great_table` | Publication quality | Reports |

### Metrics (`exhibits/metrics/`)

KPI and summary displays:

| Type | Description | Best For |
|------|-------------|----------|
| `metric_cards` | KPI cards | Key numbers |

## Common Properties

All exhibits share these common properties. See `_index.md` frontmatter for full schema.

### Required

- `type` - The exhibit type (e.g., `line_chart`)
- `domain` - Primary domain model

### Filter Inheritance

```yaml
page_filters:
  inherit: true           # Use page filters (default)
  ignore: [ticker]        # Skip specific filters

filters:                  # Add exhibit-specific filters
  - id: price_min
    type: slider
    source: stocks.fact_stock_prices.close
```

### Metrics Header

```yaml
metrics:
  - column: stocks.measures.close_price
    label: Avg Price
    aggregation: avg
    format: "$,.2f"
```
