# Markdown Notebook Parser Reference

**Parser for markdown-based analytics notebooks**

File: `app/notebook/parsers/markdown_parser.py`

---

## Overview

**MarkdownNotebookParser** parses markdown-based notebooks with YAML front matter, filter sections, and embedded exhibits. It enables **low-code analytics** by allowing users to write notebooks in plain markdown with minimal syntax.

### Key Features

- **YAML Front Matter**: Notebook metadata (title, description, models)
- **Filter Syntax**: `$filter${...}` blocks for dynamic filtering
- **Exhibit Syntax**: `$exhibits${...}` blocks for visualizations
- **Collapsible Sections**: HTML `<details>` tags for expandable content
- **Streamlined Axis Syntax**: `x:` and `y:` shortcuts instead of verbose configs
- **Error Handling**: Graceful degradation with error blocks
- **Content Blocks**: Structured representation of markdown + exhibits

### Design Philosophy

```
┌──────────────────┐
│ Markdown Notebook│
│  (plain text)    │
└────────┬─────────┘
         │
         ▼
  ┌──────────────┐
  │    Parser    │
  └──────┬───────┘
         │
         ▼
┌──────────────────┐
│ NotebookConfig   │
│ (structured data)│
└──────────────────┘
```

**Problem Solved:** Traditional notebook systems (Jupyter, etc.) require complex JSON or Python API. Markdown notebooks let analysts write notebooks in **plain markdown** with minimal syntax, making analytics accessible to non-programmers.

---

## Class Definition

**File:** `app/notebook/parsers/markdown_parser.py:50-592`

```python
class MarkdownNotebookParser:
    """Parser for markdown-based notebooks."""

    # Regex patterns
    FRONT_MATTER_PATTERN = re.compile(
        r'^---\s*\n(.*?)\n---\s*\n',
        re.MULTILINE | re.DOTALL
    )
    FILTER_PATTERN = re.compile(
        r'\$filters?\$\{\s*\n(.*?)\n\}',
        re.MULTILINE | re.DOTALL
    )
    EXHIBIT_PATTERN = re.compile(
        r'\$exhibits?\$\{\s*\n(.*?)\n\}',
        re.MULTILINE | re.DOTALL
    )
    DETAILS_PATTERN = re.compile(
        r'<details>\s*<summary>(.*?)</summary>\s*(.*?)</details>',
        re.MULTILINE | re.DOTALL
    )
```

---

## Constructor

### `__init__(repo_root: Optional[Path] = None)`

Initialize parser.

**Parameters:**
- `repo_root` - Repository root path for resolving relative paths (optional, auto-detects if not provided)

**Example:**
```python
from app.notebook.parsers.markdown_parser import MarkdownNotebookParser
from pathlib import Path

# Auto-detect repo root
parser = MarkdownNotebookParser()

# Explicit repo root
parser = MarkdownNotebookParser(repo_root=Path('/home/user/de_Funk'))
```

---

## Public Methods

### `parse_file(notebook_path: str) -> NotebookConfig`

Parse a markdown notebook file.

**Parameters:**
- `notebook_path` - Path to markdown notebook file (absolute or relative to repo root)

**Returns:** NotebookConfig object

**Raises:** `ValueError` if file missing or invalid format

**Example:**
```python
# Parse notebook
config = parser.parse_file('configs/notebooks/stocks/analysis.md')

# Access parsed data
print(config.notebook.title)        # "Stock Analysis"
print(len(config.exhibits))         # 5
print(len(config._content_blocks))  # 12
```

---

### `parse_markdown(content: str) -> NotebookConfig`

Parse markdown content into NotebookConfig.

**Main parsing entry point** - can parse from string without file.

**Parameters:**
- `content` - Markdown content string

**Returns:** NotebookConfig object

**Raises:** `ValueError` if no YAML front matter found

**Parsing Process:**
1. Extract YAML front matter
2. Remove front matter from content
3. Extract filters using `$filter${...}` syntax
4. Remove filter blocks from content
5. Extract exhibits and build content structure
6. Build NotebookConfig from parsed components

**Example:**
```python
markdown = """---
id: stock-analysis
title: Stock Analysis
models: [stocks, company]
---

# Price Trends

$filter${
type: date_range
label: Date Range
column: trade_date
}

$exhibits${
type: line_chart
title: Price History
source: stocks.fact_stock_prices
x: trade_date
y: close
}
"""

config = parser.parse_markdown(markdown)
```

---

## Protected Methods

### `_extract_front_matter(content: str) -> Optional[Dict[str, Any]]`

Extract and parse YAML front matter.

**Parameters:**
- `content` - Full markdown content

**Returns:** Parsed YAML dict or `None` if no front matter

**Front Matter Format:**
```markdown
---
id: notebook-id
title: Notebook Title
description: Optional description
models: [stocks, company]
author: Author Name
created: 2024-01-01
tags: [stocks, analysis]
---
```

**Example:**
```python
content = """---
id: test
title: Test Notebook
---

Content here...
"""

front_matter = parser._extract_front_matter(content)
# {'id': 'test', 'title': 'Test Notebook'}
```

---

### `_extract_dynamic_filters(content: str) -> FilterCollection`

Extract filters using `$filter${...}` syntax.

**Parameters:**
- `content` - Markdown content

**Returns:** FilterCollection with all parsed filters

**Filter Syntax:**
```markdown
$filter${
type: date_range
label: Date Range
column: trade_date
default:
  start: 2024-01-01
  end: 2024-12-31
}

$filter${
type: multi_select
label: Tickers
column: ticker
source:
  type: dimension
  model: stocks
  dimension: dim_stock
  column: ticker
}
```

**Example:**
```python
content = """
$filter${
type: date_range
label: Date Range
column: trade_date
}
"""

filters = parser._extract_dynamic_filters(content)
# FilterCollection with 1 date_range filter
```

**Error Handling:** Logs error and continues parsing if filter YAML is invalid

---

### `_extract_exhibits(content: str) -> Tuple[List[Exhibit], List[Dict[str, Any]]]`

Extract exhibits from markdown content and handle collapsible sections.

**Main content parsing method** - builds structured representation of notebook.

**Parameters:**
- `content` - Markdown content (with front matter and filters removed)

**Returns:** Tuple of `(exhibits list, content_blocks list)`

**Content Block Types:**
- `{'type': 'markdown', 'content': '...'}` - Markdown text
- `{'type': 'exhibit', 'id': 'exhibit_0', 'exhibit': Exhibit(...)}` - Visualization
- `{'type': 'collapsible', 'summary': '...', 'content': [...]}` - Expandable section
- `{'type': 'error', 'message': '...', 'content': '...'}` - Parse error

**Process:**
1. Extract collapsible `<details>` tags and replace with placeholders
2. Find all `$exhibits${...}` blocks
3. Build content blocks alternating markdown and exhibits
4. Restore collapsible sections with inner exhibits parsed
5. Return exhibits list and structured content blocks

**Example:**
```python
content = """
# Analysis

Here's the price chart:

$exhibits${
type: line_chart
x: trade_date
y: close
}

<details>
<summary>Advanced Metrics</summary>

$exhibits${
type: metric_cards
metrics:
  - measure: avg_close_price
}

</details>
"""

exhibits, blocks = parser._extract_exhibits(content)

# exhibits = [Exhibit(...), Exhibit(...)]
# blocks = [
#     {'type': 'markdown', 'content': '# Analysis\n\nHere\'s the price chart:'},
#     {'type': 'exhibit', 'id': 'exhibit_0', ...},
#     {'type': 'collapsible', 'summary': 'Advanced Metrics', 'content': [
#         {'type': 'exhibit', 'id': 'exhibit_1', ...}
#     ]}
# ]
```

---

### `_add_content_with_collapsibles(...) -> int`

Add content blocks, processing any collapsible section placeholders.

**Parameters:**
- `content` - Content string with collapsible placeholders
- `collapsible_sections` - Dict of placeholder → section data
- `content_blocks` - List to append blocks to (modified in place)
- `exhibits` - List to append exhibits to (modified in place)
- `exhibit_counter` - Current exhibit counter

**Returns:** Updated exhibit counter

**Process:**
1. Split content by collapsible placeholders
2. Add markdown parts
3. For collapsible sections:
   - Parse inner content for exhibits
   - Extract exhibits from inner content
   - Build nested content blocks
   - Add collapsible block with inner content
4. Return updated counter

---

### `_parse_exhibit(exhibit_yaml: str, exhibit_id: str) -> Exhibit`

Parse exhibit YAML into Exhibit object.

**Main exhibit parsing method** with streamlined syntax support.

**Parameters:**
- `exhibit_yaml` - YAML content from `$exhibits${...}` block
- `exhibit_id` - Unique ID for exhibit (e.g., `'exhibit_0'`)

**Returns:** Exhibit object

**Raises:** Exception if YAML parsing or validation fails

**Streamlined Syntax:**

**Shorthand Axis Syntax:**
```yaml
# Instead of:
x_axis:
  dimension: trade_date
  label: Trade Date
y_axis:
  measure: close
  label: Close Price

# Use:
x: trade_date
x_label: Trade Date
y: close
y_label: Close Price
```

**Full vs Shorthand:**
```yaml
# Shorthand (common case)
type: line_chart
x: trade_date
y: close
color: ticker

# Full (advanced case)
type: line_chart
x_axis:
  dimension: trade_date
  label: Trade Date
  scale: linear
y_axis:
  measure: close
  label: Close Price
  scale: log
color_by: ticker
```

**Dual Axis Charts:**
```yaml
type: line_chart
x: trade_date
y: close        # Left axis
y2: volume      # Right axis
y_label: Price
y2_label: Volume
```

**Metric Cards:**
```yaml
type: metric_cards
metrics:
  - measure: avg_close_price
    label: Average Price
    aggregation: avg
  - measure: total_volume
    label: Total Volume
    aggregation: sum
```

**Tables:**
```yaml
type: table
source: stocks.fact_stock_prices
columns: [ticker, trade_date, close, volume]
sortable: true
pagination: true
page_size: 50
download: true
```

---

### `_build_config(...) -> NotebookConfig`

Build NotebookConfig from parsed components.

**Parameters:**
- `front_matter` - Parsed YAML front matter
- `filter_collection` - Parsed filters
- `exhibits` - List of Exhibit objects
- `content_blocks` - Structured content blocks

**Returns:** Complete NotebookConfig object

**Process:**
1. Build NotebookMetadata from front matter
2. Build GraphConfig from models list
3. Build simple layout (one section per exhibit)
4. Assemble NotebookConfig with all components
5. Attach content blocks and filter collection

---

## Data Structures

### MarkdownNotebook

**File:** `app/notebook/parsers/markdown_parser.py:42-47`

Parsed markdown notebook structure (internal).

```python
@dataclass
class MarkdownNotebook:
    front_matter: Dict[str, Any]
    filters: Dict[str, Variable]
    exhibits: List[Tuple[str, Exhibit]]
    content_blocks: List[Dict[str, Any]]
```

---

## Supported Exhibit Types

| Exhibit Type | Description | Key Fields |
|-------------|-------------|------------|
| `line_chart` | Time series line chart | `x`, `y`, `color` |
| `bar_chart` | Categorical bar chart | `x`, `y`, `color` |
| `scatter_plot` | Scatter plot | `x`, `y`, `color`, `size` |
| `area_chart` | Area chart | `x`, `y`, `color` |
| `metric_cards` | Metric display cards | `metrics` |
| `table` | Data table | `columns`, `sortable`, `pagination` |
| `heatmap` | Heatmap visualization | `x`, `y`, `color` |
| `histogram` | Distribution histogram | `x`, `bins` |

---

## Supported Filter Types

| Filter Type | Description | Config Fields |
|------------|-------------|---------------|
| `date_range` | Date range selector | `column`, `default.start`, `default.end` |
| `multi_select` | Multiple value selection | `column`, `source`, `options` |
| `single_select` | Single value selection | `column`, `source`, `options` |
| `text_input` | Free text input | `column`, `default` |
| `number_range` | Numeric range | `column`, `min`, `max`, `step` |
| `boolean` | True/False toggle | `column`, `default` |

---

## Usage Patterns

### Basic Notebook

```markdown
---
id: simple-analysis
title: Simple Analysis
models: [stocks]
---

# Price Analysis

This notebook analyzes stock prices.

$filter${
type: date_range
label: Date Range
column: trade_date
default:
  start: 2024-01-01
  end: 2024-12-31
}

$exhibits${
type: line_chart
title: Price Over Time
source: stocks.fact_stock_prices
x: trade_date
y: close
color: ticker
}
```

---

### Multi-Model Notebook

```markdown
---
id: cross-model
title: Cross-Model Analysis
models: [stocks, macro, company]
---

# Economic Impact on Stocks

$filter${
type: multi_select
label: Select Tickers
column: ticker
source:
  type: dimension
  model: stocks
  dimension: dim_stock
  column: ticker
}

$exhibits${
type: line_chart
title: Stock Prices
source: stocks.fact_stock_prices
x: trade_date
y: close
color: ticker
}

$exhibits${
type: line_chart
title: Unemployment Rate
source: macro.fact_unemployment
x: date
y: unemployment_rate
}
```

---

### Collapsible Sections

```markdown
---
id: advanced
title: Advanced Analysis
models: [stocks]
---

# Main Analysis

$exhibits${
type: line_chart
x: trade_date
y: close
}

<details>
<summary>Advanced Metrics</summary>

## Detailed Metrics

$exhibits${
type: metric_cards
metrics:
  - measure: avg_close_price
  - measure: max_volume
}

$exhibits${
type: table
columns: [ticker, trade_date, close, volume]
pagination: true
}

</details>
```

---

### Dual Axis Chart

```markdown
$exhibits${
type: line_chart
title: Price and Volume
x: trade_date
y: close
y_label: Price
y2: volume
y2_label: Volume
}
```

---

### Interactive Table

```markdown
$exhibits${
type: table
title: Price Data
source: stocks.fact_stock_prices
columns: [ticker, trade_date, open, high, low, close, volume]
sortable: true
pagination: true
page_size: 50
download: true
searchable: true
}
```

---

### Metric Cards

```markdown
$exhibits${
type: metric_cards
title: Key Metrics
metrics:
  - measure: avg_close_price
    label: Average Price
    aggregation: avg
  - measure: total_volume
    label: Total Volume
    aggregation: sum
  - measure: price_change
    label: Price Change
    aggregation: change
}
```

---

## Parsing Flow

```
1. parse_file() or parse_markdown()
   ↓
2. _extract_front_matter()
   - Extract YAML metadata
   ↓
3. _extract_dynamic_filters()
   - Parse $filter${} blocks
   - Build FilterCollection
   ↓
4. _extract_exhibits()
   - Find <details> tags, replace with placeholders
   - Find $exhibits${} blocks
   - Parse each exhibit
   - Build content_blocks structure
   - Restore collapsible sections
   ↓
5. _build_config()
   - Build NotebookMetadata
   - Build GraphConfig
   - Build layout
   - Assemble NotebookConfig
   ↓
6. Return NotebookConfig
```

---

## Error Handling

### Missing Front Matter

**Error:** `ValueError: Markdown notebook must have YAML front matter`

**Cause:** Notebook doesn't start with `---\n...\n---`

**Solution:** Add front matter:
```markdown
---
id: my-notebook
title: My Notebook
models: [stocks]
---
```

---

### Invalid YAML

**Error:** YAML parsing error

**Cause:** Malformed YAML in front matter or exhibits

**Solution:** Validate YAML syntax:
```yaml
# Bad (missing quotes)
title: Price Analysis: Q1 2024

# Good (quotes around value with colon)
title: "Price Analysis: Q1 2024"
```

---

### Exhibit Parse Error

**Behavior:** Error block inserted in content

**Cause:** Invalid exhibit YAML

**Result:**
```python
{
    'type': 'error',
    'message': 'Error parsing exhibit: ...',
    'content': '<invalid YAML>'
}
```

**Solution:** Check exhibit YAML syntax and required fields

---

### Invalid Exhibit Type

**Error:** `ValueError: 'invalid_type' is not a valid ExhibitType`

**Cause:** Unknown exhibit type

**Solution:** Use supported types: `line_chart`, `bar_chart`, `table`, `metric_cards`, etc.

---

## Best Practices

1. **Always include front matter**: Required for all notebooks
2. **Use streamlined syntax**: `x:` and `y:` instead of `x_axis:`, `y_axis:`
3. **Add labels**: Make charts readable with `x_label:` and `y_label:`
4. **Use collapsible sections**: Organize complex notebooks with `<details>`
5. **Add filters early**: Place filters at top of notebook before exhibits
6. **Document with markdown**: Mix exhibits with explanatory text
7. **Test incrementally**: Parse after each section to catch errors early

---

## Regex Patterns

### Front Matter

**Pattern:** `^---\s*\n(.*?)\n---\s*\n`

**Matches:**
```markdown
---
id: test
title: Test
---
```

---

### Filter Blocks

**Pattern:** `\$filters?\$\{\s*\n(.*?)\n\}`

**Matches:**
```markdown
$filter${
type: date_range
column: trade_date
}

$filters${
type: multi_select
column: ticker
}
```

---

### Exhibit Blocks

**Pattern:** `\$exhibits?\$\{\s*\n(.*?)\n\}`

**Matches:**
```markdown
$exhibit${
type: line_chart
x: date
y: value
}

$exhibits${
type: table
columns: [a, b, c]
}
```

---

### Details Tags

**Pattern:** `<details>\s*<summary>(.*?)</summary>\s*(.*?)</details>`

**Matches:**
```html
<details>
<summary>Section Title</summary>
Content here...
</details>
```

---

## Integration with UI

Parsed notebooks are rendered by the Streamlit UI:

```python
# Parse notebook
from app.notebook.parsers.markdown_parser import MarkdownNotebookParser

parser = MarkdownNotebookParser()
config = parser.parse_file('configs/notebooks/stocks/analysis.md')

# Render in Streamlit
from app.notebook.exhibits.renderer import ExhibitRenderer

renderer = ExhibitRenderer(session, config)

# Render content blocks
for block in config._content_blocks:
    if block['type'] == 'markdown':
        st.markdown(block['content'])
    elif block['type'] == 'exhibit':
        renderer.render_exhibit(block['exhibit'])
    elif block['type'] == 'collapsible':
        with st.expander(block['summary']):
            for inner_block in block['content']:
                # Render inner blocks...
```

---

## Related Documentation

- [Notebook Schema](../schemas/notebook-schema.md) - NotebookConfig structure
- [Filter System](filter-engine.md) - Dynamic filtering
- [Exhibit Renderer](exhibit-renderer.md) - Visualization rendering
- [Streamlit App](streamlit-app.md) - UI integration
- [YAML Configuration](../03-model-framework/yaml-configuration.md) - YAML syntax
