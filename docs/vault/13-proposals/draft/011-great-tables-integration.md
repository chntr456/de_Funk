# Proposal 011: Great Tables Integration & Enhanced Exhibit Architecture

**Status**: Draft
**Created**: 2025-12-10
**Author**: Claude (AI Assistant)

## Summary

Integrate Great Tables (`great_tables`) into the de_Funk exhibit architecture, establishing a unified pattern for all exhibit types with preset configurations, dynamic function calls for filter defaults, and row/column-based table specifications.

## Motivation

### Current Limitations

1. **Table rendering is basic** - `DATA_TABLE` uses Streamlit's native table with limited styling
2. **No publication-quality tables** - Missing features like spanners, conditional formatting, source notes
3. **Filter defaults are mostly static** - Only `DateResolver` supports dynamic values (`-30d`, `today`)
4. **Exhibit types are hard-coded** - Adding new types requires code changes in multiple places

### Goals

1. Add Great Tables as a first-class exhibit type
2. Create a unified exhibit preset system (type → default params)
3. Extend dynamic defaults to support function calls (`current_date()`, `current_date() + 30`)
4. Support row/column-based table configuration alongside dimension/measure paradigm

---

## Proposed Architecture

### 1. Exhibit Type Registry

Create a registry that maps exhibit types to their preset configurations:

```
configs/exhibits/
├── registry.yaml           # Type → renderer mapping
├── presets/
│   ├── great_table.yaml    # GT presets
│   ├── line_chart.yaml     # Plotly line chart presets
│   ├── bar_chart.yaml      # Plotly bar chart presets
│   ├── metric_cards.yaml   # Metric cards presets
│   └── data_table.yaml     # Basic table presets
```

**registry.yaml**:
```yaml
exhibit_types:
  great_table:
    renderer: app.ui.components.exhibits.great_table
    preset: presets/great_table.yaml
    requires: [great_tables]

  line_chart:
    renderer: app.ui.components.exhibits.line_chart
    preset: presets/line_chart.yaml
    requires: [plotly]

  bar_chart:
    renderer: app.ui.components.exhibits.bar_chart
    preset: presets/bar_chart.yaml
    requires: [plotly]

  data_table:
    renderer: app.ui.components.exhibits.data_table
    preset: presets/data_table.yaml
    requires: []

# Aliases for convenience
aliases:
  gt: great_table
  table: great_table
  chart: line_chart
```

### 2. Great Table Exhibit Configuration

**presets/great_table.yaml**:
```yaml
# Default parameters for Great Tables exhibits
defaults:
  theme: default              # default, dark, striped, minimal
  title: null
  subtitle: null
  source_note: null

  # Row configuration
  row_group_by: null          # Column to group rows
  row_striping: true
  row_dividers: false

  # Column configuration
  column_labels: {}           # {col: "Display Label"}
  column_formats: {}          # {col: format_spec}
  column_widths: {}           # {col: "150px"}

  # Spanners (grouped headers)
  spanners: []
  # - label: "Price Metrics"
  #   columns: [open, high, low, close]

  # Conditional formatting
  formatting_rules: []
  # - column: change_pct
  #   type: color_scale
  #   palette: [red, white, green]
  #   domain: [-0.1, 0, 0.1]

  # Footer
  footnotes: []
  source_notes: []

  # Export options
  export_html: false
  export_png: false

# Available format specs
format_specs:
  currency: "$#,##0.00"
  percent: "0.00%"
  number: "#,##0.00"
  integer: "#,##0"
  date: "%Y-%m-%d"
  datetime: "%Y-%m-%d %H:%M"
```

### 3. Enhanced Exhibit YAML Syntax

**Minimal configuration** (inherits all defaults):
```yaml
$exhibits${
  type: great_table
  source: stocks.fact_stock_prices
  columns: [ticker, trade_date, open, high, low, close, volume]
}
```

**With customization**:
```yaml
$exhibits${
  type: great_table
  source: stocks.fact_stock_prices
  title: Daily Stock Prices
  subtitle: Last 30 days

  # Row configuration
  rows:
    source_column: ticker       # What defines each row
    group_by: sector           # Optional grouping
    sort_by: trade_date
    sort_order: desc
    limit: 100

  # Column configuration
  columns:
    - id: ticker
      label: Symbol
      width: 80px

    - id: trade_date
      label: Date
      format: date

    - id: close
      label: Close Price
      format: currency

    - id: volume
      label: Volume
      format: integer

    - id: change_pct
      label: Change %
      format: percent
      conditional:
        type: color_scale
        palette: [red, white, green]
        domain: [-0.05, 0, 0.05]

  # Spanners
  spanners:
    - label: Price Data
      columns: [open, high, low, close]
    - label: Volume Metrics
      columns: [volume, avg_volume]

  # Footer
  source_note: "Data from Alpha Vantage API"
  footnotes:
    - column: change_pct
      text: "Calculated as (close - prev_close) / prev_close"
}
```

### 4. Dynamic Function Calls in Filters & Exhibits

Extend the current `DateResolver` to a more general `ExpressionResolver`:

**Supported expressions**:
```yaml
# Date functions
current_date()                    # Today's date
current_date() - 30              # 30 days ago (alias for -30d)
current_date() + 7               # 7 days from now
start_of_month()                 # First day of current month
end_of_month()                   # Last day of current month
start_of_quarter()               # First day of current quarter
start_of_year()                  # First day of current year
trading_day(-1)                  # Previous trading day (excludes weekends)

# Numeric functions
max(column)                      # Max value from data
min(column)                      # Min value from data
avg(column)                      # Average value

# Reference functions
first(column)                    # First value from data
last(column)                     # Last value (most recent)
distinct(column)                 # All distinct values
top_n(column, n)                 # Top N values by frequency
```

**Usage in filters**:
```yaml
$filter${
  id: trade_date
  type: date_range
  label: Date Range
  default:
    start: current_date() - 30   # Dynamic: 30 days ago
    end: current_date()          # Dynamic: today
}

$filter${
  id: forecast_horizon
  type: date_range
  label: Forecast Period
  default:
    start: current_date()
    end: current_date() + 90     # 90 days into future
}

$filter${
  id: ticker
  type: select
  multi: true
  default: top_n(market_cap, 10)  # Top 10 by market cap
}
```

**Usage in exhibits**:
```yaml
$exhibits${
  type: great_table
  source: stocks.fact_stock_prices
  title: "Stock Performance as of {{ current_date() }}"

  filters:
    trade_date:
      start: start_of_month()
      end: current_date()
}
```

### 5. Row/Column vs Dimension/Measure Paradigm

**Tables use row/column model**:
```yaml
$exhibits${
  type: great_table
  source: company.dim_company

  rows:
    source: company.dim_company    # What populates rows
    group_by: sector              # Row grouping

  columns:                        # Explicit column list
    - company_name
    - ticker
    - market_cap
    - sector
}
```

**Charts use dimension/measure model**:
```yaml
$exhibits${
  type: line_chart
  source: stocks.fact_stock_prices

  x: trade_date                   # Dimension (x-axis)
  y: [close, sma_20]             # Measures (y-axis)
  color: ticker                   # Grouping dimension
}
```

**Unified under the hood** - both resolve to the same data query:
```python
# ExhibitDataResolver handles both paradigms
def resolve_data(exhibit):
    if exhibit.type in TABLE_TYPES:
        return resolve_table_data(exhibit.rows, exhibit.columns)
    else:
        return resolve_chart_data(exhibit.x, exhibit.y, exhibit.color)
```

---

## Implementation Plan

### Phase 1: Expression Resolver (Foundation)

**New file**: `app/notebook/expressions/resolver.py`

```python
"""
Expression resolver for dynamic defaults in filters and exhibits.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any, Dict, Optional, Union
from dataclasses import dataclass

@dataclass
class ExpressionContext:
    """Context for resolving expressions."""
    current_date: date
    data_source: Optional[str] = None  # For data-dependent expressions
    session: Optional[Any] = None      # For querying data

class ExpressionResolver:
    """
    Resolves dynamic expressions in YAML configurations.

    Supports:
    - Date functions: current_date(), start_of_month(), etc.
    - Arithmetic: current_date() + 30, current_date() - 7
    - Data functions: max(column), min(column), top_n(column, n)
    - Legacy: "-30d", "today" (backwards compatible)
    """

    DATE_FUNCTION_PATTERN = re.compile(
        r'(current_date|start_of_month|end_of_month|start_of_quarter|'
        r'start_of_year|trading_day)\(\s*(-?\d*)?\s*\)'
    )

    ARITHMETIC_PATTERN = re.compile(
        r'(.+?)\s*([+-])\s*(\d+)'
    )

    DATA_FUNCTION_PATTERN = re.compile(
        r'(max|min|avg|first|last|distinct|top_n)\(\s*(\w+)(?:\s*,\s*(\d+))?\s*\)'
    )

    def __init__(self, context: Optional[ExpressionContext] = None):
        self.context = context or ExpressionContext(current_date=date.today())

    def resolve(self, expression: Any) -> Any:
        """Resolve an expression to its value."""
        if not isinstance(expression, str):
            return expression

        # Try legacy format first (-30d, today, etc.)
        legacy_result = self._resolve_legacy(expression)
        if legacy_result is not None:
            return legacy_result

        # Try date functions
        date_result = self._resolve_date_function(expression)
        if date_result is not None:
            return date_result

        # Try data functions (requires session)
        if self.context.session:
            data_result = self._resolve_data_function(expression)
            if data_result is not None:
                return data_result

        # Return as-is if no match
        return expression

    def _resolve_legacy(self, expr: str) -> Optional[date]:
        """Resolve legacy date expressions for backwards compatibility."""
        expr = expr.strip().lower()

        if expr == 'today':
            return self.context.current_date

        # -30d, -1w, -6m, -1y format
        match = re.match(r'^(-?\d+)([dwmy])$', expr)
        if match:
            value = int(match.group(1))
            unit = match.group(2)

            if unit == 'd':
                return self.context.current_date + timedelta(days=value)
            elif unit == 'w':
                return self.context.current_date + timedelta(weeks=value)
            elif unit == 'm':
                # Approximate month as 30 days
                return self.context.current_date + timedelta(days=value * 30)
            elif unit == 'y':
                return self.context.current_date + timedelta(days=value * 365)

        return None

    def _resolve_date_function(self, expr: str) -> Optional[date]:
        """Resolve date function expressions."""
        # Handle arithmetic first
        arith_match = self.ARITHMETIC_PATTERN.match(expr)
        if arith_match:
            base_expr = arith_match.group(1).strip()
            operator = arith_match.group(2)
            days = int(arith_match.group(3))

            base_date = self._resolve_date_function(base_expr)
            if base_date:
                delta = timedelta(days=days)
                if operator == '-':
                    return base_date - delta
                else:
                    return base_date + delta

        # Handle function calls
        func_match = self.DATE_FUNCTION_PATTERN.match(expr)
        if func_match:
            func_name = func_match.group(1)
            arg = func_match.group(2)

            if func_name == 'current_date':
                return self.context.current_date
            elif func_name == 'start_of_month':
                return self.context.current_date.replace(day=1)
            elif func_name == 'end_of_month':
                next_month = self.context.current_date.replace(day=28) + timedelta(days=4)
                return next_month.replace(day=1) - timedelta(days=1)
            elif func_name == 'start_of_quarter':
                q = (self.context.current_date.month - 1) // 3
                return self.context.current_date.replace(month=q*3 + 1, day=1)
            elif func_name == 'start_of_year':
                return self.context.current_date.replace(month=1, day=1)
            elif func_name == 'trading_day':
                offset = int(arg) if arg else -1
                return self._get_trading_day(offset)

        return None

    def _get_trading_day(self, offset: int) -> date:
        """Get trading day with offset (excludes weekends)."""
        result = self.context.current_date
        step = 1 if offset > 0 else -1
        count = 0

        while count < abs(offset):
            result += timedelta(days=step)
            # Skip weekends (5=Saturday, 6=Sunday)
            if result.weekday() < 5:
                count += 1

        return result

    def _resolve_data_function(self, expr: str) -> Optional[Any]:
        """Resolve data-dependent functions (requires session)."""
        match = self.DATA_FUNCTION_PATTERN.match(expr)
        if not match:
            return None

        func_name = match.group(1)
        column = match.group(2)
        n = int(match.group(3)) if match.group(3) else None

        # Query data via session
        # Implementation depends on data source context
        # This is a placeholder - actual implementation needs session integration

        return None  # TODO: Implement data queries
```

### Phase 2: Exhibit Type Registry

**New file**: `app/notebook/exhibits/registry.py`

```python
"""
Exhibit type registry - maps types to renderers and presets.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Type
import importlib
import yaml

from config.logging import get_logger

logger = get_logger(__name__)

@dataclass
class ExhibitTypeConfig:
    """Configuration for an exhibit type."""
    name: str
    renderer_module: str
    renderer_class: str
    preset_path: Optional[Path]
    requires: list[str]

    _renderer: Optional[Type] = None
    _preset: Optional[Dict] = None

    @property
    def renderer(self) -> Type:
        """Lazy-load renderer class."""
        if self._renderer is None:
            module = importlib.import_module(self.renderer_module)
            self._renderer = getattr(module, self.renderer_class)
        return self._renderer

    @property
    def preset(self) -> Dict:
        """Lazy-load preset configuration."""
        if self._preset is None and self.preset_path:
            with open(self.preset_path) as f:
                self._preset = yaml.safe_load(f)
        return self._preset or {}

class ExhibitTypeRegistry:
    """
    Registry of exhibit types with their renderers and presets.

    Usage:
        registry = ExhibitTypeRegistry.from_config(config_path)
        renderer = registry.get_renderer("great_table")
        defaults = registry.get_defaults("great_table")
    """

    def __init__(self):
        self._types: Dict[str, ExhibitTypeConfig] = {}
        self._aliases: Dict[str, str] = {}

    @classmethod
    def from_config(cls, config_path: Path) -> "ExhibitTypeRegistry":
        """Load registry from YAML config."""
        registry = cls()

        with open(config_path) as f:
            config = yaml.safe_load(f)

        base_path = config_path.parent

        for type_name, type_config in config.get('exhibit_types', {}).items():
            preset_path = None
            if 'preset' in type_config:
                preset_path = base_path / type_config['preset']

            registry.register(
                name=type_name,
                renderer_module=type_config['renderer'].rsplit('.', 1)[0],
                renderer_class=type_config['renderer'].rsplit('.', 1)[1] + 'Renderer',
                preset_path=preset_path,
                requires=type_config.get('requires', [])
            )

        for alias, target in config.get('aliases', {}).items():
            registry.add_alias(alias, target)

        return registry

    def register(
        self,
        name: str,
        renderer_module: str,
        renderer_class: str,
        preset_path: Optional[Path] = None,
        requires: list[str] = None
    ):
        """Register an exhibit type."""
        self._types[name] = ExhibitTypeConfig(
            name=name,
            renderer_module=renderer_module,
            renderer_class=renderer_class,
            preset_path=preset_path,
            requires=requires or []
        )

    def add_alias(self, alias: str, target: str):
        """Add an alias for an exhibit type."""
        self._aliases[alias] = target

    def resolve_type(self, type_name: str) -> str:
        """Resolve alias to actual type name."""
        return self._aliases.get(type_name, type_name)

    def get_config(self, type_name: str) -> ExhibitTypeConfig:
        """Get configuration for an exhibit type."""
        resolved = self.resolve_type(type_name)
        if resolved not in self._types:
            raise ValueError(f"Unknown exhibit type: {type_name}")
        return self._types[resolved]

    def get_renderer(self, type_name: str) -> Type:
        """Get renderer class for an exhibit type."""
        return self.get_config(type_name).renderer

    def get_defaults(self, type_name: str) -> Dict:
        """Get default parameters for an exhibit type."""
        return self.get_config(type_name).preset.get('defaults', {})

    def merge_with_defaults(self, type_name: str, user_config: Dict) -> Dict:
        """Merge user config with type defaults."""
        defaults = self.get_defaults(type_name)
        return {**defaults, **user_config}
```

### Phase 3: Great Tables Renderer

**New file**: `app/ui/components/exhibits/great_table.py`

```python
"""
Great Tables exhibit renderer.

Renders publication-quality tables using the great_tables library.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Union
import pandas as pd
import streamlit as st

from great_tables import GT, loc, style
from great_tables.data import gtcars  # For examples

from config.logging import get_logger

logger = get_logger(__name__)

class GreatTableRenderer:
    """
    Renderer for Great Tables exhibits.

    Supports:
    - Column formatting (currency, percent, number, date)
    - Spanners (grouped column headers)
    - Row grouping
    - Conditional formatting
    - Source notes and footnotes
    - Themes (default, dark, striped, minimal)
    """

    FORMAT_MAP = {
        'currency': lambda gt, cols: gt.fmt_currency(columns=cols),
        'percent': lambda gt, cols: gt.fmt_percent(columns=cols),
        'number': lambda gt, cols: gt.fmt_number(columns=cols, decimals=2),
        'integer': lambda gt, cols: gt.fmt_integer(columns=cols),
        'date': lambda gt, cols: gt.fmt_date(columns=cols),
        'datetime': lambda gt, cols: gt.fmt_datetime(columns=cols),
    }

    def __init__(self, exhibit: Any, pdf: pd.DataFrame):
        self.exhibit = exhibit
        self.pdf = pdf
        self.gt: Optional[GT] = None

    def render(self):
        """Render the Great Table exhibit."""
        # Build GT object
        self.gt = GT(self.pdf)

        # Apply configuration
        self._apply_header()
        self._apply_columns()
        self._apply_spanners()
        self._apply_formatting()
        self._apply_conditional_formatting()
        self._apply_row_config()
        self._apply_footer()
        self._apply_theme()

        # Render to Streamlit
        self._render_to_streamlit()

    def _apply_header(self):
        """Apply title and subtitle."""
        title = getattr(self.exhibit, 'title', None)
        subtitle = getattr(self.exhibit, 'subtitle', None)

        if title or subtitle:
            self.gt = self.gt.tab_header(
                title=title,
                subtitle=subtitle
            )

    def _apply_columns(self):
        """Apply column labels and formatting."""
        columns_config = getattr(self.exhibit, 'columns', None)

        if not columns_config:
            return

        # Handle list of column configs
        if isinstance(columns_config, list):
            labels = {}
            for col_config in columns_config:
                if isinstance(col_config, dict):
                    col_id = col_config.get('id')
                    col_label = col_config.get('label')
                    if col_id and col_label:
                        labels[col_id] = col_label

            if labels:
                self.gt = self.gt.cols_label(**labels)

    def _apply_spanners(self):
        """Apply column spanners (grouped headers)."""
        spanners = getattr(self.exhibit, 'spanners', None)

        if not spanners:
            return

        for spanner in spanners:
            self.gt = self.gt.tab_spanner(
                label=spanner.get('label', ''),
                columns=spanner.get('columns', [])
            )

    def _apply_formatting(self):
        """Apply column formats."""
        columns_config = getattr(self.exhibit, 'columns', None)

        if not columns_config:
            return

        # Group columns by format type
        format_groups: Dict[str, List[str]] = {}

        for col_config in columns_config:
            if isinstance(col_config, dict):
                col_id = col_config.get('id')
                col_format = col_config.get('format')

                if col_id and col_format and col_format in self.FORMAT_MAP:
                    if col_format not in format_groups:
                        format_groups[col_format] = []
                    format_groups[col_format].append(col_id)

        # Apply formats
        for format_type, cols in format_groups.items():
            formatter = self.FORMAT_MAP[format_type]
            self.gt = formatter(self.gt, cols)

    def _apply_conditional_formatting(self):
        """Apply conditional formatting rules."""
        columns_config = getattr(self.exhibit, 'columns', None)

        if not columns_config:
            return

        for col_config in columns_config:
            if isinstance(col_config, dict):
                conditional = col_config.get('conditional')
                if conditional:
                    self._apply_column_conditional(
                        col_config.get('id'),
                        conditional
                    )

    def _apply_column_conditional(self, column: str, config: Dict):
        """Apply conditional formatting to a column."""
        cond_type = config.get('type')

        if cond_type == 'color_scale':
            palette = config.get('palette', ['red', 'white', 'green'])
            domain = config.get('domain', [-1, 0, 1])

            self.gt = self.gt.data_color(
                columns=column,
                palette=palette,
                domain=domain
            )

    def _apply_row_config(self):
        """Apply row configuration."""
        row_config = getattr(self.exhibit, 'rows', None)
        row_striping = getattr(self.exhibit, 'row_striping', True)

        if row_config and isinstance(row_config, dict):
            group_by = row_config.get('group_by')
            if group_by and group_by in self.pdf.columns:
                self.gt = self.gt.tab_stub(rowname_col=group_by)

        if row_striping:
            self.gt = self.gt.opt_row_striping()

    def _apply_footer(self):
        """Apply footer notes."""
        source_note = getattr(self.exhibit, 'source_note', None)
        footnotes = getattr(self.exhibit, 'footnotes', None)

        if source_note:
            self.gt = self.gt.tab_source_note(source_note)

        if footnotes:
            for fn in footnotes:
                if isinstance(fn, dict):
                    self.gt = self.gt.tab_footnote(
                        footnote=fn.get('text', ''),
                        locations=loc.body(columns=fn.get('column'))
                    )

    def _apply_theme(self):
        """Apply visual theme."""
        theme = getattr(self.exhibit, 'theme', 'default')

        # Apply built-in options based on theme
        if theme == 'striped':
            self.gt = self.gt.opt_row_striping()
        elif theme == 'minimal':
            self.gt = self.gt.opt_stylize(style=1)
        elif theme == 'dark':
            self.gt = self.gt.opt_stylize(style=6)

    def _render_to_streamlit(self):
        """Render GT to Streamlit."""
        # GT renders to HTML
        html = self.gt.as_raw_html()

        # Display in Streamlit
        st.html(html)

        # Optional: Export buttons
        export_html = getattr(self.exhibit, 'export_html', False)
        export_png = getattr(self.exhibit, 'export_png', False)

        if export_html or export_png:
            col1, col2 = st.columns(2)

            if export_html:
                with col1:
                    st.download_button(
                        label="Download HTML",
                        data=html,
                        file_name="table.html",
                        mime="text/html"
                    )

            if export_png:
                # PNG export requires additional setup (selenium/chrome)
                with col2:
                    st.info("PNG export requires browser rendering setup")


def render_great_table(exhibit: Any, pdf: pd.DataFrame):
    """
    Render a Great Tables exhibit.

    Entry point for the exhibit dispatcher.
    """
    renderer = GreatTableRenderer(exhibit, pdf)
    renderer.render()
```

### Phase 4: Schema Updates

**Update**: `app/notebook/schema.py`

```python
# Add to ExhibitType enum
class ExhibitType(Enum):
    # ... existing types ...
    GREAT_TABLE = "great_table"

# Add new dataclasses for Great Tables
@dataclass
class ColumnConfig:
    """Configuration for a table column."""
    id: str                              # Column identifier
    label: Optional[str] = None          # Display label
    format: Optional[str] = None         # currency, percent, number, date
    width: Optional[str] = None          # CSS width (e.g., "150px")
    align: Optional[str] = None          # left, center, right
    conditional: Optional[Dict] = None   # Conditional formatting rules

@dataclass
class SpannerConfig:
    """Configuration for column spanners."""
    label: str
    columns: List[str]

@dataclass
class RowConfig:
    """Configuration for table rows."""
    source_column: Optional[str] = None  # Column that defines rows
    group_by: Optional[str] = None       # Row grouping column
    sort_by: Optional[str] = None        # Sort column
    sort_order: str = "asc"              # asc or desc
    limit: Optional[int] = None          # Row limit

@dataclass
class GreatTableConfig:
    """Configuration specific to Great Tables."""
    theme: str = "default"
    row_striping: bool = True
    row_dividers: bool = False
    spanners: List[SpannerConfig] = None
    source_note: Optional[str] = None
    footnotes: List[Dict] = None
    export_html: bool = False
    export_png: bool = False
```

---

## Usage Examples

### Example 1: Simple Table

```yaml
$exhibits${
  type: great_table
  source: company.dim_company
  title: S&P 500 Companies
  columns: [company_name, ticker, sector, market_cap]
}
```

### Example 2: Formatted Financial Table

```yaml
$exhibits${
  type: great_table
  source: stocks.fact_stock_prices
  title: Daily Price Summary
  subtitle: "{{ current_date() - 30 }} to {{ current_date() }}"

  columns:
    - id: ticker
      label: Symbol
      width: 80px

    - id: close
      label: Close
      format: currency

    - id: change_pct
      label: Daily Change
      format: percent
      conditional:
        type: color_scale
        palette: ["#ef4444", "#ffffff", "#22c55e"]
        domain: [-0.05, 0, 0.05]

    - id: volume
      label: Volume
      format: integer

  spanners:
    - label: Price Data
      columns: [open, high, low, close]

  source_note: "Data from Alpha Vantage | Updated daily"
  row_striping: true
}
```

### Example 3: Grouped Table

```yaml
$exhibits${
  type: great_table
  source: company.dim_company
  title: Companies by Sector

  rows:
    group_by: sector
    sort_by: market_cap
    sort_order: desc

  columns:
    - id: company_name
      label: Company
    - id: ticker
      label: Symbol
    - id: market_cap
      label: Market Cap
      format: currency
    - id: employees
      label: Employees
      format: integer
}
```

### Example 4: Dynamic Filters

```yaml
$filter${
  id: analysis_period
  type: date_range
  label: Analysis Period
  default:
    start: start_of_quarter()
    end: current_date()
}

$filter${
  id: top_stocks
  type: select
  multi: true
  label: Top Stocks
  default: top_n(market_cap, 20)
}
```

---

## Migration Path

### Backwards Compatibility

1. **Existing notebooks work unchanged** - All current syntax supported
2. **DateResolver expressions still work** - `-30d`, `today`, etc.
3. **Existing exhibit types unchanged** - Just adding new types

### Deprecation Plan

| Old | New | Timeline |
|-----|-----|----------|
| `DATA_TABLE` | `great_table` | Keep both, recommend GT |
| `-30d` syntax | `current_date() - 30` | Keep both indefinitely |

---

## Dependencies

### New Python Dependencies

```
great_tables>=0.12.0
```

### Optional Dependencies (for PNG export)

```
selenium>=4.0.0
webdriver-manager>=4.0.0
```

---

## File Changes Summary

| Action | File |
|--------|------|
| **CREATE** | `app/notebook/expressions/resolver.py` |
| **CREATE** | `app/notebook/exhibits/registry.py` |
| **CREATE** | `app/ui/components/exhibits/great_table.py` |
| **CREATE** | `configs/exhibits/registry.yaml` |
| **CREATE** | `configs/exhibits/presets/great_table.yaml` |
| **CREATE** | `configs/exhibits/presets/line_chart.yaml` |
| **UPDATE** | `app/notebook/schema.py` - Add new types and dataclasses |
| **UPDATE** | `app/ui/components/markdown/blocks/exhibit.py` - Add GT dispatch |
| **UPDATE** | `requirements.txt` - Add great_tables |

---

## Testing Plan

1. **Unit tests** for ExpressionResolver
2. **Unit tests** for ExhibitTypeRegistry
3. **Integration tests** for GreatTableRenderer
4. **Notebook examples** demonstrating all features

---

## Open Questions

1. **PNG Export**: Should we include browser-based PNG export, or defer to HTML-only?
2. **Preset Inheritance**: Should presets support `extends` like model configs?
3. **Data Functions**: How deep should data-dependent expressions go (e.g., `max(column)` requires query)?
4. **Interactivity**: Should Great Tables support click handlers for drill-down?

---

## Appendix: Current ExhibitType Enum (for reference)

```python
class ExhibitType(Enum):
    METRIC_CARDS = "metric_cards"
    LINE_CHART = "line_chart"
    BAR_CHART = "bar_chart"
    SCATTER_CHART = "scatter_chart"
    DUAL_AXIS_CHART = "dual_axis_chart"
    HEATMAP = "heatmap"
    DATA_TABLE = "data_table"
    PIVOT_TABLE = "pivot_table"
    CUSTOM_COMPONENT = "custom_component"
    WEIGHTED_AGGREGATE_CHART = "weighted_aggregate_chart"
    FORECAST_CHART = "forecast_chart"
    FORECAST_METRICS_TABLE = "forecast_metrics_table"
    # NEW:
    GREAT_TABLE = "great_table"
```
