"""
Generic Silver Storage Service.

Provides data access to Silver layer using model registry (no table-specific methods).
Uses connection layer abstraction for future extensibility.
"""

from typing import Dict, List, Optional, Any
from pathlib import Path

from core.connection import DataConnection
from models.registry import ModelRegistry


class SilverStorageService:
    """
    Generic service for reading from Silver layer.

    Responsibilities:
    - Read any table by model + table name
    - Apply filters
    - Cache DataFrames
    - NO table-specific methods (scalable to any model/table)

    Usage:
        service = SilverStorageService(connection, model_registry)

        # Get any table
        df = service.get_table("company", "fact_prices", filters={...})

        # List available data
        models = service.list_models()
        tables = service.list_tables("company")
        schema = service.get_schema("company", "fact_prices")
    """

    def __init__(
        self,
        connection: DataConnection,
        model_registry: ModelRegistry,
    ):
        """
        Initialize storage service.

        Args:
            connection: Data connection (Spark, DuckDB, etc.)
            model_registry: Model registry for metadata
        """
        self.connection = connection
        self.model_registry = model_registry
        self._cache: Dict[str, Any] = {}

    def get_table(
        self,
        model_name: str,
        table_name: str,
        filters: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
    ) -> Any:
        """
        Get table data with optional filters.

        Args:
            model_name: Model name (e.g., 'company')
            table_name: Table name (e.g., 'fact_prices', 'dim_company')
            filters: Optional filters to apply
            use_cache: Whether to use cached data

        Returns:
            DataFrame (type depends on connection)

        Raises:
            ValueError: If model or table not found

        Example:
            df = service.get_table(
                "company",
                "fact_prices",
                filters={
                    "trade_date": {"start": "2024-01-01", "end": "2024-01-05"},
                    "ticker": ["AAPL", "GOOGL"]
                }
            )
        """
        # Validate model and table exist
        model = self.model_registry.get_model(model_name)
        if not model.has_table(table_name):
            raise ValueError(
                f"Table '{table_name}' not found in model '{model_name}'. "
                f"Available: {model.list_tables()}"
            )

        # Build cache key
        cache_key = f"{model_name}.{table_name}"

        # IMPORTANT: Skip caching when filters are provided
        # Caching large fact tables (like 22M row stock prices) before filtering
        # causes memory issues. DuckDB's lazy evaluation handles this efficiently
        # without caching - filters are pushed down to the query.
        should_cache = use_cache and not filters

        # Check cache (only for unfiltered requests)
        if should_cache and cache_key in self._cache:
            df = self._cache[cache_key]
        else:
            # Get table path from model
            table_path = model.get_table_path(table_name)

            # Read from storage (lazy - doesn't load all data)
            df = self.connection.read_table(table_path, model.storage_format)

            # Cache only unfiltered dimension tables (small, frequently accessed)
            # Don't cache fact tables or filtered queries
            if should_cache:
                df = self.connection.cache(df)
                self._cache[cache_key] = df

        # Apply filters if provided (DuckDB pushes these down to query)
        if filters:
            df = self.connection.apply_filters(df, filters)

        return df

    def list_models(self) -> List[str]:
        """
        List all available models.

        Returns:
            List of model names

        Example:
            ['company', 'fund', 'macro']
        """
        return self.model_registry.list_models()

    def list_tables(self, model_name: str) -> List[str]:
        """
        List all tables in a model.

        Args:
            model_name: Model name

        Returns:
            List of table names

        Example:
            ['dim_company', 'dim_exchange', 'fact_prices', ...]
        """
        model = self.model_registry.get_model(model_name)
        return model.list_tables()

    def list_dimensions(self, model_name: str) -> List[str]:
        """List dimension tables in a model."""
        model = self.model_registry.get_model(model_name)
        return model.list_dimensions()

    def list_facts(self, model_name: str) -> List[str]:
        """List fact tables in a model."""
        model = self.model_registry.get_model(model_name)
        return model.list_facts()

    def list_measures(self, model_name: str) -> List[str]:
        """
        List available measures in a model.

        Args:
            model_name: Model name

        Returns:
            List of measure names

        Example:
            ['avg_close_price', 'total_volume', 'max_high', ...]
        """
        model = self.model_registry.get_model(model_name)
        return model.list_measures()

    def get_schema(self, model_name: str, table_name: str) -> Dict[str, str]:
        """
        Get schema (columns and types) for a table.

        Args:
            model_name: Model name
            table_name: Table name

        Returns:
            Dict of column_name -> data_type

        Example:
            {
                'ticker': 'string',
                'company_name': 'string',
                'trade_date': 'date',
                'close': 'double'
            }
        """
        return self.model_registry.get_table_schema(model_name, table_name)

    def get_measure_config(self, model_name: str, measure_name: str) -> Dict:
        """
        Get measure configuration.

        Args:
            model_name: Model name
            measure_name: Measure name

        Returns:
            Measure configuration dict

        Example:
            {
                'name': 'avg_close_price',
                'description': 'Average closing price',
                'source': 'fact_prices.close',
                'aggregation': 'avg',
                'format': '$#,##0.00'
            }
        """
        model = self.model_registry.get_model(model_name)
        measure = model.get_measure(measure_name)

        return {
            'name': measure.name,
            'description': measure.description,
            'source': measure.source,
            'aggregation': measure.aggregation,
            'data_type': measure.data_type,
            'format': measure.format,
            'tags': measure.tags
        }

    def clear_cache(self, model_name: Optional[str] = None, table_name: Optional[str] = None):
        """
        Clear cached data.

        Args:
            model_name: If provided, clear only this model's cache
            table_name: If provided (with model_name), clear only this table
        """
        if model_name and table_name:
            # Clear specific table
            cache_key = f"{model_name}.{table_name}"
            if cache_key in self._cache:
                self.connection.uncache(self._cache[cache_key])
                del self._cache[cache_key]

        elif model_name:
            # Clear all tables for a model
            keys_to_remove = [k for k in self._cache.keys() if k.startswith(f"{model_name}.")]
            for key in keys_to_remove:
                self.connection.uncache(self._cache[key])
                del self._cache[key]

        else:
            # Clear everything
            for df in self._cache.values():
                self.connection.uncache(df)
            self._cache.clear()

    def get_model_registry(self) -> ModelRegistry:
        """Get the model registry (for advanced use cases)."""
        return self.model_registry

    def get_connection(self) -> DataConnection:
        """Get the data connection (for advanced use cases)."""
        return self.connection
