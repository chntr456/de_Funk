# Proposal: React Whiteboard UI Overhaul

**Status**: 📋 Draft (Revised)
**Author**: Claude
**Date**: 2026-01-24 (Revised from 2026-01-06)
**Priority**: High
**Estimated Effort**: 15-20 weeks

---

## Executive Summary

Replace the current Streamlit UI with a React-based whiteboard/canvas interface using ReactFlow. This enables spatial data exploration where users can arrange exhibits, draw connections between insights, and interact with data in a more flexible, powerful way—while preserving the existing markdown notebook paradigm.

### Key Changes in This Revision

1. **Exhibit-as-Markdown Pattern**: Exhibit types defined as YAML frontmatter markdown files
2. **Unified Config Structure**: `Data Sources/`, `Domains/`, `Exhibits/` folders
3. **Clean Backend Pathway**: Documented reference flow from config → query → render
4. **Dead Code Identification**: Explicit list of code to remove during migration

### Key Benefits
- **Whiteboard exploration**: Drag, arrange, and connect data visualizations spatially
- **Full CRUD**: Create, edit, delete notebooks entirely in-app (currently missing)
- **Better UX**: Modern React components, keyboard shortcuts, undo/redo
- **Same markdown source**: Existing notebooks work with minimal changes
- **Dynamic dimensions**: First-class support for dimension switching and cross-filtering
- **Geographic maps**: Full map support via Mapbox GL / DeckGL
- **Declarative Exhibits**: Exhibit types as discoverable, documented markdown configs

---

## Table of Contents

1. [Motivation](#motivation)
2. [Current State & Gaps](#current-state--gaps)
3. [Architecture Overview](#architecture-overview)
4. [Three View Modes](#three-view-modes) ← **NEW**
5. [Unified Config Architecture](#unified-config-architecture) ← **NEW**
6. [Backend Reference Pathway](#backend-reference-pathway) ← **NEW**
7. [Dead Code Identification](#dead-code-identification) ← **NEW**
8. [Technical Stack](#technical-stack)
9. [ReactFlow Container Patterns](#reactflow-container-patterns)
10. [Component Migration Guide](#component-migration-guide)
11. [API Specification](#api-specification)
12. [Phased Implementation Plan](#phased-implementation-plan)
13. [Development Environment](#development-environment)
14. [Risk Mitigation](#risk-mitigation)
15. [Success Metrics](#success-metrics)
16. [References](#references)

---

## Motivation

### Why Move Away from Streamlit?

| Limitation | Impact |
|------------|--------|
| No in-app content editing | Users must edit markdown files externally |
| Linear layout only | Can't spatially arrange related insights |
| No connection drawing | Can't visually link cause → effect |
| Limited state management | Reruns entire script on interaction |
| Basic component library | Custom widgets are difficult |
| No undo/redo | Destructive actions are permanent |
| Limited keyboard shortcuts | Power users slowed down |
| **Scattered exhibit logic** | Exhibit types hardcoded in Python, not discoverable |
| **ColumnReference bugs** | Objects leak through instead of field names |

### Why Whiteboard/Canvas?

The whiteboard paradigm enables **exploratory data analysis** where:
- Related exhibits are grouped spatially
- Connections show data flow and insights
- Users build narratives by arrangement
- Layouts persist and can be shared

**Inspiration**: Count.co, Miro + BI, Observable notebooks

---

## Current State & Gaps

### What Exists Today ✅
```
✅ Markdown notebook parser ($filter$, $exhibit$, $grid$ syntax)
✅ DuckDB/Spark backend with UniversalSession
✅ Model/measure framework
✅ Filter context system
✅ Plotly visualizations
✅ Great Tables integration
✅ Basic Streamlit rendering
✅ Domain models as markdown (domains/)
```

### Current Problems ❌

| Category | Problem | Impact |
|----------|---------|--------|
| **ColumnReference Bugs** | Objects used instead of field strings | Charts fail with cryptic errors |
| **Duplicate Code** | `extract_field_name()` in 3+ files | Inconsistent behavior |
| **Hardcoded Exhibits** | Types in Python if/elif chains | Hard to add new types |
| **No Exhibit Discovery** | Users can't browse available types | Poor documentation |
| **Mixed Concerns** | Rendering + data fetch + state in one file | Hard to maintain |

### Missing User Functionality ❌

| Category | Missing Feature | Priority |
|----------|-----------------|----------|
| **Content Management** | Create new notebook | 🔴 Critical |
| | Edit notebook content in-app | 🔴 Critical |
| | Delete notebook | 🔴 Critical |
| | Rename notebook | 🔴 Critical |
| | Duplicate notebook | 🟡 High |
| | Move between folders | 🟡 High |
| **Properties/Config** | Edit YAML frontmatter | 🔴 Critical |
| | Edit filter configs | 🔴 Critical |
| | Edit exhibit configs | 🔴 Critical |
| | Visual config builder | 🟡 High |
| **Organization** | Create folders | 🟡 High |
| | Folder tree navigation | 🟡 High |
| | Search notebooks | 🟡 High |
| | Tags/labels | 🟢 Medium |
| | Favorites | 🟢 Medium |
| | Recent notebooks | 🟢 Medium |
| **Canvas Features** | Drag/drop layout | 🔴 Critical |
| | Draw connections | 🔴 Critical |
| | Add nodes dynamically | 🔴 Critical |
| | Resize widgets | 🟡 High |
| | Grouping/frames | 🟡 High |
| | Freeform annotations | 🟢 Medium |
| **Data Interaction** | Drill-down on click | 🟡 High |
| | Cross-filtering | 🟡 High |
| | Export chart/data | 🟡 High |
| | Refresh data | 🟡 High |
| **Editing** | Undo/redo | 🔴 Critical |
| | Autosave | 🔴 Critical |
| | Version history | 🟢 Medium |
| **Collaboration** | Share link | 🟢 Medium |
| | Comments | 🟢 Medium |
| **Export** | PDF export | 🟡 High |
| | PNG/SVG export | 🟡 High |
| **System** | Templates | 🟡 High |
| | Keyboard shortcuts | 🟡 High |

---

## Architecture Overview

### Current Architecture (Streamlit) - PROBLEMATIC
```
┌─────────────────────────────────────────┐
│         Streamlit (Python)              │
│  - UI rendering                         │
│  - State management                     │
│  - Direct DuckDB calls                  │
│  - Exhibit types hardcoded              │  ← Problem
│  - ColumnReference leaks                │  ← Problem
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│         DuckDB + Parquet                │
└─────────────────────────────────────────┘
```

### New Architecture (React + FastAPI + DuckDB)
```
┌─────────────────────────────────────────────────────────────────┐
│                     React Frontend                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ ReactFlow   │  │ Plotly.js   │  │ Tabulator   │             │
│  │ (Canvas)    │  │ (Charts)    │  │ (Tables)    │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
│                                                                  │
│  State: Zustand    Styling: Tailwind + shadcn/ui                │
└─────────────────────────────┬───────────────────────────────────┘
                              │ HTTP/WebSocket
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FastAPI Backend                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ /notebooks  │  │ /query      │  │ /exhibits   │  ← NEW      │
│  │ CRUD        │  │ Execute SQL │  │ Type Defs   │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
│                                                                  │
│  Config Loaders: DomainLoader, ExhibitLoader, DataSourceLoader  │
│  Uses: UniversalSession, FilterEngine, Models (unchanged)       │
└─────────────────────────────┬───────────────────────────────────┘
                              │ SQL
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  DuckDB + Delta Lake (unchanged)                 │
│                  storage/bronze, storage/silver                  │
└─────────────────────────────────────────────────────────────────┘
```

### What Changes vs. What Stays

| Layer | Changes | Stays Same |
|-------|---------|------------|
| **Frontend** | Complete rewrite in React | — |
| **API** | New FastAPI layer | — |
| **Config** | Add Exhibits/, Data Sources/ folders | domains/, configs/notebooks/ |
| **Session** | — | UniversalSession, FilterEngine |
| **Models** | — | All model code, measures |
| **Storage** | — | DuckDB, Delta Lake files |
| **Configs** | Minor syntax additions | Markdown notebooks, YAML |

---

## Three View Modes

The React UI supports three distinct viewing modes:

### 1. Document View (Research Reports)

**Purpose**: Linear, scrollable document for professional reports

**Layout**: Standard markdown flow with `$grid${}` for structured sections

**Characteristics**:
- Print-friendly
- Sequential reading experience
- `$filter$`, `$exhibit$`, `$grid$` blocks embedded in markdown
- Resembles current Streamlit behavior
- Best for: quarterly reports, research analysis, documentation

```
┌────────────────────────────────────────┐
│ Header / Filters                        │
├────────────────────────────────────────┤
│ # Stock Analysis                        │
│                                         │
│ [Filter: Ticker] [Filter: Date Range]   │
│                                         │
│ ## Overview                             │
│ Text content...                         │
│                                         │
│ ┌──────────────┬──────────────────────┐ │
│ │ Metric Card  │ Line Chart           │ │  ← $grid${}
│ └──────────────┴──────────────────────┘ │
│                                         │
│ ## Analysis                             │
│ More text...                            │
│                                         │
│ ┌─────────────────────────────────────┐ │
│ │         Great Table                  │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ ▼ (scroll continues)                    │
└────────────────────────────────────────┘
```

### 2. Dashboard View (Fitted Displays)

**Purpose**: All exhibits fit in viewport, responsive grid layout

**Layout**: react-grid-layout with snap-to-grid tiles

**Characteristics**:
- Everything visible without scrolling
- Tiles resize responsively
- Drag to rearrange tiles
- Similar to Grafana, Looker, Tableau dashboards
- Best for: KPI dashboards, monitoring displays, executive summaries

```
┌────────────────────────────────────────┐
│ Filter Bar                              │
├────────┬──────────────────┬────────────┤
│ KPI 1  │    Line Chart    │   KPI 2    │
│        │                  │            │
├────────┼──────────────────┼────────────┤
│        │                  │            │
│  Bar   │   Great Table    │  Scatter   │
│ Chart  │                  │   Chart    │
│        │                  │            │
└────────┴──────────────────┴────────────┘
```

**Technology**: [react-grid-layout](https://github.com/react-grid-layout/react-grid-layout)
- Drag-and-drop tile positioning
- Responsive breakpoints
- Snap-to-grid
- Serializable layouts

### 3. Canvas View (Whiteboard Exploration)

**Purpose**: Free-form infinite canvas for exploratory analysis

**Layout**: ReactFlow with pan/zoom

**Characteristics**:
- Infinite space, zoom/pan navigation
- Draw connections between exhibits (cause → effect)
- Add annotations and sticky notes
- Group related items in frames
- Free positioning (not grid-aligned)
- Best for: exploratory analysis, storytelling, presenting insights

```
┌───────────────────────────────────────────────────────────┐
│ ○ ─────────────────────────────────────────────────────── │
│    ┌─────────┐      ┌──────────────┐                      │
│    │ Filter  │─────▶│ Stock Prices │                      │
│    └─────────┘      └──────┬───────┘                      │
│                            │                              │
│      ┌──────────────┐      │   ┌───────────────┐          │
│      │   Note:      │      └──▶│ Correlation   │          │
│      │  "Peak in    │          │    Chart      │          │
│      │   March"     │          └───────────────┘          │
│      └──────────────┘                                     │
│                                                           │
│                     ┌─────────────┐                       │
│                     │ Group: Q4   │                       │
│                     │ ┌─────────┐ │                       │
│                     │ │ Chart 1 │ │                       │
│                     │ │ Chart 2 │ │                       │
│                     │ └─────────┘ │                       │
│                     └─────────────┘                       │
│ ─────────────────────────────────────────────────── [+] [-]│
└───────────────────────────────────────────────────────────┘
```

### View Mode Comparison

| Feature | Document | Dashboard | Canvas |
|---------|----------|-----------|--------|
| **Layout** | Linear scroll | Fitted grid | Infinite canvas |
| **Technology** | React Markdown | react-grid-layout | ReactFlow |
| **Best for** | Reports | Monitoring | Exploration |
| **Scrolling** | Yes | No (fits viewport) | Pan/zoom |
| **Connections** | No | No | Yes |
| **Annotations** | Inline | No | Yes (sticky notes) |
| **Print-friendly** | Yes | Yes | No |
| **Grouping** | Sections | — | Frames |
| **Responsive** | Yes | Yes | No |

### Unified Notation

All three views use the **same** `$filter${}` and `$exhibit${}` syntax:

> **Note**: The `$grid${}` syntax is only used in **Document View** for inline structured layouts.
> **Dashboard View** uses react-grid-layout for tile positioning (defined in layout metadata, not inline).
> **Canvas View** uses ReactFlow for free-form node positioning.

```markdown
$filter${
  "id": "ticker_filter",
  "type": "select",
  "column": "stocks.dim_stock.ticker"
}

$exhibit${
  "id": "price_chart",
  "type": "line_chart",
  "x_axis": { "dimension": "stocks.fact_stock_prices.date" },
  "y_axis": { "measure": "stocks.fact_stock_prices.close" }
}
```

The view mode determines **how** these blocks are positioned, not **what** they contain.

---

## Unified Config Architecture

### The Pattern: Everything as Markdown

Following the successful `domains/` pattern, we extend markdown-with-YAML-frontmatter to:

1. **Data Sources** - API endpoint definitions
2. **Domains** - Model definitions (existing)
3. **Exhibits** - Visualization type definitions (NEW)

### Folder Structure

```
de_Funk/
├── Data Sources/                    # NEW: API endpoint configs
│   └── Endpoints/
│       ├── Alpha Vantage/
│       │   ├── Prices/
│       │   │   └── Time Series Daily.md
│       │   └── Fundamentals/
│       │       ├── Income Statement.md
│       │       └── Balance Sheet.md
│       ├── BLS/
│       │   └── Economic/
│       │       └── Unemployment Rate.md
│       └── Chicago/
│           └── Municipal/
│               └── Budget.md
│
├── Domains/                         # EXISTING (renamed from domains/)
│   ├── Corporate/
│   │   └── Company.md
│   ├── Securities/
│   │   ├── Stocks.md
│   │   └── Forecast/
│   │       └── Forecast.md
│   └── Foundation/
│       └── Temporal.md
│
├── Exhibits/                        # NEW: Exhibit type definitions
│   ├── Charts/
│   │   ├── Line Chart.md
│   │   ├── Bar Chart.md
│   │   ├── Scatter Chart.md
│   │   ├── Dual Axis Chart.md
│   │   └── Forecast Chart.md
│   ├── Tables/
│   │   ├── Data Table.md
│   │   └── Great Table.md
│   ├── Cards/
│   │   └── Metric Cards.md
│   └── Maps/
│       ├── Choropleth.md
│       └── Point Map.md
│
├── configs/
│   └── notebooks/                   # EXISTING: User notebooks
│       ├── stock_price_analysis.md
│       ├── sector_analysis.md
│       └── forecast_analysis.md
```

### Exhibit Type Definition Format

Each exhibit type is a markdown file with YAML frontmatter defining its schema:

```markdown
# Exhibits/Charts/Line Chart.md
---
exhibit_type: line_chart
version: 2.0
description: "Time series visualization with multiple series support"

# Schema definition for this exhibit type
schema:
  required:
    x_axis:
      type: axis_config
      description: "X-axis configuration (typically time dimension)"
      properties:
        dimension:
          type: column_reference
          description: "Column to use for X axis"
        label:
          type: string
          description: "Axis label"

    y_axis:
      type: axis_config
      description: "Y-axis configuration"
      properties:
        measures:
          type: array
          items:
            type: column_reference
          description: "Measures to plot"
        label:
          type: string

  optional:
    color_by:
      type: column_reference
      description: "Dimension for color grouping (e.g., ticker)"

    measure_selector:
      type: selector_config
      description: "Dynamic measure selection UI"
      properties:
        available_measures:
          type: array
        default_measures:
          type: array

    dimension_selector:
      type: selector_config
      description: "Dynamic dimension selection UI"

    title:
      type: string

    description:
      type: string

    interactive:
      type: boolean
      default: true

# Rendering configuration
render:
  library: plotly
  component: Scatter  # Plotly component to use
  mode: lines+markers

# Default styling
styling:
  height: 400
  margin:
    l: 40
    r: 40
    t: 40
    b: 40
  template: plotly_white

# Example usage
example: |
  $exhibit${
    "id": "price-trend",
    "type": "line_chart",
    "x_axis": {
      "dimension": "stocks.fact_stock_prices.trade_date",
      "label": "Date"
    },
    "y_axis": {
      "measures": ["stocks.fact_stock_prices.close"],
      "label": "Price ($)"
    },
    "color_by": "stocks.dim_stock.ticker"
  }
---

# Line Chart

Displays time series data as connected points. Ideal for showing trends over time.

## Features

- Multiple series support via `color_by`
- Dynamic measure selection
- Interactive zoom and pan
- Hover tooltips with data values

## Common Use Cases

1. **Stock Price Trends**: Show OHLC prices over time
2. **Performance Comparison**: Compare multiple tickers
3. **Metric Tracking**: Monitor KPIs over time

## Configuration Examples

### Basic Line Chart

```yaml
type: line_chart
x_axis:
  dimension: trade_date
y_axis:
  measures: [close]
```

### Multi-Series with Color

```yaml
type: line_chart
x_axis:
  dimension: trade_date
y_axis:
  measures: [close, volume]
color_by: ticker
```
```

### Data Source Definition Format

```markdown
# Data Sources/Endpoints/Alpha Vantage/Prices/Time Series Daily.md
---
provider: alpha_vantage
endpoint: TIME_SERIES_DAILY
version: 1.0
description: "Daily OHLCV stock price data"

# API configuration
api:
  function: TIME_SERIES_DAILY
  parameters:
    symbol:
      type: string
      required: true
      description: "Stock ticker symbol"
    outputsize:
      type: enum
      values: [compact, full]
      default: compact
      description: "compact=100 days, full=20+ years"
    datatype:
      type: enum
      values: [json, csv]
      default: json

# Rate limiting
rate_limit:
  calls_per_minute: 5
  premium_calls_per_minute: 75

# Response schema (maps to Bronze table)
response_schema:
  time_series:
    type: object
    properties:
      date:
        type: date
        source: "Meta Data.3. Last Refreshed"
      open:
        type: decimal
        source: "1. open"
      high:
        type: decimal
        source: "2. high"
      low:
        type: decimal
        source: "3. low"
      close:
        type: decimal
        source: "4. close"
      volume:
        type: integer
        source: "5. volume"

# Bronze table mapping
bronze_table: securities_prices_daily
bronze_schema:
  ticker: string
  trade_date: date
  asset_type: string
  open: decimal(18,4)
  high: decimal(18,4)
  low: decimal(18,4)
  close: decimal(18,4)
  volume: bigint
---

# Time Series Daily

Retrieves daily OHLCV (Open, High, Low, Close, Volume) data for a given stock ticker.

## Usage

This endpoint is used by the Bronze ingestion pipeline to populate `securities_prices_daily`.

## Example Response

```json
{
  "Meta Data": {
    "1. Information": "Daily Prices",
    "2. Symbol": "AAPL",
    "3. Last Refreshed": "2026-01-24"
  },
  "Time Series (Daily)": {
    "2026-01-24": {
      "1. open": "185.50",
      "2. high": "187.25",
      "3. low": "184.00",
      "4. close": "186.75",
      "5. volume": "52000000"
    }
  }
}
```
```

### Benefits of This Pattern

| Benefit | Description |
|---------|-------------|
| **Discoverability** | Users can browse available exhibit types |
| **Self-documenting** | Each type includes usage docs and examples |
| **Validation** | Schema validates notebook configs at parse time |
| **Extensibility** | Add new exhibit types without code changes |
| **IDE Support** | YAML schema enables autocomplete |
| **Version Control** | Config changes tracked in git |

---

## Backend Reference Pathway

### Current Flow (Problematic)

```
Notebook.md
    │
    ▼ MarkdownParser (Python)
    │   - Parses $exhibit${...}
    │   - Creates Exhibit dataclass with ColumnReference objects
    │
    ▼ ExhibitRenderer (Streamlit)
    │   - Receives Exhibit object
    │   - Has x_axis.dimension as ColumnReference  ← BUG: Not string!
    │   - Calls pdf[x_col] where x_col is ColumnReference  ← CRASH
    │
    ▼ Plotly/Great Tables
        - Expects string column names
        - Gets ColumnReference objects → Error
```

**Root Cause**: `ColumnReference` objects created by parser are passed through without extracting `.field` attribute.

### New Flow (Clean)

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. CONFIG LAYER (Markdown + YAML)                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Exhibits/Charts/Line Chart.md                                  │
│  ├── schema: { x_axis: { dimension: column_reference } }        │
│  └── render: { library: plotly }                                │
│                                                                  │
│  configs/notebooks/stock_analysis.md                            │
│  └── $exhibit${ type: "line_chart", x_axis: { dimension: "..." }}
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. PARSE LAYER (Python → TypeScript)                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ExhibitLoader.load_type("line_chart")                          │
│  ├── Reads Exhibits/Charts/Line Chart.md                        │
│  ├── Returns ExhibitTypeSchema                                  │
│  └── Validates notebook exhibit against schema                  │
│                                                                  │
│  NotebookParser.parse(notebook_content)                         │
│  ├── Parses $exhibit${...} blocks                               │
│  ├── Resolves ColumnReference → { namespace, table, field }     │
│  └── Returns ExhibitConfig with RESOLVED field names            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. API LAYER (FastAPI)                                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  POST /api/query                                                 │
│  {                                                               │
│    "model": "stocks",                                            │
│    "table": "fact_stock_prices",                                 │
│    "columns": ["trade_date", "close", "ticker"],  ← Strings!    │
│    "filters": [...]                                              │
│  }                                                               │
│                                                                  │
│  Response: { data: [...], columns: [...] }                      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. QUERY LAYER (Python Backend)                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  UniversalSession.query_model(                                  │
│    model="stocks",                                               │
│    table="fact_stock_prices",                                    │
│    columns=["trade_date", "close", "ticker"],  ← Strings!       │
│    filters=[...]                                                 │
│  )                                                               │
│                                                                  │
│  FilterEngine.apply(df, filters)                                │
│  ├── All filter columns are strings                             │
│  └── No ColumnReference objects at this layer                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. RENDER LAYER (React Frontend)                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  <ExhibitNode                                                    │
│    type="line_chart"                                             │
│    data={queryResult}                                            │
│    config={{                                                     │
│      x: "trade_date",      ← String!                            │
│      y: ["close"],         ← Strings!                           │
│      color: "ticker"       ← String!                            │
│    }}                                                            │
│  />                                                              │
│                                                                  │
│  Plotly.newPlot(element, [{                                     │
│    x: data.map(d => d.trade_date),                              │
│    y: data.map(d => d.close),                                   │
│  }])                                                             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Key Principle: ColumnReference Resolution

**ColumnReference objects exist ONLY in the parser layer.** They are resolved to strings before leaving the parser.

```python
# WRONG (current): ColumnReference leaks through
exhibit.x_axis.dimension = ColumnReference(namespace='stocks', table='fact_stock_prices', field='trade_date')

# CORRECT (new): Resolved at parse time
exhibit_config = {
    "x_axis": {
        "dimension": "trade_date",  # String!
        "source_table": "stocks.fact_stock_prices",  # Metadata for debugging
    }
}
```

### API Contract

The API layer ONLY deals with strings:

```typescript
// TypeScript types for API requests/responses
interface QueryRequest {
  model: string;
  table: string;
  columns: string[];  // Always strings
  filters: Filter[];
  limit?: number;
}

interface Filter {
  column: string;     // Always string
  operator: 'eq' | 'in' | 'between' | 'gt' | 'lt' | 'gte' | 'lte';
  value: any;
}

interface QueryResponse {
  data: Record<string, any>[];
  columns: ColumnInfo[];
  row_count: number;
  execution_time_ms: number;
}

interface ColumnInfo {
  name: string;       // Column name (string)
  type: string;       // Data type
  source?: string;    // Original qualified name for debugging
}
```

---

## Dead Code Identification

### Files to DELETE During Migration

These files will be completely removed:

#### Streamlit UI Layer (Entire `app/ui/` directory)

| File | Reason for Deletion |
|------|---------------------|
| `app/ui/notebook_app_duckdb.py` | Replaced by React App.tsx |
| `app/ui/components/notebook_view.py` | Replaced by React DocumentView |
| `app/ui/components/sidebar.py` | Replaced by React Sidebar |
| `app/ui/components/model_graph_viewer.py` | Replaced by ReactFlow |
| `app/ui/components/filters.py` | Replaced by React FilterNode |
| `app/ui/components/dynamic_filters.py` | Replaced by React hooks |
| `app/ui/components/active_filters_display.py` | Replaced by React chips |
| `app/ui/components/yaml_editor.py` | Replaced by Monaco Editor |
| `app/ui/components/notebook_creator.py` | Replaced by React dialog |
| `app/ui/components/theme.py` | Replaced by Tailwind |
| `app/ui/components/toggle_container.py` | Replaced by React Collapsible |
| `app/ui/state/session_state.py` | Replaced by Zustand |
| `app/ui/callbacks/block_callbacks.py` | Replaced by React handlers |

#### Exhibit Renderers (Entire `app/ui/components/exhibits/` directory)

| File | Issues | Replacement |
|------|--------|-------------|
| `exhibits/__init__.py` | Hardcoded if/elif dispatcher | React component registry |
| `exhibits/bar_chart.py` | ColumnReference bugs | React + Plotly.js |
| `exhibits/line_chart.py` | ColumnReference bugs (lines 136, 141, 167, 181) | React + Plotly.js |
| `exhibits/forecast_chart.py` | ColumnReference bugs (lines 186, 284, 339, 353) | React + Plotly.js |
| `exhibits/great_table.py` | Complex styling logic | React + Tabulator |
| `exhibits/data_table.py` | Simple, no issues | React + Tabulator |
| `exhibits/metric_cards.py` | Minor issues | React + Plotly Indicator |
| `exhibits/weighted_aggregate_chart.py` | ColumnReference bugs | React + Plotly.js |
| `exhibits/dimension_selector.py` | Streamlit-specific | React MultiSelect |
| `exhibits/measure_selector.py` | Streamlit-specific | React MultiSelect |
| `exhibits/click_events.py` | Streamlit-specific | React event handlers |
| `exhibits/base_renderer.py` | ColumnReference bug in `_apply_aggregation` (line 241) | React base component |

#### Markdown Renderers (Entire `app/ui/components/markdown/` directory)

| File | Replacement |
|------|-------------|
| `markdown/renderer.py` | React MarkdownRenderer |
| `markdown/parser.py` | TypeScript parser (or keep Python via API) |
| `markdown/styles.py` | Tailwind CSS |
| `markdown/utils.py` | TypeScript utils |
| `markdown/grid_renderer.py` | React GridLayout |
| `markdown/flat_renderer.py` | Part of DocumentView |
| `markdown/toggle_container.py` | React Collapsible |
| `markdown/blocks/*.py` | React components |
| `markdown/editors/*.py` | React editors + Monaco |

### Files to KEEP (Backend Core)

These files are backend infrastructure and remain unchanged:

| Directory | Files | Status |
|-----------|-------|--------|
| `core/session/` | `universal_session.py`, `filters.py` | ✅ Keep |
| `core/duckdb_connection.py` | DuckDB connection | ✅ Keep |
| `models/api/` | `session.py`, `auto_join.py`, `aggregation.py` | ✅ Keep |
| `models/base/` | All model infrastructure | ✅ Keep |
| `config/` | `loader.py`, `domain_loader.py`, `models.py` | ✅ Keep |
| `datapipelines/` | All ingestion code | ✅ Keep |
| `storage/` | All data files | ✅ Keep |

### Files to MODIFY

| File | Changes Needed |
|------|----------------|
| `app/notebook/schema.py` | Add `resolve_to_string()` method to ColumnReference |
| `app/notebook/parsers/markdown_parser.py` | Resolve ColumnReferences at parse time |
| `config/domain_loader.py` | Add ExhibitLoader, DataSourceLoader |

### Known Bugs to Fix BEFORE Migration

These bugs exist in current code and should be fixed if any interim releases are needed:

```python
# line_chart.py - Lines 136, 141, 167, 181
# Uses x_col (ColumnReference) instead of x_col_name (string)
x_col = exhibit.x_axis.dimension  # Line 50: ColumnReference
x_col_name = extract_field_name(x_col)  # Line 52: string
# But then uses x_col instead of x_col_name:
pdf = pdf.groupby([x_col, ...])  # Line 136: BUG!
pdf = pdf.sort_values(by=x_col)  # Line 141: BUG!
x=df_subset[x_col]               # Line 167: BUG!
x=pdf[x_col]                     # Line 181: BUG!

# forecast_chart.py - Lines 186, 284, 339, 353
x_col = self.exhibit.x_axis.dimension  # Line 183: ColumnReference
pdf_sorted = self.pdf.sort_values(by=x_col)  # Line 186: BUG!
x_label = ... or x_col.replace('_', ' ')  # Line 284: BUG! .replace() on ColumnReference
x=df_subset[x_col]  # Line 339: BUG!
x=df_measure[x_col]  # Line 353: BUG!

# base_renderer.py - Line 241
x_col = self.exhibit.x_axis.dimension  # ColumnReference, not string
# Used directly in SQL without extraction
```

---

## Technical Stack

### Frontend
```json
{
  "framework": "React 18+ with TypeScript",
  "build": "Vite",
  "canvas": "ReactFlow",
  "charts": "Plotly.js (react-plotly.js)",
  "tables": "Tabulator (react-tabulator)",
  "maps": "Mapbox GL JS + DeckGL",
  "styling": "Tailwind CSS + shadcn/ui",
  "state": "Zustand",
  "forms": "React Hook Form + Zod",
  "markdown": "react-markdown + remark-gfm",
  "editors": {
    "markdown": "Milkdown or BlockNote",
    "yaml": "Monaco Editor",
    "code": "Monaco Editor"
  },
  "icons": "Lucide React"
}
```

### Backend
```python
# requirements-api.txt
fastapi>=0.109.0
uvicorn>=0.27.0
pydantic>=2.0
python-multipart
aiofiles
websockets  # Future: real-time collaboration

# Existing (unchanged)
duckdb
pyarrow
pyyaml
```

### Development
```
IDE: VS Code (monorepo)
Node: v20 LTS
Python: 3.11+
Package Manager: pnpm (frontend), pip (backend)
```

---

## ReactFlow Container Patterns

### Node Types

```typescript
// frontend/src/types/nodes.ts
export type NodeType =
  | 'markdown'    // Text content
  | 'filter'      // Dimension selector
  | 'exhibit'     // Chart (Plotly)
  | 'grid'        // Table (Tabulator)
  | 'map'         // Geographic map
  | 'group'       // Container for other nodes
  | 'frame'       // Visual annotation frame
  | 'note';       // Sticky note annotation

export interface BaseNodeData {
  id: string;
  label?: string;
}

export interface ExhibitNodeData extends BaseNodeData {
  exhibitType: string;  // References Exhibits/{type}.md
  query: QueryConfig;
  // All column references are strings at this point!
  x: string;
  y: string | string[];
  color?: string;
  title?: string;
}

export interface FilterNodeData extends BaseNodeData {
  dimension: string;  // String, not ColumnReference!
  type: 'select' | 'multiselect' | 'date_range' | 'slider';
  selected?: any;
}

export interface GridNodeData extends BaseNodeData {
  query: QueryConfig;
  columns: ColumnDef[];  // Column names are strings!
  groupBy?: string;
  showFooter?: boolean;
}

export interface GroupNodeData extends BaseNodeData {
  label: string;
  collapsed?: boolean;
  style?: 'default' | 'dashed' | 'solid';
}

// Query config uses strings for all column references
export interface QueryConfig {
  model: string;
  table: string;
  columns: string[];
  filters?: Filter[];
}
```

### Parent-Child Grouping

```typescript
// Nodes can be nested inside group nodes
const nodes = [
  {
    id: 'group-sector-analysis',
    type: 'group',
    position: { x: 100, y: 100 },
    style: { width: 600, height: 400 },
    data: { label: 'Sector Analysis' }
  },
  {
    id: 'filter-sector',
    type: 'filter',
    position: { x: 20, y: 50 },      // Relative to parent
    parentId: 'group-sector-analysis', // Key: parent reference
    extent: 'parent',                  // Constrain to parent bounds
    data: { dimension: 'sector', type: 'select' }  // String!
  },
  {
    id: 'chart-revenue',
    type: 'exhibit',
    position: { x: 200, y: 50 },
    parentId: 'group-sector-analysis',
    extent: 'parent',
    data: {
      exhibitType: 'bar_chart',
      query: {
        model: 'stocks',
        table: 'dim_stock',
        columns: ['sector', 'market_cap'],
      },
      x: 'sector',  // String!
      y: 'market_cap'  // String!
    }
  }
];
```

### Group Node Component

```tsx
// frontend/src/components/nodes/GroupNode.tsx
import { NodeResizer } from '@reactflow/node-resizer';
import { memo, useState } from 'react';
import { NodeProps, useReactFlow } from 'reactflow';

export const GroupNode = memo(({ id, data, selected }: NodeProps<GroupNodeData>) => {
  const [collapsed, setCollapsed] = useState(data.collapsed ?? false);
  const { setNodes } = useReactFlow();

  const toggleCollapse = () => {
    const newCollapsed = !collapsed;
    setCollapsed(newCollapsed);

    // Hide/show child nodes
    setNodes(nodes => nodes.map(node => {
      if (node.parentId === id) {
        return { ...node, hidden: newCollapsed };
      }
      return node;
    }));
  };

  return (
    <>
      <NodeResizer
        minWidth={200}
        minHeight={150}
        isVisible={selected}
        lineClassName="border-blue-500"
        handleClassName="bg-blue-500"
      />
      <div className={`
        rounded-lg border-2 border-dashed border-blue-400
        bg-blue-50/50 min-h-full
        ${collapsed ? 'h-12' : ''}
      `}>
        <div className="flex items-center justify-between px-3 py-2 border-b border-blue-300">
          <span className="font-semibold text-blue-700">{data.label}</span>
          <button
            onClick={toggleCollapse}
            className="text-blue-500 hover:text-blue-700"
          >
            {collapsed ? '▶' : '▼'}
          </button>
        </div>
        {!collapsed && (
          <div className="p-2">
            {/* Child nodes render here via parentId */}
          </div>
        )}
      </div>
    </>
  );
});
```

### Edge Types

```typescript
// frontend/src/types/edges.ts
export type EdgeType =
  | 'dataFlow'    // Solid line: filter → exhibit data connection
  | 'insight'     // Dashed line: user-drawn insight/annotation
  | 'dependency'; // Dotted line: model/query dependency

export interface InsightEdgeData {
  label?: string;
  color?: string;
}
```

```tsx
// frontend/src/components/edges/InsightEdge.tsx
import { BaseEdge, EdgeLabelRenderer, getBezierPath } from 'reactflow';

export function InsightEdge({
  id, sourceX, sourceY, targetX, targetY,
  sourcePosition, targetPosition, data, style
}) {
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX, sourceY, sourcePosition,
    targetX, targetY, targetPosition,
  });

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        style={{
          ...style,
          strokeDasharray: '5,5',
          stroke: data?.color ?? '#64748b'
        }}
      />
      {data?.label && (
        <EdgeLabelRenderer>
          <div
            style={{
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
            }}
            className="bg-white px-2 py-1 rounded border text-sm"
          >
            {data.label}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}
```

### Canvas State Structure

```typescript
// frontend/src/stores/canvasStore.ts
import { create } from 'zustand';
import { Node, Edge } from 'reactflow';

interface CanvasState {
  nodes: Node[];
  edges: Edge[];

  // Actions
  setNodes: (nodes: Node[]) => void;
  setEdges: (edges: Edge[]) => void;
  addNode: (node: Node) => void;
  updateNode: (id: string, data: Partial<Node>) => void;
  deleteNode: (id: string) => void;
  addEdge: (edge: Edge) => void;
  deleteEdge: (id: string) => void;

  // History for undo/redo
  history: { nodes: Node[], edges: Edge[] }[];
  historyIndex: number;
  undo: () => void;
  redo: () => void;

  // Persistence
  loadCanvas: (notebookId: string) => Promise<void>;
  saveCanvas: () => Promise<void>;
}

export const useCanvasStore = create<CanvasState>((set, get) => ({
  nodes: [],
  edges: [],
  history: [],
  historyIndex: -1,

  // ... implementation
}));
```

---

## Component Migration Guide

### Charts: Plotly (Direct Transfer)

Plotly configs transfer nearly 1:1:

```python
# Current Python
fig = px.bar(df, x='sector', y='revenue', color='region')
st.plotly_chart(fig)
```

```tsx
// New React - ALL column references are strings
import Plot from 'react-plotly.js';

function ExhibitNode({ data }: NodeProps<ExhibitNodeData>) {
  const { data: chartData } = useQuery(['chart', data.query], () =>
    fetchQuery(data.query)
  );

  return (
    <Plot
      data={[{
        type: 'bar',
        x: chartData.map(d => d[data.x]),  // data.x is always a string!
        y: chartData.map(d => d[data.y]),  // data.y is always a string!
        marker: { color: data.color }
      }]}
      layout={{
        title: data.title,
        autosize: true,
      }}
      useResizeHandler
      style={{ width: '100%', height: '100%' }}
    />
  );
}
```

### Tables: Great Tables → Tabulator

```python
# Current Python (Great Tables)
GT(df).tab_header(title="Revenue").fmt_currency(columns="revenue")
```

```tsx
// New React (Tabulator)
import { ReactTabulator } from 'react-tabulator';
import 'react-tabulator/lib/styles.css';

function GridNode({ data }: NodeProps<GridNodeData>) {
  const { data: tableData } = useQuery(['table', data.query], () =>
    fetchQuery(data.query)
  );

  const columns = data.columns.map(col => ({
    title: col.label,
    field: col.field,  // Always a string!
    formatter: col.format === 'currency' ? 'money' : undefined,
    formatterParams: col.format === 'currency' ? { symbol: '$' } : undefined,
    bottomCalc: col.showTotal ? 'sum' : undefined,
    headerFilter: data.filterable ? true : undefined,
  }));

  return (
    <div className="grid-node">
      {data.title && <h3 className="font-semibold mb-2">{data.title}</h3>}
      <ReactTabulator
        data={tableData}
        columns={columns}
        layout="fitDataFill"
        groupBy={data.groupBy}  // String!
        options={{
          pagination: data.paginate ? 'local' : false,
          paginationSize: 20,
        }}
      />
    </div>
  );
}
```

### Tabulator Feature Mapping

| Great Tables | Tabulator Equivalent |
|--------------|---------------------|
| `tab_header(title=)` | Wrapper `<h3>` or custom header |
| `tab_spanner(label=, columns=)` | `{ title: "Group", columns: [...] }` |
| `fmt_currency()` | `formatter: "money"` |
| `fmt_percent()` | `formatter: "progress"` or custom |
| `data_color(palette=)` | `formatter` function with style |
| `tab_footnote()` | Custom footer component |
| `cols_label()` | `title` in column def |
| Row grouping | `groupBy` option |
| Footer calculations | `bottomCalc: "sum"/"avg"/"count"` |

### Maps: New Capability

```tsx
// frontend/src/components/nodes/MapNode.tsx
import Map, { Layer, Source } from 'react-map-gl';
import 'mapbox-gl/dist/mapbox-gl.css';

function MapNode({ data }: NodeProps<MapNodeData>) {
  const { data: geoData } = useQuery(['map', data.query], () =>
    fetchQuery(data.query)
  );

  return (
    <Map
      mapboxAccessToken={MAPBOX_TOKEN}
      initialViewState={{
        longitude: -98.5,
        latitude: 39.8,
        zoom: 3.5
      }}
      style={{ width: '100%', height: '100%' }}
      mapStyle="mapbox://styles/mapbox/light-v11"
    >
      <Source type="geojson" data={geoData}>
        <Layer
          type="fill"
          paint={{
            'fill-color': [
              'interpolate',
              ['linear'],
              ['get', data.valueField],  // String!
              0, '#f7fbff',
              100, '#08306b'
            ],
            'fill-opacity': 0.7
          }}
        />
      </Source>
    </Map>
  );
}
```

### Filters: Enhanced

```tsx
// frontend/src/components/nodes/FilterNode.tsx
import { Select, MultiSelect, DateRangePicker, Slider } from '@/components/ui';

function FilterNode({ data, id }: NodeProps<FilterNodeData>) {
  const { dimensions } = useDimensions();
  const { setFilterValue, getConnectedNodes } = useCanvasStore();

  const handleChange = (value: any) => {
    setFilterValue(id, value);

    // Trigger re-query on connected exhibit nodes
    const connected = getConnectedNodes(id);
    connected.forEach(nodeId => invalidateQueries(['chart', nodeId]));
  };

  // data.dimension is always a string!
  const options = dimensions[data.dimension]?.values ?? [];

  switch (data.type) {
    case 'select':
      return (
        <Select
          label={data.label ?? data.dimension}
          options={options}
          value={data.selected}
          onChange={handleChange}
        />
      );
    case 'multiselect':
      return (
        <MultiSelect
          label={data.label ?? data.dimension}
          options={options}
          value={data.selected ?? []}
          onChange={handleChange}
        />
      );
    case 'date_range':
      return (
        <DateRangePicker
          label={data.label ?? 'Date Range'}
          value={data.selected}
          onChange={handleChange}
        />
      );
    case 'slider':
      return (
        <Slider
          label={data.label ?? data.dimension}
          min={data.min}
          max={data.max}
          value={data.selected}
          onChange={handleChange}
        />
      );
  }
}
```

---

## API Specification

### Endpoints

```yaml
# Notebooks
GET    /api/notebooks              # List all notebooks
GET    /api/notebooks/{id}         # Get notebook content + canvas state
POST   /api/notebooks              # Create notebook
PUT    /api/notebooks/{id}         # Update notebook
DELETE /api/notebooks/{id}         # Delete notebook
POST   /api/notebooks/{id}/duplicate  # Duplicate notebook

# Folders
GET    /api/folders                # List folder tree
POST   /api/folders                # Create folder
PUT    /api/folders/{id}           # Rename/move folder
DELETE /api/folders/{id}           # Delete folder

# Queries - ALL COLUMN REFERENCES ARE STRINGS
POST   /api/query                  # Execute SQL query
POST   /api/query/validate         # Validate SQL without executing

# Dimensions
GET    /api/dimensions             # List available dimensions
GET    /api/dimensions/{name}      # Get dimension values

# Exhibits (NEW)
GET    /api/exhibits               # List available exhibit types
GET    /api/exhibits/{type}        # Get exhibit type schema

# Data Sources (NEW)
GET    /api/datasources            # List available data sources
GET    /api/datasources/{provider}/{endpoint}  # Get endpoint config

# Canvas
PUT    /api/notebooks/{id}/canvas  # Save canvas layout
GET    /api/notebooks/{id}/canvas  # Get canvas layout

# Export
POST   /api/export/pdf             # Export canvas to PDF
POST   /api/export/png             # Export canvas to PNG
POST   /api/export/data            # Export query results
```

### Request/Response Models

```python
# api/models/notebooks.py
from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime

class NotebookBase(BaseModel):
    title: str
    folder_id: Optional[str] = None
    tags: List[str] = []

class NotebookCreate(NotebookBase):
    content: str  # Markdown content

class NotebookUpdate(NotebookBase):
    content: Optional[str] = None
    canvas_state: Optional[dict] = None

class NotebookResponse(NotebookBase):
    id: str
    content: str
    canvas_state: Optional[dict]
    created_at: datetime
    updated_at: datetime

class QueryRequest(BaseModel):
    """All column references are strings!"""
    model: str
    table: str
    columns: List[str]  # Strings, not ColumnReference!
    filters: Optional[List[dict]] = None
    limit: int = 10000

class QueryResponse(BaseModel):
    data: List[dict]
    columns: List[dict]  # name (string), type
    row_count: int
    execution_time_ms: float

class DimensionResponse(BaseModel):
    name: str
    display_name: str
    values: List[Any]
    type: str  # string, number, date

class ExhibitTypeResponse(BaseModel):
    """Schema for an exhibit type from Exhibits/*.md"""
    type: str
    version: str
    description: str
    schema: dict  # JSON Schema for validation
    render: dict  # Rendering configuration
    example: str  # Example usage
```

### FastAPI Implementation

```python
# api/routers/queries.py
from fastapi import APIRouter, HTTPException
from core.session.universal_session import UniversalSession
import time

router = APIRouter(prefix="/api")
session = UniversalSession(backend="duckdb")

@router.post("/query", response_model=QueryResponse)
async def execute_query(request: QueryRequest):
    """Execute a query. All column references must be strings."""
    start = time.time()
    try:
        # Build query from model/table/columns - ALL STRINGS
        df = session.query_model(
            model=request.model,
            table=request.table,
            columns=request.columns,  # Strings!
            filters=request.filters,
            limit=request.limit
        )

        return QueryResponse(
            data=df.to_dict(orient="records"),
            columns=[
                {"name": col, "type": str(df[col].dtype)}
                for col in df.columns
            ],
            row_count=len(df),
            execution_time_ms=(time.time() - start) * 1000
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/dimensions/{name}", response_model=DimensionResponse)
async def get_dimension(name: str):
    """Get dimension values. Name is always a string."""
    values = session.get_dimension_values(name)  # String!
    return DimensionResponse(
        name=name,
        display_name=name.replace("_", " ").title(),
        values=values,
        type="string"
    )

@router.get("/exhibits", response_model=List[ExhibitTypeResponse])
async def list_exhibit_types():
    """List all available exhibit types from Exhibits/*.md"""
    from config.exhibit_loader import ExhibitLoader
    loader = ExhibitLoader(Path("Exhibits"))
    return loader.list_types()

@router.get("/exhibits/{exhibit_type}", response_model=ExhibitTypeResponse)
async def get_exhibit_type(exhibit_type: str):
    """Get schema for a specific exhibit type."""
    from config.exhibit_loader import ExhibitLoader
    loader = ExhibitLoader(Path("Exhibits"))
    return loader.load_type(exhibit_type)
```

---

## Phased Implementation Plan

### Phase 0: Pre-Migration Cleanup (Week 0)
**Goal**: Fix critical bugs, prepare codebase

```
Week 0: Stabilization
├── Fix ColumnReference bugs in line_chart.py
├── Fix ColumnReference bugs in forecast_chart.py
├── Fix ColumnReference bugs in base_renderer.py
├── Add extract_field_name to all exhibit renderers
├── Create Exhibits/ folder structure
├── Create Data Sources/ folder structure
├── Document all exhibit types as markdown
└── Verify existing notebooks still work
```

### Phase 1: Foundation (Weeks 1-4)
**Goal**: React app with feature parity to current Streamlit

```
Week 1-2: Project Setup
├── Initialize Vite + React + TypeScript
├── Configure Tailwind + shadcn/ui
├── Set up FastAPI with basic routers
├── Notebook CRUD endpoints
├── Query execution endpoint (strings only!)
├── Exhibit type listing endpoint
├── Project structure and conventions
└── ExhibitLoader for Exhibits/*.md

Week 3-4: Core Views
├── Notebook tree sidebar
├── Document view (linear markdown rendering)
├── Filter components (strings only!)
├── Exhibit components (Plotly charts)
├── Grid components (Tabulator tables)
└── Basic navigation and routing
```

**Deliverable**: Browse and view existing notebooks in React

### Phase 2: Editing & Management (Weeks 5-8)
**Goal**: Full content management in-app

```
Week 5-6: Content Editing
├── Markdown editor integration (Milkdown/BlockNote)
├── YAML/properties panel (Monaco)
├── Create new notebook
├── Delete/rename notebook
├── Autosave with debounce
└── Undo/redo system

Week 7-8: Organization
├── Folder creation and management
├── Drag-drop in tree view
├── Search functionality
├── Templates system (from Exhibits/*.md examples)
├── Duplicate notebook
└── Recent/favorites
```

**Deliverable**: Full notebook CRUD entirely in-app

### Phase 3: Canvas/Whiteboard (Weeks 9-13)
**Goal**: ReactFlow whiteboard implementation

```
Week 9-10: Canvas Foundation
├── ReactFlow integration
├── Markdown → nodes parser (resolve ColumnRef to strings!)
├── Custom node types (filter, exhibit, grid, markdown)
├── Auto-layout algorithm (dagre)
├── Manual drag positioning
└── Position persistence to markdown

Week 11-12: Connections & Interaction
├── Data flow edges (filter → exhibit)
├── Insight edges (user annotations)
├── Cross-filtering via connections
├── Node resize handles
├── Group nodes (containers)
└── Minimap and controls

Week 13: Polish
├── Keyboard shortcuts
├── Context menus
├── View toggle (document/canvas/split)
├── Canvas templates
└── Performance optimization
```

**Deliverable**: Full whiteboard experience with drawable connections

### Phase 4: Advanced Features (Weeks 14-17)
**Goal**: Production-ready polish

```
Week 14-15: Data Interaction
├── Click-through drill-down
├── Chart ↔ filter synchronization
├── Data refresh controls
├── Export (PNG, PDF, CSV)
└── Embed code generation

Week 16-17: Maps & Visualization
├── Map node type (Mapbox GL)
├── Choropleth support
├── Point/marker layers
├── DeckGL integration (3D, heatmaps)
└── GeoJSON upload
```

**Deliverable**: Full-featured data exploration platform

### Phase 5: Deprecation & Cleanup (Week 18)
**Goal**: Remove dead code

```
Week 18: Streamlit Removal
├── Delete app/ui/ directory entirely
├── Delete app/notebook/parsers/ (if moved to API)
├── Update CLAUDE.md
├── Update all documentation
├── Remove Streamlit from requirements.txt
└── Final testing
```

### Phase 6: Collaboration (Weeks 19-20, Optional)
**Goal**: Multi-user features

```
├── User authentication
├── Share links (view-only, edit)
├── Comments on nodes
├── Real-time cursors (WebSocket)
└── Permission system
```

---

## Development Environment

### Recommended Setup

**IDE**: VS Code (monorepo for frontend + backend)

```bash
# Install VS Code extensions
code --install-extension dbaeumer.vscode-eslint
code --install-extension esbenp.prettier-vscode
code --install-extension bradlc.vscode-tailwindcss
code --install-extension ms-python.python
code --install-extension ms-python.vscode-pylance
```

### Project Structure

```
de_Funk/
├── frontend/                    # React application
│   ├── src/
│   │   ├── components/
│   │   │   ├── canvas/         # ReactFlow setup
│   │   │   ├── nodes/          # Custom node types
│   │   │   ├── edges/          # Custom edge types
│   │   │   ├── panels/         # Sidebar panels
│   │   │   ├── editors/        # Markdown, YAML editors
│   │   │   └── ui/             # shadcn/ui components
│   │   ├── views/
│   │   │   ├── DocumentView/
│   │   │   ├── CanvasView/
│   │   │   └── SplitView/
│   │   ├── hooks/
│   │   ├── stores/             # Zustand stores
│   │   ├── services/           # API client
│   │   ├── types/
│   │   └── utils/
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── tailwind.config.js
│
├── api/                         # FastAPI backend
│   ├── routers/
│   │   ├── notebooks.py
│   │   ├── queries.py
│   │   ├── dimensions.py
│   │   ├── exhibits.py         # NEW: Exhibit type API
│   │   ├── datasources.py      # NEW: Data source API
│   │   └── export.py
│   ├── services/
│   ├── models/
│   └── main.py
│
├── Data Sources/                # NEW: API endpoint configs
│   └── Endpoints/
│       ├── Alpha Vantage/
│       ├── BLS/
│       └── Chicago/
│
├── Domains/                     # Renamed from domains/
│   ├── Corporate/
│   ├── Securities/
│   └── Foundation/
│
├── Exhibits/                    # NEW: Exhibit type definitions
│   ├── Charts/
│   ├── Tables/
│   ├── Cards/
│   └── Maps/
│
├── app/                         # DEPRECATED: Streamlit (to be deleted)
├── configs/                     # Notebooks, models (unchanged)
├── core/                        # Session, filters (unchanged)
├── models/                      # Domain models (unchanged)
└── storage/                     # Data (unchanged)
```

### Development Workflow

```bash
# Terminal 1: Frontend dev server
cd frontend
pnpm install
pnpm dev  # http://localhost:5173

# Terminal 2: Backend dev server
cd api
pip install -r requirements.txt
uvicorn main:app --reload --port 8000  # http://localhost:8000

# Terminal 3: Existing DuckDB (if needed)
# DuckDB is file-based, no server needed
```

---

## Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| ReactFlow learning curve | Medium | Medium | Prototype early, validate with complex layouts |
| State management complexity | Medium | High | Start simple with Zustand, add complexity as needed |
| Parser compatibility | Low | High | Keep Python parser, call via API |
| Performance with many nodes | Medium | Medium | Virtual rendering, lazy loading, benchmarking |
| Tabulator styling parity | Medium | Low | Invest in CSS theme early |
| Map integration complexity | Medium | Medium | Start with basic choropleth, add features incrementally |
| **ColumnReference bugs** | **High** | **High** | **Fix in Phase 0 before migration** |
| **Dead code accumulation** | Medium | Medium | Explicit deletion in Phase 5 |

---

## Success Metrics

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| Time to create notebook | N/A (external) | < 30 seconds | In-app creation |
| Time to edit content | N/A (external) | < 5 seconds | In-app editing |
| Canvas interactions/minute | N/A | > 20 | Drag, connect, resize |
| Page load time | ~3s | < 1s | Lighthouse |
| Bundle size | N/A | < 500KB gzipped | Build output |
| Test coverage | ~20% | > 70% | Jest + pytest |
| **ColumnReference bugs** | **Multiple** | **Zero** | Error logs |
| **Dead code lines** | **~5000** | **0** | LOC count |

---

## UI Wireframe

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  de_Funk                    [🔍 Search...]           [+ New] [⚙️] [👤]      │
├────────────────┬────────────────────────────────────────────────────────────┤
│                │  Market Analysis            [📄 Doc] [🎨 Canvas] [⊞ Split] │
│  📁 Notebooks  │────────────────────────────────────────────────────────────│
│  ├─ 📁 Equity  │                                                            │
│  │  ├─ 📄 Over.│  ┌────────────────────────────────────────────────────┐   │
│  │  └─ 📄 Tech │  │                  CANVAS VIEW                       │   │
│  ├─ 📁 Macro   │  │                                                    │   │
│  └─ 📄 Dashb.. │  │  ┌─── Sector Analysis ─────────────────────────┐  │   │
│                │  │  │                                              │  │   │
│  ───────────── │  │  │  [Sector ▼]────────┐                        │  │   │
│  📊 Exhibits   │  │  │  [Technology]       │                        │  │   │
│  ├─ Charts     │  │  │  [Healthcare]       ▼                        │  │   │
│  │  ├─ Line    │  │  │              ┌─────────────┐                 │  │   │
│  │  └─ Bar     │  │  │              │ ████ Bar    │                 │  │   │
│  └─ Tables     │  │  │              │ ██████      │                 │  │   │
│                │  │  │              │ ███         │                 │  │   │
│  ───────────── │  │  │              └──────┬──────┘                 │  │   │
│  ⭐ Favorites  │  │  │                     │                        │  │   │
│  ├─ 📄 Daily   │  │  └─────────────────────┼────────────────────────┘  │   │
│  └─ 📄 Weekly  │  │                        │                           │   │
│                │  │         ┌──────────────┴──────────────┐           │   │
│  🕐 Recent     │  │         ▼                             ▼           │   │
│  ├─ 📄 Q4 Rev  │  │  ┌─────────────┐           ┌─────────────────┐   │   │
│  └─ 📄 Forecast│  │  │ 🗺️ Map     │◀ ─ ─ ─ ─ ─│ Grid Table      │   │   │
│                │  │  │ [Choropleth]│  insight  │ AAPL  $185.50   │   │   │
│                │  │  │             │   arrow   │ MSFT  $420.00   │   │   │
│                │  │  └─────────────┘           │ GOOGL $175.25   │   │   │
│                │  │                            └─────────────────┘   │   │
│                │  │                                                    │   │
│                │  └────────────────────────────────────────────────────┘   │
│                │  [🔍 100%] [⊡ Fit] [🔒 Lock] [📤 Export ▼]               │
├────────────────┴────────────────────────────────────────────────────────────┤
│  Properties Panel (collapsible)                                             │
│  ┌─ Selected: revenue-chart ────────────────────────────────────────────┐  │
│  │ Type: [Bar ▼]    X: [sector ▼]    Y: [revenue ▼]    Color: [🎨]     │  │
│  │ Title: [Revenue by Sector           ]  Legend: [✓]  Animate: [✓]    │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Markdown Syntax Extensions

Minimal additions to support canvas positions (backward compatible):

```markdown
---
title: Market Analysis
canvas:
  default_view: canvas  # or "document" or "split"
  auto_layout: dagre    # or "manual"
---

# Overview

Analysis of sector performance and trends.

$filter${
  "id": "sector-filter",
  "type": "multiselect",
  "dimension": "sector",
  "canvas": { "x": 100, "y": 100, "width": 200 }
}

$exhibit${
  "id": "revenue-chart",
  "type": "bar_chart",
  "x_axis": {
    "dimension": "sector"
  },
  "y_axis": {
    "measures": ["revenue"]
  },
  "connects_from": ["sector-filter"],
  "canvas": { "x": 400, "y": 100, "width": 400, "height": 300 }
}

$grid${
  "id": "company-table",
  "columns": ["ticker", "revenue", "growth"],
  "connects_from": ["sector-filter"],
  "canvas": { "x": 400, "y": 450, "width": 400 }
}

$insight${
  "from": "revenue-chart",
  "to": "company-table",
  "label": "Click to drill down"
}
```

---

## References

- [ReactFlow Documentation](https://reactflow.dev/)
- [Tabulator Documentation](http://tabulator.info/)
- [Plotly.js React](https://plotly.com/javascript/react/)
- [Mapbox GL JS](https://docs.mapbox.com/mapbox-gl-js/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [shadcn/ui Components](https://ui.shadcn.com/)
- [Zustand State Management](https://zustand-demo.pmnd.rs/)

---

## Appendix A: Node Type Specifications

### ExhibitNode (Charts)

```typescript
interface ExhibitNodeData {
  id: string;
  exhibitType: string;  // References Exhibits/{type}.md

  // Query config - all strings!
  query: {
    model: string;
    table: string;
    columns: string[];
    filters?: Filter[];
  };

  // Axes - ALL STRINGS, never ColumnReference
  x: string;
  y: string | string[];  // Multiple Y for multi-series
  color?: string;        // Color dimension
  size?: string;         // Size dimension (scatter)

  // Labels
  title?: string;
  xAxisLabel?: string;
  yAxisLabel?: string;

  // Options
  showLegend?: boolean;
  animate?: boolean;
  stacked?: boolean;     // For bar/area

  // Canvas
  canvas?: {
    x: number;
    y: number;
    width: number;
    height: number;
  };

  // Connections
  connects_from?: string[];  // Filter node IDs
}
```

### GridNode (Tables)

```typescript
interface GridNodeData {
  id: string;
  query: QueryConfig;

  // Columns - ALL STRINGS
  columns: {
    field: string;      // String, not ColumnReference!
    label?: string;
    format?: 'currency' | 'percent' | 'number' | 'date' | 'text';
    align?: 'left' | 'center' | 'right';
    width?: number;
    sortable?: boolean;
    showTotal?: boolean;
  }[];

  // Grouping
  groupBy?: string;     // String!

  // Features
  sortable?: boolean;
  filterable?: boolean;
  paginate?: boolean;
  pageSize?: number;

  // Footer
  showFooter?: boolean;

  // Canvas
  canvas?: { x: number; y: number; width: number; height: number; };
  connects_from?: string[];
}
```

### MapNode (Geographic)

```typescript
interface MapNodeData {
  id: string;
  mapType: 'choropleth' | 'points' | 'heatmap' | 'arc';
  query: QueryConfig;

  // Geography - ALL STRINGS
  geoField: string;       // String!
  geoType: 'us_states' | 'us_counties' | 'countries' | 'custom';
  customGeoJson?: string; // URL or inline GeoJSON

  // Value - STRINGS
  valueField: string;     // String!
  colorScale?: string;    // 'blues', 'reds', 'viridis', etc.

  // Points (for point maps) - STRINGS
  latField?: string;
  lonField?: string;
  sizeField?: string;

  // Options
  showLegend?: boolean;
  interactive?: boolean;

  // Canvas
  canvas?: { x: number; y: number; width: number; height: number; };
  connects_from?: string[];
}
```

### FilterNode

```typescript
interface FilterNodeData {
  id: string;
  dimension: string;     // STRING, not ColumnReference!
  type: 'select' | 'multiselect' | 'date_range' | 'slider' | 'text';

  // Display
  label?: string;
  placeholder?: string;

  // Options (for select types)
  options?: { value: any; label: string; }[];
  optionsQuery?: string;  // Dynamic options from query

  // Range (for slider/date)
  min?: number | string;
  max?: number | string;
  step?: number;

  // State
  selected?: any;
  defaultValue?: any;

  // Canvas
  canvas?: { x: number; y: number; width: number; };
}
```

### GroupNode (Container)

```typescript
interface GroupNodeData {
  id: string;
  label: string;

  // Style
  style?: 'default' | 'dashed' | 'solid' | 'none';
  color?: string;

  // State
  collapsed?: boolean;
  locked?: boolean;  // Prevent child dragging outside

  // Canvas
  canvas?: { x: number; y: number; width: number; height: number; };
}
```

---

## Appendix B: Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl/Cmd + S` | Save notebook |
| `Ctrl/Cmd + Z` | Undo |
| `Ctrl/Cmd + Shift + Z` | Redo |
| `Ctrl/Cmd + D` | Duplicate selected node |
| `Delete / Backspace` | Delete selected node |
| `Ctrl/Cmd + G` | Group selected nodes |
| `Ctrl/Cmd + Shift + G` | Ungroup |
| `Ctrl/Cmd + A` | Select all nodes |
| `Escape` | Deselect all |
| `Ctrl/Cmd + +` | Zoom in |
| `Ctrl/Cmd + -` | Zoom out |
| `Ctrl/Cmd + 0` | Fit view |
| `Space + Drag` | Pan canvas |
| `Ctrl/Cmd + Click` | Multi-select |
| `Ctrl/Cmd + E` | Toggle edit mode |
| `Ctrl/Cmd + 1` | Document view |
| `Ctrl/Cmd + 2` | Canvas view |
| `Ctrl/Cmd + 3` | Split view |

---

## Appendix C: Migration Checklist

### Pre-Migration (Phase 0)
- [ ] Fix ColumnReference bugs in line_chart.py
- [ ] Fix ColumnReference bugs in forecast_chart.py
- [ ] Fix ColumnReference bugs in base_renderer.py
- [ ] Create Exhibits/ folder with all exhibit types as markdown
- [ ] Create Data Sources/ folder structure
- [ ] Audit all existing notebooks
- [ ] Document custom Streamlit components
- [ ] List all Great Tables usages
- [ ] Identify Python-only rendering
- [ ] Set up VS Code workspace

### Phase 1 Checklist
- [ ] Vite + React + TypeScript initialized
- [ ] Tailwind + shadcn/ui configured
- [ ] FastAPI with CORS configured
- [ ] `/api/notebooks` CRUD working
- [ ] `/api/query` executing SQL (strings only!)
- [ ] `/api/exhibits` listing types from Exhibits/*.md
- [ ] Basic notebook tree rendering
- [ ] Document view rendering markdown
- [ ] Filter components functional (strings only!)
- [ ] Plotly charts rendering (strings only!)
- [ ] Tabulator tables rendering

### Phase 2 Checklist
- [ ] Markdown editor integrated
- [ ] YAML editor for properties
- [ ] Create notebook working
- [ ] Delete notebook working
- [ ] Autosave implemented
- [ ] Undo/redo functional
- [ ] Folder management working
- [ ] Search implemented
- [ ] Templates system working (from Exhibits/*.md)

### Phase 3 Checklist
- [ ] ReactFlow canvas rendering
- [ ] All node types implemented
- [ ] Edge drawing working
- [ ] Cross-filtering via edges
- [ ] Node resize working
- [ ] Group nodes working
- [ ] Position persistence working
- [ ] View toggle working
- [ ] Keyboard shortcuts implemented

### Phase 4 Checklist
- [ ] Click drill-down working
- [ ] Export to PNG/PDF working
- [ ] Map node type working
- [ ] Choropleth rendering
- [ ] Point maps rendering
- [ ] Performance optimized

### Phase 5 Checklist (Dead Code Removal)
- [ ] Delete `app/ui/` directory entirely
- [ ] Delete `app/ui/components/exhibits/` directory
- [ ] Delete `app/ui/components/markdown/` directory
- [ ] Delete `app/ui/state/` directory
- [ ] Delete `app/ui/callbacks/` directory
- [ ] Remove Streamlit from requirements.txt
- [ ] Update CLAUDE.md to remove Streamlit references
- [ ] Update all documentation

### Post-Migration
- [ ] All existing notebooks render correctly
- [ ] Feature parity verified
- [ ] Performance benchmarked
- [ ] Documentation updated
- [ ] Zero ColumnReference bugs in error logs

---

## Appendix D: Dead Code Deletion Script

```bash
#!/bin/bash
# scripts/maintenance/remove_streamlit_ui.sh
# Run this AFTER Phase 5 migration is complete

echo "Removing Streamlit UI code..."

# Remove entire UI directory
rm -rf app/ui/

# Remove Streamlit-specific components
rm -rf app/notebook/parsers/

# Remove old entry points
rm -f run_app.py
rm -f run_app.sh

# Update requirements
sed -i '/streamlit/d' requirements.txt
sed -i '/great_tables/d' requirements.txt  # Replaced by Tabulator

# Remove Streamlit config
rm -rf .streamlit/

echo "Streamlit UI removed. Total lines deleted: $(wc -l app/ui/**/*.py 2>/dev/null | tail -1 | awk '{print $1}')"
echo "Remember to update CLAUDE.md!"
```

---

## Appendix E: ExhibitLoader Implementation

```python
# config/exhibit_loader.py
"""
Load exhibit type definitions from Exhibits/*.md files.
"""
from pathlib import Path
from typing import Dict, List, Optional
import yaml
import frontmatter

class ExhibitLoader:
    """Load and validate exhibit type definitions."""

    def __init__(self, exhibits_path: Path):
        self.exhibits_path = exhibits_path
        self._cache: Dict[str, dict] = {}

    def list_types(self) -> List[dict]:
        """List all available exhibit types."""
        types = []
        for md_file in self.exhibits_path.rglob("*.md"):
            try:
                config = self._load_file(md_file)
                types.append({
                    "type": config.get("exhibit_type"),
                    "version": config.get("version"),
                    "description": config.get("description"),
                    "category": md_file.parent.name,
                })
            except Exception as e:
                continue
        return types

    def load_type(self, exhibit_type: str) -> Optional[dict]:
        """Load a specific exhibit type definition."""
        if exhibit_type in self._cache:
            return self._cache[exhibit_type]

        # Search for matching file
        for md_file in self.exhibits_path.rglob("*.md"):
            config = self._load_file(md_file)
            if config.get("exhibit_type") == exhibit_type:
                self._cache[exhibit_type] = config
                return config

        return None

    def validate_exhibit(self, exhibit_config: dict) -> List[str]:
        """Validate an exhibit config against its type schema."""
        exhibit_type = exhibit_config.get("type")
        type_def = self.load_type(exhibit_type)

        if not type_def:
            return [f"Unknown exhibit type: {exhibit_type}"]

        errors = []
        schema = type_def.get("schema", {})

        # Check required fields
        for field, field_def in schema.get("required", {}).items():
            if field not in exhibit_config:
                errors.append(f"Missing required field: {field}")

        return errors

    def _load_file(self, path: Path) -> dict:
        """Load a markdown file with YAML frontmatter."""
        post = frontmatter.load(path)
        return dict(post.metadata)
```

---

## Appendix F: API Endpoints Required by Components

Each React component needs these API endpoints:

| Component | Endpoints Required |
|-----------|-------------------|
| Sidebar | `GET /api/notebooks`, `GET /api/folders`, `GET /api/exhibits` |
| Document/Canvas View | `GET /api/notebooks/{id}` |
| Filters | `GET /api/dimensions/{name}`, `POST /api/query` |
| Exhibits | `POST /api/query`, `GET /api/exhibits/{type}` |
| Grid/Table | `POST /api/query` |
| Markdown Editor | `PUT /api/notebooks/{id}` |
| Notebook Creator | `POST /api/notebooks`, `GET /api/exhibits` (for templates) |
| Delete | `DELETE /api/notebooks/{id}` |
| Canvas Save | `PUT /api/notebooks/{id}/canvas` |
| Model Graph | `GET /api/models`, `GET /api/models/graph` |
| Export | `POST /api/export/png`, `POST /api/export/pdf` |
| Maps | `GET /api/geo/{region}`, `POST /api/query` |
| Data Sources Browser | `GET /api/datasources` |

---

## Appendix G: Exhaustive Migration Todo Sequence

**Purpose**: This appendix provides a complete, step-by-step checklist for migrating from Streamlit to React/ReactFlow. Each task is atomic and can be checked off. Follow in order—later tasks depend on earlier ones.

**For the Next Claude Session**: Work through this list sequentially. Each major section is a logical milestone. Don't skip ahead—dependencies matter.

---

### PHASE 0: PRE-MIGRATION STABILIZATION (Before Any React Work)

#### 0.1 Fix Critical ColumnReference Bugs in Current Codebase

These bugs cause runtime errors. Fix them to stabilize the current app before migration.

**0.1.1 Fix `line_chart.py`**
- [ ] Read `app/ui/components/exhibits/line_chart.py`
- [ ] Line 50: `x_col = exhibit.x_axis.dimension` gets ColumnReference
- [ ] Line 52: `x_col_name = extract_field_name(x_col)` extracts string
- [ ] Line 136: Change `pdf.groupby([x_col, ...])` → `pdf.groupby([x_col_name, ...])`
- [ ] Line 141: Change `pdf.sort_values(by=x_col)` → `pdf.sort_values(by=x_col_name)`
- [ ] Line 167: Change `x=df_subset[x_col]` → `x=df_subset[x_col_name]`
- [ ] Line 181: Change `x=pdf[x_col]` → `x=pdf[x_col_name]`
- [ ] Test line chart rendering with sample notebook

**0.1.2 Fix `forecast_chart.py`**
- [ ] Read `app/ui/components/exhibits/forecast_chart.py`
- [ ] Line 183: `x_col = self.exhibit.x_axis.dimension` gets ColumnReference
- [ ] Add after line 183: `x_col_name = extract_field_name(x_col)`
- [ ] Line 186: Change `self.pdf.sort_values(by=x_col)` → `self.pdf.sort_values(by=x_col_name)`
- [ ] Line 284: Change `x_col.replace('_', ' ')` → `x_col_name.replace('_', ' ')`
- [ ] Line 339: Change `x=df_subset[x_col]` → `x=df_subset[x_col_name]`
- [ ] Line 353: Change `x=df_measure[x_col]` → `x=df_measure[x_col_name]`
- [ ] Import `extract_field_name` from `base_renderer` at top of file
- [ ] Test forecast chart rendering

**0.1.3 Fix `base_renderer.py`**
- [ ] Read `app/ui/components/exhibits/base_renderer.py`
- [ ] Line 241: `x_col = self.exhibit.x_axis.dimension` gets ColumnReference
- [ ] Add after line 241: `x_col_name = extract_field_name(x_col)`
- [ ] Line 243: Change `x_col not in self.pdf.columns` → `x_col_name not in self.pdf.columns`
- [ ] Lines 276-280: Change all `{x_col}` → `{x_col_name}` in SQL string
- [ ] Test aggregation functionality

**0.1.4 Fix `__init__.py` Helper Functions**
- [ ] Read `app/ui/components/exhibits/__init__.py`
- [ ] Import `extract_field_name` from `base_renderer`
- [ ] `_get_scatter_chart_html` (line 197): Add `x_col = extract_field_name(exhibit.x_axis.dimension)`
- [ ] `_get_heatmap_html` (line 247): Add field name extraction
- [ ] `_get_dual_axis_chart_html` (line 284): Add field name extraction
- [ ] `_get_forecast_chart_html` (line 335): Add field name extraction
- [ ] `_get_weighted_aggregate_chart_html` (line 380): Add field name extraction
- [ ] Test all exhibit types in current UI

**0.1.5 Verify Current App Works**
- [ ] Run `python run_app.py`
- [ ] Open each notebook in `configs/notebooks/`
- [ ] Verify no ColumnReference errors in logs
- [ ] Document any remaining issues

---

#### 0.2 Create New Folder Structures

**0.2.1 Create Exhibits/ Structure**
- [ ] Create `Exhibits/` directory at repo root
- [ ] Create `Exhibits/Charts/` subdirectory
- [ ] Create `Exhibits/Tables/` subdirectory
- [ ] Create `Exhibits/Cards/` subdirectory
- [ ] Create `Exhibits/Maps/` subdirectory

**0.2.2 Create Data Sources/ Structure**
- [ ] Create `Data Sources/` directory at repo root
- [ ] Create `Data Sources/Endpoints/` subdirectory
- [ ] Create `Data Sources/Endpoints/Alpha Vantage/` subdirectory
- [ ] Create `Data Sources/Endpoints/Alpha Vantage/Prices/` subdirectory
- [ ] Create `Data Sources/Endpoints/Alpha Vantage/Fundamentals/` subdirectory
- [ ] Create `Data Sources/Endpoints/BLS/` subdirectory
- [ ] Create `Data Sources/Endpoints/Chicago/` subdirectory

**0.2.3 Rename domains/ to Domains/**
- [ ] Rename `domains/` → `Domains/`
- [ ] Update `config/domain_loader.py` to use new path
- [ ] Update any imports referencing `domains/`
- [ ] Test model loading still works

---

#### 0.3 Document Exhibit Types as Markdown

Create a markdown file for each exhibit type with YAML frontmatter schema.

**0.3.1 Charts**
- [ ] Create `Exhibits/Charts/Line Chart.md` with schema (see proposal for template)
- [ ] Create `Exhibits/Charts/Bar Chart.md` with schema
- [ ] Create `Exhibits/Charts/Scatter Chart.md` with schema
- [ ] Create `Exhibits/Charts/Dual Axis Chart.md` with schema
- [ ] Create `Exhibits/Charts/Forecast Chart.md` with schema
- [ ] Create `Exhibits/Charts/Heatmap.md` with schema

**0.3.2 Tables**
- [ ] Create `Exhibits/Tables/Data Table.md` with schema
- [ ] Create `Exhibits/Tables/Great Table.md` with schema (include column spanner config)

**0.3.3 Cards**
- [ ] Create `Exhibits/Cards/Metric Cards.md` with schema

**0.3.4 Maps (Future)**
- [ ] Create `Exhibits/Maps/Choropleth.md` with schema (placeholder)
- [ ] Create `Exhibits/Maps/Point Map.md` with schema (placeholder)

**0.3.5 Document Data Sources**
- [ ] Create `Data Sources/Endpoints/Alpha Vantage/Prices/Time Series Daily.md`
- [ ] Create `Data Sources/Endpoints/Alpha Vantage/Fundamentals/Income Statement.md`
- [ ] Create `Data Sources/Endpoints/Alpha Vantage/Fundamentals/Balance Sheet.md`
- [ ] Create `Data Sources/Endpoints/Alpha Vantage/Fundamentals/Cash Flow.md`
- [ ] Create `Data Sources/Endpoints/Alpha Vantage/Fundamentals/Earnings.md`
- [ ] Document any BLS endpoints in use
- [ ] Document any Chicago endpoints in use

---

#### 0.4 Create Config Loaders

**0.4.1 ExhibitLoader**
- [ ] Create `config/exhibit_loader.py`
- [ ] Implement `ExhibitLoader` class (see Appendix E for code)
- [ ] Add `list_types()` method
- [ ] Add `load_type(exhibit_type)` method
- [ ] Add `validate_exhibit(config)` method
- [ ] Write unit tests for ExhibitLoader
- [ ] Verify it can load all exhibit types from `Exhibits/`

**0.4.2 DataSourceLoader**
- [ ] Create `config/datasource_loader.py`
- [ ] Implement `DataSourceLoader` class (similar pattern)
- [ ] Add `list_sources()` method
- [ ] Add `load_source(provider, endpoint)` method
- [ ] Write unit tests

---

### PHASE 1: FASTAPI BACKEND FOUNDATION (Weeks 1-2)

#### 1.1 Project Setup

**1.1.1 Create API Directory Structure**
- [ ] Create `api/` directory at repo root
- [ ] Create `api/__init__.py`
- [ ] Create `api/main.py` (FastAPI app entry point)
- [ ] Create `api/routers/` directory
- [ ] Create `api/models/` directory (Pydantic models)
- [ ] Create `api/services/` directory

**1.1.2 Install Dependencies**
- [ ] Create `api/requirements.txt` with FastAPI deps
- [ ] Add: `fastapi>=0.109.0`
- [ ] Add: `uvicorn>=0.27.0`
- [ ] Add: `pydantic>=2.0`
- [ ] Add: `python-multipart`
- [ ] Add: `aiofiles`
- [ ] Install dependencies: `pip install -r api/requirements.txt`

**1.1.3 Create FastAPI App Skeleton**
- [ ] Create `api/main.py` with FastAPI app instance
- [ ] Add CORS middleware configuration
- [ ] Add health check endpoint: `GET /api/health`
- [ ] Test: `uvicorn api.main:app --reload --port 8000`
- [ ] Verify http://localhost:8000/docs shows Swagger UI

---

#### 1.2 Implement Core API Endpoints

**1.2.1 Notebooks Router**
- [ ] Create `api/routers/notebooks.py`
- [ ] Create `api/models/notebooks.py` with Pydantic models:
  - [ ] `NotebookBase`
  - [ ] `NotebookCreate`
  - [ ] `NotebookUpdate`
  - [ ] `NotebookResponse`
- [ ] Implement `GET /api/notebooks` - List all notebooks
- [ ] Implement `GET /api/notebooks/{id}` - Get notebook by ID
- [ ] Implement `POST /api/notebooks` - Create notebook
- [ ] Implement `PUT /api/notebooks/{id}` - Update notebook
- [ ] Implement `DELETE /api/notebooks/{id}` - Delete notebook
- [ ] Implement `POST /api/notebooks/{id}/duplicate` - Duplicate notebook
- [ ] Register router in `main.py`
- [ ] Test all endpoints via Swagger UI

**1.2.2 Folders Router**
- [ ] Create `api/routers/folders.py`
- [ ] Create `api/models/folders.py` with Pydantic models
- [ ] Implement `GET /api/folders` - List folder tree
- [ ] Implement `POST /api/folders` - Create folder
- [ ] Implement `PUT /api/folders/{id}` - Rename/move folder
- [ ] Implement `DELETE /api/folders/{id}` - Delete folder
- [ ] Register router in `main.py`
- [ ] Test all endpoints

**1.2.3 Query Router (CRITICAL: Strings Only!)**
- [ ] Create `api/routers/queries.py`
- [ ] Create `api/models/queries.py` with:
  - [ ] `QueryRequest` (model, table, columns: List[str], filters)
  - [ ] `QueryResponse` (data, columns, row_count, execution_time_ms)
  - [ ] `Filter` (column: str, operator, value)
- [ ] Implement `POST /api/query` - Execute query
  - [ ] Accept ONLY string column names (never ColumnReference)
  - [ ] Use UniversalSession.query_model()
  - [ ] Return JSON data
- [ ] Implement `POST /api/query/validate` - Validate SQL
- [ ] Register router in `main.py`
- [ ] Test query execution

**1.2.4 Dimensions Router**
- [ ] Create `api/routers/dimensions.py`
- [ ] Create `api/models/dimensions.py` with `DimensionResponse`
- [ ] Implement `GET /api/dimensions` - List all dimensions
- [ ] Implement `GET /api/dimensions/{name}` - Get dimension values
- [ ] Register router in `main.py`
- [ ] Test endpoints

**1.2.5 Exhibits Router (NEW)**
- [ ] Create `api/routers/exhibits.py`
- [ ] Create `api/models/exhibits.py` with `ExhibitTypeResponse`
- [ ] Implement `GET /api/exhibits` - List exhibit types from `Exhibits/*.md`
- [ ] Implement `GET /api/exhibits/{type}` - Get exhibit type schema
- [ ] Use `ExhibitLoader` from config/
- [ ] Register router in `main.py`
- [ ] Test endpoints

**1.2.6 Data Sources Router (NEW)**
- [ ] Create `api/routers/datasources.py`
- [ ] Implement `GET /api/datasources` - List data sources
- [ ] Implement `GET /api/datasources/{provider}/{endpoint}` - Get endpoint config
- [ ] Use `DataSourceLoader` from config/
- [ ] Register router in `main.py`
- [ ] Test endpoints

**1.2.7 Canvas Router**
- [ ] Create `api/routers/canvas.py`
- [ ] Implement `GET /api/notebooks/{id}/canvas` - Get canvas state
- [ ] Implement `PUT /api/notebooks/{id}/canvas` - Save canvas state
- [ ] Register router in `main.py`
- [ ] Test endpoints

---

#### 1.3 API Integration Tests

- [ ] Create `tests/api/` directory
- [ ] Create `tests/api/test_notebooks.py`
- [ ] Create `tests/api/test_queries.py`
- [ ] Create `tests/api/test_exhibits.py`
- [ ] Run all API tests: `pytest tests/api/`
- [ ] Verify 100% endpoint coverage

---

### PHASE 2: REACT FRONTEND FOUNDATION (Weeks 3-4)

#### 2.1 Project Setup

**2.1.1 Initialize React Project**
- [ ] Create `frontend/` directory at repo root
- [ ] Initialize with Vite: `pnpm create vite@latest . --template react-ts`
- [ ] Install dependencies: `pnpm install`
- [ ] Verify dev server works: `pnpm dev`

**2.1.2 Configure Tailwind CSS**
- [ ] Install Tailwind: `pnpm add -D tailwindcss postcss autoprefixer`
- [ ] Initialize Tailwind: `npx tailwindcss init -p`
- [ ] Configure `tailwind.config.js` content paths
- [ ] Add Tailwind directives to `src/index.css`
- [ ] Verify Tailwind classes work

**2.1.3 Install shadcn/ui**
- [ ] Initialize shadcn: `npx shadcn-ui@latest init`
- [ ] Configure components.json
- [ ] Add Button component: `npx shadcn-ui@latest add button`
- [ ] Add Input component: `npx shadcn-ui@latest add input`
- [ ] Add Select component: `npx shadcn-ui@latest add select`
- [ ] Add Dialog component: `npx shadcn-ui@latest add dialog`
- [ ] Add Tabs component: `npx shadcn-ui@latest add tabs`
- [ ] Add Collapsible component: `npx shadcn-ui@latest add collapsible`
- [ ] Verify components render correctly

**2.1.4 Install Core Dependencies**
- [ ] Install ReactFlow: `pnpm add reactflow`
- [ ] Install Plotly: `pnpm add react-plotly.js plotly.js`
- [ ] Install Tabulator: `pnpm add react-tabulator`
- [ ] Install Zustand: `pnpm add zustand`
- [ ] Install React Query: `pnpm add @tanstack/react-query`
- [ ] Install React Router: `pnpm add react-router-dom`
- [ ] Install React Markdown: `pnpm add react-markdown remark-gfm`
- [ ] Install Lucide icons: `pnpm add lucide-react`
- [ ] Install Axios: `pnpm add axios`

**2.1.5 Configure API Client**
- [ ] Create `frontend/src/services/api.ts`
- [ ] Configure Axios instance with base URL (http://localhost:8000/api)
- [ ] Add request/response interceptors
- [ ] Create typed API functions for each endpoint

---

#### 2.2 Create Directory Structure

- [ ] Create `frontend/src/components/`
- [ ] Create `frontend/src/components/canvas/`
- [ ] Create `frontend/src/components/nodes/`
- [ ] Create `frontend/src/components/edges/`
- [ ] Create `frontend/src/components/panels/`
- [ ] Create `frontend/src/components/editors/`
- [ ] Create `frontend/src/components/ui/` (shadcn components go here)
- [ ] Create `frontend/src/views/`
- [ ] Create `frontend/src/hooks/`
- [ ] Create `frontend/src/stores/`
- [ ] Create `frontend/src/types/`
- [ ] Create `frontend/src/utils/`

---

#### 2.3 Create Type Definitions

**2.3.1 Node Types**
- [ ] Create `frontend/src/types/nodes.ts`
- [ ] Define `NodeType` union type
- [ ] Define `BaseNodeData` interface
- [ ] Define `ExhibitNodeData` interface (all strings!)
- [ ] Define `FilterNodeData` interface (all strings!)
- [ ] Define `GridNodeData` interface (all strings!)
- [ ] Define `MarkdownNodeData` interface
- [ ] Define `GroupNodeData` interface

**2.3.2 Edge Types**
- [ ] Create `frontend/src/types/edges.ts`
- [ ] Define `EdgeType` union type
- [ ] Define `DataFlowEdgeData` interface
- [ ] Define `InsightEdgeData` interface

**2.3.3 API Types**
- [ ] Create `frontend/src/types/api.ts`
- [ ] Define `QueryRequest` interface
- [ ] Define `QueryResponse` interface
- [ ] Define `Filter` interface
- [ ] Define `Notebook` interface
- [ ] Define `ExhibitType` interface
- [ ] Define `Dimension` interface

---

#### 2.4 Create State Management (Zustand Stores)

**2.4.1 App Store**
- [ ] Create `frontend/src/stores/appStore.ts`
- [ ] Add `currentNotebook` state
- [ ] Add `editMode` state
- [ ] Add `theme` state (light/dark)
- [ ] Add setter actions

**2.4.2 Filter Store**
- [ ] Create `frontend/src/stores/filterStore.ts`
- [ ] Add `filterValues` map (filterId → value)
- [ ] Add `setFilterValue(id, value)` action
- [ ] Add `clearFilters()` action
- [ ] Add `getActiveFilters()` selector

**2.4.3 Canvas Store**
- [ ] Create `frontend/src/stores/canvasStore.ts`
- [ ] Add `nodes` state
- [ ] Add `edges` state
- [ ] Add `selectedNodes` state
- [ ] Add `history` and `historyIndex` for undo/redo
- [ ] Add `setNodes`, `setEdges` actions
- [ ] Add `addNode`, `updateNode`, `deleteNode` actions
- [ ] Add `addEdge`, `deleteEdge` actions
- [ ] Add `undo`, `redo` actions
- [ ] Add `loadCanvas`, `saveCanvas` async actions

---

#### 2.5 Create Core Views

**2.5.1 App Shell**
- [ ] Create `frontend/src/App.tsx` with layout structure
- [ ] Add React Router configuration
- [ ] Add sidebar + main content layout
- [ ] Add header with navigation
- [ ] Add theme provider

**2.5.2 Sidebar Component**
- [ ] Create `frontend/src/components/Sidebar.tsx`
- [ ] Add notebook tree view with folders
- [ ] Add expand/collapse for folders
- [ ] Add notebook selection handler
- [ ] Add "New Notebook" button
- [ ] Add Exhibits browser section
- [ ] Add Favorites section
- [ ] Add Recent section
- [ ] Fetch notebooks from `GET /api/notebooks`

**2.5.3 Document View**
- [ ] Create `frontend/src/views/DocumentView.tsx`
- [ ] Render markdown content using react-markdown
- [ ] Parse and render $filter$ blocks
- [ ] Parse and render $exhibit$ blocks
- [ ] Parse and render $grid$ blocks
- [ ] Implement linear scrolling layout

**2.5.4 Canvas View (Initial)**
- [ ] Create `frontend/src/views/CanvasView.tsx`
- [ ] Initialize ReactFlow
- [ ] Add background grid
- [ ] Add minimap
- [ ] Add controls (zoom, fit)
- [ ] Render nodes from canvas state

**2.5.5 Split View**
- [ ] Create `frontend/src/views/SplitView.tsx`
- [ ] Add resizable split pane
- [ ] Show Document on left, Canvas on right
- [ ] Sync scroll/selection between views

**2.5.6 View Switcher**
- [ ] Add view toggle buttons in header (Doc / Canvas / Split)
- [ ] Store view preference in app store
- [ ] Route to correct view component

---

### PHASE 3: REACT COMPONENTS - FILTERS & EXHIBITS (Weeks 5-6)

#### 3.1 Filter Components

**3.1.1 Select Filter**
- [ ] Create `frontend/src/components/filters/SelectFilter.tsx`
- [ ] Fetch options from `GET /api/dimensions/{name}`
- [ ] Use shadcn Select component
- [ ] Call `setFilterValue` on change
- [ ] Style to match design

**3.1.2 MultiSelect Filter**
- [ ] Create `frontend/src/components/filters/MultiSelectFilter.tsx`
- [ ] Support multiple selection
- [ ] Add "Select All" / "Clear All"
- [ ] Show selected items as chips

**3.1.3 Date Range Filter**
- [ ] Create `frontend/src/components/filters/DateRangeFilter.tsx`
- [ ] Add start/end date pickers
- [ ] Add preset options (YTD, Last 30 days, etc.)

**3.1.4 Slider Filter**
- [ ] Create `frontend/src/components/filters/SliderFilter.tsx`
- [ ] Support single value and range modes
- [ ] Show min/max labels

**3.1.5 Filter Factory**
- [ ] Create `frontend/src/components/filters/FilterFactory.tsx`
- [ ] Return correct filter component based on type
- [ ] Accept uniform props interface

**3.1.6 Active Filters Display**
- [ ] Create `frontend/src/components/filters/ActiveFilters.tsx`
- [ ] Show chips for all active filters
- [ ] Click chip to remove filter
- [ ] Add "Clear All" button

---

#### 3.2 Exhibit Components (Charts)

**3.2.1 Line Chart**
- [ ] Create `frontend/src/components/exhibits/LineChart.tsx`
- [ ] Accept data, x, y, color props (ALL STRINGS!)
- [ ] Use Plotly Scatter with mode='lines+markers'
- [ ] Support multiple y series
- [ ] Add hover tooltips
- [ ] Support theme (light/dark)

**3.2.2 Bar Chart**
- [ ] Create `frontend/src/components/exhibits/BarChart.tsx`
- [ ] Support vertical and horizontal
- [ ] Support stacked mode
- [ ] Support grouped mode

**3.2.3 Scatter Chart**
- [ ] Create `frontend/src/components/exhibits/ScatterChart.tsx`
- [ ] Support size-by dimension
- [ ] Support color-by dimension

**3.2.4 Dual Axis Chart**
- [ ] Create `frontend/src/components/exhibits/DualAxisChart.tsx`
- [ ] Use Plotly subplots
- [ ] Primary Y on left, secondary on right

**3.2.5 Forecast Chart**
- [ ] Create `frontend/src/components/exhibits/ForecastChart.tsx`
- [ ] Show actual line (solid)
- [ ] Show forecast line (dashed)
- [ ] Show confidence intervals (shaded area)

**3.2.6 Heatmap**
- [ ] Create `frontend/src/components/exhibits/Heatmap.tsx`
- [ ] Use Plotly imshow or heatmap
- [ ] Support color scales

**3.2.7 Exhibit Factory**
- [ ] Create `frontend/src/components/exhibits/ExhibitFactory.tsx`
- [ ] Return correct exhibit component based on type
- [ ] Load exhibit schema from `GET /api/exhibits/{type}`

---

#### 3.3 Table Components

**3.3.1 Data Table**
- [ ] Create `frontend/src/components/tables/DataTable.tsx`
- [ ] Use react-tabulator
- [ ] Support sorting
- [ ] Support filtering
- [ ] Support pagination

**3.3.2 Great Table**
- [ ] Create `frontend/src/components/tables/GreatTable.tsx`
- [ ] Support column spanners/groups
- [ ] Support currency formatting
- [ ] Support percent formatting
- [ ] Support conditional coloring
- [ ] Support footer calculations
- [ ] Support row grouping

---

#### 3.4 Other Exhibits

**3.4.1 Metric Cards**
- [ ] Create `frontend/src/components/exhibits/MetricCards.tsx`
- [ ] Use Plotly Indicator
- [ ] Support delta/comparison
- [ ] Support multiple metrics in grid

---

#### 3.5 Layout Components

> **Note**: These are React layout primitives used by both Document View and Canvas View.
> ReactFlow provides canvas positioning, but NOT internal layout within nodes.

**3.5.1 GridLayout Component**
- [ ] Create `frontend/src/components/layout/GridLayout.tsx`
- [ ] Accept `columns` prop (number or template string)
- [ ] Accept `rows` prop (number or template string)
- [ ] Accept `gap` prop for spacing
- [ ] Accept `cells` prop with cell definitions (row, col, span, content)
- [ ] Use CSS Grid for layout
- [ ] Support responsive breakpoints

**3.5.2 CollapsibleSection Component**
- [ ] Create `frontend/src/components/layout/CollapsibleSection.tsx`
- [ ] Accept `title` and `defaultExpanded` props
- [ ] Add expand/collapse toggle button
- [ ] Animate height transition
- [ ] Preserve child state when collapsed

**3.5.3 TabsContainer Component**
- [ ] Create `frontend/src/components/layout/TabsContainer.tsx`
- [ ] Use shadcn Tabs
- [ ] Accept tabs as array of {label, content} objects
- [ ] Support controlled and uncontrolled modes

**3.5.4 SplitPane Component**
- [ ] Create `frontend/src/components/layout/SplitPane.tsx`
- [ ] Support horizontal and vertical splits
- [ ] Add draggable divider
- [ ] Persist split ratio in state

---

### PHASE 4: REACT COMPONENTS - CANVAS NODES (Weeks 7-9)

#### 4.1 Base Node Infrastructure

**4.1.1 Node Wrapper**
- [ ] Create `frontend/src/components/nodes/NodeWrapper.tsx`
- [ ] Add title bar with label
- [ ] Add resize handles
- [ ] Add connection handles (source/target)
- [ ] Add selection styling

**4.1.2 Register Custom Nodes**
- [ ] Update `CanvasView.tsx` with nodeTypes map
- [ ] Register all custom node types

---

#### 4.2 Implement Node Types

**4.2.1 ExhibitNode**
- [ ] Create `frontend/src/components/nodes/ExhibitNode.tsx`
- [ ] Wrap ExhibitFactory
- [ ] Fetch data via `POST /api/query`
- [ ] Apply filters from connected filter nodes
- [ ] Add loading state
- [ ] Add error state

**4.2.2 FilterNode**
- [ ] Create `frontend/src/components/nodes/FilterNode.tsx`
- [ ] Wrap FilterFactory
- [ ] Add output handle for connections
- [ ] Compact styling for canvas

**4.2.3 GridNode**
- [ ] Create `frontend/src/components/nodes/GridNode.tsx`
- [ ] Wrap GridLayout component (for `$grid${}` syntax)
- [ ] Support nested exhibits within grid cells
- [ ] Add resize handles for node dimensions
- [ ] Grid cells auto-adjust within node bounds

**4.2.4 TableNode**
- [ ] Create `frontend/src/components/nodes/TableNode.tsx`
- [ ] Wrap DataTable or GreatTable
- [ ] Add scroll within node bounds

**4.2.5 MarkdownNode**
- [ ] Create `frontend/src/components/nodes/MarkdownNode.tsx`
- [ ] Render markdown content
- [ ] Support inline editing on double-click

**4.2.6 GroupNode**
- [ ] Create `frontend/src/components/nodes/GroupNode.tsx`
- [ ] Use @reactflow/node-resizer
- [ ] Support collapse/expand
- [ ] Child nodes use `parentId` and `extent: 'parent'`
- [ ] Dashed border styling

**4.2.7 NoteNode**
- [ ] Create `frontend/src/components/nodes/NoteNode.tsx`
- [ ] Sticky note styling
- [ ] Editable text
- [ ] Color options

---

#### 4.3 Implement Edge Types

**4.3.1 DataFlowEdge**
- [ ] Create `frontend/src/components/edges/DataFlowEdge.tsx`
- [ ] Solid line style
- [ ] Arrow head
- [ ] Animated option

**4.3.2 InsightEdge**
- [ ] Create `frontend/src/components/edges/InsightEdge.tsx`
- [ ] Dashed line style
- [ ] Editable label
- [ ] Color picker

**4.3.3 Register Custom Edges**
- [ ] Update `CanvasView.tsx` with edgeTypes map

---

#### 4.4 Canvas Interactions

**4.4.1 Node Operations**
- [ ] Implement drag to reposition
- [ ] Implement resize via handles
- [ ] Implement multi-select with Ctrl+Click
- [ ] Implement delete with Delete key
- [ ] Implement duplicate with Ctrl+D

**4.4.2 Edge Operations**
- [ ] Implement edge creation by dragging from handle
- [ ] Implement edge deletion
- [ ] Implement edge label editing

**4.4.3 Canvas Operations**
- [ ] Implement pan with space+drag
- [ ] Implement zoom with scroll
- [ ] Implement fit view
- [ ] Implement minimap navigation

---

### PHASE 5: MARKDOWN PARSING INTEGRATION (Weeks 10-11)

#### 5.1 Markdown Parser

**5.1.1 Create TypeScript Parser**
- [ ] Create `frontend/src/utils/markdownParser.ts`
- [ ] Parse YAML frontmatter
- [ ] Parse $filter${...} blocks
- [ ] Parse $exhibit${...} blocks
- [ ] Parse $grid${...} blocks
- [ ] Parse $insight${...} blocks (for edges)
- [ ] Return structured AST

**5.1.2 ColumnReference Resolution**
- [ ] Create `frontend/src/utils/resolveColumnRef.ts`
- [ ] Input: `"stocks.fact_stock_prices.trade_date"`
- [ ] Output: `{ model: "stocks", table: "fact_stock_prices", column: "trade_date" }`
- [ ] Always return strings, never objects

**5.1.3 Markdown to Nodes Converter**
- [ ] Create `frontend/src/utils/markdownToNodes.ts`
- [ ] Convert parsed markdown to ReactFlow nodes
- [ ] Handle canvas positions from config
- [ ] Auto-layout if no positions specified (use dagre)
- [ ] Create edges from `connects_from` properties

---

#### 5.2 Auto-Layout

**5.2.1 Install Dagre**
- [ ] Install: `pnpm add dagre @types/dagre`

**5.2.2 Implement Auto-Layout**
- [ ] Create `frontend/src/utils/autoLayout.ts`
- [ ] Use dagre for node positioning
- [ ] Support horizontal and vertical layouts
- [ ] Preserve manual positions when set

---

#### 5.3 Position Persistence

**5.3.1 Canvas State to Markdown**
- [ ] Create `frontend/src/utils/nodesToMarkdown.ts`
- [ ] Convert nodes back to markdown with canvas positions
- [ ] Preserve non-exhibit content

**5.3.2 Save/Load Integration**
- [ ] On canvas change, update markdown with new positions
- [ ] On load, parse markdown and create nodes
- [ ] Use `PUT /api/notebooks/{id}/canvas` for persistence

---

### PHASE 6: EDITING & MANAGEMENT (Weeks 12-13)

#### 6.1 Editors

**6.1.1 Install Monaco Editor**
- [ ] Install: `pnpm add @monaco-editor/react`

**6.1.2 YAML Editor**
- [ ] Create `frontend/src/components/editors/YamlEditor.tsx`
- [ ] Use Monaco with YAML language
- [ ] Add syntax highlighting
- [ ] Add validation

**6.1.3 Markdown Editor**
- [ ] Install Milkdown or BlockNote
- [ ] Create `frontend/src/components/editors/MarkdownEditor.tsx`
- [ ] WYSIWYG mode
- [ ] Source mode toggle

**6.1.4 Properties Panel**
- [ ] Create `frontend/src/components/panels/PropertiesPanel.tsx`
- [ ] Show when node selected
- [ ] Edit exhibit config
- [ ] Edit filter config
- [ ] Validate against exhibit type schema

---

#### 6.2 Notebook Management

**6.2.1 Create Notebook Dialog**
- [ ] Create `frontend/src/components/dialogs/NewNotebookDialog.tsx`
- [ ] Title input
- [ ] Folder selection
- [ ] Template selection (from Exhibits/*.md examples)
- [ ] Create button calls `POST /api/notebooks`

**6.2.2 Delete Confirmation**
- [ ] Create `frontend/src/components/dialogs/DeleteDialog.tsx`
- [ ] Confirm before delete
- [ ] Call `DELETE /api/notebooks/{id}`

**6.2.3 Rename Dialog**
- [ ] Create `frontend/src/components/dialogs/RenameDialog.tsx`
- [ ] Edit title
- [ ] Call `PUT /api/notebooks/{id}`

**6.2.4 Duplicate**
- [ ] Add duplicate option to context menu
- [ ] Call `POST /api/notebooks/{id}/duplicate`

---

#### 6.3 Undo/Redo System

**6.3.1 History Management**
- [ ] Implement history stack in canvasStore
- [ ] Push state on every change
- [ ] Limit history size (e.g., 50 entries)

**6.3.2 Keyboard Shortcuts**
- [ ] Implement Ctrl+Z for undo
- [ ] Implement Ctrl+Shift+Z for redo
- [ ] Add undo/redo buttons to toolbar

---

#### 6.4 Autosave

**6.4.1 Implement Autosave**
- [ ] Create debounced save function (2 second delay)
- [ ] Call `PUT /api/notebooks/{id}` on change
- [ ] Show save indicator in header

---

### PHASE 7: KEYBOARD SHORTCUTS & UX POLISH (Week 14)

#### 7.1 Keyboard Shortcuts

- [ ] Implement `Ctrl+S` - Save
- [ ] Implement `Ctrl+Z` - Undo
- [ ] Implement `Ctrl+Shift+Z` - Redo
- [ ] Implement `Ctrl+D` - Duplicate node
- [ ] Implement `Delete` - Delete node
- [ ] Implement `Ctrl+G` - Group selected
- [ ] Implement `Ctrl+Shift+G` - Ungroup
- [ ] Implement `Ctrl+A` - Select all
- [ ] Implement `Escape` - Deselect
- [ ] Implement `Ctrl++` - Zoom in
- [ ] Implement `Ctrl+-` - Zoom out
- [ ] Implement `Ctrl+0` - Fit view
- [ ] Implement `Ctrl+1` - Document view
- [ ] Implement `Ctrl+2` - Canvas view
- [ ] Implement `Ctrl+3` - Split view

---

#### 7.2 Context Menus

**7.2.1 Node Context Menu**
- [ ] Create right-click menu for nodes
- [ ] Add: Edit, Duplicate, Delete, Group
- [ ] Add: Bring to Front, Send to Back

**7.2.2 Canvas Context Menu**
- [ ] Create right-click menu for canvas background
- [ ] Add: Add Filter, Add Exhibit, Add Note
- [ ] Add: Paste, Select All

**7.2.3 Edge Context Menu**
- [ ] Create right-click menu for edges
- [ ] Add: Edit Label, Change Style, Delete

---

#### 7.3 Search

**7.3.1 Search Component**
- [ ] Create `frontend/src/components/Search.tsx`
- [ ] Search notebooks by title
- [ ] Search content
- [ ] Show results with highlights
- [ ] Navigate to result on click

---

### PHASE 8: EXPORT & ADVANCED FEATURES (Weeks 15-17)

#### 8.1 Export Functionality

**8.1.1 Export Router (Backend)**
- [ ] Create `api/routers/export.py`
- [ ] Implement `POST /api/export/png`
- [ ] Implement `POST /api/export/pdf`
- [ ] Implement `POST /api/export/data` (CSV/Excel)

**8.1.2 Export Dialog (Frontend)**
- [ ] Create `frontend/src/components/dialogs/ExportDialog.tsx`
- [ ] PNG export option
- [ ] PDF export option
- [ ] Data export option (CSV, Excel)
- [ ] Call export API and download file

---

#### 8.2 Maps (Future Enhancement)

**8.2.1 Install Map Dependencies**
- [ ] Install: `pnpm add react-map-gl mapbox-gl`
- [ ] Install: `pnpm add @deck.gl/core @deck.gl/layers @deck.gl/react`

**8.2.2 Choropleth Map**
- [ ] Create `frontend/src/components/exhibits/ChoroplethMap.tsx`
- [ ] Support US states, counties, countries
- [ ] Color by value

**8.2.3 Point Map**
- [ ] Create `frontend/src/components/exhibits/PointMap.tsx`
- [ ] Support markers
- [ ] Support size-by and color-by

**8.2.4 MapNode**
- [ ] Create `frontend/src/components/nodes/MapNode.tsx`
- [ ] Wrap map components
- [ ] Fetch geo data via API

---

### PHASE 9: STREAMLIT DEPRECATION & CLEANUP (Week 18)

#### 9.1 Verify Feature Parity

- [ ] Create feature comparison checklist
- [ ] Test every notebook renders correctly in React
- [ ] Test all filter types work
- [ ] Test all exhibit types work
- [ ] Test create/edit/delete notebooks
- [ ] Test canvas positioning
- [ ] Test undo/redo
- [ ] Test autosave
- [ ] Test keyboard shortcuts
- [ ] Document any missing features

---

#### 9.2 Delete Streamlit Code

**9.2.1 Delete UI Directory**
- [ ] Delete `app/ui/notebook_app_duckdb.py`
- [ ] Delete `app/ui/components/notebook_view.py`
- [ ] Delete `app/ui/components/sidebar.py`
- [ ] Delete `app/ui/components/model_graph_viewer.py`
- [ ] Delete `app/ui/components/filters.py`
- [ ] Delete `app/ui/components/dynamic_filters.py`
- [ ] Delete `app/ui/components/active_filters_display.py`
- [ ] Delete `app/ui/components/yaml_editor.py`
- [ ] Delete `app/ui/components/notebook_creator.py`
- [ ] Delete `app/ui/components/theme.py`
- [ ] Delete `app/ui/components/toggle_container.py`
- [ ] Delete `app/ui/state/` directory
- [ ] Delete `app/ui/callbacks/` directory

**9.2.2 Delete Exhibit Renderers**
- [ ] Delete `app/ui/components/exhibits/__init__.py`
- [ ] Delete `app/ui/components/exhibits/bar_chart.py`
- [ ] Delete `app/ui/components/exhibits/line_chart.py`
- [ ] Delete `app/ui/components/exhibits/forecast_chart.py`
- [ ] Delete `app/ui/components/exhibits/great_table.py`
- [ ] Delete `app/ui/components/exhibits/data_table.py`
- [ ] Delete `app/ui/components/exhibits/metric_cards.py`
- [ ] Delete `app/ui/components/exhibits/weighted_aggregate_chart.py`
- [ ] Delete `app/ui/components/exhibits/dimension_selector.py`
- [ ] Delete `app/ui/components/exhibits/measure_selector.py`
- [ ] Delete `app/ui/components/exhibits/click_events.py`
- [ ] Delete `app/ui/components/exhibits/base_renderer.py`
- [ ] Delete `app/ui/components/exhibits/` directory

**9.2.3 Delete Markdown Renderers**
- [ ] Delete `app/ui/components/markdown/renderer.py`
- [ ] Delete `app/ui/components/markdown/parser.py`
- [ ] Delete `app/ui/components/markdown/styles.py`
- [ ] Delete `app/ui/components/markdown/utils.py`
- [ ] Delete `app/ui/components/markdown/grid_renderer.py`
- [ ] Delete `app/ui/components/markdown/flat_renderer.py`
- [ ] Delete `app/ui/components/markdown/toggle_container.py`
- [ ] Delete `app/ui/components/markdown/blocks/` directory
- [ ] Delete `app/ui/components/markdown/editors/` directory
- [ ] Delete `app/ui/components/markdown/` directory

**9.2.4 Delete Entry Points**
- [ ] Delete `run_app.py`
- [ ] Delete `run_app.sh`
- [ ] Delete `.streamlit/` directory

**9.2.5 Clean Requirements**
- [ ] Remove `streamlit` from `requirements.txt`
- [ ] Remove `great_tables` from `requirements.txt` (replaced by Tabulator)
- [ ] Remove any other Streamlit-specific deps

---

#### 9.3 Update Documentation

**9.3.1 Update CLAUDE.md**
- [ ] Remove all Streamlit references
- [ ] Update architecture diagram
- [ ] Update "Running the App" section
- [ ] Update file structure
- [ ] Add React/FastAPI sections

**9.3.2 Update README**
- [ ] Update installation instructions
- [ ] Update running instructions
- [ ] Update architecture description

**9.3.3 Update Other Docs**
- [ ] Update `QUICKSTART.md`
- [ ] Update `RUNNING.md`
- [ ] Archive this proposal as "Completed"

---

#### 9.4 Final Verification

- [ ] Run full test suite
- [ ] Verify zero ColumnReference errors in logs
- [ ] Verify all notebooks load
- [ ] Performance benchmark (page load < 1s)
- [ ] Bundle size check (< 500KB gzipped)
- [ ] Create release notes

---

### PHASE 10: POST-MIGRATION ENHANCEMENTS (Optional, Weeks 19-20)

#### 10.1 Collaboration Features

- [ ] Add user authentication
- [ ] Add share links (view-only, edit)
- [ ] Add comments on nodes
- [ ] Add real-time cursors (WebSocket)
- [ ] Add permission system

#### 10.2 Additional Enhancements

- [ ] Add version history for notebooks
- [ ] Add templates library
- [ ] Add embed code generation
- [ ] Add scheduled refresh
- [ ] Add alerts/notifications

---

### SUMMARY: Key Milestones

| Milestone | Phase | Description |
|-----------|-------|-------------|
| **M0** | Phase 0 | Current app stabilized, no ColumnReference bugs |
| **M1** | Phase 1 | FastAPI backend complete, all endpoints working |
| **M2** | Phase 2 | React shell renders, can browse notebooks |
| **M3** | Phase 3 | All filters and exhibits render in React |
| **M4** | Phase 4 | Canvas with all node types working |
| **M5** | Phase 5 | Markdown ↔ Canvas bidirectional sync |
| **M6** | Phase 6 | Full CRUD, editing, undo/redo |
| **M7** | Phase 7 | Keyboard shortcuts, polish complete |
| **M8** | Phase 8 | Export and maps working |
| **M9** | Phase 9 | Streamlit code deleted, migration complete |
| **M10** | Phase 10 | Collaboration features (optional) |

---

### CRITICAL INVARIANTS (Never Violate These)

1. **ColumnReference → String at Parse Time**: Never pass ColumnReference objects to UI components. Always resolve to strings in the parser/API layer.

2. **API Contract Uses Strings**: All `POST /api/query` requests use string column names. No objects.

3. **No Direct DuckDB in Frontend**: All data access goes through FastAPI. No direct database connections from React.

4. **Canvas State Source of Truth**: The markdown file is the source of truth. Canvas positions are persisted back to markdown.

5. **Delete Before Adding**: When migrating a component, delete the old Streamlit version AFTER the React version is complete and tested, not before.

6. **Test at Each Phase**: Don't proceed to the next phase until all tests pass for the current phase.

---

**END OF EXHAUSTIVE TODO SEQUENCE**
