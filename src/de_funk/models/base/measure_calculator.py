"""
Measure Calculator for BaseModel.

Handles measure calculations:
- Simple measures (aggregations from YAML)
- Computed measures (expressions)
- Python measures (complex calculations)

This module is used by BaseModel via composition.
"""

from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Type alias for DataFrame (can be Spark or DuckDB)
DataFrame = Any


class MeasureCalculator:
    """
    Calculates measures defined in model configuration.

    Supports:
    - Simple aggregation measures (avg, sum, max, etc.)
    - Computed measures (custom expressions)
    - Python measures (complex calculations via Python modules)
    """

    def __init__(self, model):
        """
        Initialize measure calculator.

        Args:
            model: BaseModel instance
        """
        self.model = model

    @property
    def model_cfg(self) -> Dict:
        return self.model.model_cfg

    @property
    def model_name(self) -> str:
        return self.model.model_name

    @property
    def backend(self) -> str:
        return self.model.backend

    def calculate_measure(
        self,
        measure_name: str,
        entity_column: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        **kwargs
    ):
        """
        Calculate any measure defined in model config (UNIFIED METHOD).

        This is the unified measure execution method that works with:
        - All measure types (simple, computed, weighted, Python)
        - All backends (DuckDB, Spark)
        - All domain-specific patterns (weighting, windowing, etc.)

        Replaces calculate_measure_by_entity() with a more flexible interface.

        Args:
            measure_name: Name of measure from config (e.g., 'avg_close_price', 'sharpe_ratio')
            entity_column: Optional entity column to group by (e.g., 'ticker')
            filters: Optional filters to apply
            limit: Optional limit for top-N results
            **kwargs: Additional measure-specific parameters

        Returns:
            QueryResult with data and metadata, or DataFrame for Python measures

        Example:
            # Simple measure (YAML)
            result = model.calculate_measure('avg_close_price', entity_column='ticker', limit=10)

            # Python measure
            result = model.calculate_measure('sharpe_ratio', ticker='AAPL', window_days=252)

            # Access data
            df = result.data if hasattr(result, 'data') else result
        """
        # Check if this is a Python measure
        if self._is_python_measure(measure_name):
            return self._execute_python_measure(measure_name, filters=filters, **kwargs)

        # Otherwise, use standard measure executor
        return self.model.measures.execute_measure(
            measure_name=measure_name,
            entity_column=entity_column,
            filters=filters,
            limit=limit,
            **kwargs
        )

    def _is_python_measure(self, measure_name: str) -> bool:
        """
        Check if a measure is defined as a Python measure.

        Args:
            measure_name: Name of the measure

        Returns:
            True if it's a Python measure, False otherwise
        """
        measures_config = self.model_cfg.get('measures', {})
        python_measures = measures_config.get('python_measures', {})
        return measure_name in python_measures

    def _execute_python_measure(self, measure_name: str, **kwargs):
        """
        Execute a Python measure function.

        Args:
            measure_name: Name of the Python measure
            **kwargs: Parameters to pass to the measure function

        Returns:
            Result from the Python measure function (typically a DataFrame)

        Raises:
            ValueError: If measure not found or Python measures not available
        """
        # Get measures config
        measures_config = self.model_cfg.get('measures', {})
        python_measures = measures_config.get('python_measures', {})

        if measure_name not in python_measures:
            raise ValueError(f"Python measure '{measure_name}' not found in model '{self.model_name}'")

        # Get Python measures instance
        if self.model.python_measures is None:
            raise RuntimeError(
                f"No Python measures module loaded for model '{self.model_name}'. "
                f"Check that measures.py exists in models/implemented/{self.model_name}/"
            )

        # Get measure configuration
        measure_cfg = python_measures[measure_name]
        function_name = measure_cfg['function'].split('.')[-1]

        # Get the function from Python measures instance
        if not hasattr(self.model.python_measures, function_name):
            raise AttributeError(
                f"Function '{function_name}' not found in {self.model_name}.measures module"
            )

        func = getattr(self.model.python_measures, function_name)

        # Merge params from YAML config and kwargs
        params = measure_cfg.get('params', {}).copy()
        params.update(kwargs)

        logger.info(f"Executing Python measure '{measure_name}' with params: {params}")

        # Execute the function
        try:
            result = func(**params)
            return result
        except Exception as e:
            logger.error(f"Error executing Python measure '{measure_name}': {e}")
            raise

    def calculate_measure_by_entity(
        self,
        measure_name: str,
        entity_column: str,
        limit: Optional[int] = None
    ) -> DataFrame:
        """
        Calculate a measure aggregated by entity (generic method for all models).

        This method reads measure definitions from YAML config and calculates
        them as operations on fact tables. This is proper dimensional modeling:
        measures are calculated from facts, not stored in dimensions.

        Note: Currently only supported for Spark backend

        Args:
            measure_name: Name of measure from config (e.g., 'market_cap', 'avg_close_price')
            entity_column: Column to group by (e.g., 'ticker', 'indicator_id', 'city_id')
            limit: Optional limit for top-N results (ordered descending by measure value)

        Returns:
            DataFrame with columns: <entity_column>, <measure_name>

        Example:
            # In CompanyModel
            df = self.calculate_measure_by_entity('market_cap', 'ticker', limit=10)
            # Returns: DataFrame with [ticker, market_cap]

            # In MacroModel
            df = self.calculate_measure_by_entity('avg_value', 'indicator_id', limit=5)
            # Returns: DataFrame with [indicator_id, avg_value]

        Raises:
            ValueError: If measure not defined in config
        """
        # Measure calculations not yet implemented for DuckDB
        if self.backend == 'duckdb':
            raise NotImplementedError(
                f"Measure calculations not yet supported for DuckDB backend. "
                f"Use Spark backend for measure: '{measure_name}'"
            )

        from pyspark.sql import functions as F

        # Get measure configuration from YAML
        measures = self.model_cfg.get('measures', {})

        if measure_name not in measures:
            available = list(measures.keys())
            raise ValueError(
                f"Measure '{measure_name}' not defined in {self.model_name}. "
                f"Available measures: {available}"
            )

        measure_config = measures[measure_name]

        # Get source table and column
        source = measure_config.get('source', '')
        if '.' not in source:
            raise ValueError(f"Measure source must be 'table.column', got: {source}")

        table_name, column_name = source.split('.', 1)

        # Get the source table
        source_table = self.model.get_table(table_name)

        # Calculate measure based on type
        measure_type = measure_config.get('type', 'simple')
        aggregation = measure_config.get('aggregation', 'avg')

        if measure_type == 'computed':
            # Computed measure with custom expression (e.g., close * volume)
            expression = measure_config.get('expression', '')
            if not expression:
                raise ValueError(
                    f"Computed measure '{measure_name}' requires 'expression' in config"
                )

            result = (
                source_table
                .withColumn('_measure_value', F.expr(expression))
                .groupBy(entity_column)
                .agg(F.avg('_measure_value').alias(measure_name))
            )

        else:
            # Simple aggregation measure (e.g., avg, sum, max)
            agg_func = getattr(F, aggregation, F.avg)

            result = (
                source_table
                .groupBy(entity_column)
                .agg(agg_func(F.col(column_name)).alias(measure_name))
            )

        # Filter nulls and order by measure value descending
        result = (
            result
            .filter(F.col(measure_name).isNotNull())
            .orderBy(F.desc(measure_name))
        )

        # Apply limit if specified
        if limit:
            result = result.limit(limit)

        return result
