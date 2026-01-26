"""
Dynamic filter schema and types.

Defines filter configurations that pull options dynamically from the database
and support fuzzy filtering with session state.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Any, Dict
from enum import Enum


class FilterType(Enum):
    """Types of dynamic filters."""
    DATE_RANGE = "date_range"
    DATE = "date"  # Single date with expression support (e.g., current_date())
    SELECT = "select"  # Single or multi-select (auto-detected)
    NUMBER_RANGE = "number_range"
    TEXT_SEARCH = "text_search"  # Fuzzy text search
    BOOLEAN = "boolean"
    SLIDER = "slider"  # Numeric slider


class FilterOperator(Enum):
    """Filter comparison operators."""
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    IN = "in"
    NOT_IN = "not_in"
    GREATER_THAN = "gt"
    GREATER_EQUAL = "gte"
    LESS_THAN = "lt"
    LESS_EQUAL = "lte"
    BETWEEN = "between"
    CONTAINS = "contains"  # For text search
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    FUZZY = "fuzzy"  # Fuzzy text matching


@dataclass
class FilterSource:
    """Source configuration for dynamic filter options."""
    model: str  # Model name (e.g., "company")
    table: str  # Table name (e.g., "fact_prices")
    column: str  # Column to get values from
    distinct: bool = True  # Get distinct values
    sort: bool = True  # Sort values
    limit: Optional[int] = None  # Limit number of options


@dataclass
class FilterConfig:
    """
    Dynamic filter configuration.

    Filters are defined inline in markdown notebooks using $filter${...} syntax
    and rendered in the sidebar with options dynamically pulled from the database.
    """
    id: str  # Unique filter ID (also used as column name for filtering)
    type: FilterType  # Filter type
    label: str  # Display label

    # Source configuration (for dynamic options)
    source: Optional[FilterSource] = None  # If None, uses id as column name in current context

    # Default values
    default: Any = None  # Default value(s)

    # Filter behavior
    operator: FilterOperator = FilterOperator.IN  # Comparison operator
    multi: bool = True  # Allow multiple selections (for select type)
    required: bool = False  # Is this filter required?

    # UI configuration
    placeholder: Optional[str] = None  # Placeholder text
    help_text: Optional[str] = None  # Help tooltip

    # Fuzzy search configuration
    fuzzy_threshold: float = 0.6  # Fuzzy match threshold (0-1)
    fuzzy_enabled: bool = False  # Enable fuzzy matching

    # Range configuration (for number_range, date_range)
    min_value: Optional[Any] = None
    max_value: Optional[Any] = None
    step: Optional[Any] = None

    # Options (static, used if source is not provided)
    options: Optional[List[Any]] = None

    # Column to apply filter to (if different from id)
    apply_to: Optional[str] = None


@dataclass
class FilterState:
    """
    Runtime state for a filter.

    Tracks current value, available options, and validation state.
    """
    filter_id: str
    config: FilterConfig
    current_value: Any = None
    available_options: Optional[List[Any]] = None
    is_valid: bool = True
    error_message: Optional[str] = None
    last_updated: Optional[str] = None


@dataclass
class FilterCollection:
    """
    Collection of filters for a notebook.

    Manages filter state and provides filtering operations.
    """
    filters: Dict[str, FilterConfig] = field(default_factory=dict)
    states: Dict[str, FilterState] = field(default_factory=dict)

    def add_filter(self, filter_config: FilterConfig):
        """Add a filter to the collection."""
        self.filters[filter_config.id] = filter_config

        # Resolve expression-based defaults (e.g., current_date())
        resolved_default = self._resolve_default(filter_config)

        self.states[filter_config.id] = FilterState(
            filter_id=filter_config.id,
            config=filter_config,
            current_value=resolved_default
        )

    def _resolve_default(self, filter_config: FilterConfig) -> Any:
        """
        Resolve filter default value, handling expressions like current_date().

        Args:
            filter_config: Filter configuration

        Returns:
            Resolved default value
        """
        if filter_config.default is None:
            return None

        # For DATE type filters, resolve date expressions
        if filter_config.type == FilterType.DATE:
            return self._resolve_date_expression(filter_config.default)

        # For DATE_RANGE type, resolve both start and end
        elif filter_config.type == FilterType.DATE_RANGE:
            if isinstance(filter_config.default, dict):
                start = filter_config.default.get('start')
                end = filter_config.default.get('end')
                return {
                    'start': self._resolve_date_expression(start) if start else None,
                    'end': self._resolve_date_expression(end) if end else None,
                }
            return filter_config.default

        return filter_config.default

    def _resolve_date_expression(self, value: Any) -> Any:
        """
        Resolve a date expression to its value.

        Supports:
        - ISO dates: "2024-01-01" -> "2024-01-01"
        - Expressions: "current_date()" -> today's date as string
        - Arithmetic: "current_date() - 365" -> 365 days ago

        Args:
            value: Date string or expression

        Returns:
            Resolved date string in ISO format
        """
        if not isinstance(value, str):
            return value

        # Check if this looks like an expression (contains function call)
        if '(' in value and ')' in value:
            try:
                from ..expressions.resolver import ExpressionResolver
                resolver = ExpressionResolver()
                result = resolver.resolve(value)

                # Convert date object to ISO string
                if hasattr(result, 'isoformat'):
                    return result.isoformat()
                return result
            except Exception:
                # If resolution fails, return original value
                return value

        return value

    def get_filter(self, filter_id: str) -> Optional[FilterConfig]:
        """Get filter configuration by ID."""
        return self.filters.get(filter_id)

    def get_state(self, filter_id: str) -> Optional[FilterState]:
        """Get filter state by ID."""
        return self.states.get(filter_id)

    def update_value(self, filter_id: str, value: Any):
        """Update filter value."""
        if filter_id in self.states:
            self.states[filter_id].current_value = value

    def get_active_filters(self) -> Dict[str, Any]:
        """Get all filters with non-null values."""
        return {
            fid: state.current_value
            for fid, state in self.states.items()
            if state.current_value is not None
        }

    def build_sql_conditions(self) -> List[str]:
        """
        Build SQL WHERE conditions from active filters.

        Returns:
            List of SQL condition strings
        """
        conditions = []

        for filter_id, state in self.states.items():
            if state.current_value is None:
                continue

            config = state.config
            column = config.apply_to or config.id
            value = state.current_value

            if config.operator == FilterOperator.EQUALS:
                conditions.append(f"{column} = '{value}'")

            elif config.operator == FilterOperator.IN:
                if isinstance(value, list):
                    if value:  # Only add if list is not empty
                        values_str = ','.join([f"'{v}'" for v in value])
                        conditions.append(f"{column} IN ({values_str})")
                else:
                    conditions.append(f"{column} = '{value}'")

            elif config.operator == FilterOperator.BETWEEN:
                if isinstance(value, dict) and 'start' in value and 'end' in value:
                    conditions.append(f"{column} BETWEEN '{value['start']}' AND '{value['end']}'")

            elif config.operator == FilterOperator.GREATER_EQUAL:
                conditions.append(f"{column} >= {value}")

            elif config.operator == FilterOperator.LESS_EQUAL:
                conditions.append(f"{column} <= {value}")

            elif config.operator == FilterOperator.CONTAINS:
                conditions.append(f"{column} LIKE '%{value}%'")

            elif config.operator == FilterOperator.FUZZY:
                # Fuzzy matching using LIKE with wildcards
                search_term = value.replace(' ', '%')
                conditions.append(f"{column} LIKE '%{search_term}%'")

        return conditions

    def to_dict(self) -> Dict[str, Any]:
        """Export filter states to dictionary."""
        return {
            fid: state.current_value
            for fid, state in self.states.items()
        }

    def from_dict(self, values: Dict[str, Any]):
        """Import filter states from dictionary."""
        for filter_id, value in values.items():
            if filter_id in self.states:
                self.states[filter_id].current_value = value
