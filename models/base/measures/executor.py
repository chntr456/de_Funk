"""
Unified measure executor for all measure types.

Provides single entry point for measure calculation across all backends.
"""

from typing import Optional, Any, Dict

from models.base.backend.adapter import BackendAdapter
from models.base.backend.duckdb_adapter import DuckDBAdapter
from models.base.backend.spark_adapter import SparkAdapter
from .registry import MeasureRegistry

# Bootstrap: Import measure implementations to trigger @MeasureRegistry.register decorators
# This ensures all measure types are registered before create_measure() is called
import models.measures.simple
import models.measures.computed
import models.measures.weighted


class MeasureExecutor:
    """
    Unified executor for all measure types.

    Provides single entry point for measure calculation,
    abstracting backend and measure type details.

    Design:
    - Reads measure definitions from model config (YAML)
    - Uses MeasureRegistry to instantiate measure objects
    - Uses BackendAdapter for execution
    - Returns backend-agnostic results

    Example:
        executor = MeasureExecutor(model, backend='duckdb')
        result = executor.execute_measure('avg_close_price', entity_column='ticker')
    """

    def __init__(self, model, backend: str = 'duckdb'):
        """
        Initialize measure executor.

        Args:
            model: Model instance (BaseModel or subclass)
            backend: Backend type ('duckdb', 'spark')
        """
        self.model = model
        self.backend = backend

        # Create appropriate backend adapter
        self.adapter = self._create_adapter()

    def _create_adapter(self) -> BackendAdapter:
        """
        Factory method for backend adapters.

        Returns:
            Backend-specific adapter instance

        Raises:
            ValueError: If backend is not supported
        """
        if self.backend == 'duckdb':
            return DuckDBAdapter(self.model.connection, self.model)
        elif self.backend == 'spark':
            return SparkAdapter(self.model.connection, self.model)
        else:
            raise ValueError(
                f"Unsupported backend: '{self.backend}'. "
                f"Supported backends: duckdb, spark"
            )

    def execute_measure(
        self,
        measure_name: str,
        entity_column: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        **kwargs
    ):
        """
        Execute a measure from model configuration.

        This is the main entry point for measure execution.
        Works with ANY measure type and ANY backend!

        Args:
            measure_name: Name of measure from model config
            entity_column: Optional entity column to group by
            filters: Optional filters to apply
            limit: Optional limit for results
            **kwargs: Additional measure-specific parameters

        Returns:
            QueryResult with data and metadata

        Raises:
            ValueError: If measure not defined in model config

        Example:
            # Simple measure
            result = executor.execute_measure('avg_close_price', entity_column='ticker')

            # Weighted measure
            result = executor.execute_measure('volume_weighted_index')

            # With filters
            result = executor.execute_measure(
                'avg_close_price',
                filters={'trade_date': '2024-01-01'},
                limit=10
            )
        """
        # Get measure config from model
        measure_config = self._get_measure_config(measure_name)

        # Create measure instance using registry
        measure = MeasureRegistry.create_measure(measure_config)

        # Build execution context
        exec_context = {
            'entity_column': entity_column,
            'filters': filters,
            'limit': limit,
            **kwargs
        }

        # Execute using adapter (backend-agnostic!)
        result = measure.execute(self.adapter, **exec_context)

        # Apply limit if specified and not already applied
        if limit and result.rows > limit:
            if self.backend == 'duckdb':
                result.data = result.data.head(limit)
            elif self.backend == 'spark':
                result.data = result.data.limit(limit)

        return result

    def _get_measure_config(self, measure_name: str) -> Dict[str, Any]:
        """
        Get measure configuration from model.

        Args:
            measure_name: Name of measure

        Returns:
            Measure configuration dictionary

        Raises:
            ValueError: If measure not found
        """
        measures = self.model.model_cfg.get('measures', {})

        if measure_name not in measures:
            available = list(measures.keys())
            raise ValueError(
                f"Measure '{measure_name}' not defined in model '{self.model.model_name}'. "
                f"Available measures: {available}"
            )

        # Get config and add name field
        measure_config = measures[measure_name].copy()
        measure_config['name'] = measure_name

        return measure_config

    def list_measures(self) -> Dict[str, Dict[str, Any]]:
        """
        List all available measures in model.

        Returns:
            Dictionary of measure name -> measure config
        """
        return self.model.model_cfg.get('measures', {})

    def get_measure_info(self, measure_name: str) -> Dict[str, Any]:
        """
        Get information about a specific measure.

        Args:
            measure_name: Name of measure

        Returns:
            Dictionary with measure metadata

        Raises:
            ValueError: If measure not found
        """
        config = self._get_measure_config(measure_name)

        return {
            'name': measure_name,
            'type': config.get('type', 'simple'),
            'description': config.get('description', ''),
            'source': config.get('source', ''),
            'data_type': config.get('data_type', 'double'),
            'tags': config.get('tags', []),
        }

    def explain_measure(self, measure_name: str) -> str:
        """
        Generate SQL for a measure without executing it.

        Useful for debugging and optimization.

        Args:
            measure_name: Name of measure

        Returns:
            SQL query string

        Example:
            sql = executor.explain_measure('volume_weighted_index')
            print(sql)
        """
        measure_config = self._get_measure_config(measure_name)
        measure = MeasureRegistry.create_measure(measure_config)

        return measure.to_sql(self.adapter)
