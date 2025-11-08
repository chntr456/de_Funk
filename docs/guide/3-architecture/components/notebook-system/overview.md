# Notebook System - Overview

## Introduction

The **Notebook System** provides a markdown-based framework for defining interactive analytics notebooks. Users write notebooks in markdown with embedded exhibit definitions, and the system handles parsing, execution, and rendering.

## Architecture

```
┌────────────────────────────────────────────────────────┐
│               Notebook System Stack                    │
└────────────────────────────────────────────────────────┘

User writes:
┌─────────────────────────┐
│  stock_analysis.md      │  Markdown file with $exhibit${...} tags
│  - Text sections        │
│  - Filter definitions   │
│  - Exhibit specs        │
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│  MarkdownParser         │  Parses markdown, extracts exhibits
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│  NotebookManager        │  Orchestrates lifecycle
│  - Load notebook        │
│  - Manage filters       │
│  - Execute exhibits     │
└──────────┬──────────────┘
           │
     ┌─────┴─────┐
     │           │
     ▼           ▼
┌──────────┐  ┌──────────────┐
│  Filter  │  │   Exhibits   │
│  Engine  │  │  - Charts    │
│          │  │  - Tables    │
│          │  │  - Metrics   │
└──────────┘  └──────────────┘
```

## Key Components

### 1. NotebookManager (`app/notebook/managers/notebook_manager.py`)
- Notebook lifecycle management
- Filter context coordination
- Exhibit execution orchestration

### 2. MarkdownParser (`app/notebook/parsers/markdown_parser.py`)
- Parse markdown with `$exhibit${...}` syntax
- Extract filter definitions
- Build notebook configuration

### 3. FilterSystem (`app/notebook/filters/`)
- Dynamic filter UI generation
- Filter context management
- Hierarchical filter merging

### 4. Exhibits (`app/notebook/exhibits/`)
- Chart exhibits (line, bar, etc.)
- Table exhibits
- Metric exhibits
- Custom exhibit types

### 5. FolderContext (`app/notebook/folder_context.py`)
- Folder-based filter sharing
- Context isolation across folders
- Persistent filter state

## Markdown Notebook Format

```markdown
# Stock Analysis

Select tickers and date range to analyze:

$filter${
  "type": "dimension_selector",
  "dimension": "ticker",
  "model": "company"
}

$filter${
  "type": "date_range",
  "dimension": "date"
}

## Price Trends

$exhibit${
  "type": "line_chart",
  "title": "Stock Prices Over Time",
  "query": {
    "model": "company",
    "table": "fact_prices",
    "measures": ["close", "volume"]
  },
  "x_axis": "date",
  "y_axis": "close"
}

## Summary Metrics

$exhibit${
  "type": "metric_cards",
  "metrics": [
    {
      "name": "Avg Close",
      "query": {"model": "company", "aggregation": "avg(close)"}
    }
  ]
}
```

## Notebook Lifecycle

```
1. LOAD
   ┌─────────────────────┐
   │ Load .md file       │
   │ Parse markdown      │
   │ Extract exhibits    │
   └──────┬──────────────┘

2. FILTER SETUP
          │
          ▼
   ┌─────────────────────┐
   │ Initialize filters  │
   │ Load folder context │
   │ Merge global/local  │
   └──────┬──────────────┘

3. EXECUTE
          │
          ▼
   ┌─────────────────────┐
   │ For each exhibit:   │
   │  - Build query      │
   │  - Apply filters    │
   │  - Fetch data       │
   │  - Render visual    │
   └─────────────────────┘
```

## Usage Example

```python
from app.notebook.managers.notebook_manager import NotebookManager
from models.api.session import UniversalSession

# Initialize session
session = UniversalSession(conn, storage_cfg, repo_root, models=['company'])

# Create notebook manager
manager = NotebookManager(
    universal_session=session,
    repo_root=repo_root
)

# Load notebook
notebook = manager.load_notebook("configs/notebooks/stock_analysis.md")

# Set filters
manager.update_filter('ticker', ['AAPL', 'GOOGL'])
manager.update_filter('date', {'start': '2024-01-01', 'end': '2024-12-31'})

# Execute exhibits
for exhibit in notebook.exhibits:
    data = manager.execute_exhibit(exhibit)
    print(f"Exhibit {exhibit.title}: {len(data)} rows")
```

**File**: `/home/user/de_Funk/docs/guide/3-architecture/components/notebook-system/overview.md`
