# UI System

**Streamlit-based interactive analytics interface**

---

## Overview

de_Funk provides a Streamlit-based UI for interactive analytics, featuring markdown notebooks with dynamic filters and visualizations.

---

## Documents

| Document | Description |
|----------|-------------|
| [Notebook System](notebook-system.md) | Notebook architecture overview |
| [Notebook Parser](notebook-parser.md) | Markdown parsing and rendering |
| [Filter Engine UI](filter-engine-ui.md) | Dynamic filter components |
| [Exhibits](exhibits.md) | Visualization components |
| [Streamlit App](streamlit-app.md) | Main application structure |

---

## Architecture

```
┌────────────────────────────────────────────────────┐
│                 Streamlit App                       │
├────────────────────────────────────────────────────┤
│                                                    │
│  ┌──────────────┐  ┌──────────────┐               │
│  │   Sidebar    │  │   Main       │               │
│  │   - Filters  │  │   - Notebook │               │
│  │   - Nav      │  │   - Exhibits │               │
│  └──────────────┘  └──────────────┘               │
│                                                    │
├────────────────────────────────────────────────────┤
│              Notebook Manager                       │
│  (Loads/parses markdown notebooks)                 │
├────────────────────────────────────────────────────┤
│              Filter Engine                          │
│  (Applies filters to queries)                      │
├────────────────────────────────────────────────────┤
│              Universal Session                      │
│  (Executes queries against Silver layer)           │
└────────────────────────────────────────────────────┘
```

---

## Notebook System

### Markdown Format

Notebooks are markdown files with embedded filter and exhibit definitions:

```markdown
---
title: Stock Analysis
model: stocks
---

# Stock Analysis

$filter${
  "type": "dropdown",
  "label": "Ticker",
  "column": "ticker"
}

## Price History

$exhibits${
  "type": "line_chart",
  "data": "fact_stock_prices",
  "x": "trade_date",
  "y": "close"
}
```

### Filter Types

| Type | Description |
|------|-------------|
| `dropdown` | Single/multi-select dropdown |
| `date_range` | Date picker with range |
| `text` | Free text input |
| `slider` | Numeric range slider |

### Exhibit Types

| Type | Description |
|------|-------------|
| `line_chart` | Time series visualization |
| `bar_chart` | Categorical comparisons |
| `table` | Data table display |
| `metric` | Single value display |

---

## Running the UI

```bash
# Using run script (recommended)
python run_app.py

# Or directly
streamlit run app/ui/notebook_app_duckdb.py

# Using shell script
./run_app.sh
```

---

## Notebook Location

Notebooks are stored in: `configs/notebooks/`

```
configs/notebooks/
├── overview/
│   └── dashboard.md
├── stocks/
│   └── analysis.md
└── macro/
    └── indicators.md
```

---

## Filter Context

Folder-level filter defaults via `.filter_context.yaml`:

```yaml
# configs/notebooks/stocks/.filter_context.yaml
model: stocks
default_filters:
  ticker: AAPL
  date_range:
    start: 2024-01-01
```

---

## Related Documentation

- [Examples Catalog](../09-examples-catalog/) - Notebook examples
- [Core Framework](../01-core-framework/) - Filter engine details
- [Scripts Reference](../08-scripts-reference/) - UI scripts
