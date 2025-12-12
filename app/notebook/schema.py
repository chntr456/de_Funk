"""
Schema definitions for YAML notebooks.

Provides dataclass representations of notebook components.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Union
from enum import Enum


class VariableType(Enum):
    """Types of variables supported in notebooks."""
    DATE_RANGE = "date_range"
    MULTI_SELECT = "multi_select"
    SINGLE_SELECT = "single_select"
    NUMBER = "number"
    TEXT = "text"
    BOOLEAN = "boolean"


class MeasureType(Enum):
    """Types of measures supported."""
    SIMPLE = "simple"
    WEIGHTED_AVERAGE = "weighted_average"
    WEIGHTED_AGGREGATE = "weighted_aggregate"  # Multi-stock weighted index
    CALCULATION = "calculation"
    WINDOW_FUNCTION = "window_function"
    RATIO = "ratio"


class AggregationType(Enum):
    """Aggregation functions."""
    SUM = "sum"
    AVG = "avg"
    WEIGHTED_AVG = "weighted_avg"
    MIN = "min"
    MAX = "max"
    COUNT = "count"
    STDDEV = "stddev"
    VARIANCE = "variance"
    FIRST = "first"
    LAST = "last"


class WeightingMethod(Enum):
    """Weighting methods for aggregate calculations."""
    EQUAL = "equal"  # Equal weighting (simple average)
    MARKET_CAP = "market_cap"  # Market capitalization weighted
    VOLUME = "volume"  # Volume weighted
    PRICE = "price"  # Price weighted
    CUSTOM = "custom"  # Custom expression-based weighting
    VOLUME_DEVIATION = "volume_deviation"  # (volume - avg_volume) * price weighted
    VOLATILITY = "volatility"  # Inverse volatility weighted


class ExhibitType(Enum):
    """Types of exhibits (visualizations)."""
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
    # Great Tables (publication-quality tables)
    GREAT_TABLE = "great_table"


@dataclass
class SourceReference:
    """Reference to a data source (model.node.column)."""
    model: str
    node: str
    column: Optional[str] = None
    filter: Optional[List[str]] = None


@dataclass
class ModelReference:
    """Reference to a backend model."""
    name: str
    config: str
    nodes: List[str]


@dataclass
class Bridge:
    """Bridge between models (cross-model join)."""
    from_source: str  # model.node
    to_source: str    # model.node
    on: List[str]     # join conditions
    type: str = "left"  # join type
    description: Optional[str] = None


@dataclass
class GraphConfig:
    """Graph configuration for notebook."""
    models: List[ModelReference]
    bridges: Optional[List[Bridge]] = None


@dataclass
class DateRangeDefault:
    """Default value for date range variable."""
    start: str  # Can be ISO date or relative like "-30d"
    end: str    # Can be ISO date or relative like "today"


@dataclass
class Variable:
    """Variable definition (filter parameter)."""
    id: str
    type: VariableType
    display_name: str
    default: Any
    source: Optional[SourceReference] = None
    description: Optional[str] = None
    format: Optional[str] = None
    options: Optional[List[Any]] = None


@dataclass
class Dimension:
    """Dimension definition (attribute from dimension table)."""
    id: str
    source: SourceReference
    display_name: str
    type: str  # string, number, date, boolean
    format: Optional[str] = None


@dataclass
class WindowConfig:
    """Window function configuration."""
    partition_by: List[str]
    order_by: List[str]
    rows_between: Optional[List[int]] = None  # [start, end] relative to current row
    range_between: Optional[List[str]] = None


@dataclass
class Measure:
    """Measure definition (calculation/aggregation)."""
    id: str
    display_name: str
    type: MeasureType = MeasureType.SIMPLE
    source: Optional[SourceReference] = None
    aggregation: Optional[AggregationType] = None
    format: Optional[str] = None

    # For weighted average
    value_column: Optional[SourceReference] = None
    weight_column: Optional[SourceReference] = None

    # For weighted aggregate (multi-stock indices)
    weighting_method: Optional[WeightingMethod] = None
    group_by: Optional[List[str]] = None  # e.g., ["trade_date"]
    weight_config: Optional[Dict[str, Any]] = None  # Method-specific config

    # For calculations
    expression: Optional[str] = None
    sources: Optional[Dict[str, SourceReference]] = None

    # For window functions
    function: Optional[str] = None
    window: Optional[WindowConfig] = None


@dataclass
class AxisConfig:
    """Chart axis configuration."""
    dimension: Optional[str] = None
    measure: Optional[str] = None
    measures: Optional[List[str]] = None
    label: Optional[str] = None
    scale: Optional[str] = None  # linear, log, etc.
    source: Optional[SourceReference] = None


@dataclass
class ComparisonConfig:
    """Metric comparison configuration."""
    period: str  # previous, year_ago, custom
    label: str


@dataclass
class MetricConfig:
    """Metric card configuration."""
    measure: str
    label: Optional[str] = None
    aggregation: Optional[AggregationType] = None
    comparison: Optional[ComparisonConfig] = None


@dataclass
class SortConfig:
    """Sort configuration."""
    by: str
    order: str = "asc"  # asc or desc


@dataclass
class LayoutConfig:
    """Layout configuration for exhibits."""
    columns: Optional[int] = None
    rows: Optional[int] = None
    # Grid membership (when exhibit is part of a grid)
    grid_id: Optional[str] = None
    grid_position: Optional[int] = None


class GridGap(Enum):
    """Grid gap size options."""
    NONE = "none"
    SM = "sm"      # 0.5rem / ~8px
    MD = "md"      # 1rem / ~16px (default)
    LG = "lg"      # 1.5rem / ~24px
    XL = "xl"      # 2rem / ~32px


class GridTemplate(Enum):
    """Pre-defined grid layout templates."""
    TWO_BY_TWO = "2x2"          # 4 exhibits in 2x2 grid
    ONE_TWO = "1-2"             # 1 on top, 2 below
    TWO_ONE = "2-1"             # 2 on top, 1 below
    TWO_ONE_TWO = "2-1-2"       # 2 top, 1 middle, 2 bottom
    THREE_COL = "3col"          # 3 equal columns
    FOUR_COL = "4col"           # 4 equal columns
    SIDEBAR = "sidebar"         # 2:1 ratio (main + sidebar)
    SIDEBAR_LEFT = "sidebar-left"  # 1:2 ratio (sidebar + main)
    CUSTOM = "custom"           # Custom configuration


@dataclass
class GridConfig:
    """
    Configuration for exhibit grid layout.

    Supports multiple specification modes:
    1. Simple columns: columns=2 (equal width)
    2. Column ratios: columns=[2, 1] (2:1 ratio)
    3. Row definitions: rows=[[1,1], [2]] (custom spans per row)
    4. Templates: template="2x2" (pre-defined patterns)

    Example usage in markdown:
        $grid${
          template: 2x2
          gap: lg
        }
        $exhibits${ ... }
        $exhibits${ ... }
        $/grid$
    """
    # Column specification - int for equal columns, list for ratios
    columns: Union[int, List[int]] = 2

    # Row definitions (optional, for complex layouts)
    # Each row is a list of column spans, e.g., [[1,1], [2]] = 2 cols then 1 spanning
    rows: Optional[List[List[int]]] = None

    # Pre-defined template (overrides columns/rows if set)
    template: Optional[GridTemplate] = None

    # Styling
    gap: GridGap = GridGap.NONE  # Default to no gap - borders touching
    align_items: str = "stretch"  # stretch, start, center, end
    min_height: Optional[int] = None  # Minimum row height in pixels
    max_height: Optional[int] = None  # Max height for scrollable grid (enables linked scrolling)
    scroll: bool = True  # Enable scrolling by default (uses max_height of 400 if not set)
    sync_scroll: bool = False  # Synchronize scrolling across all grid cells (default off)

    # Identification
    id: Optional[str] = None

    def get_column_spec(self) -> List[float]:
        """
        Convert columns config to Streamlit column ratios.

        Returns:
            List of floats for st.columns()
        """
        if self.template and self.template != GridTemplate.CUSTOM:
            # Get first row from template
            rows = self._template_to_rows()
            return rows[0] if rows else [0.5, 0.5]

        if isinstance(self.columns, int):
            return [1.0 / self.columns] * self.columns

        # Normalize ratios to sum to 1.0
        total = sum(self.columns)
        return [c / total for c in self.columns]

    def get_row_specs(self) -> List[List[float]]:
        """
        Get row specifications for multi-row layouts.

        Returns:
            List of row specs, each row is a list of column ratios
        """
        if self.template and self.template != GridTemplate.CUSTOM:
            return self._template_to_rows()

        if self.rows:
            return [
                [c / sum(row) for c in row] if sum(row) > 0 else [1.0]
                for row in self.rows
            ]

        # Single row with column spec
        return [self.get_column_spec()]

    def get_total_cells(self) -> int:
        """Get total number of cells across all rows."""
        row_specs = self.get_row_specs()
        return sum(len(row) for row in row_specs)

    def _template_to_rows(self) -> List[List[float]]:
        """Convert template to row specifications."""
        templates = {
            GridTemplate.TWO_BY_TWO: [[0.5, 0.5], [0.5, 0.5]],
            GridTemplate.ONE_TWO: [[1.0], [0.5, 0.5]],
            GridTemplate.TWO_ONE: [[0.5, 0.5], [1.0]],
            GridTemplate.TWO_ONE_TWO: [[0.5, 0.5], [1.0], [0.5, 0.5]],
            GridTemplate.THREE_COL: [[1/3, 1/3, 1/3]],
            GridTemplate.FOUR_COL: [[0.25, 0.25, 0.25, 0.25]],
            GridTemplate.SIDEBAR: [[2/3, 1/3]],
            GridTemplate.SIDEBAR_LEFT: [[1/3, 2/3]],
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
    _start_index: int = 0  # Position in content_blocks where grid starts
    _end_index: int = 0    # Position where grid ends


@dataclass
class WeightingConfig:
    """Configuration for weighted aggregation."""
    method: WeightingMethod
    weight_column: Optional[str] = None  # Column to use for weighting (for CUSTOM)
    expression: Optional[str] = None  # Custom weight expression
    normalize: bool = True  # Whether to normalize weights to sum to 1


@dataclass
class MeasureSelectorConfig:
    """Configuration for dynamic measure selection in exhibits."""
    available_measures: List[str]  # List of measure column names available for selection
    default_measures: Optional[List[str]] = None  # Measures selected by default
    label: Optional[str] = None  # Label for the selector UI
    allow_multiple: bool = True  # Allow multiple measure selection
    selector_type: str = "checkbox"  # Type: checkbox, multiselect, radio
    help_text: Optional[str] = None  # Help text for the selector


@dataclass
class DimensionSelectorConfig:
    """Configuration for dynamic dimension selection in exhibits."""
    available_dimensions: List[str]  # List of dimension column names available for selection
    default_dimension: Optional[str] = None  # Dimension selected by default
    label: Optional[str] = None  # Label for the selector UI
    selector_type: str = "radio"  # Type: radio, selectbox
    help_text: Optional[str] = None  # Help text for the selector
    applies_to: str = "group_by"  # What the dimension applies to: "group_by", "color", "x"
    # Aggregation settings for when grouping by non-primary dimensions
    aggregation: str = "avg"  # Aggregation method: avg, sum, min, max, first, last
    primary_dimension: Optional[str] = None  # Primary dimension (no aggregation), defaults to first in list
    aggregate_on_change: bool = True  # Whether to aggregate when dimension changes from primary


# =============================================================================
# Great Tables Configuration Classes
# =============================================================================

@dataclass
class GTColumnConfig:
    """Configuration for a Great Table column."""
    id: str  # Column identifier
    label: Optional[str] = None  # Display label
    format: Optional[str] = None  # currency, currency_millions, percent, number, integer, date
    width: Optional[str] = None  # CSS width (e.g., "150px")
    align: Optional[str] = None  # left, center, right
    style: Optional[Dict[str, Any]] = None  # Inline styles (bold, background, border_top)
    conditional: Optional[Dict[str, Any]] = None  # Conditional formatting rules


@dataclass
class GTSpannerConfig:
    """Configuration for Great Table column spanners (grouped headers)."""
    label: str  # Spanner label text
    columns: List[str] = field(default_factory=list)  # Columns under this spanner
    from_model: Optional[str] = None  # Reference to model schema column_group


@dataclass
class GTRowConfig:
    """Configuration for Great Table rows."""
    dimension: Optional[str] = None  # Column that defines each row
    group_by: Optional[str] = None  # Row grouping column
    sort_by: Optional[str] = None  # Sort column
    sort_order: str = "asc"  # asc or desc
    limit: Optional[int] = None  # Row limit
    subtotals: bool = False  # Show subtotals for groups
    hierarchy: Optional[List[Dict[str, Any]]] = None  # Hierarchical row structure


@dataclass
class GTDateDimensionConfig:
    """Configuration for date dimension as columns (pivot-style)."""
    source_column: str  # Date column name
    granularity: str = "annually"  # monthly, quarterly, annually
    periods: Optional[int] = None  # Number of periods to show
    format: Optional[str] = None  # Date format string
    granularity_selector: Optional[Dict[str, Any]] = None  # Interactive granularity selection
    subtotals: Optional[Dict[str, Any]] = None  # Subtotal configuration


@dataclass
class GTFootnoteConfig:
    """Configuration for Great Table footnotes."""
    text: str  # Footnote text
    column: Optional[str] = None  # Column to attach footnote to
    row: Optional[int] = None  # Row index to attach footnote to


@dataclass
class GreatTableConfig:
    """Configuration specific to Great Tables exhibits."""
    theme: str = "default"  # default, financial, dark, striped, minimal
    row_striping: bool = True
    row_dividers: bool = False
    columns: Optional[List[Union[str, GTColumnConfig]]] = None
    spanners: Optional[Union[str, List[GTSpannerConfig]]] = None  # "auto" or list
    rows: Optional[GTRowConfig] = None
    date_dimension: Optional[GTDateDimensionConfig] = None
    source_note: Optional[str] = None
    footnotes: Optional[List[GTFootnoteConfig]] = None
    export_html: bool = False
    export_png: bool = False
    calculated_columns: Optional[Dict[str, Dict[str, Any]]] = None  # Derived measures


@dataclass
class Exhibit:
    """Exhibit definition (visualization)."""
    id: str
    type: ExhibitType
    title: str
    description: Optional[str] = None
    source: Optional[str] = None  # model.table reference (e.g., "company.prices_with_company")
    filters: Optional[Dict[str, str]] = None  # filter_id: variable_ref

    # Chart configurations
    x_axis: Optional[AxisConfig] = None
    y_axis: Optional[AxisConfig] = None
    y_axis_left: Optional[AxisConfig] = None
    y_axis_right: Optional[AxisConfig] = None
    color_by: Optional[str] = None
    size_by: Optional[str] = None
    legend: bool = True
    interactive: bool = True

    # Metric cards
    metrics: Optional[List[MetricConfig]] = None

    # Measure selector (dynamic measure selection)
    measure_selector: Optional[MeasureSelectorConfig] = None

    # Dimension selector (dynamic dimension selection for grouping/coloring)
    dimension_selector: Optional[DimensionSelectorConfig] = None

    # Collapsible exhibit configuration
    collapsible: bool = False  # Whether to render exhibit in collapsible section
    collapsible_title: Optional[str] = None  # Title for collapsible section (defaults to exhibit title)
    collapsible_expanded: bool = True  # Whether collapsible section is expanded by default
    nest_in_expander: bool = True  # Whether to render chart inside Configuration expander (with selectors)

    # Weighted aggregate configurations
    weighting: Optional[WeightingConfig] = None
    aggregate_by: Optional[str] = None  # Dimension to aggregate by (e.g., "trade_date")
    value_measures: Optional[List[str]] = None  # Measures to aggregate (e.g., ["close", "volume"])
    group_by: Optional[Union[str, List[str]]] = None  # Grouping dimension(s) for aggregation
    aggregations: Optional[Dict[str, str]] = None  # Dict of column -> agg function (e.g., {"close": "avg"})

    # Table configurations
    columns: Optional[List[str]] = None  # dimension or measure ids
    pagination: bool = False
    page_size: int = 50
    download: bool = False
    sortable: bool = True
    searchable: bool = False

    # Sort and layout
    sort: Optional[SortConfig] = None
    layout: Optional[LayoutConfig] = None

    # Custom component
    component: Optional[str] = None
    params: Optional[Dict[str, Any]] = None

    # Additional options
    options: Optional[Dict[str, Any]] = None

    # Forecast chart specific options
    actual_column: Optional[str] = None  # Column name for actual values
    predicted_column: Optional[str] = None  # Column name for predicted values
    confidence_bounds: Optional[List[str]] = None  # [lower_bound_col, upper_bound_col]

    # Great Tables specific options
    theme: Optional[str] = None  # default, financial, dark, striped, minimal
    spanners: Optional[Any] = None  # "auto" or list of spanner configs
    rows: Optional[Any] = None  # GTRowConfig or dict
    row_striping: bool = True
    source_note: Optional[str] = None
    footnotes: Optional[List[Dict[str, Any]]] = None
    export_html: bool = False
    export_png: bool = False
    subtitle: Optional[str] = None  # Subtitle for Great Tables
    calculated_columns: Optional[Dict[str, Any]] = None  # Derived/computed columns
    scroll: bool = False  # Enable scrollable container (default height 400px)
    max_height: Optional[int] = None  # Max height in pixels for scrollable container

    # Raw data for 1:1 serialization - stores original YAML dict for round-trip editing
    _raw_data: Optional[Dict[str, Any]] = None


@dataclass
class Section:
    """Layout section containing exhibits."""
    title: Optional[str] = None
    exhibits: List[str] = field(default_factory=list)
    columns: int = 1
    description: Optional[str] = None


@dataclass
class ExportConfig:
    """Export configuration."""
    id: str
    type: str  # pdf, excel, csv
    title: str
    include: List[str]  # exhibit ids
    format: Optional[Dict[str, Any]] = None


@dataclass
class NotebookMetadata:
    """Notebook metadata."""
    id: str
    title: str
    description: Optional[str] = None
    author: Optional[str] = None
    created: Optional[str] = None
    updated: Optional[str] = None
    tags: Optional[List[str]] = None


@dataclass
class NotebookConfig:
    """Complete notebook configuration."""
    version: str
    notebook: NotebookMetadata
    graph: GraphConfig
    variables: Dict[str, Variable]
    exhibits: List[Exhibit]
    layout: List[Section]
    dimensions: Optional[List[Dimension]] = None  # Optional: deprecated in favor of model-defined dimensions
    measures: Optional[List[Measure]] = None  # Optional: deprecated in favor of model-defined measures
    exports: Optional[List[ExportConfig]] = None
    # Markdown-specific fields
    _content_blocks: Optional[List[Dict[str, Any]]] = None  # For markdown rendering
    _is_markdown: bool = False  # Flag to indicate markdown format
    _filter_collection: Optional[Any] = None  # Dynamic filters (FilterCollection)
    _block_positions: Optional[List[Any]] = None  # Block positions for editing
    _grid_blocks: Optional[List['GridBlock']] = None  # Grid layout blocks
