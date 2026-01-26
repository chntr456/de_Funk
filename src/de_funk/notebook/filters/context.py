"""
Filter context for managing active filter values.

Handles filter inheritance and overrides between notebook and exhibit levels.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from copy import deepcopy

from ..schema import Variable, VariableType, DateRangeDefault
from ..parsers.yaml_parser import DateResolver


class FilterContext:
    """
    Manages the current state of filters in a notebook.

    Supports:
    - Notebook-level default values
    - Exhibit-level overrides
    - Filter inheritance
    - Variable resolution
    """

    def __init__(self, variables: Dict[str, Variable]):
        """
        Initialize filter context.

        Args:
            variables: Notebook variable definitions
        """
        self.variables = variables
        self._values: Dict[str, Any] = {}
        self._initialize_defaults()

    def _initialize_defaults(self):
        """Initialize filter values with defaults."""
        for var_id, variable in self.variables.items():
            if variable.default is not None:
                self._values[var_id] = self._resolve_default(variable)

    def _resolve_default(self, variable: Variable) -> Any:
        """
        Resolve a variable's default value.

        Handles relative dates and other dynamic defaults.
        """
        if variable.type == VariableType.DATE_RANGE:
            if isinstance(variable.default, DateRangeDefault):
                start = DateResolver.resolve(variable.default.start)
                end = DateResolver.resolve(variable.default.end)
                return {
                    'start': start,
                    'end': end,
                }
            return variable.default
        else:
            return variable.default

    def get(self, var_id: str) -> Any:
        """
        Get current filter value.

        Args:
            var_id: Variable ID

        Returns:
            Current value or None if not set
        """
        return self._values.get(var_id)

    def set(self, var_id: str, value: Any):
        """
        Set filter value.

        Args:
            var_id: Variable ID
            value: New value
        """
        if var_id not in self.variables:
            raise ValueError(f"Unknown variable: {var_id}")

        # Validate value type
        self._validate_value(self.variables[var_id], value)

        self._values[var_id] = value

    def update(self, values: Dict[str, Any]):
        """
        Update multiple filter values.

        Args:
            values: Dictionary of variable_id -> value
        """
        for var_id, value in values.items():
            self.set(var_id, value)

    def get_all(self) -> Dict[str, Any]:
        """
        Get all current filter values.

        Returns:
            Dictionary of variable_id -> value
        """
        return deepcopy(self._values)

    def create_exhibit_context(
        self,
        exhibit_filters: Optional[Dict[str, str]] = None
    ) -> 'FilterContext':
        """
        Create a new filter context for an exhibit.

        Inherits notebook-level filters and applies exhibit-specific overrides.

        Args:
            exhibit_filters: Exhibit filter overrides (filter_id: variable_ref)

        Returns:
            New FilterContext for the exhibit
        """
        # Create a copy with same variables
        exhibit_context = FilterContext(self.variables)
        exhibit_context._values = deepcopy(self._values)

        # Apply exhibit-specific overrides
        if exhibit_filters:
            for filter_id, var_ref in exhibit_filters.items():
                # Variable references start with $
                if var_ref.startswith('$'):
                    var_name = var_ref[1:]
                    if var_name in self._values:
                        exhibit_context._values[filter_id] = self._values[var_name]
                else:
                    # Direct value
                    exhibit_context._values[filter_id] = var_ref

        return exhibit_context

    def _validate_value(self, variable: Variable, value: Any):
        """
        Validate a value for a variable.

        Args:
            variable: Variable definition
            value: Value to validate

        Raises:
            ValueError if validation fails
        """
        if value is None:
            return

        if variable.type == VariableType.DATE_RANGE:
            if not isinstance(value, dict) or 'start' not in value or 'end' not in value:
                raise ValueError(
                    f"Date range filter must have 'start' and 'end' keys"
                )

        elif variable.type == VariableType.MULTI_SELECT:
            if not isinstance(value, (list, tuple)):
                raise ValueError(
                    f"Multi-select filter must be a list, got {type(value)}"
                )

        elif variable.type == VariableType.NUMBER:
            if not isinstance(value, (int, float)):
                raise ValueError(
                    f"Number filter must be numeric, got {type(value)}"
                )

        elif variable.type == VariableType.BOOLEAN:
            if not isinstance(value, bool):
                raise ValueError(
                    f"Boolean filter must be bool, got {type(value)}"
                )

    def get_filter_options(self, var_id: str) -> Optional[List[Any]]:
        """
        Get available options for a filter.

        For filters with predefined options or loaded from dimension tables.

        Args:
            var_id: Variable ID

        Returns:
            List of available options or None
        """
        if var_id not in self.variables:
            return None

        variable = self.variables[var_id]

        # Return predefined options if available
        if variable.options:
            return variable.options

        # If source is specified, options should be loaded from dimension table
        # This would be handled by the UI layer
        return None

    def reset(self):
        """Reset all filters to default values."""
        self._values.clear()
        self._initialize_defaults()

    def reset_variable(self, var_id: str):
        """
        Reset a specific variable to its default value.

        Args:
            var_id: Variable ID
        """
        if var_id not in self.variables:
            raise ValueError(f"Unknown variable: {var_id}")

        variable = self.variables[var_id]
        if variable.default is not None:
            self._values[var_id] = self._resolve_default(variable)
        else:
            self._values.pop(var_id, None)

    def __repr__(self) -> str:
        """String representation."""
        return f"FilterContext(variables={len(self.variables)}, values={len(self._values)})"
