# Collapsible Sections System

The collapsible sections system provides a way to organize notebook content into expandable/collapsible sections based on markdown headers.

## Overview

Headers in markdown notebooks automatically become collapsible toggle sections:
- `# H1` - Top-level sections (expanded by default)
- `## H2` - Nested under H1 sections
- `### H3` - Nested under H2 sections

## Features

### Toggle Containers
- Click section headers to expand/collapse content
- Expand/collapse all buttons (⊞/⊟) in the toolbar (right side)
- Nested sections maintain hierarchy

### Editing Capabilities
When edit mode is enabled:
- **Edit button (✏️)** - Edit section content including nested subsections
- **Delete button (🗑️)** - Remove section and its children
- **Add button (➕)** - Add new sections with header level selection (H1, H2, H3)
- Edit/delete buttons visible when section is collapsed (at top level)
- Nested section buttons appear inside the expanded toggle

### Exhibits in Sections
- Exhibits (`$exhibits${...}`) can be placed anywhere in the markdown
- When editing a section containing exhibits, they appear as `$exhibits${...}` syntax
- Exhibits are preserved when saving changes
- Error handling prevents exhibit errors from breaking the entire page

### Section Grouping
When editing a section:
- Editor shows full content including nested subsections and exhibits
- Changes preserve the header hierarchy
- Content-based save/delete ensures accuracy
- Fallback header-based matching for robust saves

## Usage

### Adding Sections
1. Click the ➕ button
2. Enter section title
3. Select header level (H1, H2, H3)
4. Click Add

### Editing Sections
1. Click the ✏️ button next to any section
2. Edit content in the text area (including nested content and exhibits)
3. Click Save to apply changes

### Adding Exhibits
Add exhibits using the `$exhibits${...}` syntax within any section:
```markdown
$exhibits${
  type: line_chart
  source: company.fact_prices
  x: trade_date
  y: close
  color: ticker
  title: Price Trends
}
```

### Deleting Sections
1. Click the 🗑️ button next to any section
2. Section and all nested content will be removed

## Implementation

### Key Components (v2.2 Modular Architecture)

The markdown rendering system has been split into a modular subpackage under `app/ui/components/markdown/`:

**Core Modules:**
- `renderer.py` (286 lines) - Main orchestrator, entry point
- `parser.py` (238 lines) - Markdown parsing and header extraction
- `styles.py` (142 lines) - CSS constants and styling
- `utils.py` (285 lines) - Utility functions

**Block Renderers** (`blocks/`):
- `text.py` - Markdown text block rendering
- `exhibit.py` - Data exhibit rendering
- `collapsible.py` - Collapsible section handling
- `error.py` - Error block display
- `header.py` - Notebook header rendering

**Section Editors** (`editors/`):
- `section_editor.py` - Section content editing
- `inline_editor.py` - Inline text editing
- `block_editor.py` - Block-level editing
- `insert_button.py` - New section insertion

**Toggle Component:**
- `toggle_container.py` - Custom component replacing st.expander
  - `ToggleContainer` class
  - `expand_all()` / `collapse_all()` functions
  - Toggle registry for state management

**State & Callbacks** (`app/ui/`):
- `state/session_state.py` - Session state management
- `callbacks/block_callbacks.py` - Block edit/delete callbacks

**`notebook_app_duckdb.py`** (thin orchestrator):
- Delegates to state and callback modules
- Uses modular markdown renderer

### Content-Based Operations
Edit and delete operations use content-based find/replace:
- Original content stored in session state
- Try exact content match first
- Fall back to header-based matching if needed
- Preserves exhibits and handles whitespace differences

### Error Handling
- Exhibit rendering wrapped in try/except
- Error blocks displayed without crashing the page
- Collapsible and unknown block types handled gracefully
- Main render functions protected with error boundaries

## Example Notebooks

**`configs/notebooks/example_nested_sections.md`**
- Nested header hierarchy (H1 > H2 > H3)
- Multiple nesting levels
- Edit/delete functionality

**`configs/notebooks/example_toggle_demo.md`**
- Basic toggle features
- Tables and formatting
- Edit mode usage

**`configs/notebooks/stock_analysis_dynamic.md`**
- Exhibits within sections
- Dynamic filters
- Collapsible details sections
