# Proposal: Exhibit Grid Layouts

**Status**: Draft
**Author**: Claude
**Date**: 2025-12-11
**Priority**: Medium

---

## Summary

This proposal introduces a grid layout system for exhibits in markdown notebooks, allowing users to arrange multiple exhibits in configurable grid patterns (2x2, 1x2, 2x1, 3 columns, etc.). The system integrates naturally with the existing `$exhibits${}` syntax while providing intuitive visual grouping capabilities.

---

## Motivation

### Current State

Exhibits currently render sequentially in full-width rows:

```
┌─────────────────────────────────────────────┐
│              Exhibit 1 (full width)          │
└─────────────────────────────────────────────┘
┌─────────────────────────────────────────────┐
│              Exhibit 2 (full width)          │
└─────────────────────────────────────────────┘
┌─────────────────────────────────────────────┐
│              Exhibit 3 (full width)          │
└─────────────────────────────────────────────┘
```

### Problems

1. **Space inefficiency**: Small charts (like KPI cards, mini sparklines) don't need full width
2. **Related data separation**: Comparing two charts requires scrolling between them
3. **Dashboard-style layouts impossible**: Cannot create side-by-side comparisons
4. **Unused schema fields**: `LayoutConfig` and `Section.columns` exist but are not implemented

### Desired State

```
┌──────────────────────┬──────────────────────┐
│      Exhibit 1       │      Exhibit 2       │
└──────────────────────┴──────────────────────┘
┌─────────────────────────────────────────────┐
│              Exhibit 3 (full width)          │
└─────────────────────────────────────────────┘
┌───────────────┬───────────────┬─────────────┐
│   Exhibit 4   │   Exhibit 5   │  Exhibit 6  │
└───────────────┴───────────────┴─────────────┘
```

---

## Detailed Design

### Design Philosophy

1. **Markdown-first**: Syntax should be readable as plain markdown
2. **Progressive enhancement**: Works without layouts (backward compatible)
3. **Minimal learning curve**: Intuitive for existing users
4. **Flexible but constrained**: Support common patterns, not arbitrary CSS

### Proposed Syntax Options

After evaluating three approaches, **Option A (Grid Block)** is recommended.

#### Option A: Grid Block (Recommended)

Wrap consecutive exhibits in a `$grid${}` block:

```yaml
$grid${
  columns: 2
  gap: md
}

$exhibits${
  type: line_chart
  source: stocks.fact_stock_prices
  x: trade_date
  y: close
  title: Price Trend
}

$exhibits${
  type: bar_chart
  source: stocks.fact_stock_prices
  x: trade_date
  y: volume
  title: Volume
}

$/grid$
```

**Pros:**
- Clear visual boundary for grouped exhibits
- Explicit start/end markers
- Grid properties separate from exhibit properties
- Supports non-uniform layouts (span configuration)

**Cons:**
- New syntax element to learn
- Slightly more verbose

#### Option B: Inline Layout Property

Add layout hints directly to exhibits:

```yaml
$exhibits${
  type: line_chart
  title: Price Trend
  layout: {row: 1, col: 1, colspan: 1}
}

$exhibits${
  type: bar_chart
  title: Volume
  layout: {row: 1, col: 2, colspan: 1}
}
```

**Pros:**
- No new syntax element
- Each exhibit is self-contained

**Cons:**
- Requires coordination across exhibits (row/col numbering)
- No visual grouping in markdown source
- Error-prone (what if row numbers conflict?)

#### Option C: Named Grid Groups

Reference a grid by ID:

```yaml
$grid${
  id: comparison_grid
  columns: 2
}

$exhibits${
  type: line_chart
  grid: comparison_grid
}

$exhibits${
  type: bar_chart
  grid: comparison_grid
}
```

**Pros:**
- Exhibits can be non-adjacent in markdown

**Cons:**
- Disconnects visual structure from markdown order
- More complex mental model
- Harder to edit

### Recommended Approach: Option A with Enhancements

```yaml
# Basic 2-column grid (exhibits fill left-to-right)
$grid${
  columns: 2
}
$exhibits${ ... }
$exhibits${ ... }
$/grid$

# 3-column grid with custom gap
$grid${
  columns: 3
  gap: lg
}
$exhibits${ ... }
$exhibits${ ... }
$exhibits${ ... }
$/grid$

# Custom column widths (ratios)
$grid${
  columns: [2, 1]  # First column 2x wider than second
}
$exhibits${ ... }  # 66% width
$exhibits${ ... }  # 33% width
$/grid$

# Multi-row with spanning
$grid${
  columns: 2
  rows:
    - [1, 1]      # Row 1: two equal columns
    - [2]         # Row 2: one spanning both columns
}
$exhibits${ ... }  # Row 1, Col 1
$exhibits${ ... }  # Row 1, Col 2
$exhibits${ ... }  # Row 2, spans both
$/grid$
```

### Pre-defined Layout Templates

For common patterns, provide shorthand templates:

```yaml
$grid${
  template: 2x2      # 4 exhibits in 2x2 grid
}

$grid${
  template: 1-2      # 1 on top, 2 below
}

$grid${
  template: 2-1      # 2 on top, 1 below
}

$grid${
  template: 2-1-2    # 2 top, 1 middle, 2 bottom
}

$grid${
  template: sidebar  # 1 large + 1 narrow sidebar
}
```

**Template Definitions:**

| Template | Pattern | Description |
|----------|---------|-------------|
| `2x2` | `[[1,1],[1,1]]` | 4 equal cells |
| `1-2` | `[[2],[1,1]]` | 1 full-width, 2 below |
| `2-1` | `[[1,1],[2]]` | 2 on top, 1 full-width |
| `2-1-2` | `[[1,1],[2],[1,1]]` | 5 exhibits in 3 rows |
| `3col` | `[[1,1,1]]` | 3 equal columns |
| `sidebar` | `[[2,1]]` | 2:1 ratio (main + sidebar) |
| `sidebar-left` | `[[1,2]]` | 1:2 ratio (sidebar + main) |

### Schema Changes

#### New Dataclasses (`app/notebook/schema.py`)

```python
from dataclasses import dataclass, field
from typing import List, Optional, Union
from enum import Enum


class GridGap(Enum):
    """Grid gap size options."""
    NONE = "none"
    SM = "sm"      # 0.5rem
    MD = "md"      # 1rem (default)
    LG = "lg"      # 1.5rem
    XL = "xl"      # 2rem


class GridTemplate(Enum):
    """Pre-defined grid layout templates."""
    TWO_BY_TWO = "2x2"
    ONE_TWO = "1-2"
    TWO_ONE = "2-1"
    TWO_ONE_TWO = "2-1-2"
    THREE_COL = "3col"
    SIDEBAR = "sidebar"
    SIDEBAR_LEFT = "sidebar-left"
    CUSTOM = "custom"


@dataclass
class GridConfig:
    """
    Configuration for exhibit grid layout.

    Supports multiple specification modes:
    1. Simple columns: columns=2 (equal width)
    2. Column ratios: columns=[2, 1] (2:1 ratio)
    3. Row definitions: rows=[[1,1], [2]] (custom spans)
    4. Templates: template="2x2" (pre-defined patterns)
    """
    # Column specification
    columns: Union[int, List[int]] = 2  # Number or ratio list

    # Row definitions (optional, for complex layouts)
    # Each row is a list of column spans, e.g., [[1,1], [2]] = 2 cols then 1 spanning
    rows: Optional[List[List[int]]] = None

    # Pre-defined template (overrides columns/rows if set)
    template: Optional[GridTemplate] = None

    # Styling
    gap: GridGap = GridGap.MD
    align_items: str = "stretch"  # stretch, start, center, end
    min_height: Optional[int] = None  # Minimum row height in pixels

    # Identification
    id: Optional[str] = None  # Optional grid identifier

    def get_column_spec(self) -> List[float]:
        """
        Convert columns config to Streamlit column ratios.

        Returns:
            List of floats for st.columns()
        """
        if self.template:
            return self._template_to_columns()

        if isinstance(self.columns, int):
            return [1.0] * self.columns

        # Normalize ratios to sum to 1.0
        total = sum(self.columns)
        return [c / total for c in self.columns]

    def get_row_specs(self) -> List[List[float]]:
        """
        Get row specifications for multi-row layouts.

        Returns:
            List of row specs, each row is a list of column ratios
        """
        if self.template:
            return self._template_to_rows()

        if self.rows:
            return [
                [c / sum(row) for c in row]
                for row in self.rows
            ]

        # Single row with column spec
        return [self.get_column_spec()]

    def _template_to_rows(self) -> List[List[float]]:
        """Convert template to row specifications."""
        templates = {
            GridTemplate.TWO_BY_TWO: [[0.5, 0.5], [0.5, 0.5]],
            GridTemplate.ONE_TWO: [[1.0], [0.5, 0.5]],
            GridTemplate.TWO_ONE: [[0.5, 0.5], [1.0]],
            GridTemplate.TWO_ONE_TWO: [[0.5, 0.5], [1.0], [0.5, 0.5]],
            GridTemplate.THREE_COL: [[0.333, 0.333, 0.334]],
            GridTemplate.SIDEBAR: [[0.667, 0.333]],
            GridTemplate.SIDEBAR_LEFT: [[0.333, 0.667]],
        }
        return templates.get(self.template, [[0.5, 0.5]])


@dataclass
class GridBlock:
    """
    A grid block containing multiple exhibits.

    Represents a parsed $grid${}..$/grid$ block from markdown.
    """
    config: GridConfig
    exhibit_ids: List[str] = field(default_factory=list)
    _start_index: int = 0  # Position in content_blocks
    _end_index: int = 0
```

#### Update Existing LayoutConfig

```python
@dataclass
class LayoutConfig:
    """Layout configuration for exhibits (updated)."""
    columns: Optional[int] = None
    rows: Optional[int] = None
    # NEW: Grid membership
    grid_id: Optional[str] = None  # ID of parent grid
    grid_position: Optional[int] = None  # Position within grid (0-indexed)
```

### Parser Changes (`app/notebook/parsers/markdown_parser.py`)

Add new regex pattern and parsing logic:

```python
# New patterns for grid blocks
GRID_START_PATTERN = re.compile(
    r'\$grid\$\{\s*\n?(.*?)\n?\}',
    re.MULTILINE | re.DOTALL
)
GRID_END_PATTERN = re.compile(r'\$/grid\$', re.MULTILINE)


def _parse_grid_blocks(self, content: str) -> Tuple[str, List[GridBlock]]:
    """
    Parse grid blocks from markdown content.

    Returns:
        Tuple of (content with grid markers replaced, list of GridBlocks)
    """
    grids = []

    # Find matching $grid${}..$/grid$ pairs
    start_matches = list(GRID_START_PATTERN.finditer(content))
    end_matches = list(GRID_END_PATTERN.finditer(content))

    for start_match, end_match in zip(start_matches, end_matches):
        # Parse grid config YAML
        config_yaml = start_match.group(1)
        config_dict = yaml.safe_load(config_yaml) or {}

        # Create GridConfig
        grid_config = GridConfig(
            columns=config_dict.get('columns', 2),
            rows=config_dict.get('rows'),
            template=GridTemplate(config_dict['template'])
                     if 'template' in config_dict else None,
            gap=GridGap(config_dict.get('gap', 'md')),
            id=config_dict.get('id'),
        )

        # Extract exhibits between start and end
        grid_content = content[start_match.end():end_match.start()]
        exhibit_matches = list(EXHIBIT_PATTERN.finditer(grid_content))

        grid_block = GridBlock(
            config=grid_config,
            exhibit_ids=[],  # Populated during exhibit parsing
            _start_index=start_match.start(),
            _end_index=end_match.end(),
        )
        grids.append(grid_block)

    return content, grids
```

### Renderer Changes (`app/ui/components/markdown/`)

#### New File: `grid_renderer.py`

```python
"""
Grid layout renderer for exhibit groups.

Renders multiple exhibits in configurable grid patterns using
Streamlit's column system.
"""

import streamlit as st
from typing import List, Dict, Any, Callable
from app.notebook.schema import GridConfig, GridGap


# Gap size mappings (Streamlit doesn't have native gap, use container margins)
GAP_SIZES = {
    GridGap.NONE: 0,
    GridGap.SM: 5,
    GridGap.MD: 10,
    GridGap.LG: 15,
    GridGap.XL: 20,
}


def render_exhibit_grid(
    grid_config: GridConfig,
    exhibits: List[Dict[str, Any]],
    render_exhibit_fn: Callable[[Dict[str, Any]], None],
    notebook_session,
    connection,
):
    """
    Render a group of exhibits in a grid layout.

    Args:
        grid_config: Grid configuration (columns, rows, gap, etc.)
        exhibits: List of exhibit blocks to render
        render_exhibit_fn: Function to render a single exhibit
        notebook_session: NotebookSession for data retrieval
        connection: DataConnection for pandas conversion
    """
    row_specs = grid_config.get_row_specs()
    gap = GAP_SIZES.get(grid_config.gap, 10)

    # Flatten exhibits into iterator
    exhibit_iter = iter(exhibits)

    # Apply gap styling via container
    with st.container():
        if gap > 0:
            st.markdown(
                f'<style>.grid-row {{ margin-bottom: {gap}px; }}</style>',
                unsafe_allow_html=True
            )

        for row_idx, row_spec in enumerate(row_specs):
            # Create columns for this row
            cols = st.columns(row_spec, gap="small")

            for col_idx, col in enumerate(cols):
                try:
                    exhibit_block = next(exhibit_iter)
                    with col:
                        render_exhibit_fn(
                            exhibit_block,
                            notebook_session,
                            connection
                        )
                except StopIteration:
                    # No more exhibits, leave remaining cells empty
                    with col:
                        st.empty()
                    break


def render_simple_grid(
    columns: int,
    exhibits: List[Dict[str, Any]],
    render_exhibit_fn: Callable,
    notebook_session,
    connection,
):
    """
    Render exhibits in a simple N-column grid.

    Exhibits flow left-to-right, top-to-bottom.

    Args:
        columns: Number of columns
        exhibits: List of exhibit blocks
        render_exhibit_fn: Render function
        notebook_session: Session
        connection: Connection
    """
    # Calculate number of rows needed
    num_exhibits = len(exhibits)
    num_rows = (num_exhibits + columns - 1) // columns

    exhibit_iter = iter(exhibits)

    for row in range(num_rows):
        cols = st.columns(columns)
        for col in cols:
            try:
                exhibit_block = next(exhibit_iter)
                with col:
                    render_exhibit_fn(
                        exhibit_block,
                        notebook_session,
                        connection
                    )
            except StopIteration:
                break
```

#### Update `flat_renderer.py`

```python
def render_flat_notebook(
    content_blocks: List[Dict[str, Any]],
    notebook_session,
    connection,
    editable: bool = False,
    # ... existing params ...
    grid_blocks: Optional[List[GridBlock]] = None,  # NEW
):
    """Render notebook with grid support."""

    # Build grid membership map
    grid_map = _build_grid_map(content_blocks, grid_blocks)

    # Track which blocks are rendered via grids
    rendered_in_grid = set()

    for block in visible_blocks:
        block_id = block['_flat_id']

        # Check if block starts a grid
        if block_id in grid_map['grid_starts']:
            grid_info = grid_map['grid_starts'][block_id]

            # Collect all exhibits in this grid
            grid_exhibits = [
                b for b in visible_blocks
                if b.get('_flat_id') in grid_info['exhibit_ids']
            ]

            # Render the grid
            render_exhibit_grid(
                grid_info['config'],
                grid_exhibits,
                _render_block_content,
                notebook_session,
                connection,
            )

            # Mark all grid exhibits as rendered
            rendered_in_grid.update(grid_info['exhibit_ids'])
            continue

        # Skip if already rendered in a grid
        if block_id in rendered_in_grid:
            continue

        # Normal row rendering
        render_flat_row(block, notebook_session, connection, ...)
```

### File Structure Changes

```
app/ui/components/markdown/
├── grid_renderer.py          # NEW: Grid rendering logic
├── flat_renderer.py          # MODIFIED: Grid awareness
├── parser.py                 # MODIFIED: Grid parsing
└── blocks/
    └── grid.py               # NEW: Grid block handling
```

### Responsive Behavior

Grids should adapt to screen size:

```python
def get_responsive_columns(base_columns: int, viewport_width: int) -> int:
    """
    Adjust column count for viewport width.

    Args:
        base_columns: Desired number of columns
        viewport_width: Current viewport width in pixels

    Returns:
        Adjusted column count
    """
    if viewport_width < 768:  # Mobile
        return min(base_columns, 1)
    elif viewport_width < 1024:  # Tablet
        return min(base_columns, 2)
    else:  # Desktop
        return base_columns
```

**Note**: Streamlit doesn't expose viewport width directly. Options:
1. Use CSS media queries for column collapse
2. Add a "mobile mode" toggle in UI
3. Accept fixed layouts (simplest)

---

## User Experience

### Writing Grid Layouts

**Simple Side-by-Side:**
```markdown
## Comparison View

$grid${
  columns: 2
}

$exhibits${
  type: line_chart
  title: Price
  source: stocks.fact_stock_prices
  x: trade_date
  y: close
}

$exhibits${
  type: bar_chart
  title: Volume
  source: stocks.fact_stock_prices
  x: trade_date
  y: volume
}

$/grid$
```

**Dashboard Layout (2x2):**
```markdown
## Dashboard

$grid${
  template: 2x2
  gap: lg
}

$exhibits${
  type: metric_cards
  metrics: [{column: close, label: "Price"}]
}

$exhibits${
  type: metric_cards
  metrics: [{column: volume, label: "Volume"}]
}

$exhibits${
  type: line_chart
  title: Trend
}

$exhibits${
  type: bar_chart
  title: Distribution
}

$/grid$
```

**Hero Chart + Details:**
```markdown
## Overview

$grid${
  template: 1-2
}

$exhibits${
  type: line_chart
  title: Main Price Chart
  height: 400
}

$exhibits${
  type: metric_cards
  title: Key Stats
}

$exhibits${
  type: data_table
  title: Recent Trades
  page_size: 5
}

$/grid$
```

### Error Handling

```markdown
<!-- Too few exhibits for template -->
$grid${
  template: 2x2  # Expects 4 exhibits
}
$exhibits${ ... }  # Only 1
$/grid$

<!-- Result: Warning shown, single exhibit renders full-width -->
```

### Editing Grids in UI

When editing mode is enabled:
1. Grid blocks show a dotted border around grouped exhibits
2. "Edit Grid" button allows changing columns/template
3. Drag-and-drop reordering within grid (future enhancement)

---

## Alternatives Considered

### Alternative 1: CSS Grid/Flexbox Classes

Add CSS classes to exhibits for layout:

```yaml
$exhibits${
  type: line_chart
  class: "col-6"  # Bootstrap-style
}
```

**Rejected**: Requires CSS knowledge, not markdown-native, harder to maintain.

### Alternative 2: Section-Based Layouts

Use existing `Section` objects for grouping:

```yaml
---
layout:
  sections:
    - title: Comparison
      exhibits: [exhibit_0, exhibit_1]
      columns: 2
---
```

**Rejected**: Requires exhibit ID references, doesn't match markdown flow.

### Alternative 3: Implicit Grid Detection

Auto-detect adjacent same-type exhibits and grid them:

```markdown
<!-- These would auto-grid -->
$exhibits${type: metric_cards}
$exhibits${type: metric_cards}
$exhibits${type: metric_cards}
```

**Rejected**: Too magical, unexpected behavior, no user control.

---

## Impact

### Benefits

1. **Better data visualization**: Side-by-side comparisons
2. **Dashboard capabilities**: Create overview pages
3. **Space efficiency**: Small charts don't waste vertical space
4. **User expectation**: Modern BI tools support layouts
5. **Leverage existing code**: LayoutConfig, Section.columns defined but unused

### Drawbacks

1. **Learning curve**: New syntax to learn
2. **Complexity**: Grid configuration can be confusing
3. **Responsive challenges**: Streamlit has limited responsive support
4. **Testing burden**: Many layout combinations to test

### Breaking Changes

**None** - This is purely additive. Existing notebooks work unchanged.

---

## Implementation Plan

### Phase 1: Core Grid System (MVP)

**Files to modify:**
- `app/notebook/schema.py` - Add GridConfig, GridBlock dataclasses
- `app/notebook/parsers/markdown_parser.py` - Parse $grid$ blocks
- `app/ui/components/markdown/grid_renderer.py` - NEW: Render grids
- `app/ui/components/markdown/flat_renderer.py` - Integrate grid rendering

**Deliverables:**
- Simple N-column grids (`columns: 2`)
- Gap configuration
- Basic template support (`2x2`, `1-2`, `2-1`)

**Estimated scope:** ~400 lines new code, ~100 lines modifications

### Phase 2: Advanced Layouts

**Features:**
- Custom column ratios (`columns: [2, 1]`)
- Multi-row definitions (`rows: [[1,1], [2]]`)
- All templates (`2-1-2`, `sidebar`, etc.)
- Row minimum heights

**Estimated scope:** ~200 lines additions

### Phase 3: UI Editing

**Features:**
- Grid editing in UI mode
- Visual grid border indicators
- Template selector dropdown

**Estimated scope:** ~300 lines

### Phase 4: Real-World Example - Financial Statements Dashboard

**Target**: Convert `configs/notebooks/examples/financial_statements_gt.md` to demonstrate grid layouts.

**Current State** (sequential layout):
```
┌─────────────────────────────────────────────┐
│         Income Statement (full width)        │
└─────────────────────────────────────────────┘
┌─────────────────────────────────────────────┐
│          Balance Sheet (full width)          │
└─────────────────────────────────────────────┘
┌─────────────────────────────────────────────┐
│        Cash Flow Statement (full width)      │
└─────────────────────────────────────────────┘
┌─────────────────────────────────────────────┐
│       Earnings Analysis (full width)         │
└─────────────────────────────────────────────┘
```

**Proposed State** (dashboard layout):
```
┌──────────────────────┬──────────────────────┐
│   Income Statement   │    Balance Sheet     │
│     (Great Table)    │    (Great Table)     │
└──────────────────────┴──────────────────────┘
┌──────────────────────┬──────────────────────┐
│  Cash Flow Statement │  Earnings Analysis   │
│     (Great Table)    │    (Great Table)     │
└──────────────────────┴──────────────────────┘
```

**Or Hero + Details layout:**
```
┌─────────────────────────────────────────────┐
│      Income Statement (full width hero)      │
└─────────────────────────────────────────────┘
┌──────────────────────┬──────────────────────┐
│    Balance Sheet     │  Cash Flow Statement │
└──────────────────────┴──────────────────────┘
┌─────────────────────────────────────────────┐
│      Earnings Analysis (full width)          │
└─────────────────────────────────────────────┘
```

**Implementation**: See [Financial Statements Grid Example](#financial-statements-grid-example) below.

**Deliverables:**
- Working grid layout in financial_statements_gt.md
- Documentation with real examples
- CSS polish for Great Tables in grids
- Responsive behavior for financial dashboards

**Estimated scope:** ~100 lines modifications to notebook, documentation updates

---

## Open Questions

1. **Should grids be nestable?**
   - Grid inside grid for complex layouts?
   - Recommendation: No, keep it simple initially

2. **How to handle exhibit height variations?**
   - Same-height rows (stretch)?
   - Natural height (start)?
   - Recommendation: Default to stretch, allow configuration

3. **Should grids work in collapsible sections?**
   - `<details>` wrapping a grid?
   - Recommendation: Yes, should work naturally

4. **What happens with measure/dimension selectors in grids?**
   - Each exhibit has its own selector?
   - Recommendation: Yes, independent selectors per exhibit

5. **Editor support for grid manipulation?**
   - Drag to reorder exhibits within grid?
   - Recommendation: Future enhancement, not MVP

---

## Testing Plan

### Unit Tests

```python
def test_grid_config_column_spec():
    """Test column specification parsing."""
    config = GridConfig(columns=3)
    assert config.get_column_spec() == [1/3, 1/3, 1/3]

    config = GridConfig(columns=[2, 1])
    assert config.get_column_spec() == [2/3, 1/3]

def test_grid_template_expansion():
    """Test template to row conversion."""
    config = GridConfig(template=GridTemplate.TWO_BY_TWO)
    rows = config.get_row_specs()
    assert len(rows) == 2
    assert rows[0] == [0.5, 0.5]

def test_grid_parsing():
    """Test grid block extraction from markdown."""
    content = '''
$grid${
  columns: 2
}
$exhibits${ type: line_chart }
$exhibits${ type: bar_chart }
$/grid$
'''
    grids = parser._parse_grid_blocks(content)
    assert len(grids) == 1
    assert grids[0].config.columns == 2
```

### Integration Tests

```python
def test_grid_rendering_streamlit():
    """Test grid renders correctly in Streamlit."""
    # Mock streamlit columns
    with patch('streamlit.columns') as mock_cols:
        render_simple_grid(2, exhibits, render_fn, session, conn)
        mock_cols.assert_called_with(2)

def test_notebook_with_grids():
    """Test full notebook with grid blocks."""
    notebook = load_notebook("test_grid_notebook.md")
    assert len(notebook.grid_blocks) == 1
    render_notebook(notebook)
    # Verify exhibits rendered in grid
```

### Manual Test Cases

1. Basic 2-column grid renders side-by-side
2. 2x2 template shows 4 exhibits in grid
3. Exhibits overflow to next row correctly
4. Grid inside `<details>` works
5. Edit mode shows grid boundaries
6. Missing exhibits show empty cells
7. Different exhibit types in same grid

---

## References

- [Streamlit Columns Documentation](https://docs.streamlit.io/library/api-reference/layout/st.columns)
- [CSS Grid Layout](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_grid_layout)
- [Existing LayoutConfig](../../../app/notebook/schema.py) - Lines 211-214
- [Flat Renderer](../../../app/ui/components/markdown/flat_renderer.py) - Current rendering

---

## Financial Statements Grid Example

This is the primary example based on the existing `configs/notebooks/examples/financial_statements_gt.md` notebook.

### Current Notebook (Before - Sequential Layout)

```markdown
---
id: financial_statements_gt
title: Company Financial Statements
models: [company, core]
---

# Financial Statement Analysis

## Income Statement
$exhibits${
  type: great_table
  source: company.fact_income_statement
  title: Consolidated Statement of Operations
  theme: financial
  ...
}

## Balance Sheet
$exhibits${
  type: great_table
  source: company.fact_balance_sheet
  title: Consolidated Balance Sheet
  ...
}

## Cash Flow Statement
$exhibits${
  type: great_table
  source: company.fact_cash_flow
  title: Consolidated Statement of Cash Flows
  ...
}

## Earnings Analysis
$exhibits${
  type: great_table
  source: company.fact_earnings
  title: Earnings History
  ...
}
```

### Proposed Notebook (After - Grid Layout)

**Option A: 2x2 Dashboard Grid**

```markdown
---
id: financial_statements_gt
title: Company Financial Statements
models: [company, core]
---

# Financial Statement Analysis

Select a company to view their financial statements in a dashboard layout.

$filter${
  id: ticker
  type: select
  multi: false
  label: Company
  source: {model: company, table: dim_company, column: ticker}
  default: AAPL
}

## Financial Overview

$grid${
  template: 2x2
  gap: lg
}

$exhibits${
  type: great_table
  source: company.fact_income_statement
  title: Income Statement
  theme: financial
  sort: {by: fiscal_date_ending, order: desc}
  columns:
    - {id: fiscal_date_ending, label: Period, format: date}
    - {id: total_revenue, label: Revenue, format: currency_millions}
    - {id: gross_profit, label: Gross Profit, format: currency_millions, style: {bold: true}}
    - {id: operating_income, label: Operating Income, format: currency_millions}
    - {id: net_income, label: Net Income, format: currency_millions, style: {bold: true}, conditional: {type: color_scale, palette: ['#ffcccc', '#ffffff', '#ccffcc'], domain: [-1000000000, 0, 10000000000]}}
  spanners:
    - {label: Revenue, columns: [total_revenue, gross_profit]}
    - {label: Bottom Line, columns: [operating_income, net_income]}
  source_note: "Amounts in millions USD"
  row_striping: true
}

$exhibits${
  type: great_table
  source: company.fact_balance_sheet
  title: Balance Sheet
  theme: financial
  sort: {by: fiscal_date_ending, order: desc}
  columns:
    - {id: fiscal_date_ending, label: Period, format: date}
    - {id: total_assets, label: Total Assets, format: currency_millions, style: {bold: true}}
    - {id: total_liabilities, label: Total Liabilities, format: currency_millions}
    - {id: total_shareholder_equity, label: Equity, format: currency_millions, style: {bold: true}}
  source_note: "Amounts in millions USD"
  row_striping: true
}

$exhibits${
  type: great_table
  source: company.fact_cash_flow
  title: Cash Flow
  theme: financial
  sort: {by: fiscal_date_ending, order: desc}
  columns:
    - {id: fiscal_date_ending, label: Period, format: date}
    - {id: operating_cashflow, label: Operating, format: currency_millions, style: {bold: true}}
    - {id: cashflow_from_investment, label: Investing, format: currency_millions}
    - {id: cashflow_from_financing, label: Financing, format: currency_millions}
    - {id: free_cash_flow, label: FCF, format: currency_millions, style: {bold: true}, conditional: {type: color_scale, palette: ['#ef4444', '#ffffff', '#22c55e'], domain: [-5000000000, 0, 20000000000]}}
  source_note: "Amounts in millions USD"
  row_striping: true
}

$exhibits${
  type: great_table
  source: company.fact_earnings
  title: Earnings
  theme: financial
  sort: {by: fiscal_date_ending, order: desc}
  columns:
    - {id: fiscal_date_ending, label: Period, format: date}
    - {id: reported_eps, label: EPS, format: currency}
    - {id: estimated_eps, label: Est. EPS, format: currency}
    - {id: surprise_percentage, label: Surprise %, format: percent, conditional: {type: color_scale, palette: ['#ef4444', '#fbbf24', '#22c55e'], domain: [-0.1, 0, 0.1]}}
  source_note: "EPS data from Alpha Vantage"
  row_striping: true
}

$/grid$
```

**Option B: Hero + Details Layout (1-2-1 pattern)**

For analysts who want to focus on the income statement with supporting details:

```markdown
## Financial Overview

$grid${
  rows:
    - [1]        # Income statement full width (hero)
    - [1, 1]     # Balance sheet + Cash flow side by side
    - [1]        # Earnings full width
  gap: lg
}

$exhibits${
  type: great_table
  source: company.fact_income_statement
  title: Consolidated Statement of Operations
  theme: financial
  # Full income statement config with all columns...
}

$exhibits${
  type: great_table
  source: company.fact_balance_sheet
  title: Balance Sheet Summary
  theme: financial
  # Condensed balance sheet columns for side-by-side...
}

$exhibits${
  type: great_table
  source: company.fact_cash_flow
  title: Cash Flow Summary
  theme: financial
  # Condensed cash flow columns for side-by-side...
}

$exhibits${
  type: great_table
  source: company.fact_earnings
  title: Earnings History
  theme: financial
  # Full earnings table...
}

$/grid$
```

**Option C: Three-Statement Model + Metrics**

Common financial analyst view with key metrics:

```markdown
## Quick Overview

$grid${
  columns: 4
  gap: sm
}

$exhibits${
  type: metric_cards
  source: company.fact_income_statement
  metrics:
    - {column: total_revenue, label: "Revenue", aggregation: last, format: "$,.0f"}
}

$exhibits${
  type: metric_cards
  source: company.fact_income_statement
  metrics:
    - {column: net_income, label: "Net Income", aggregation: last, format: "$,.0f"}
}

$exhibits${
  type: metric_cards
  source: company.fact_cash_flow
  metrics:
    - {column: free_cash_flow, label: "Free Cash Flow", aggregation: last, format: "$,.0f"}
}

$exhibits${
  type: metric_cards
  source: company.fact_balance_sheet
  metrics:
    - {column: total_shareholder_equity, label: "Equity", aggregation: last, format: "$,.0f"}
}

$/grid$

## Detailed Statements

$grid${
  template: 2x2
  gap: md
}

$exhibits${
  type: great_table
  source: company.fact_income_statement
  title: Income Statement
  ...
}

$exhibits${
  type: great_table
  source: company.fact_balance_sheet
  title: Balance Sheet
  ...
}

$exhibits${
  type: great_table
  source: company.fact_cash_flow
  title: Cash Flow
  ...
}

$exhibits${
  type: great_table
  source: company.fact_earnings
  title: Earnings
  ...
}

$/grid$
```

### Visual Comparison

**Before (Current):**
```
┌─────────────────────────────────────────────────────────────┐
│                    Income Statement                          │
│    (full width, tall, requires scroll to see next)          │
└─────────────────────────────────────────────────────────────┘
                              ↓ scroll
┌─────────────────────────────────────────────────────────────┐
│                      Balance Sheet                           │
│    (full width, can't compare to Income Statement)          │
└─────────────────────────────────────────────────────────────┘
                              ↓ scroll
┌─────────────────────────────────────────────────────────────┐
│                    Cash Flow Statement                       │
└─────────────────────────────────────────────────────────────┘
                              ↓ scroll
┌─────────────────────────────────────────────────────────────┐
│                    Earnings Analysis                         │
└─────────────────────────────────────────────────────────────┘
```

**After (2x2 Grid):**
```
┌────────────────────────────┬────────────────────────────────┐
│      Income Statement      │        Balance Sheet           │
│   ┌──────────────────┐    │   ┌──────────────────────┐    │
│   │ Period │ Revenue │    │   │ Period │ Assets │ Eq │    │
│   │ Q3'24  │ $94.9B  │    │   │ Q3'24  │ $352B │$56B│    │
│   │ Q2'24  │ $85.8B  │    │   │ Q2'24  │ $349B │$54B│    │
│   └──────────────────┘    │   └──────────────────────┘    │
└────────────────────────────┴────────────────────────────────┘
┌────────────────────────────┬────────────────────────────────┐
│     Cash Flow Statement    │      Earnings Analysis         │
│   ┌──────────────────┐    │   ┌────────────────────────┐  │
│   │ Period │ Op │ FCF│    │   │ Period│ EPS │ Est │ +/-│  │
│   │ Q3'24  │$27B│$22B│    │   │ Q3'24 │1.64 │1.60 │+2% │  │
│   │ Q2'24  │$25B│$20B│    │   │ Q2'24 │1.26 │1.35 │-7% │  │
│   └──────────────────┘    │   └────────────────────────┘  │
└────────────────────────────┴────────────────────────────────┘
```

### Benefits for Financial Analysis

1. **At-a-glance overview**: All 4 statements visible without scrolling
2. **Cross-statement comparison**: Easy to correlate revenue growth with asset changes
3. **Professional layout**: Matches investment banking presentation standards
4. **Flexible density**: Condensed columns for grid view, expanded for detail
5. **Great Tables integration**: Publication-quality formatting in grid cells
