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

from ..schema import NotebookConfig, Exhibit
from ..parser import NotebookParser
from ..filters.context import FilterContext
from models.registry import ModelRegistry
from app.services.storage_service import SilverStorageService


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
        self.repo_root = repo_root or Path.cwd()

        # Initialize storage service
        self.storage_service = SilverStorageService(connection, model_registry)

        # Initialize components
        self.parser = NotebookParser(self.repo_root)
        self.filter_context: Optional[FilterContext] = None

        # Current notebook
        self.notebook_config: Optional[NotebookConfig] = None

    def load_notebook(self, notebook_path: str) -> NotebookConfig:
        """
        Load and parse a notebook.

        Args:
            notebook_path: Path to notebook YAML file

        Returns:
            NotebookConfig object
        """
        # Parse notebook
        self.notebook_config = self.parser.parse_file(notebook_path)

        # Initialize filter context with notebook variables
        self.filter_context = FilterContext(self.notebook_config.variables)

        return self.notebook_config

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

        # Parse source (format: "model.table")
        if not hasattr(exhibit, 'source') or not exhibit.source:
            raise ValueError(f"Exhibit {exhibit_id} has no source defined")

        model_name, table_name = self._parse_source(exhibit.source)

        # Build filters from filter context and exhibit filters
        filters = self._build_filters(exhibit)

        # Query data from storage service
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

        Handles conversion of filter values based on variable types:
        - date_range: Already in {'start': ..., 'end': ...} format
        - multi_select: List of values
        - number: Convert to {'min': value} for range filtering
        - single_select/boolean: Direct value

        Args:
            exhibit: Exhibit configuration

        Returns:
            Dictionary of filters to apply (column_name -> filter_value)
        """
        filters = {}

        # Start with notebook-level filters from filter context
        if self.filter_context and self.notebook_config:
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
