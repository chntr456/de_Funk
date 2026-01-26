# Notebook System

**Markdown-based analytics notebooks**

Files: `app/notebook/`, `configs/notebooks/`
Related: [NotebookParser](notebook-parser.md) for parsing details

---

## Overview

de_Funk's notebook system enables **low-code analytics** through markdown-based notebooks with embedded filters and visualizations.

**Format**: Markdown with YAML front matter + `$filter${}` and `$exhibits${}` blocks

---

## Notebook Structure

```markdown
---
id: my-notebook
title: My Analysis
models: [equity, corporate]
---

# Analysis Title

Description text...

$filter${
type: date_range
label: Date Range
column: trade_date
}

$exhibits${
type: line_chart
x: trade_date
y: close
color: ticker
}
```

---

## Quick Reference

### Front Matter (Required)

```yaml
---
id: unique-id
title: Display Title
description: Optional description
models: [model1, model2]
author: Your Name
tags: [tag1, tag2]
---
```

### Filter Syntax

```markdown
$filter${
type: date_range | multi_select | single_select | number_range
label: User-facing label
column: Column to filter
default: Default value(s)
source:  # For select filters
  type: dimension
  model: model_name
  dimension: dim_table
  column: column_name
}
```

### Exhibit Syntax

```markdown
$exhibits${
type: line_chart | bar_chart | table | metric_cards
title: Chart Title
source: model.table  # Optional, can query multiple models
x: x_column
y: y_column | [y1, y2]  # Single or multiple
color: color_by_column
}
```

---

## Exhibit Types

| Type | Purpose | Key Fields |
|------|---------|------------|
| `line_chart` | Time series | `x`, `y`, `color` |
| `bar_chart` | Categories | `x`, `y`, `color` |
| `scatter_plot` | Correlations | `x`, `y`, `color`, `size` |
| `table` | Data table | `columns`, `sortable`, `pagination` |
| `metric_cards` | KPIs | `metrics` list |

---

## Filter Types

| Type | Purpose | Fields |
|------|---------|--------|
| `date_range` | Date selection | `column`, `default.start/end` |
| `multi_select` | Multiple values | `column`, `source`, `options` |
| `single_select` | Single value | `column`, `source` |
| `number_range` | Numeric range | `column`, `min`, `max` |

---

## Collapsible Sections

```markdown
<details>
<summary>Section Title</summary>

Content here (can include exhibits)...

$exhibits${
type: table
columns: [a, b, c]
}

</details>
```

---

## Example Notebooks

See `/configs/notebooks/` for examples:
- `equity/price-analysis.md` - Stock price analysis
- `macro/economic-indicators.md` - Economic data
- `cross-model/sector-performance.md` - Multi-model analysis

---

## Related Documentation

- [NotebookParser](notebook-parser.md) - Parsing markdown notebooks
- [Filter Engine](filter-engine-ui.md) - Filter system details
- [Exhibits](exhibits.md) - Visualization types
- [Streamlit App](streamlit-app.md) - UI rendering
