"""
Helper methods for parsing filters in markdown parser.
Split out for clarity.
"""

import yaml
from typing import Any, Dict
from .filters.dynamic import (
    FilterConfig,
    FilterType,
    FilterOperator,
    FilterSource,
)
from .yaml_utils import normalize_yaml_indentation


def parse_filter(filter_yaml: str) -> FilterConfig:
    """
    Parse filter YAML into FilterConfig object.

    Supports both simple and advanced syntax:

    Simple:
    ```yaml
    id: ticker
    label: Stock Tickers
    ```

    Advanced:
    ```yaml
    id: trade_date
    type: date_range
    label: Date Range
    operator: between
    default: {start: "2024-01-01", end: "2024-12-31"}
    ```

    With source:
    ```yaml
    id: ticker
    label: Stock Tickers
    source: {model: company, table: dim_company, column: ticker}
    multi: true
    ```

    Note: YAML is auto-normalized to fix copy/paste indentation issues.
    """
    # Normalize YAML indentation to handle copy/paste issues
    normalized_yaml = normalize_yaml_indentation(filter_yaml)
    data = yaml.safe_load(normalized_yaml)

    # Parse filter type
    filter_type = FilterType.SELECT  # Default
    if 'type' in data:
        filter_type = FilterType(data['type'])

    # Parse source if present
    source = None
    if 'source' in data:
        src = data['source']
        if isinstance(src, dict):
            source = FilterSource(
                model=src['model'],
                table=src['table'],
                column=src['column'],
                distinct=src.get('distinct', True),
                sort=src.get('sort', True),
                limit=src.get('limit')
            )
        elif isinstance(src, str):
            # Simple format: "model.table.column"
            parts = src.split('.')
            if len(parts) == 3:
                source = FilterSource(
                    model=parts[0],
                    table=parts[1],
                    column=parts[2]
                )

    # Parse operator
    operator = FilterOperator.IN  # Default
    if 'operator' in data:
        operator = FilterOperator(data['operator'])

    # Auto-detect type from operator if not specified
    if 'type' not in data:
        if operator == FilterOperator.BETWEEN:
            # Check if dealing with dates or numbers
            if 'date' in data.get('id', '').lower():
                filter_type = FilterType.DATE_RANGE
            else:
                filter_type = FilterType.NUMBER_RANGE
        elif operator in [FilterOperator.CONTAINS, FilterOperator.FUZZY]:
            filter_type = FilterType.TEXT_SEARCH

    # Parse default value
    default = data.get('default')

    # Build filter config
    return FilterConfig(
        id=data['id'],
        type=filter_type,
        label=data.get('label', data['id'].replace('_', ' ').title()),
        source=source,
        default=default,
        operator=operator,
        multi=data.get('multi', True),
        required=data.get('required', False),
        placeholder=data.get('placeholder'),
        help_text=data.get('help_text'),
        fuzzy_threshold=data.get('fuzzy_threshold', 0.6),
        fuzzy_enabled=data.get('fuzzy_enabled', False),
        min_value=data.get('min_value'),
        max_value=data.get('max_value'),
        step=data.get('step'),
        options=data.get('options'),
        apply_to=data.get('apply_to')
    )
