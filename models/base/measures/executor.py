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

            # With auto-enrichment (columns not in source table)
            result = executor.execute_measure(
                'avg_close_by_exchange',
                entity_column='exchange_name',  # Not in fact_equity_prices!
                # auto_enrich=True in measure config enables dynamic join
            )
        """
        # Get measure config from model
        measure_config = self._get_measure_config(measure_name)

        # Create measure instance using registry
        measure = MeasureRegistry.create_measure(measure_config)

        # Check if auto-enrichment is enabled
        if measure.auto_enrich:
            # Perform auto-enrichment before execution
            self._auto_enrich_measure(measure, measure_config, entity_column, filters, kwargs)

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

        Supports both v1.x flat structure and v2.0 nested structure.

        Args:
            measure_name: Name of measure

        Returns:
            Measure configuration dictionary

        Raises:
            ValueError: If measure not found
        """
        measures = self.model.model_cfg.get('measures', {})

        # Check if v2.0 nested structure
        if 'simple_measures' in measures or 'computed_measures' in measures or 'python_measures' in measures:
            # v2.0 nested - search across all measure types
            for measure_type in ['simple_measures', 'computed_measures', 'python_measures']:
                if measure_type in measures and isinstance(measures[measure_type], dict):
                    if measure_name in measures[measure_type]:
                        measure_config = measures[measure_type][measure_name].copy()
                        measure_config['name'] = measure_name
                        return measure_config

            # Not found in any measure type
            all_measures = {}
            for measure_type in ['simple_measures', 'computed_measures', 'python_measures']:
                if measure_type in measures and isinstance(measures[measure_type], dict):
                    all_measures.update(measures[measure_type])

            available = list(all_measures.keys())
            raise ValueError(
                f"Measure '{measure_name}' not defined in model '{self.model.model_name}'. "
                f"Available measures: {available}"
            )
        else:
            # v1.x flat structure
            if measure_name not in measures:
                available = list(measures.keys())
                raise ValueError(
                    f"Measure '{measure_name}' not defined in model '{self.model.model_name}'. "
                    f"Available measures: {available}"
                )

            measure_config = measures[measure_name].copy()
            measure_config['name'] = measure_name
            return measure_config

    def list_measures(self) -> Dict[str, Dict[str, Any]]:
        """
        List all available measures in model.

        Returns a flattened dictionary for both v1.x and v2.0 structures.

        Returns:
            Dictionary of measure name -> measure config
        """
        measures = self.model.model_cfg.get('measures', {})

        # Check if v2.0 nested structure
        if 'simple_measures' in measures or 'computed_measures' in measures or 'python_measures' in measures:
            # v2.0 nested - flatten all measure types
            all_measures = {}
            for measure_type in ['simple_measures', 'computed_measures', 'python_measures']:
                if measure_type in measures and isinstance(measures[measure_type], dict):
                    all_measures.update(measures[measure_type])
            return all_measures
        else:
            # v1.x flat structure
            return measures

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

    def _auto_enrich_measure(
        self,
        measure,
        measure_config: Dict[str, Any],
        entity_column: Optional[str],
        filters: Optional[Dict[str, Any]],
        kwargs: Dict[str, Any]
    ) -> None:
        """
        Automatically enrich measure source table with columns from related tables.

        Uses GraphQueryPlanner to find and join required tables when columns
        are not available in the base source table.

        Args:
            measure: Measure instance
            measure_config: Measure configuration
            entity_column: Entity column for grouping (may not be in source table)
            filters: Filter conditions (may reference columns not in source table)
            kwargs: Additional parameters

        Example:
            Measure config:
                avg_close_by_exchange:
                    source: fact_equity_prices.close
                    entity_column: exchange_name  # Not in fact_equity_prices!
                    auto_enrich: true

            This method will:
            1. Detect that exchange_name is not in fact_equity_prices
            2. Use query planner to find path: fact_equity_prices -> dim_equity -> dim_exchange
            3. Get enriched table with exchange_name column
            4. Update adapter to use enriched table
        """
        # Get base table from source
        base_table = measure._get_table_name()

        # Collect all required columns
        required_columns = set()

        # Add source column
        source_column = measure._get_column_name()
        required_columns.add(source_column)

        # Add entity column if specified
        if entity_column:
            required_columns.add(entity_column)

        # Add group_by columns from config
        group_by = measure_config.get('group_by', [])
        if group_by:
            required_columns.update(group_by)

        # Add weight_column for weighted measures
        if hasattr(measure, 'weight_column') and measure.weight_column:
            # Extract column name from 'table.column' format
            if '.' in measure.weight_column:
                weight_col = measure.weight_column.split('.')[-1]
            else:
                weight_col = measure.weight_column
            required_columns.add(weight_col)

        # Add columns from expression for computed measures
        if hasattr(measure, 'expression') and measure.expression:
            # Extract column names from expression (simple regex)
            import re
            expr_columns = re.findall(r'\b([a-z_][a-z0-9_]*)\b', measure.expression.lower())
            # Filter out SQL keywords
            keywords = {'and', 'or', 'not', 'is', 'null', 'true', 'false', 'in', 'between', 'like', 'case', 'when', 'then', 'else', 'end'}
            expr_columns = [col for col in expr_columns if col not in keywords]
            required_columns.update(expr_columns)

        # Add filter columns
        if filters:
            required_columns.update(filters.keys())

        # Add columns from kwargs (filter parameters)
        required_columns.update(kwargs.keys())

        # Get schema for base table
        base_table_schema = self._get_table_schema(base_table)
        base_columns = set(base_table_schema.keys()) if base_table_schema else set()

        # Find columns not in base table
        missing_columns = required_columns - base_columns

        if not missing_columns:
            # All columns available in base table, no enrichment needed
            return

        # Use query planner to find which tables have the missing columns
        query_planner = self.model.query_planner

        # Find tables that contain the missing columns and build full join paths
        # Use dict to preserve order and track distance from base table
        all_join_tables_dict = {}

        for column in missing_columns:
            # Search for tables with this column
            tables_with_column = query_planner.find_tables_with_column(column)
            if tables_with_column:
                target_table = tables_with_column[0]

                # Get the full join path from base_table to target_table
                join_path = query_planner.get_join_path(base_table, target_table)

                if join_path and len(join_path) > 1:
                    # Add all intermediate tables (excluding base table) in order
                    for i, table in enumerate(join_path[1:], start=1):
                        if table not in all_join_tables_dict:
                            # Store table with its distance from base as value
                            all_join_tables_dict[table] = i
                else:
                    # No path found - column exists but not reachable via joins
                    # Let it fail naturally with a better error message
                    pass
            else:
                # Column not found in any table - will fail during execution
                # Let it fail naturally with a better error message
                pass

        if not all_join_tables_dict:
            # No enrichment possible
            return

        # Sort tables by distance from base (closest first) to ensure correct join order
        # This ensures dim_equity comes before dim_exchange in the join chain
        sorted_tables = sorted(all_join_tables_dict.keys(), key=lambda t: all_join_tables_dict[t])

        # Get enriched table using query planner with tables in correct order
        enriched_df = self.model.get_table_enriched(
            base_table,
            enrich_with=sorted_tables,
            columns=None  # Get all columns
        )

        # Update adapter to use enriched table
        # Store enriched DataFrame in adapter's table cache
        self.adapter.set_enriched_table(base_table, enriched_df)

    def _get_table_schema(self, table_name: str) -> Optional[Dict[str, str]]:
        """
        Get schema for a table from model config.

        Args:
            table_name: Table name

        Returns:
            Dictionary of column_name -> data_type, or None if not found
        """
        schema = self.model.model_cfg.get('schema', {})

        # Check dimensions
        dims = schema.get('dimensions', {})
        if table_name in dims:
            return dims[table_name].get('columns', {})

        # Check facts
        facts = schema.get('facts', {})
        if table_name in facts:
            return facts[table_name].get('columns', {})

        return None
