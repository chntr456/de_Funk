# Proposal 014: Obsidian Canvas Integration

**Status**: Approved
**Author**: Claude (with user direction)
**Date**: 2026-01-26
**Priority**: High
**Estimated Effort**: 6 weeks

---

## Executive Summary

This proposal describes integrating de_Funk's data visualization capabilities into **Obsidian** using its Canvas feature and a custom plugin. The solution provides full interactivity (live filters, drill-down, real-time queries) while keeping users in the familiar Obsidian environment.

### Key Decisions Made

1. **Full interactivity** - Live filters, drill-down, real-time queries
2. **Obsidian plugin approach** - Custom code block processors render inline
3. **Dual rendering** - Same components work in BOTH markdown notes AND Canvas
4. **Code block syntax** - Use ` ```exhibit `, ` ```metric ` for content blocks (Obsidian standard)
5. **Frontmatter filters** - Page/canvas filters defined in YAML frontmatter properties
6. **Per-note/canvas scope** - Each note has its OWN independent filter set (NOT global)
7. **Sidebar reflects frontmatter** - Sidebar panel shows filters defined in that note's properties
8. **NO folder context** - Removing `.filter_context.yaml` pattern entirely
9. **Dynamic exhibit selectors** - Users can switch measures and dimensions at runtime
10. **Domain model references** - Exhibits reference domain measures/dimensions, not raw columns
11. **3-level Canvas hierarchy** - Global (canvas) → Container (group) → Exhibit filters

---

## Table of Contents

1. [Background & Motivation](#background--motivation)
2. [Architecture Overview](#architecture-overview)
3. [Syntax Specification](#syntax-specification)
4. [Filter System](#filter-system)
5. [Exhibit System](#exhibit-system)
6. [Backend API](#backend-api)
7. [Obsidian Plugin Structure](#obsidian-plugin-structure)
8. [Implementation Phases](#implementation-phases)
9. [File Changes Required](#file-changes-required)
10. [Migration Guide](#migration-guide)
11. [Testing & Verification](#testing--verification)

---

## Background & Motivation

### Why Obsidian Instead of Custom React UI?

The original proposal (013) described building a custom React + ReactFlow application. This proposal adapts that concept to use Obsidian for several reasons:

| Factor | Custom React | Obsidian Plugin |
|--------|--------------|-----------------|
| Development effort | 15-20 weeks | 6 weeks |
| User familiarity | New interface to learn | Existing Obsidian skills |
| Markdown support | Build from scratch | Native |
| Canvas/whiteboard | ReactFlow integration | Built-in Canvas |
| Plugin ecosystem | None | Dataview, Charts, etc. |
| Maintenance burden | Full ownership | Obsidian handles core |

### What Obsidian Canvas Provides

1. **Infinite canvas** with pan/zoom
2. **Cards** - text, file embed, link, image
3. **Edges** with labels and colors between cards
4. **Groups** for organizing related items
5. **Plugin API** for custom rendering via code block processors

### What We Need to Build

1. **Frontmatter parser** for extracting filter definitions from YAML properties
2. **Code block processors** for ` ```exhibit ` and ` ```metric ` blocks
3. **FastAPI backend** for DuckDB queries
4. **Sidebar filter panel** rendering filters from current note's frontmatter
5. **Plotly.js integration** for chart rendering
6. **State management** for filter synchronization (per-note scope)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                     OBSIDIAN                             │
│  ┌───────────────────────────────────────────────────┐  │
│  │           Canvas View OR Markdown Note             │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌───────────┐ │  │
│  │  │ ```filter   │  │ ```exhibit  │  │ Markdown  │ │  │
│  │  │ (dropdown)  │──│ (chart)     │  │ (text)    │ │  │
│  │  └─────────────┘  └─────────────┘  └───────────┘ │  │
│  └────────────────────────┬──────────────────────────┘  │
│                           │                              │
│  ┌────────────────────────▼──────────────────────────┐  │
│  │              de_Funk Obsidian Plugin               │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌───────────┐ │  │
│  │  │ Processors  │  │ Components  │  │ Sidebar   │ │  │
│  │  │ (parse YAML)│  │ (Plotly.js) │  │ (filters) │ │  │
│  │  └─────────────┘  └─────────────┘  └───────────┘ │  │
│  └────────────────────────┬──────────────────────────┘  │
└───────────────────────────┼──────────────────────────────┘
                            │ HTTP
               ┌────────────▼────────────┐
               │     FastAPI Backend      │
               │  POST /api/query         │
               │  GET  /api/dimensions    │
               │  GET  /api/exhibits      │
               │  GET  /api/domains       │
               └────────────┬─────────────┘
                            │ SQL
               ┌────────────▼────────────┐
               │   DuckDB + Delta Lake    │
               │   (existing storage)     │
               └──────────────────────────┘
```

### Data Flow

1. User opens markdown note or Canvas in Obsidian
2. Plugin's code block processors find ` ```filter ` and ` ```exhibit ` blocks
3. For filters: Plugin calls `/api/dimensions` to get available values
4. For exhibits: Plugin calls `/api/query` with filter state
5. Backend executes DuckDB query against Delta Lake storage
6. Results returned as JSON
7. Plugin renders filter UI or Plotly chart
8. Filter changes trigger re-query of connected exhibits

---

## Syntax Specification

### Filter Scope Summary

| Scope | Defined In | Renders In | Applies To |
|-------|------------|------------|------------|
| **Page filters** | Frontmatter `filters:` | Sidebar panel | All exhibits (unless ignored) |
| **Exhibit filters** | Exhibit block `filters:` | Inside exhibit UI | That exhibit only |

### Exhibit Filter Override Behavior

Exhibit filters can **add to** OR **override** page filters:

| Behavior | Config | Result |
|----------|--------|--------|
| **Inherit all** | `page_filters: { inherit: true }` | Page + exhibit filters combined |
| **Ignore specific** | `page_filters: { inherit: true, ignore: [ticker] }` | Page filters except ticker |
| **Ignore all** | `page_filters: { inherit: false }` | Only exhibit filters apply |
| **Override value** | Exhibit filter with same `id` as page filter | Exhibit value wins |

**Override Example:**
```yaml
# Frontmatter defines:
filters:
  - id: min_price
    type: slider
    default: 0          # Page default: $0

# Exhibit overrides with same filter ID:
```exhibit
filters:
  - id: min_price       # Same ID = OVERRIDE
    type: slider
    default: 100        # Exhibit forces: $100 minimum
```
```

```
FRONTMATTER (filters:)          SIDEBAR PANEL
─────────────────────    →    ─────────────────
- id: ticker                  │ Ticker [▼]    │
- id: date_range              │ Date [━━━━━]  │
- id: min_price (default: 0)  │ Min $: [$0]   │
                              └───────────────┘
                                     │
                                     ▼ (inherited by default)
┌─────────────────────────────────────────────────────────────────┐
│ EXHIBIT BLOCK                     EXHIBIT UI                     │
│ ───────────────                   ──────────                     │
│ page_filters:                     ┌─────────────────────────────┐│
│   inherit: true                   │ Min $: [━━━●━━] $100        ││ ← OVERRIDES
│   ignore: [date_range]            │ (same id, exhibit value)    ││   page filter
│                                   │                             ││
│ filters:                          │ Volume: [━━●━━━] 1M         ││ ← ADDS new
│   - id: min_price                 │ (new filter, exhibit only)  ││   filter
│     default: 100  # override!     └─────────────────────────────┘│
│   - id: volume                                                   │
│     default: 1000000              [═══════════ CHART ═══════════]│
│                                                                  │
│                                   Final filters applied:         │
│                                   • ticker (from page)           │
│                                   • min_price = $100 (override!) │
│                                   • volume = 1M (added)          │
│                                   • date_range = IGNORED         │
└──────────────────────────────────────────────────────────────────┘
```

### Filter Hierarchy Overview

Filters are defined at the **page/canvas level** in YAML frontmatter, and appear in the sidebar. Each note/canvas has its own independent filter set.

```
┌─────────────────────────────────────────────────────────────────┐
│ NOTE/CANVAS FRONTMATTER (defines sidebar filters)               │
│ ---                                                              │
│ title: Stock Analysis                                            │
│ filters:                       ← Sidebar filters for THIS page  │
│   - id: ticker                                                   │
│     type: select                                                 │
│     source: stocks.dim_stock.ticker                              │
│   - id: date_range                                               │
│     type: date_range                                             │
│     source: temporal.dim_calendar.date                           │
│ ---                                                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ Renders in SIDEBAR
┌─────────────────────────────────────────────────────────────────┐
│                        SIDEBAR PANEL                             │
│  (Specific to this note/canvas - not global)                     │
│  ┌─────────────┐  ┌─────────────────────────────────┐           │
│  │ Ticker      │  │ Date Range                       │           │
│  │ [AAPL ▼]    │  │ [2024-01-01] → [2024-12-31]     │           │
│  └─────────────┘  └─────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ (inherited by exhibits)
┌─────────────────────────────────────────────────────────────────┐
│                         EXHIBIT                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ page_filters:                                              │  │
│  │   inherit: true          # Use page filters (default)     │  │
│  │   ignore: [date_range]   # Optionally ignore specific     │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              +                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ filters: (exhibit-specific, additive)                      │  │
│  │   - price_min: > $100    # Additional filter              │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Page-Level Filters (Frontmatter)

Sidebar filters are defined in the note's YAML frontmatter:

```yaml
---
title: Stock Price Analysis
domain: stocks                        # Primary domain for this page

# SIDEBAR FILTERS - defined here, appear in sidebar panel
filters:
  - id: ticker
    type: select
    label: Stock Ticker
    source: stocks.dim_stock.ticker
    default: ["AAPL", "MSFT"]
    multi: true

  - id: date_range
    type: date_range
    label: Analysis Period
    source: temporal.dim_calendar.date
    default:
      start: "2024-01-01"
      end: "2024-12-31"

  - id: sector
    type: select
    label: Sector
    source: stocks.dim_stock.sector
    multi: true

  - id: min_price
    type: slider
    label: Minimum Price
    source: stocks.fact_stock_prices.close
    min: 0
    max: 1000
    default: 0
---

# Stock Price Analysis

Content and exhibits below...
```

### Filter Scope: Per-Note/Canvas

| Aspect | Behavior |
|--------|----------|
| **Scope** | Each note/canvas has its OWN filters |
| **Isolation** | Switching notes loads different filters |
| **Persistence** | Filter values saved per note |
| **No global** | Filters don't affect other notes |

### Filter Types Reference

| Type | Description | UI Component | Default Value Format |
|------|-------------|--------------|---------------------|
| `select` | Single/multi dropdown | Dropdown | `"AAPL"` or `["AAPL", "MSFT"]` |
| `date_range` | Date range picker | Two date inputs | `{start: "2024-01-01", end: "2024-12-31"}` |
| `date` | Single date | Date input | `"2024-01-01"` |
| `number_range` | Numeric range | Dual slider/inputs | `{min: 0, max: 100}` |
| `slider` | Single numeric | Slider | `50` |
| `text_search` | Text input | Search box | `"search term"` |
| `boolean` | True/false | Toggle switch | `true` or `false` |

### Exhibit Block Syntax (Complete)

Exhibits contain **everything** needed to render: chart config, filters, and metrics.

```yaml
```exhibit
# ═══════════════════════════════════════════════════════════════
# IDENTITY
# ═══════════════════════════════════════════════════════════════
id: price-analysis                  # Unique ID for this exhibit (required)
type: line_chart                    # Chart type (required)
domain: stocks                      # Primary domain model (required)
title: Stock Price Analysis         # Display title (optional)
description: Daily closing prices   # Subtitle/description (optional)

# ═══════════════════════════════════════════════════════════════
# PAGE FILTER INHERITANCE (from frontmatter)
# ═══════════════════════════════════════════════════════════════
page_filters:
  inherit: true                     # Inherit filters from frontmatter (default: true)
  ignore: [sector]                  # Ignore these specific page filters
  # If inherit: false, page filters are completely ignored

# ═══════════════════════════════════════════════════════════════
# EXHIBIT-SPECIFIC FILTERS (Nested, additive to sidebar)
# ═══════════════════════════════════════════════════════════════
filters:
  - id: price_min                   # Filter ID (scoped to this exhibit)
    type: number_range
    label: Price Range
    source: stocks.fact_stock_prices.close
    default: { min: 0, max: 500 }

  - id: volume_threshold
    type: slider
    label: Min Volume
    source: stocks.fact_stock_prices.volume
    min: 0
    max: 100000000
    default: 1000000
    format: ",.0f"

  - id: show_outliers
    type: boolean
    label: Include Outliers
    default: false

# ═══════════════════════════════════════════════════════════════
# EXHIBIT-SPECIFIC METRICS (Displayed as KPI cards in header)
# ═══════════════════════════════════════════════════════════════
metrics:
  - id: avg_close
    column: stocks.measures.close_price
    label: Avg Close
    aggregation: avg
    format: "$,.2f"

  - id: total_volume
    column: stocks.measures.volume
    label: Total Volume
    aggregation: sum
    format: ",.0f"
    suffix: " shares"

  - id: price_change
    column: stocks.measures.daily_return
    label: Period Return
    aggregation: sum
    format: "+.2%"
    conditional_color: true         # Green if positive, red if negative

# ═══════════════════════════════════════════════════════════════
# AXIS CONFIGURATION (with optional dynamic selectors)
# ═══════════════════════════════════════════════════════════════
x_axis:
  # Option 1: Static (no selector)
  dimension: temporal.dim_calendar.date
  label: Date

  # Option 2: Dynamic selector
  # available:
  #   - temporal.dim_calendar.date
  #   - temporal.dim_calendar.week
  #   - temporal.dim_calendar.month
  # default: temporal.dim_calendar.date

y_axis:
  # Option 1: Static
  measure: stocks.measures.close_price
  label: Price ($)

  # Option 2: Dynamic selector with multi-select
  # available:
  #   - stocks.measures.close_price
  #   - stocks.measures.open_price
  #   - stocks.measures.volume
  # default: [stocks.measures.close_price]
  # multi: true

color:
  dimension: stocks.dim_stock.ticker
  # Or dynamic:
  # available:
  #   - stocks.dim_stock.ticker
  #   - stocks.dim_stock.sector
  # default: stocks.dim_stock.ticker

# ═══════════════════════════════════════════════════════════════
# DISPLAY OPTIONS
# ═══════════════════════════════════════════════════════════════
display:
  height: 450                       # Chart height in pixels
  show_legend: true                 # Show color legend
  show_filters: true                # Show exhibit filters above chart
  show_metrics: true                # Show metrics as KPI cards
  metrics_position: top             # top | bottom | left | right
  interactive: true                 # Enable zoom/pan/hover

# ═══════════════════════════════════════════════════════════════
# CHART-SPECIFIC OPTIONS (varies by type)
# ═══════════════════════════════════════════════════════════════
options:
  # Line chart options
  mode: lines+markers               # lines | markers | lines+markers
  fill: none                        # none | tozeroy | tonexty

  # Bar chart options
  # orientation: vertical           # vertical | horizontal
  # bar_mode: group                 # group | stack | overlay
```
```

### Exhibit Rendering Layout

Shows where each component renders within an exhibit:

```
┌─────────────────────────────────────────────────────────────────┐
│ Stock Price Analysis                     ← title (from exhibit) │
│ Daily closing prices                     ← description          │
├─────────────────────────────────────────────────────────────────┤
│ EXHIBIT METRICS (from exhibit.metrics:)                          │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                 │
│ │ Avg Close   │ │ Total Vol   │ │ Period Ret  │                 │
│ │   $185.50   │ │  52.3M      │ │   +12.5%    │                 │
│ └─────────────┘ └─────────────┘ └─────────────┘                 │
├─────────────────────────────────────────────────────────────────┤
│ EXHIBIT FILTERS (from exhibit.filters:)  ← renders HERE only    │
│ Price Range: [$0 ───●─── $500]   Min Volume: [1M ▼]  Outliers: ☐│
│ (These are ADDITIONAL to page filters from sidebar)             │
├─────────────────────────────────────────────────────────────────┤
│ AXIS SELECTORS (if using dynamic available: [...])               │
│ X-Axis: [Date ▼]   Measures: [✓ Close ☐ Open ☐ Volume]          │
│ Color By: [Ticker ▼]                                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│                         C H A R T                                │
│    (filtered by: page filters + exhibit filters combined)       │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│ Legend: ● AAPL  ● MSFT  ● GOOGL                                 │
└─────────────────────────────────────────────────────────────────┘

Page filters (sidebar)     +    Exhibit filters (inside exhibit)
─────────────────────           ─────────────────────────────────
ticker = ['AAPL','MSFT']   AND  price_min > 100
date_range = 2024                min_volume > 1M
                                 show_outliers = false
```

### Filter Inheritance Examples

#### Example 1: Inherit all page filters (default)
```yaml
```exhibit
id: basic-chart
type: line_chart
domain: stocks
# page_filters not specified = inherit: true by default
# All page-level (frontmatter) filters apply to this exhibit
x_axis:
  dimension: temporal.dim_calendar.date
y_axis:
  measure: stocks.measures.close_price
```
```

#### Example 2: Inherit page filters but ignore specific ones
```yaml
```exhibit
id: sector-comparison
type: bar_chart
domain: stocks
title: Sector Comparison (ignores ticker filter)

page_filters:
  inherit: true
  ignore: [ticker]                  # Show ALL tickers, not just selected

x_axis:
  dimension: stocks.dim_stock.sector
y_axis:
  measure: stocks.measures.market_cap
  aggregation: sum
```
```

#### Example 3: Ignore all page filters
```yaml
```exhibit
id: full-market-view
type: heatmap
domain: stocks
title: Full Market Heatmap (independent)

page_filters:
  inherit: false                    # Completely independent of frontmatter filters

# Only these exhibit-specific filters apply
filters:
  - id: date_snapshot
    type: date
    label: Snapshot Date
    source: temporal.dim_calendar.date
    default: "2024-12-31"
```
```

#### Example 4: Layer exhibit filters on top of page filters
```yaml
```exhibit
id: filtered-analysis
type: line_chart
domain: stocks
title: High-Volume Stock Analysis

page_filters:
  inherit: true                     # Use ticker + date from frontmatter

# Add additional constraints
filters:
  - id: min_volume
    type: slider
    label: Minimum Daily Volume
    source: stocks.fact_stock_prices.volume
    min: 0
    max: 100000000
    default: 5000000

  - id: price_floor
    type: number_range
    label: Price Range
    source: stocks.fact_stock_prices.close
    default: { min: 50, max: 500 }

# Effective: page(ticker, date) AND volume > 5M AND price BETWEEN 50-500
```
```

### Exhibit Types Reference

| Type | Description | Required Fields |
|------|-------------|-----------------|
| `line_chart` | Time series with traces | `x_axis`, `y_axis` |
| `bar_chart` | Categorical bars | `x_axis`, `y_axis` |
| `scatter_chart` | X-Y scatter plot | `x_axis`, `y_axis` |
| `area_chart` | Filled area chart | `x_axis`, `y_axis` |
| `heatmap` | 2D color matrix | `x_axis`, `y_axis`, `value` |
| `pie_chart` | Proportional slices | `dimension`, `measure` |
| `data_table` | Interactive table | `columns` |
| `pivot_table` | Grouped pivot | `rows`, `columns`, `values` |
| `great_table` | Publication quality | `columns`, `styling` |
| `metric_cards` | KPI display only | `metrics` |

---

## Canvas-Specific Filter Hierarchy

In Canvas view, filters operate at three levels:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CANVAS                                          │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ GLOBAL FILTERS (apply to entire canvas)                                │  │
│  │ ```filter                                                              │  │
│  │ id: global_ticker                                                      │  │
│  │ scope: global           ← KEY: scope defines filter level              │  │
│  │ ```                                                                    │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                    │                                         │
│            ┌───────────────────────┴───────────────────────┐                │
│            ▼                                               ▼                │
│  ┌─────────────────────────────┐           ┌─────────────────────────────┐  │
│  │ CONTAINER: Sector Analysis  │           │ CONTAINER: Company Deep Dive│  │
│  │ ┌─────────────────────────┐ │           │ ┌─────────────────────────┐ │  │
│  │ │ CONTAINER FILTER        │ │           │ │ CONTAINER FILTER        │ │  │
│  │ │ ```filter               │ │           │ │ ```filter               │ │  │
│  │ │ id: sector              │ │           │ │ id: company             │ │  │
│  │ │ scope: container        │ │           │ │ scope: container        │ │  │
│  │ │ ```                     │ │           │ │ ```                     │ │  │
│  │ └─────────────────────────┘ │           │ └─────────────────────────┘ │  │
│  │            │                │           │            │                │  │
│  │     ┌──────┴──────┐         │           │     ┌──────┴──────┐         │  │
│  │     ▼             ▼         │           │     ▼             ▼         │  │
│  │ ┌────────┐   ┌────────┐     │           │ ┌────────┐   ┌────────┐     │  │
│  │ │Exhibit │   │Exhibit │     │           │ │Exhibit │   │Exhibit │     │  │
│  │ │(bar)   │   │(table) │     │           │ │(line)  │   │(metrics│     │  │
│  │ │        │   │        │     │           │ │        │   │        │     │  │
│  │ └────────┘   └────────┘     │           │ └────────┘   └────────┘     │  │
│  └─────────────────────────────┘           └─────────────────────────────┘  │
│                                                                              │
│  Effective filters for "Sector Analysis > Bar Chart":                       │
│    global_ticker (inherited) + sector (container) + exhibit.filters         │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Filter Scope Levels

| Scope | Location | Applies To |
|-------|----------|------------|
| `global` | Anywhere in Canvas | ALL exhibits in entire Canvas |
| `container` | Inside a Canvas group | All exhibits in that group only |
| `exhibit` | Nested in exhibit block | That specific exhibit only |

### Global Filter Syntax (Canvas-level)

```yaml
```filter
id: global_date_range
scope: global                       # ← Canvas-wide filter
type: date_range
label: Analysis Period
source: temporal.dim_calendar.date
default: { start: "2024-01-01", end: "2024-12-31" }
```
```

### Container Filter Syntax (Group-level)

```yaml
```filter
id: sector_focus
scope: container                    # ← Applies to exhibits in same Canvas group
type: select
label: Sector
source: stocks.dim_stock.sector
default: ["Technology"]
```
```

### Exhibit Filter Inheritance in Canvas

Exhibits in Canvas inherit filters based on their location:

```yaml
```exhibit
id: sector-performance
type: bar_chart
domain: stocks

# Canvas filter inheritance
canvas_filters:
  inherit_global: true              # Inherit global Canvas filters (default: true)
  inherit_container: true           # Inherit container/group filters (default: true)
  ignore: [some_global_filter]      # Optionally ignore specific filters

# Additional exhibit-specific filters (always additive)
filters:
  - id: min_market_cap
    type: slider
    source: stocks.measures.market_cap
    min: 0
    max: 1000000000000
    default: 10000000000
```
```

### Canvas Filter Resolution Order

When an exhibit renders, filters are resolved in this order:

```
1. GLOBAL FILTERS (scope: global)
   ├── Defined anywhere in Canvas
   ├── Apply to ALL exhibits
   └── Visible in Canvas-level filter panel

2. CONTAINER FILTERS (scope: container)
   ├── Defined inside Canvas groups
   ├── Apply only to exhibits in same group
   └── Visible in group header

3. EXHIBIT FILTERS (nested in exhibit)
   ├── Defined inside exhibit block
   ├── Apply only to that exhibit
   └── Visible inside exhibit UI

4. RESOLUTION
   └── final_filters = global + container + exhibit
       (with ignore rules applied)
```

### Canvas Group with Container Filter Example

In Canvas JSON format:

```json
{
  "nodes": [
    {
      "id": "group-sector-analysis",
      "type": "group",
      "x": 0,
      "y": 0,
      "width": 800,
      "height": 600,
      "label": "Sector Analysis"
    },
    {
      "id": "container-filter-sector",
      "type": "text",
      "text": "```filter\nid: sector\nscope: container\ntype: select\nsource: stocks.dim_stock.sector\n```",
      "x": 20,
      "y": 40,
      "width": 200,
      "height": 80,
      "parentId": "group-sector-analysis"
    },
    {
      "id": "exhibit-sector-bar",
      "type": "text",
      "text": "```exhibit\nid: sector-revenue\ntype: bar_chart\n...\n```",
      "x": 20,
      "y": 140,
      "width": 350,
      "height": 300,
      "parentId": "group-sector-analysis"
    },
    {
      "id": "exhibit-sector-table",
      "type": "text",
      "text": "```exhibit\nid: sector-companies\ntype: data_table\n...\n```",
      "x": 400,
      "y": 140,
      "width": 350,
      "height": 300,
      "parentId": "group-sector-analysis"
    }
  ]
}
```

Both exhibits inherit the container's `sector` filter automatically.

### Canvas Filter Panel UI

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Canvas: Stock Analysis                                     [⚙️] [📤] [🔍]   │
├─────────────────────────────────────────────────────────────────────────────┤
│ GLOBAL FILTERS                                                               │
│ ┌───────────────┐ ┌───────────────┐ ┌───────────────┐                       │
│ │ Date Range    │ │ Ticker        │ │ Exchange      │                       │
│ │ [2024-01-01 → │ │ [AAPL, MSFT]  │ │ [NYSE ▼]      │                       │
│ │  2024-12-31]  │ │               │ │               │                       │
│ └───────────────┘ └───────────────┘ └───────────────┘                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌─── Sector Analysis ─────────────────────────────────────────────┐       │
│   │ CONTAINER FILTER: Sector [Technology ▼]                          │       │
│   │ ┌─────────────────────────┐ ┌─────────────────────────────────┐ │       │
│   │ │ Revenue by Company      │ │ Company Details                  │ │       │
│   │ │ ┌─────────────────────┐ │ │ ┌─────────────────────────────┐ │ │       │
│   │ │ │      [BAR CHART]    │ │ │ │      [DATA TABLE]           │ │ │       │
│   │ │ └─────────────────────┘ │ │ └─────────────────────────────┘ │ │       │
│   │ └─────────────────────────┘ └─────────────────────────────────┘ │       │
│   └──────────────────────────────────────────────────────────────────┘       │
│                                                                              │
│   ┌─── Company Deep Dive ───────────────────────────────────────────┐       │
│   │ CONTAINER FILTER: Company [Apple Inc. ▼]                         │       │
│   │ ┌─────────────────────────┐ ┌─────────────────────────────────┐ │       │
│   │ │ Price History           │ │ Financial Metrics               │ │       │
│   │ │ ┌─────────────────────┐ │ │ ┌─────────────────────────────┐ │ │       │
│   │ │ │     [LINE CHART]    │ │ │ │    [METRIC CARDS]           │ │ │       │
│   │ │ └─────────────────────┘ │ │ └─────────────────────────────┘ │ │       │
│   │ └─────────────────────────┘ └─────────────────────────────────┘ │       │
│   └──────────────────────────────────────────────────────────────────┘       │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Markdown Note vs Canvas Filter Comparison

| Feature | Markdown Note | Canvas |
|---------|---------------|--------|
| Global filters | Sidebar panel | Canvas-level panel |
| Container filters | N/A | Canvas groups |
| Exhibit filters | Nested in block | Nested in block |
| Filter inheritance | 2 levels | 3 levels |
| Visual connections | N/A | Edges show data flow |

---

### Standalone Metric Block (Optional)

For standalone metric displays (not inside an exhibit):

```yaml
```metric
id: portfolio-summary
domain: stocks
title: Portfolio Overview

page_filters:
  inherit: true                     # Use filters from frontmatter

metrics:
  - column: stocks.measures.close_price
    label: Avg Price
    aggregation: avg
    format: "$,.2f"

  - column: stocks.measures.market_cap
    label: Total Market Cap
    aggregation: sum
    format: "$,.2fB"
    divide_by: 1000000000

layout: horizontal                  # horizontal | vertical | grid
style: cards                        # cards | inline | compact
```
```

---

## Filter System

### Sidebar Filter Panel

The plugin registers a sidebar view (like Obsidian's file explorer) that:

1. **Reads filters from frontmatter** of the currently active note
2. **Renders filter UI components** for each filter defined in properties
3. **Persists while scrolling** - always accessible
4. **Scoped per note** - switching notes loads that note's filters
5. **No global filters** - each note/canvas is completely independent

```
┌──────────────────────────────────────────────────────────┐
│ Obsidian                                                  │
├──────────────┬───────────────────────────────────────────┤
│              │  ---                                       │
│ FILTER PANEL │  title: Stock Analysis                     │
│ ───────────  │  filters:                                  │
│ (from front- │    - id: ticker         ← Defined here    │
│  matter)     │      type: select                          │
│              │      source: stocks...                     │
│ Ticker       │    - id: date_range     ← And here        │
│ [AAPL ▼]  ←──┼──    type: date_range                      │
│              │  ---                                       │
│ Date Range   │                                            │
│ [2024-2025]←─┼─ ## Stock Analysis                         │
│              │                                            │
│              │  Some analysis text here...                │
│              │                                            │
│              │  ```exhibit                                │
│              │  page_filters:                             │
│              │    inherit: true    ← Uses frontmatter     │
│              │  [═══════ CHART ═══════════]               │
│              │  ```                                       │
│              │                                            │
└──────────────┴───────────────────────────────────────────┘
```

### Filter Definition Location

**All page-level filters are defined in YAML frontmatter** (not as code blocks):

```yaml
---
title: Stock Analysis
domain: stocks

filters:
  - id: ticker
    type: select
    source: stocks.dim_stock.ticker
    default: ["AAPL"]

  - id: date_range
    type: date_range
    source: temporal.dim_calendar.date
---
```

**Exhibit-specific filters are defined inside the exhibit block** and add constraints:

```yaml
```exhibit
id: price-chart
domain: stocks

page_filters:
  inherit: true              # Uses frontmatter filters

filters:                     # Additional constraints
  - id: price_min
    type: slider
    source: stocks.fact_stock_prices.close
```
```

### Filter State Management

```typescript
// State structure per note (isolated from other notes)
interface NoteFilterState {
  noteId: string;
  notePath: string;

  // Filters defined in frontmatter (page-level)
  pageFilters: Map<string, FilterDefinition>;

  // Current values for all filters
  filterValues: Map<string, FilterValue>;  // filterId -> current value

  // Methods
  loadFromFrontmatter(frontmatter: FrontMatter): void;
  getValue(filterId: string): FilterValue;
  setValue(filterId: string, value: FilterValue): void;
  getPageFilters(): FilterDefinition[];  // All page-level filters for sidebar
  subscribe(callback: (state: NoteFilterState) => void): void;
}

// Filter definition from frontmatter
interface FilterDefinition {
  id: string;
  type: 'select' | 'date_range' | 'date' | 'number_range' | 'slider' | 'boolean';
  label?: string;
  source: string;
  default?: any;
  multi?: boolean;
}

// Filter value types
type FilterValue =
  | string                    // Single select
  | string[]                  // Multi select
  | { start: Date; end: Date } // Date range
  | { min: number; max: number } // Number range
  | boolean;                  // Boolean toggle
```

---

## Exhibit System

### Dynamic Selectors

When an exhibit has `available` arrays, the UI renders dropdowns:

```
┌─────────────────────────────────────────────────────────┐
│ X-Axis: [Date ▼]  Measures: [✓ Close ✓ Volume]         │
│ Color By: [Ticker ▼]                                    │
├─────────────────────────────────────────────────────────┤
│                                                         │
│                        CHART                            │
│       (updates dynamically as selectors change)        │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Domain Model References

Exhibits use domain model references instead of raw column paths:

| Reference | Resolution |
|-----------|------------|
| `stocks.measures.close_price` | Looks up measure in `domains/securities/stocks.md` |
| `stocks.dim_stock.ticker` | Looks up column in domain schema |
| `temporal.dim_calendar.date` | Cross-domain reference to calendar |

**Backend Resolution:**
1. Parse domain reference (e.g., `stocks.measures.close_price`)
2. Load domain config from `domains/securities/stocks.md`
3. Find measure definition with aggregation, format, etc.
4. Generate SQL expression
5. Execute against DuckDB

### Chart Rendering

Charts are rendered using Plotly.js:

```typescript
interface ChartConfig {
  type: 'line' | 'bar' | 'scatter' | 'area' | 'heatmap';
  data: PlotlyData[];
  layout: PlotlyLayout;
  config: PlotlyConfig;
}

// Plotly integration
import Plotly from 'plotly.js-dist-min';

function renderChart(container: HTMLElement, config: ChartConfig) {
  Plotly.newPlot(container, config.data, config.layout, config.config);
}
```

---

## Backend API

### Endpoints

#### POST /api/query

Execute a query against the data warehouse.

**Request:**
```json
{
  "domain": "stocks",
  "columns": [
    "temporal.dim_calendar.date",
    "stocks.measures.close_price",
    "stocks.dim_stock.ticker"
  ],
  "filters": [
    {
      "column": "stocks.dim_stock.ticker",
      "operator": "in",
      "value": ["AAPL", "MSFT"]
    },
    {
      "column": "temporal.dim_calendar.date",
      "operator": "between",
      "value": ["2024-01-01", "2024-12-31"]
    }
  ],
  "group_by": ["temporal.dim_calendar.date", "stocks.dim_stock.ticker"],
  "order_by": [{"column": "temporal.dim_calendar.date", "direction": "asc"}],
  "limit": 10000
}
```

**Response:**
```json
{
  "data": [
    {"date": "2024-01-02", "close_price": 185.50, "ticker": "AAPL"},
    {"date": "2024-01-02", "close_price": 375.25, "ticker": "MSFT"}
  ],
  "columns": [
    {"name": "date", "type": "date", "source": "temporal.dim_calendar.date"},
    {"name": "close_price", "type": "float", "source": "stocks.measures.close_price"},
    {"name": "ticker", "type": "string", "source": "stocks.dim_stock.ticker"}
  ],
  "row_count": 500,
  "execution_time_ms": 45
}
```

#### GET /api/dimensions/{domain}/{dimension}

Get distinct values for a dimension (for filter dropdowns).

**Example:** `GET /api/dimensions/stocks/dim_stock.ticker`

**Response:**
```json
{
  "dimension": "stocks.dim_stock.ticker",
  "values": ["AAPL", "AMZN", "GOOGL", "META", "MSFT", "NVDA", "TSLA"],
  "count": 7,
  "type": "string"
}
```

#### GET /api/exhibits

List available exhibit types with their schemas.

**Response:**
```json
{
  "exhibits": [
    {
      "type": "line_chart",
      "description": "Time series visualization",
      "required_fields": ["x", "y"],
      "optional_fields": ["color", "title", "height"]
    },
    {
      "type": "bar_chart",
      "description": "Categorical bar chart",
      "required_fields": ["x", "y"],
      "optional_fields": ["color", "orientation"]
    }
  ]
}
```

#### GET /api/domains

List available domain models with their measures and dimensions.

**Response:**
```json
{
  "domains": [
    {
      "name": "stocks",
      "description": "Stock securities data",
      "dimensions": [
        {"name": "dim_stock", "columns": ["ticker", "sector", "market_cap"]},
        {"name": "fact_stock_prices", "columns": ["open", "high", "low", "close", "volume"]}
      ],
      "measures": [
        {"name": "close_price", "type": "simple", "aggregation": "avg"},
        {"name": "volume", "type": "simple", "aggregation": "sum"},
        {"name": "daily_return", "type": "computed", "expression": "..."}
      ]
    }
  ]
}
```

### Backend Implementation

**Location:** `src/de_funk/api/` (new top-level directory)

The API module fits into the existing `src/de_funk/` package structure:

```
src/de_funk/
├── api/                      # NEW - FastAPI backend for Obsidian
│   ├── __init__.py
│   ├── main.py               # FastAPI application
│   ├── routers/
│   │   ├── query.py          # Query endpoint
│   │   ├── dimensions.py     # Dimension values endpoint
│   │   ├── exhibits.py       # Exhibit types endpoint
│   │   └── domains.py        # Domain models endpoint
│   └── models/
│       └── requests.py       # Pydantic request/response models
├── config/                   # Existing - Configuration system
├── core/                     # Existing - Infrastructure (session, filters)
├── models/                   # Existing - Domain models (used by API)
├── notebook/                 # Existing - Notebook backend
├── services/                 # Existing - Business logic services
├── pipelines/                # Existing - Data ingestion
├── orchestration/            # Existing - Pipeline orchestration
└── utils/                    # Existing - Utilities
```

The API layer uses existing components:
- `core.session.universal_session` for DuckDB queries
- `config.domain_loader` for domain model resolution
- `models.api.registry` for model discovery

```python
# src/de_funk/api/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import query, dimensions, exhibits, domains

app = FastAPI(title="de_Funk API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["app://obsidian.md"],  # Obsidian's origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(query.router, prefix="/api")
app.include_router(dimensions.router, prefix="/api")
app.include_router(exhibits.router, prefix="/api")
app.include_router(domains.router, prefix="/api")
```

```python
# src/de_funk/api/routers/query.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Any
import time

from de_funk.core.session.universal_session import UniversalSession
from de_funk.config.domain_loader import ModelConfigLoader

router = APIRouter()
session = UniversalSession(backend="duckdb")
loader = ModelConfigLoader(Path("domains"))

class QueryRequest(BaseModel):
    domain: str
    columns: List[str]
    filters: Optional[List[dict]] = None
    group_by: Optional[List[str]] = None
    order_by: Optional[List[dict]] = None
    limit: int = 10000

class QueryResponse(BaseModel):
    data: List[dict]
    columns: List[dict]
    row_count: int
    execution_time_ms: float

@router.post("/query", response_model=QueryResponse)
async def execute_query(request: QueryRequest):
    start = time.time()
    try:
        # Resolve domain references to SQL
        resolved_columns = resolve_columns(request.domain, request.columns)
        resolved_filters = resolve_filters(request.domain, request.filters)

        # Build and execute query
        df = session.query_model(
            model=request.domain,
            columns=resolved_columns,
            filters=resolved_filters,
            group_by=request.group_by,
            order_by=request.order_by,
            limit=request.limit
        )

        return QueryResponse(
            data=df.to_dict(orient="records"),
            columns=[{"name": c, "type": str(df[c].dtype)} for c in df.columns],
            row_count=len(df),
            execution_time_ms=(time.time() - start) * 1000
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
```

---

## Obsidian Plugin Structure

### Directory Layout

```
obsidian-defunk/
├── manifest.json                    # Plugin metadata
├── main.ts                          # Plugin entry point
├── src/
│   ├── api/
│   │   ├── client.ts                # HTTP client for FastAPI
│   │   └── types.ts                 # Request/response types
│   ├── parsers/
│   │   ├── frontmatter-parser.ts    # Extract filters from YAML frontmatter
│   │   └── yaml-parser.ts           # YAML parsing utilities
│   ├── processors/
│   │   ├── exhibit-processor.ts     # ```exhibit block handler
│   │   └── metric-processor.ts      # ```metric block handler
│   ├── components/
│   │   ├── filters/
│   │   │   ├── select-filter.ts     # Dropdown component
│   │   │   ├── date-range-filter.ts # Date range picker
│   │   │   ├── slider-filter.ts     # Numeric slider
│   │   │   └── filter-factory.ts    # Factory for filter types
│   │   ├── exhibits/
│   │   │   ├── chart-exhibit.ts     # Plotly chart wrapper
│   │   │   ├── table-exhibit.ts     # Data table
│   │   │   ├── metric-exhibit.ts    # Metric cards
│   │   │   └── exhibit-factory.ts   # Factory for exhibit types
│   │   └── selectors/
│   │       ├── measure-selector.ts  # Measure dropdown
│   │       └── dimension-selector.ts # Dimension dropdown
│   ├── views/
│   │   └── filter-sidebar.ts        # Sidebar panel view (reads from frontmatter)
│   ├── state/
│   │   ├── filter-state.ts          # Per-note filter value management
│   │   ├── query-cache.ts           # Query result caching
│   │   └── note-context.ts          # Per-note state (isolated)
│   └── settings.ts                  # Plugin settings
├── styles.css                       # Component styling
├── package.json
├── tsconfig.json
└── esbuild.config.mjs               # Build configuration
```

### Plugin Entry Point

```typescript
// main.ts
import { Plugin, WorkspaceLeaf, TFile, CachedMetadata } from 'obsidian';
import { FrontmatterParser } from './src/parsers/frontmatter-parser';
import { ExhibitProcessor } from './src/processors/exhibit-processor';
import { MetricProcessor } from './src/processors/metric-processor';
import { FilterSidebarView, FILTER_SIDEBAR_VIEW } from './src/views/filter-sidebar';
import { NoteFilterState } from './src/state/filter-state';
import { ApiClient } from './src/api/client';
import { DeFunkSettings, DEFAULT_SETTINGS, DeFunkSettingTab } from './src/settings';

export default class DeFunkPlugin extends Plugin {
  settings: DeFunkSettings;
  filterStateMap: Map<string, NoteFilterState>;  // Per-note filter states
  apiClient: ApiClient;

  async onload() {
    await this.loadSettings();

    // Initialize API client
    this.apiClient = new ApiClient(this.settings.apiUrl);

    // Initialize per-note filter state map
    this.filterStateMap = new Map();

    // Register sidebar view (reads filters from active note's frontmatter)
    this.registerView(
      FILTER_SIDEBAR_VIEW,
      (leaf) => new FilterSidebarView(leaf, this)
    );

    // Listen for active file changes to update sidebar
    this.registerEvent(
      this.app.workspace.on('active-leaf-change', () => {
        this.updateFilterStateForActiveNote();
      })
    );

    // Listen for frontmatter changes to refresh filters
    this.registerEvent(
      this.app.metadataCache.on('changed', (file: TFile) => {
        if (file === this.app.workspace.getActiveFile()) {
          this.updateFilterStateForActiveNote();
        }
      })
    );

    // Register code block processors (exhibits and metrics only)
    // Note: Filters come from frontmatter, not code blocks
    this.registerMarkdownCodeBlockProcessor(
      'exhibit',
      (source, el, ctx) => new ExhibitProcessor(this).process(source, el, ctx)
    );

    this.registerMarkdownCodeBlockProcessor(
      'metric',
      (source, el, ctx) => new MetricProcessor(this).process(source, el, ctx)
    );

    // Add ribbon icon to toggle sidebar
    this.addRibbonIcon('filter', 'Toggle Filter Panel', () => {
      this.toggleFilterSidebar();
    });

    // Add settings tab
    this.addSettingTab(new DeFunkSettingTab(this.app, this));
  }

  // Get or create filter state for a specific note
  getFilterState(notePath: string): NoteFilterState {
    if (!this.filterStateMap.has(notePath)) {
      this.filterStateMap.set(notePath, new NoteFilterState(notePath, this));
    }
    return this.filterStateMap.get(notePath)!;
  }

  // Update filter state when active note changes
  updateFilterStateForActiveNote() {
    const activeFile = this.app.workspace.getActiveFile();
    if (!activeFile) return;

    const cache = this.app.metadataCache.getFileCache(activeFile);
    const frontmatter = cache?.frontmatter;

    const state = this.getFilterState(activeFile.path);
    state.loadFromFrontmatter(frontmatter);

    // Notify sidebar to re-render
    this.app.workspace.trigger('defunk:filters-changed', activeFile.path);
  }

  async toggleFilterSidebar() {
    const existing = this.app.workspace.getLeavesOfType(FILTER_SIDEBAR_VIEW);
    if (existing.length) {
      existing[0].detach();
    } else {
      const leaf = this.app.workspace.getRightLeaf(false);
      await leaf.setViewState({ type: FILTER_SIDEBAR_VIEW, active: true });
    }
  }

  async loadSettings() {
    this.settings = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());
  }

  async saveSettings() {
    await this.saveData(this.settings);
  }
}
```

### Frontmatter Parser

```typescript
// src/parsers/frontmatter-parser.ts
import { parse as parseYaml } from 'yaml';
import type { FilterDefinition } from '../state/filter-state';

interface NoteFrontmatter {
  title?: string;
  domain?: string;
  filters?: FilterDefinition[];
}

export class FrontmatterParser {
  /**
   * Extract filter definitions from note frontmatter.
   * Filters are defined in YAML properties, not code blocks.
   */
  static parseFilters(frontmatter: Record<string, any> | undefined): FilterDefinition[] {
    if (!frontmatter || !frontmatter.filters) {
      return [];
    }

    const filters: FilterDefinition[] = [];

    for (const filter of frontmatter.filters) {
      // Validate required fields
      if (!filter.id || !filter.type || !filter.source) {
        console.warn(`Invalid filter definition: missing required fields`, filter);
        continue;
      }

      filters.push({
        id: filter.id,
        type: filter.type,
        label: filter.label,
        source: filter.source,
        default: filter.default,
        multi: filter.multi ?? false,
      });
    }

    return filters;
  }

  /**
   * Get the primary domain from frontmatter.
   */
  static getDomain(frontmatter: Record<string, any> | undefined): string | undefined {
    return frontmatter?.domain;
  }
}
```

### Note Filter State

```typescript
// src/state/filter-state.ts
import type DeFunkPlugin from '../../main';
import { FrontmatterParser } from '../parsers/frontmatter-parser';
import { FilterFactory } from '../components/filters/filter-factory';

export interface FilterDefinition {
  id: string;
  type: 'select' | 'date_range' | 'date' | 'number_range' | 'slider' | 'boolean';
  label?: string;
  source: string;
  default?: any;
  multi?: boolean;
}

export type FilterValue =
  | string
  | string[]
  | { start: Date; end: Date }
  | { min: number; max: number }
  | boolean;

export class NoteFilterState {
  private pageFilters: FilterDefinition[] = [];
  private filterValues: Map<string, FilterValue> = new Map();
  private subscribers: Set<(state: NoteFilterState) => void> = new Set();

  constructor(
    public readonly notePath: string,
    private plugin: DeFunkPlugin
  ) {}

  /**
   * Load filters from frontmatter and initialize values.
   */
  loadFromFrontmatter(frontmatter: Record<string, any> | undefined): void {
    this.pageFilters = FrontmatterParser.parseFilters(frontmatter);

    // Initialize default values for new filters
    for (const filter of this.pageFilters) {
      if (!this.filterValues.has(filter.id) && filter.default !== undefined) {
        this.filterValues.set(filter.id, filter.default);
      }
    }

    this.notifySubscribers();
  }

  getPageFilters(): FilterDefinition[] {
    return this.pageFilters;
  }

  getValue(filterId: string): FilterValue | undefined {
    return this.filterValues.get(filterId);
  }

  setValue(filterId: string, value: FilterValue): void {
    this.filterValues.set(filterId, value);
    this.notifySubscribers();
  }

  subscribe(callback: (state: NoteFilterState) => void): () => void {
    this.subscribers.add(callback);
    return () => this.subscribers.delete(callback);
  }

  private notifySubscribers(): void {
    for (const callback of this.subscribers) {
      callback(this);
    }
  }
}
```

### Exhibit Processor

```typescript
// src/processors/exhibit-processor.ts
import { MarkdownPostProcessorContext } from 'obsidian';
import { parse as parseYaml } from 'yaml';
import Plotly from 'plotly.js-dist-min';
import type DeFunkPlugin from '../../main';

interface ExhibitConfig {
  type: string;
  domain: string;
  title?: string;
  x?: string;
  y?: string | string[];
  color?: string;
  x_axis?: AxisConfig;
  y_axis?: AxisConfig;
  filters?: string[];
  height?: number;
  interactive?: boolean;
}

interface AxisConfig {
  available?: string[];
  default?: string;
  multi?: boolean;
}

export class ExhibitProcessor {
  constructor(private plugin: DeFunkPlugin) {}

  async process(source: string, el: HTMLElement, ctx: MarkdownPostProcessorContext) {
    try {
      const config = parseYaml(source) as ExhibitConfig;

      // Validate
      if (!config.type || !config.domain) {
        throw new Error('Exhibit requires type and domain fields');
      }

      // Create container
      el.empty();
      el.addClass('defunk-exhibit');

      const container = el.createDiv({ cls: 'defunk-exhibit-container' });

      // Add selectors if dynamic
      let currentX = config.x || config.x_axis?.default;
      let currentY = config.y || config.y_axis?.default;
      let currentColor = config.color || config.color?.default;

      if (config.x_axis?.available || config.y_axis?.available) {
        const selectorBar = container.createDiv({ cls: 'defunk-selector-bar' });

        if (config.x_axis?.available) {
          this.addSelector(selectorBar, 'X-Axis', config.x_axis.available, currentX, (v) => {
            currentX = v;
            this.refreshChart(chartEl, config, currentX, currentY, currentColor);
          });
        }

        if (config.y_axis?.available) {
          this.addSelector(selectorBar, 'Measures', config.y_axis.available, currentY, (v) => {
            currentY = v;
            this.refreshChart(chartEl, config, currentX, currentY, currentColor);
          }, config.y_axis.multi);
        }
      }

      // Chart container
      const chartEl = container.createDiv({ cls: 'defunk-chart' });
      chartEl.style.height = `${config.height || 400}px`;

      // Initial render
      await this.renderChart(chartEl, config, currentX, currentY, currentColor);

      // Subscribe to filter changes
      if (config.filters) {
        config.filters.forEach(filterId => {
          this.plugin.filterState.subscribe(filterId, () => {
            this.refreshChart(chartEl, config, currentX, currentY, currentColor);
          });
        });
      }

    } catch (error) {
      el.createEl('div', {
        cls: 'defunk-error',
        text: `Exhibit error: ${error.message}`
      });
    }
  }

  private async renderChart(
    el: HTMLElement,
    config: ExhibitConfig,
    x: string,
    y: string | string[],
    color?: string
  ) {
    // Get current filter values
    const filters = this.plugin.filterState.getFiltersForExhibit(config.filters || []);

    // Query data
    const columns = [x, ...(Array.isArray(y) ? y : [y])];
    if (color) columns.push(color);

    const response = await this.plugin.apiClient.query({
      domain: config.domain,
      columns,
      filters,
      group_by: color ? [x, color] : [x],
      order_by: [{ column: x, direction: 'asc' }]
    });

    // Convert to Plotly format
    const plotlyData = this.toPlotlyData(response.data, config.type, x, y, color);
    const layout = this.getLayout(config);

    Plotly.newPlot(el, plotlyData, layout, { responsive: true });
  }

  private toPlotlyData(data: any[], type: string, x: string, y: string | string[], color?: string) {
    // Group by color if specified
    if (color) {
      const groups = new Map<string, any[]>();
      data.forEach(row => {
        const key = row[color];
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key)!.push(row);
      });

      return Array.from(groups.entries()).map(([name, rows]) => ({
        type: type === 'line_chart' ? 'scatter' : 'bar',
        mode: type === 'line_chart' ? 'lines+markers' : undefined,
        name,
        x: rows.map(r => r[x]),
        y: rows.map(r => r[Array.isArray(y) ? y[0] : y])
      }));
    }

    return [{
      type: type === 'line_chart' ? 'scatter' : 'bar',
      mode: type === 'line_chart' ? 'lines+markers' : undefined,
      x: data.map(r => r[x]),
      y: data.map(r => r[Array.isArray(y) ? y[0] : y])
    }];
  }

  private getLayout(config: ExhibitConfig) {
    return {
      title: config.title,
      autosize: true,
      margin: { l: 50, r: 30, t: config.title ? 50 : 20, b: 50 }
    };
  }
}
```

---

## Implementation Phases

### Phase 1: Backend API (Weeks 1-2)

**Goal:** FastAPI server with core endpoints

**Tasks:**
1. Create `src/de_funk/api/` directory structure
2. Implement FastAPI application with CORS
3. Implement `/api/query` endpoint
4. Implement `/api/dimensions` endpoint
5. Implement `/api/exhibits` endpoint
6. Implement `/api/domains` endpoint
7. Add FastAPI and uvicorn to `pyproject.toml`
8. Create startup script for backend

**Verification:**
```bash
# Start backend
uvicorn de_funk.api.main:app --reload --port 8000

# Test query
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"domain": "stocks", "columns": ["stocks.dim_stock.ticker"]}'
```

### Phase 2: Obsidian Plugin Scaffold (Week 3)

**Goal:** Basic plugin that loads in Obsidian

**Tasks:**
1. Initialize npm project with TypeScript
2. Create `manifest.json` with plugin metadata
3. Implement `main.ts` entry point
4. Set up esbuild for compilation
5. Create settings tab with API URL config
6. Register empty code block processors
7. Test loading in Obsidian dev vault

**Verification:**
- Plugin loads in Obsidian without errors
- Settings tab shows API URL field
- ` ```filter ` and ` ```exhibit ` blocks show "Coming soon" placeholder

### Phase 3: Exhibit Rendering (Week 4)

**Goal:** Charts render in markdown notes and Canvas

**Tasks:**
1. Implement exhibit processor with YAML parsing
2. Integrate Plotly.js
3. Implement line, bar, scatter chart types
4. Add dynamic measure/dimension selectors
5. Implement domain model reference resolution
6. Style charts with CSS
7. Test in both markdown notes and Canvas text nodes

**Verification:**
- ` ```exhibit ` block renders Plotly chart
- Chart updates when selectors change
- Works in both markdown reading view and Canvas

### Phase 4: Filter System (Week 5)

**Goal:** Interactive filters with sidebar panel

**Tasks:**
1. Implement frontmatter parser for filter extraction
2. Create filter components (select, date range, slider, etc.)
3. Implement per-note filter state manager
4. Create sidebar panel view that reads from frontmatter
5. Implement filter value persistence per note
6. Connect filters to exhibits (trigger re-query on change)
7. Handle active note change events to update sidebar

**Verification:**
- Sidebar shows filters defined in active note's frontmatter
- Switching notes updates sidebar with that note's filters
- Changing filter value updates connected exhibits
- Filter values persist when switching between notes

### Phase 5: Canvas Features (Week 6)

**Goal:** Canvas-specific enhancements

**Tasks:**
1. Custom styling for filter/exhibit nodes in Canvas
2. Edge-based filter propagation (optional)
3. Group templates for common layouts
4. Performance optimization (query caching)
5. Error handling and loading states
6. Documentation and examples

**Verification:**
- Filters and exhibits render beautifully in Canvas
- Drawing edge from filter to exhibit connects them
- Plugin performs well with multiple exhibits

---

## File Changes Required

### Python (Backend)

| Path | Action | Description |
|------|--------|-------------|
| `src/de_funk/api/__init__.py` | Create | Package init with version |
| `src/de_funk/api/main.py` | Create | FastAPI app with CORS for Obsidian |
| `src/de_funk/api/routers/__init__.py` | Create | Router package init |
| `src/de_funk/api/routers/query.py` | Create | `/api/query` endpoint |
| `src/de_funk/api/routers/dimensions.py` | Create | `/api/dimensions` endpoint |
| `src/de_funk/api/routers/exhibits.py` | Create | `/api/exhibits` endpoint |
| `src/de_funk/api/routers/domains.py` | Create | `/api/domains` endpoint |
| `src/de_funk/api/models/__init__.py` | Create | Models package init |
| `src/de_funk/api/models/requests.py` | Create | Pydantic request/response models |
| `pyproject.toml` | Modify | Add `api` extras: fastapi, uvicorn |
| `scripts/api/run_api_server.py` | Create | Startup script for the API server |

**Key Integration Points:**

| Existing Component | API Usage |
|-------------------|-----------|
| `core.session.universal_session.UniversalSession` | Execute DuckDB queries |
| `config.domain_loader.ModelConfigLoader` | Resolve domain model references |
| `models.api.registry.get_model_registry` | Discover available models |
| `core.session.filters.FilterEngine` | Apply filters to queries |

### TypeScript (Plugin)

The Obsidian plugin is a **separate repository** that connects to the de_Funk API:

**Location Options:**
1. `de_Funk/obsidian-defunk/` - Subdirectory within de_Funk repo
2. Separate `obsidian-defunk/` repository (recommended for Obsidian community plugins)

| Path | Action | Description |
|------|--------|-------------|
| `obsidian-defunk/manifest.json` | Create | Plugin metadata for Obsidian |
| `obsidian-defunk/main.ts` | Create | Plugin entry point |
| `obsidian-defunk/src/parsers/frontmatter-parser.ts` | Create | Extract filters from YAML frontmatter |
| `obsidian-defunk/src/processors/exhibit-processor.ts` | Create | Handle ` ```exhibit ` code blocks |
| `obsidian-defunk/src/processors/metric-processor.ts` | Create | Handle ` ```metric ` code blocks |
| `obsidian-defunk/src/state/filter-state.ts` | Create | Per-note filter state management |
| `obsidian-defunk/src/views/filter-sidebar.ts` | Create | Sidebar panel (reads frontmatter) |
| `obsidian-defunk/src/api/client.ts` | Create | HTTP client for de_Funk API |
| `obsidian-defunk/src/components/**/*.ts` | Create | UI components (filters, charts) |
| `obsidian-defunk/styles.css` | Create | Component styling |
| `obsidian-defunk/package.json` | Create | npm config with dependencies |
| `obsidian-defunk/tsconfig.json` | Create | TypeScript configuration |
| `obsidian-defunk/esbuild.config.mjs` | Create | Build configuration |

### Documentation

| Path | Action | Description |
|------|--------|-------------|
| `docs/obsidian-integration.md` | Create | User guide |
| `CLAUDE.md` | Modify | Add Obsidian section |

---

## Migration Guide

### Converting Old Syntax to New

**Old (current):**
```markdown
$filter${
  "id": "ticker",
  "type": "select",
  "source": {"model": "stocks", "table": "dim_stock", "column": "ticker"}
}

$exhibits${
  "type": "line_chart",
  "x": "temporal.dim_calendar.date",
  "y": "stocks.fact_stock_prices.close"
}
```

**New (Obsidian):**
````markdown
```filter
id: ticker
type: select
source: stocks.dim_stock.ticker
```

```exhibit
type: line_chart
domain: stocks
x: temporal.dim_calendar.date
y: stocks.measures.close_price
```
````

### Migration Script

```python
# scripts/maintenance/migrate_to_obsidian_syntax.py
import re
import json
from pathlib import Path

def migrate_filter(match):
    """Convert $filter${...} to ```filter ... ```"""
    content = match.group(1)
    config = json.loads(content)

    # Convert source format
    if isinstance(config.get('source'), dict):
        s = config['source']
        config['source'] = f"{s['model']}.{s['table']}.{s['column']}"

    # Convert to YAML
    yaml_lines = []
    for key, value in config.items():
        if isinstance(value, list):
            yaml_lines.append(f"{key}: {json.dumps(value)}")
        elif isinstance(value, dict):
            yaml_lines.append(f"{key}:")
            for k, v in value.items():
                yaml_lines.append(f"  {k}: {v}")
        else:
            yaml_lines.append(f"{key}: {value}")

    return "```filter\n" + "\n".join(yaml_lines) + "\n```"

def migrate_exhibit(match):
    """Convert $exhibits${...} to ```exhibit ... ```"""
    content = match.group(1)
    config = json.loads(content)

    # Add domain if not present
    if 'domain' not in config and 'source' in config:
        config['domain'] = config['source'].split('.')[0]

    # Convert to YAML
    yaml_lines = ["```exhibit"]
    for key, value in config.items():
        yaml_lines.append(f"{key}: {value}")
    yaml_lines.append("```")

    return "\n".join(yaml_lines)

def migrate_file(path: Path):
    content = path.read_text()

    # Migrate filters
    content = re.sub(
        r'\$filter\$\{([^}]+)\}',
        migrate_filter,
        content,
        flags=re.DOTALL
    )

    # Migrate exhibits
    content = re.sub(
        r'\$exhibits?\$\{([^}]+)\}',
        migrate_exhibit,
        content,
        flags=re.DOTALL
    )

    path.write_text(content)
    print(f"Migrated: {path}")

if __name__ == "__main__":
    notebooks_dir = Path("notebooks")
    for md_file in notebooks_dir.rglob("*.md"):
        migrate_file(md_file)
```

---

## Testing & Verification

### Unit Tests

**Backend:**
```python
# tests/api/test_query.py
import pytest
from fastapi.testclient import TestClient
from de_funk.api.main import app

client = TestClient(app)

def test_query_basic():
    response = client.post("/api/query", json={
        "domain": "stocks",
        "columns": ["stocks.dim_stock.ticker"],
        "limit": 10
    })
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "row_count" in data

def test_dimensions():
    response = client.get("/api/dimensions/stocks/dim_stock.ticker")
    assert response.status_code == 200
    data = response.json()
    assert "values" in data
    assert len(data["values"]) > 0
```

**Plugin:**
```typescript
// obsidian-defunk/tests/yaml-parser.test.ts
import { parseFilterConfig } from '../src/processors/yaml-parser';

test('parses basic filter config', () => {
  const yaml = `
id: ticker
type: select
source: stocks.dim_stock.ticker
`;
  const config = parseFilterConfig(yaml);
  expect(config.id).toBe('ticker');
  expect(config.type).toBe('select');
  expect(config.source).toBe('stocks.dim_stock.ticker');
});
```

### Integration Tests

```bash
# Start backend
uvicorn de_funk.api.main:app --port 8000 &

# Test from plugin
curl http://localhost:8000/api/domains
curl http://localhost:8000/api/dimensions/stocks/dim_stock.ticker
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"domain":"stocks","columns":["stocks.dim_stock.ticker"],"limit":5}'
```

### Manual Testing Checklist

- [ ] Plugin loads in Obsidian
- [ ] Settings tab shows API URL
- [ ] Sidebar shows filters from active note's frontmatter
- [ ] Switching notes updates sidebar with new note's filters
- [ ] Filter dropdowns populate with values from API
- [ ] ` ```exhibit ` renders Plotly chart in markdown note
- [ ] ` ```exhibit ` renders Plotly chart in Canvas text node
- [ ] Chart updates when frontmatter filter changes
- [ ] Exhibit-specific filters render inside exhibit UI
- [ ] Dynamic selectors change chart axes
- [ ] Multiple exhibits in same note share frontmatter filters
- [ ] Filter values persist when switching between notes
- [ ] Works with multiple notes open simultaneously

---

## Appendix: Dependencies

### Python (pyproject.toml additions)

```toml
[project.optional-dependencies]
api = [
    "fastapi>=0.109.0",
    "uvicorn[standard]>=0.27.0",
    "pydantic>=2.0",
]
```

### TypeScript (package.json)

```json
{
  "name": "obsidian-defunk",
  "version": "0.1.0",
  "description": "de_Funk data visualization for Obsidian",
  "main": "main.js",
  "scripts": {
    "dev": "node esbuild.config.mjs",
    "build": "node esbuild.config.mjs production"
  },
  "devDependencies": {
    "@types/node": "^16.18.0",
    "builtin-modules": "^3.3.0",
    "esbuild": "^0.19.0",
    "obsidian": "latest",
    "typescript": "^5.3.0"
  },
  "dependencies": {
    "plotly.js-dist-min": "^2.29.0",
    "yaml": "^2.3.0"
  }
}
```

---

## References

- [Original React Proposal (013)](./013-react-whiteboard-ui-overhaul.md)
- [Obsidian Plugin API Documentation](https://docs.obsidian.md/Plugins/Getting+started/Build+a+plugin)
- [Obsidian Canvas Format](https://jsoncanvas.org/)
- [Plotly.js Documentation](https://plotly.com/javascript/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
