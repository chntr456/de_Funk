"""
Filter types and operators.
"""

from enum import Enum


class FilterType(Enum):
    """Filter types."""
    DATE_RANGE = "date_range"
    MULTI_SELECT = "multi_select"
    SINGLE_SELECT = "single_select"
    NUMBER = "number"
    TEXT = "text"
    BOOLEAN = "boolean"


class FilterOperator(Enum):
    """Filter operators for numeric and text filters."""
    EQUALS = "="
    NOT_EQUALS = "!="
    GREATER_THAN = ">"
    GREATER_THAN_OR_EQUAL = ">="
    LESS_THAN = "<"
    LESS_THAN_OR_EQUAL = "<="
    BETWEEN = "between"
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"
