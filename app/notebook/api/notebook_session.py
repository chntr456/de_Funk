"""
Notebook session for executing and rendering notebooks with DuckDB backend.

This session uses StorageService to query data, providing 10-100x faster
performance compared to Spark for interactive notebook queries.

Key Features:
- DuckDB backend for instant queries
- Filter management and application
- Exhibit data preparation
- Source parsing (model.table format)
"""

from typing import Dict, List, Optional, Any
from pathlib import Path
import logging

from ..schema import NotebookConfig, Exhibit, ExhibitType
from ..parsers import NotebookParser, MarkdownNotebookParser
from ..filters.context import FilterContext
from models.registry import ModelRegistry

logger = logging.getLogger(__name__)
from app.services.storage_service import SilverStorageService
import pandas as pd


class NotebookSession:
    """
    Session for executing YAML notebooks with DuckDB backend.

    Provides:
    - Notebook loading and parsing
    - Filter management and application
    - Exhibit data queries via StorageService
    - Support for multiple data connections (DuckDB, Spark)
    """

    def __init__(
        self,
        connection: Any,
        model_registry: ModelRegistry,
        repo_root: Optional[Path] = None,
    ):
        """
        Initialize notebook session.

        Args:
            connection: DataConnection instance (DuckDB or Spark)
            model_registry: Model registry for accessing model metadata
            repo_root: Repository root for resolving paths
        """
        self.connection = connection
        self.model_registry = model_registry
        if repo_root is None:
            from utils.repo import get_repo_root
            repo_root = get_repo_root()
        self.repo_root = repo_root

        # Initialize storage service
        self.storage_service = SilverStorageService(connection, model_registry)

        # Initialize components
        self.yaml_parser = NotebookParser(self.repo_root)
        self.markdown_parser = MarkdownNotebookParser(self.repo_root)
        self.filter_context: Optional[FilterContext] = None

        # Current notebook
        self.notebook_config: Optional[NotebookConfig] = None

        # Model sessions (initialized from notebook front matter)
        self.model_sessions: Dict[str, Any] = {}

    def load_notebook(self, notebook_path: str) -> NotebookConfig:
        """
        Load and parse a notebook (YAML or Markdown format).

        Args:
            notebook_path: Path to notebook file (.yaml or .md)

        Returns:
            NotebookConfig object
        """
        path = Path(notebook_path)

        # Detect format based on extension
        if path.suffix in ['.md', '.markdown']:
            # Parse markdown notebook
            self.notebook_config = self.markdown_parser.parse_file(notebook_path)
        else:
            # Parse YAML notebook
            self.notebook_config = self.yaml_parser.parse_file(notebook_path)

        # Initialize filter context with notebook variables
        self.filter_context = FilterContext(self.notebook_config.variables)

        # Initialize model sessions from front matter
        self._initialize_model_sessions()

        return self.notebook_config

    def _initialize_model_sessions(self):
        """
        Initialize model sessions based on models listed in notebook front matter.

        This loads the models and makes them available for querying.
        """
        if not self.notebook_config or not self.notebook_config.graph:
            return

        # Clear existing sessions
        self.model_sessions.clear()

        # Initialize each model
        for model_ref in self.notebook_config.graph.models:
            model_name = model_ref.name

            try:
                # Get model from registry
                if model_name in self.model_registry._models:
                    model = self.model_registry._models[model_name]
                    self.model_sessions[model_name] = {
                        'model': model,
                        'config': model_ref.config,
                        'initialized': True
                    }
                else:
                    # Model not found in registry
                    self.model_sessions[model_name] = {
                        'model': None,
                        'config': model_ref.config,
                        'initialized': False,
                        'error': f"Model '{model_name}' not found in registry"
                    }
            except Exception as e:
                self.model_sessions[model_name] = {
                    'model': None,
                    'config': model_ref.config,
                    'initialized': False,
                    'error': str(e)
                }

    def get_model_session(self, model_name: str) -> Optional[Any]:
        """
        Get a model session by name.

        Args:
            model_name: Name of the model

        Returns:
            Model session or None if not found
        """
        if model_name in self.model_sessions:
            session = self.model_sessions[model_name]
            if session['initialized']:
                return session['model']
        return None

    def get_filter_context(self) -> Dict[str, Any]:
        """Get current filter context."""
        if self.filter_context is None:
            return {}
        return self.filter_context.get_all()

    def update_filters(self, filter_values: Dict[str, Any]):
        """
        Update filter values.

        Args:
            filter_values: Dictionary of filter_id -> value
        """
        if self.filter_context is not None:
            self.filter_context.update(filter_values)

    def get_exhibit_data(self, exhibit_id: str) -> Any:
        """
        Get data for an exhibit by querying the storage service.

        Args:
            exhibit_id: ID of the exhibit

        Returns:
            DataFrame (Spark or DuckDB relation) with exhibit data
        """
        if not self.notebook_config:
            raise ValueError("No notebook loaded")

        # Find the exhibit
        exhibit = self._find_exhibit(exhibit_id)
        if not exhibit:
            raise ValueError(f"Exhibit not found: {exhibit_id}")

        # Special handling for weighted aggregate charts
        if exhibit.type == ExhibitType.WEIGHTED_AGGREGATE_CHART:
            return self._get_weighted_aggregate_data(exhibit)

        # Parse source (format: "model.table")
        if not hasattr(exhibit, 'source') or not exhibit.source:
            raise ValueError(f"Exhibit {exhibit_id} has no source defined")

        model_name, table_name = self._parse_source(exhibit.source)

        # Build filters from filter context and exhibit filters
        filters = self._build_filters(exhibit)

        logger.info(f"get_exhibit_data: {model_name}.{table_name}, filters={filters}")

        # Query data from storage service
        # Note: Storage service skips caching when filters are provided,
        # allowing DuckDB's lazy evaluation to handle large tables efficiently
        df = self.storage_service.get_table(model_name, table_name, filters)

        return df

    def _find_exhibit(self, exhibit_id: str) -> Optional[Exhibit]:
        """Find an exhibit by ID."""
        if not self.notebook_config:
            return None

        for exhibit in self.notebook_config.exhibits:
            if exhibit.id == exhibit_id:
                return exhibit
        return None

    def _parse_source(self, source: str) -> tuple[str, str]:
        """
        Parse exhibit source string.

        Args:
            source: Source string in format "model.table"

        Returns:
            Tuple of (model_name, table_name)

        Raises:
            ValueError: If source format is invalid
        """
        parts = source.split('.')
        if len(parts) != 2:
            raise ValueError(f"Invalid source format: {source}. Expected 'model.table'")

        return parts[0], parts[1]

    def _build_filters(self, exhibit: Exhibit) -> Dict[str, Any]:
        """
        Build filters for an exhibit from filter context and exhibit-specific filters.

        Now supports both old filter context (FilterContext) and new dynamic filters (FilterCollection).

        Args:
            exhibit: Exhibit configuration

        Returns:
            Dictionary of filters to apply (column_name -> filter_value)
        """
        filters = {}

        # Check if we have dynamic filters (new system)
        if (self.notebook_config and
            hasattr(self.notebook_config, '_filter_collection') and
            self.notebook_config._filter_collection):

            # Get active filters from collection
            filter_collection = self.notebook_config._filter_collection
            active_filters = filter_collection.get_active_filters()

            # Convert filter values to storage service format
            from app.notebook.filters.dynamic import FilterType, FilterOperator

            for filter_id, value in active_filters.items():
                if value is None:
                    continue

                filter_config = filter_collection.get_filter(filter_id)
                if not filter_config:
                    filters[filter_id] = value
                    continue

                # Convert based on filter type and operator
                if filter_config.type == FilterType.DATE_RANGE:
                    # Already in correct format: {'start': ..., 'end': ...}
                    filters[filter_id] = value

                elif filter_config.type == FilterType.SELECT:
                    # Already in correct format: list or single value
                    if value:  # Only add non-empty values
                        filters[filter_id] = value

                elif filter_config.type == FilterType.NUMBER_RANGE:
                    # Already in correct format: {'min': ..., 'max': ...}
                    filters[filter_id] = value

                elif filter_config.type == FilterType.SLIDER:
                    # Convert single value based on operator
                    if filter_config.operator == FilterOperator.GREATER_EQUAL:
                        if value > 0:  # Only add if > 0
                            filters[filter_id] = {'min': value}
                    elif filter_config.operator == FilterOperator.LESS_EQUAL:
                        filters[filter_id] = {'max': value}
                    elif filter_config.operator == FilterOperator.EQUALS:
                        filters[filter_id] = value
                    else:
                        # Default to min for other operators
                        if value > 0:
                            filters[filter_id] = {'min': value}

                elif filter_config.type == FilterType.TEXT_SEARCH:
                    # For text search, just pass the value
                    if value:
                        filters[filter_id] = value

                elif filter_config.type == FilterType.BOOLEAN:
                    # For boolean, pass the value
                    filters[filter_id] = value

                else:
                    # Default: pass value as-is
                    filters[filter_id] = value

        # Otherwise use old filter context system
        elif self.filter_context and self.notebook_config:
            context_filters = self.filter_context.get_all()

            # Convert filter values based on variable types
            for var_id, value in context_filters.items():
                if var_id not in self.notebook_config.variables:
                    continue

                variable = self.notebook_config.variables[var_id]

                # For number variables, convert to range format if not already
                if variable.type.value == 'number' and not isinstance(value, dict):
                    # Convert single number to min/max range
                    if value is not None and value > 0:
                        filters[var_id] = {'min': value}
                    # Skip if 0 or None (no filter)
                elif variable.type.value == 'date_range':
                    # Date range already in correct format
                    filters[var_id] = value
                elif variable.type.value == 'multi_select':
                    # List of values for IN clause
                    if value:  # Only add if not empty
                        filters[var_id] = value
                else:
                    # Single value filters
                    if value is not None:
                        filters[var_id] = value

        # Apply exhibit-level filters (override notebook filters if present)
        if hasattr(exhibit, 'filters') and exhibit.filters:
            filters.update(exhibit.filters)

        return filters

    def _get_weighted_aggregate_data(self, exhibit: Exhibit) -> Any:
        """
        Get data for weighted aggregate charts by querying model-defined measures.

        This queries pre-built weighted aggregate views from the silver layer,
        avoiding the need for UI-level calculations.

        Args:
            exhibit: Weighted aggregate chart exhibit

        Returns:
            DataFrame with columns: aggregate_by, weighted_value, measure_id
        """
        if not hasattr(exhibit, 'value_measures') or not exhibit.value_measures:
            raise ValueError(f"Weighted aggregate exhibit {exhibit.id} has no value_measures defined")

        aggregate_by = exhibit.aggregate_by or 'trade_date'
        measure_ids = exhibit.value_measures  # e.g., ["equal_weighted_index", "volume_weighted_index"]

        # Build filter clause for the query
        # NOTE: Weighted aggregates are already aggregated across all stocks (no ticker column),
        # so we only apply filters that exist in the aggregated view (mainly date filters)
        filters = self._build_filters(exhibit)
        where_clauses = []

        # Columns that don't exist in aggregated views (skip these filters)
        skip_filters = {'ticker', 'symbol', 'stock_id'}

        # Handle different filter types
        for filter_name, filter_value in filters.items():
            # Skip dimension filters that don't exist in aggregated views
            if filter_name in skip_filters:
                continue

            if isinstance(filter_value, dict):
                # Date range filter
                if 'start' in filter_value and 'end' in filter_value:
                    where_clauses.append(f"{filter_name} BETWEEN '{filter_value['start']}' AND '{filter_value['end']}'")
                # Numeric range filter
                elif 'min' in filter_value:
                    where_clauses.append(f"{filter_name} >= {filter_value['min']}")
                if 'max' in filter_value:
                    where_clauses.append(f"{filter_name} <= {filter_value['max']}")
            elif isinstance(filter_value, list):
                # Multi-select filter (IN clause) - skip if it's a dimension filter
                if filter_name not in skip_filters:
                    values_str = ','.join([f"'{v}'" for v in filter_value])
                    where_clauses.append(f"{filter_name} IN ({values_str})")
            else:
                # Simple equality filter
                where_clauses.append(f"{filter_name} = '{filter_value}'")

        where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"

        # Query each weighted aggregate measure with dynamic normalization
        results = []
        for measure_id in measure_ids:
            # Query with dynamic normalization based on filtered date range
            # The index will always start at 100 for the first date in the filtered results
            sql = f"""
            WITH raw_data AS (
                SELECT
                    {aggregate_by},
                    weighted_value
                FROM {measure_id}
                WHERE {where_clause}
                ORDER BY {aggregate_by}
            ),
            base_value AS (
                SELECT
                    weighted_value as base_weighted_value
                FROM raw_data
                LIMIT 1
            )
            SELECT
                rd.{aggregate_by},
                (rd.weighted_value / bv.base_weighted_value) * 100 as weighted_value,
                '{measure_id}' as measure_id
            FROM raw_data rd
            CROSS JOIN base_value bv
            ORDER BY rd.{aggregate_by}
            """

            try:
                # Execute query and fetch result
                df = self.connection.conn.execute(sql).fetchdf()
                results.append(df)
            except Exception as e:
                # If the measure doesn't exist, provide helpful error
                raise ValueError(
                    f"Error querying weighted aggregate '{measure_id}': {str(e)}. "
                    f"Make sure to run 'python scripts/build_weighted_aggregates_duckdb.py' "
                    f"to create the weighted aggregate views."
                )

        # Combine all measures into a single DataFrame
        if results:
            combined_df = pd.concat(results, ignore_index=True)
            # Convert to DuckDB relation for consistency
            return self.connection.conn.from_df(combined_df)
        else:
            # Return empty DataFrame
            return self.connection.conn.from_df(pd.DataFrame(columns=[aggregate_by, 'weighted_value', 'measure_id']))
