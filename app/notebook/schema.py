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


@dataclass
class WeightingConfig:
    """Configuration for weighted aggregation."""
    method: WeightingMethod
    weight_column: Optional[str] = None  # Column to use for weighting (for CUSTOM)
    expression: Optional[str] = None  # Custom weight expression
    normalize: bool = True  # Whether to normalize weights to sum to 1


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

    # Weighted aggregate configurations
    weighting: Optional[WeightingConfig] = None
    aggregate_by: Optional[str] = None  # Dimension to aggregate by (e.g., "trade_date")
    value_measures: Optional[List[str]] = None  # Measures to aggregate (e.g., ["close", "volume"])
    group_by: Optional[str] = None  # Optional grouping dimension

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
