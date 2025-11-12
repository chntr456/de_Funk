"""
Base measure abstraction for all measure types.

Defines the contract that all measure implementations must follow.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple
from enum import Enum


class MeasureType(Enum):
    """Types of measures supported by the framework."""
    SIMPLE = "simple"              # Direct aggregation (avg, sum, etc.)
    COMPUTED = "computed"          # Expression-based (close * volume)
    WEIGHTED = "weighted"          # Weighted aggregations
    WINDOW = "window"              # Window functions (rolling, lag, etc.)
    RATIO = "ratio"                # Ratios and percentages
    CUSTOM = "custom"              # Custom SQL/code


class BaseMeasure(ABC):
    """
    Abstract base class for all measure types.

    Design Philosophy:
    - Measures generate SQL (business logic)
    - Backend adapters execute SQL (infrastructure)
    - Same measure works across backends

    Measures are defined in YAML and instantiated via the MeasureRegistry.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize measure from configuration.

        Args:
            config: Measure configuration from YAML (with 'name' added)

        Common config fields:
            - name: Measure identifier
            - description: Human-readable description
            - source: Source table and column (e.g., 'fact_prices.close')
            - data_type: Data type of result
            - tags: Classification tags
        """
        self.name = config['name']
        self.description = config.get('description', '')
        self.source = config['source']
        self.data_type = config.get('data_type', 'double')
        self.format = config.get('format')
        self.tags = config.get('tags', [])

    @abstractmethod
    def to_sql(self, adapter) -> str:
        """
        Generate SQL for this measure.

        This is the core method - all measures must be able to generate SQL.
        Uses backend adapter for dialect-specific references.

        Args:
            adapter: BackendAdapter instance for dialect-specific SQL

        Returns:
            SQL query string

        Raises:
            NotImplementedError: If measure cannot be expressed in SQL
        """
        pass

    def execute(self, adapter, **kwargs):
        """
        Execute measure using backend adapter.

        Default implementation generates SQL and executes via adapter.
        Can be overridden for measures requiring custom logic.

        Args:
            adapter: BackendAdapter instance
            **kwargs: Additional execution parameters

        Returns:
            QueryResult with data and metadata
        """
        sql = self.to_sql(adapter)
        return adapter.execute_sql(sql)

    def _parse_source(self) -> Tuple[str, str]:
        """
        Parse source into table and column.

        Args:
            None (uses self.source)

        Returns:
            Tuple of (table_name, column_name)

        Raises:
            ValueError: If source format is invalid

        Example:
            'fact_prices.close' -> ('fact_prices', 'close')
        """
        if '.' not in self.source:
            raise ValueError(
                f"Measure source must be in format 'table.column', got: {self.source}"
            )
        return self.source.rsplit('.', 1)

    def _get_table_name(self) -> str:
        """Get table name from source."""
        return self._parse_source()[0]

    def _get_column_name(self) -> str:
        """Get column name from source."""
        return self._parse_source()[1]

    def __repr__(self) -> str:
        """String representation of measure."""
        return f"{self.__class__.__name__}(name='{self.name}', source='{self.source}')"
