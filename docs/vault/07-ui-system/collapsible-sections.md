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
- Expand/collapse all buttons (⊞/⊟) in the toolbar
- Nested sections maintain hierarchy

### Editing Capabilities
When edit mode is enabled:
- **Edit button (✏️)** - Edit section content including nested subsections
- **Delete button (🗑️)** - Remove section and its children
- **Add button (➕)** - Add new sections with header level selection (H1, H2, H3)

### Section Grouping
When editing a section:
- Editor shows full content including nested subsections
- Changes preserve the header hierarchy
- Content-based save/delete ensures accuracy

## Usage

### Adding Sections
1. Click the ➕ button
2. Enter section title
3. Select header level (H1, H2, H3)
4. Click Add

### Editing Sections
1. Click the ✏️ button next to any section
2. Edit content in the text area
3. Click Save to apply changes

### Deleting Sections
1. Click the 🗑️ button next to any section
2. Section and all nested content will be removed

## Implementation

### Key Components

**`markdown_renderer.py`**
- `_split_markdown_by_headers()` - Splits content at header boundaries
- `_build_header_tree()` - Creates nested tree from headers
- `_render_nested_toggles()` - Renders collapsible sections
- `_gather_section_content()` - Collects section + children content

**`toggle_container.py`**
- `ToggleContainer` - Custom component replacing st.expander
- `expand_all()` / `collapse_all()` - Bulk operations
- Toggle registry for state management

### Content-Based Operations
Edit and delete operations use content-based find/replace:
- Original content stored in session state
- Find exact content in file and replace
- Avoids index mismatch issues from header splitting

## Example Notebooks

**`configs/notebooks/example_nested_sections.md`**
- Nested header hierarchy (H1 > H2 > H3)
- Multiple nesting levels
- Edit/delete functionality

**`configs/notebooks/example_toggle_demo.md`**
- Basic toggle features
- Tables and formatting
- Edit mode usage
