"""
Notebook Manager for notebook lifecycle management.

This manager separates notebook parsing and lifecycle management from data access.
All data queries are delegated to UniversalSession, maintaining clean separation of concerns.

Key changes from NotebookSession:
- Uses UniversalSession for all data access (not SilverStorageService)
- Uses centralized FilterEngine for filter application
- Focused on notebook parsing, filter management, and exhibit preparation
- No direct database queries (delegated to UniversalSession)
- Supports folder-based filter contexts (shared within folder, isolated across folders)
"""

from typing import Dict, List, Optional, Any
from pathlib import Path
import pandas as pd

from ..schema import NotebookConfig, Exhibit, ExhibitType
from ..parsers import NotebookParser, MarkdownNotebookParser
from ..filters.context import FilterContext
from ..folder_context import FolderFilterContextManager
from models.api.session import UniversalSession
from models.registry import ModelRegistry
from core.session.filters import FilterEngine


class NotebookManager:
    """
    Manager for notebook lifecycle and execution.

    Responsibilities:
    - Notebook loading and parsing (YAML and Markdown)
    - Filter context management
    - Exhibit data preparation (delegates queries to UniversalSession)
    - Model session initialization

    Does NOT:
    - Execute database queries directly (delegates to UniversalSession)
    - Manage connections (handled by UniversalSession)
    - Apply filters at database level (uses FilterEngine via UniversalSession)
    """

    def __init__(
        self,
        universal_session: UniversalSession,
        repo_root: Optional[Path] = None,
        notebooks_root: Optional[Path] = None,
    ):
        """
        Initialize notebook manager.

        Args:
            universal_session: UniversalSession for data access
            repo_root: Repository root for resolving paths
            notebooks_root: Root directory for notebooks (defaults to repo_root/configs/notebooks)
        """
        self.session = universal_session
        self.repo_root = repo_root or Path.cwd()

        # Initialize parsers
        self.yaml_parser = NotebookParser(self.repo_root)
        self.markdown_parser = MarkdownNotebookParser(self.repo_root)

        # Folder-based filter context management
        if notebooks_root is None:
            notebooks_root = self.repo_root / "configs" / "notebooks"
        self.folder_context_manager = FolderFilterContextManager(notebooks_root)

        # Notebook state
        self.notebook_config: Optional[NotebookConfig] = None
        self.current_notebook_path: Optional[Path] = None
        self.current_folder: Optional[Path] = None
        self.filter_context: Optional[FilterContext] = None  # Legacy compatibility
        self.model_sessions: Dict[str, Any] = {}

    def load_notebook(self, notebook_path: str) -> NotebookConfig:
        """
        Load and parse a notebook (YAML or Markdown format).

        Handles folder context switching - if notebook is in a different folder,
        switches to that folder's filter context.

        Args:
            notebook_path: Path to notebook file (.yaml or .md)

        Returns:
            NotebookConfig object

        Raises:
            ValueError: If notebook file format is unsupported
        """
        path = Path(notebook_path).resolve()

        # Detect format based on extension
        if path.suffix in ['.md', '.markdown']:
            # Parse markdown notebook
            self.notebook_config = self.markdown_parser.parse_file(notebook_path)
        elif path.suffix in ['.yaml', '.yml']:
            # Parse YAML notebook
            self.notebook_config = self.yaml_parser.parse_file(notebook_path)
        else:
            raise ValueError(
                f"Unsupported notebook format: {path.suffix}. "
                "Supported formats: .md, .markdown, .yaml, .yml"
            )

        # Track notebook path and folder
        new_folder = self.folder_context_manager.get_folder_for_notebook(path)
        folder_changed = self.folder_context_manager.has_context_changed(new_folder, self.current_folder)

        self.current_notebook_path = path
        self.current_folder = new_folder

        # Load folder-based filter context
        folder_filters = self.folder_context_manager.get_filters(new_folder)

        # Initialize filter context with notebook variables and folder filters
        self.filter_context = FilterContext(self.notebook_config.variables)

        # Apply folder filters to context (if they match notebook variables)
        if folder_filters:
            # Only apply filters that match notebook variables
            valid_filters = {
                k: v for k, v in folder_filters.items()
                if k in self.notebook_config.variables
            }
            if valid_filters:
                self.filter_context.update(valid_filters)

        # Initialize model sessions from front matter
        self._initialize_model_sessions()

        return self.notebook_config

    def _initialize_model_sessions(self):
        """
        Initialize model sessions based on models listed in notebook front matter.

        Uses UniversalSession's load_model method to ensure models are available.
        """
        if not self.notebook_config or not self.notebook_config.graph:
            return

        # Clear existing sessions
        self.model_sessions.clear()

        # Load each model via UniversalSession
        for model_ref in self.notebook_config.graph.models:
            model_name = model_ref.name

            try:
                # Load model via UniversalSession
                model = self.session.load_model(model_name)
                self.model_sessions[model_name] = {
                    'model': model,
                    'config': model_ref.config,
                    'initialized': True
                }
            except Exception as e:
                # Model failed to load
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
            Model instance or None if not found
        """
        if model_name in self.model_sessions:
            session = self.model_sessions[model_name]
            if session['initialized']:
                return session['model']
        return None

    def get_filter_context(self) -> Dict[str, Any]:
        """
        Get current filter context.

        Returns:
            Dictionary of filter values
        """
        if self.filter_context is None:
            return {}
        return self.filter_context.get_all()

    def get_current_folder(self) -> Optional[Path]:
        """
        Get the current folder path.

        Returns:
            Path to current folder, or None if no notebook loaded
        """
        return self.current_folder

    def get_folder_display_name(self) -> str:
        """
        Get display name for current folder (relative to notebooks root).

        Returns:
            Folder name for display (e.g., "company_analysis" or "market/overview")
        """
        if self.current_folder is None:
            return "No folder"

        try:
            notebooks_root = self.folder_context_manager.notebooks_root
            relative = self.current_folder.relative_to(notebooks_root)
            return str(relative) if str(relative) != '.' else self.current_folder.name
        except ValueError:
            # Not relative to notebooks root
            return self.current_folder.name

    def update_filters(self, filter_values: Dict[str, Any]):
        """
        Update filter values.

        Updates both the in-memory filter context and the folder-level
        persistent context (saved to .filter_context.yaml).

        Args:
            filter_values: Dictionary of filter_id -> value
        """
        # Update in-memory context
        if self.filter_context is not None:
            self.filter_context.update(filter_values)

        # Update folder-level persistent context
        if self.current_folder is not None:
            self.folder_context_manager.update_filters(
                self.current_folder,
                filter_values,
                auto_save=True  # Persist to disk
            )

    def get_exhibit_data(self, exhibit_id: str) -> Any:
        """
        Get data for an exhibit.

        Delegates data queries to UniversalSession and applies filters using FilterEngine.

        Args:
            exhibit_id: ID of the exhibit

        Returns:
            DataFrame with exhibit data

        Raises:
            ValueError: If notebook not loaded or exhibit not found
        """
        if not self.notebook_config:
            raise ValueError("No notebook loaded. Call load_notebook() first.")

        # Find the exhibit
        exhibit = self._find_exhibit(exhibit_id)
        if not exhibit:
            raise ValueError(f"Exhibit '{exhibit_id}' not found in notebook")

        # Special handling for weighted aggregate charts
        if exhibit.type == ExhibitType.WEIGHTED_AGGREGATE_CHART:
            return self._get_weighted_aggregate_data(exhibit)

        # Parse source (format: "model.table")
        if not hasattr(exhibit, 'source') or not exhibit.source:
            raise ValueError(f"Exhibit '{exhibit_id}' has no source defined")

        model_name, table_name = self._parse_source(exhibit.source)

        # Get raw data from UniversalSession
        df = self.session.get_table(model_name, table_name)

        # Build and apply filters
        filters = self._build_filters(exhibit)
        if filters:
            df = FilterEngine.apply_from_session(df, filters, self.session)

        return df

    def _find_exhibit(self, exhibit_id: str) -> Optional[Exhibit]:
        """
        Find an exhibit by ID.

        Args:
            exhibit_id: Exhibit identifier

        Returns:
            Exhibit object or None if not found
        """
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
            raise ValueError(
                f"Invalid source format: '{source}'. Expected format: 'model.table'"
            )

        return parts[0], parts[1]

    def _build_filters(self, exhibit: Exhibit) -> Dict[str, Any]:
        """
        Build filters for an exhibit from filter context and exhibit-specific filters.

        Supports both old filter context (FilterContext) and new dynamic filters (FilterCollection).

        Args:
            exhibit: Exhibit configuration

        Returns:
            Dictionary of filters (column_name -> filter_value)
        """
        filters = {}

        # Check for dynamic filters (new system)
        if (self.notebook_config and
            hasattr(self.notebook_config, '_filter_collection') and
            self.notebook_config._filter_collection):

            # Get active filters from collection
            filter_collection = self.notebook_config._filter_collection
            active_filters = filter_collection.get_active_filters()

            # Convert filter values to FilterEngine format
            from app.notebook.filters.dynamic import FilterType, FilterOperator

            for filter_id, value in active_filters.items():
                if value is None:
                    continue

                filter_config = filter_collection.get_filter(filter_id)
                if not filter_config:
                    filters[filter_id] = value
                    continue

                # Convert based on filter type
                if filter_config.type == FilterType.DATE_RANGE:
                    filters[filter_id] = value

                elif filter_config.type == FilterType.SELECT:
                    if value:  # Only add non-empty values
                        filters[filter_id] = value

                elif filter_config.type == FilterType.NUMBER_RANGE:
                    filters[filter_id] = value

                elif filter_config.type == FilterType.SLIDER:
                    # Convert based on operator
                    if filter_config.operator == FilterOperator.GREATER_EQUAL:
                        if value > 0:
                            filters[filter_id] = {'min': value}
                    elif filter_config.operator == FilterOperator.LESS_EQUAL:
                        filters[filter_id] = {'max': value}
                    elif filter_config.operator == FilterOperator.EQUALS:
                        filters[filter_id] = value
                    else:
                        if value > 0:
                            filters[filter_id] = {'min': value}

                elif filter_config.type == FilterType.TEXT_SEARCH:
                    if value:
                        filters[filter_id] = value

                elif filter_config.type == FilterType.BOOLEAN:
                    filters[filter_id] = value

                else:
                    filters[filter_id] = value

        # Use old filter context system
        elif self.filter_context and self.notebook_config:
            context_filters = self.filter_context.get_all()

            # Convert filter values based on variable types
            for var_id, value in context_filters.items():
                if var_id in self.notebook_config.variables:
                    # Variable defined in notebook - use its type for conversion
                    variable = self.notebook_config.variables[var_id]

                    # Convert to FilterEngine format
                    if variable.type.value == 'number' and not isinstance(value, dict):
                        if value is not None and value > 0:
                            filters[var_id] = {'min': value}
                    elif variable.type.value == 'date_range':
                        filters[var_id] = value
                    elif variable.type.value == 'multi_select':
                        if value:
                            filters[var_id] = value
                    else:
                        if value is not None:
                            filters[var_id] = value
                else:
                    # Variable NOT defined in notebook, but exists in folder context
                    # Apply it anyway (folder context drives filtering)
                    if value is not None:
                        # Smart conversion based on value type
                        if isinstance(value, list):
                            filters[var_id] = value  # Multi-select
                        elif isinstance(value, dict) and ('start' in value or 'min' in value):
                            filters[var_id] = value  # Date range or number range
                        else:
                            filters[var_id] = value  # Direct value

            # Also include extra folder filters that couldn't be added to FilterContext
            if hasattr(self, '_extra_folder_filters'):
                for var_id, value in self._extra_folder_filters.items():
                    if value is not None and var_id not in filters:
                        if isinstance(value, list):
                            filters[var_id] = value
                        elif isinstance(value, dict):
                            filters[var_id] = value
                        else:
                            filters[var_id] = value

        # Apply exhibit-level filters (override notebook filters)
        if hasattr(exhibit, 'filters') and exhibit.filters:
            filters.update(exhibit.filters)

        return filters

    def _get_weighted_aggregate_data(self, exhibit: Exhibit) -> Any:
        """
        Get data for weighted aggregate charts.

        Queries pre-built weighted aggregate views from the database.
        This method uses raw SQL since weighted aggregates are specialized views.

        Args:
            exhibit: Weighted aggregate chart exhibit

        Returns:
            DataFrame with columns: aggregate_by, weighted_value, measure_id

        Raises:
            ValueError: If exhibit configuration is invalid or views don't exist
        """
        if not hasattr(exhibit, 'value_measures') or not exhibit.value_measures:
            raise ValueError(
                f"Weighted aggregate exhibit '{exhibit.id}' has no value_measures defined"
            )

        aggregate_by = exhibit.aggregate_by or 'trade_date'
        measure_ids = exhibit.value_measures

        # Build filters
        filters = self._build_filters(exhibit)

        # Convert filters to SQL WHERE clause using FilterEngine
        where_clause = FilterEngine.build_filter_sql(filters)

        # Skip dimension filters that don't exist in aggregated views
        skip_filters = {'ticker', 'symbol', 'stock_id'}
        filtered_where_clauses = []

        for clause in where_clause.split(' AND '):
            # Skip if clause contains any of the skip filters
            if not any(skip_filter in clause for skip_filter in skip_filters):
                filtered_where_clauses.append(clause)

        final_where_clause = " AND ".join(filtered_where_clauses) if filtered_where_clauses else "1=1"

        # Query each weighted aggregate measure
        results = []
        for measure_id in measure_ids:
            # Query with dynamic normalization based on filtered date range
            sql = f"""
            WITH raw_data AS (
                SELECT
                    {aggregate_by},
                    weighted_value
                FROM {measure_id}
                WHERE {final_where_clause}
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
                # Execute query (assumes DuckDB connection)
                # TODO: Make this backend-agnostic
                df = self.session.connection.conn.execute(sql).fetchdf()
                results.append(df)
            except Exception as e:
                raise ValueError(
                    f"Error querying weighted aggregate '{measure_id}': {str(e)}. "
                    f"Ensure weighted aggregate views exist in the database."
                )

        # Combine all measures into a single DataFrame
        if results:
            combined_df = pd.concat(results, ignore_index=True)
            # Convert to DuckDB relation for consistency
            return self.session.connection.conn.from_df(combined_df)
        else:
            # Return empty DataFrame
            return self.session.connection.conn.from_df(
                pd.DataFrame(columns=[aggregate_by, 'weighted_value', 'measure_id'])
            )

    def get_exhibit_list(self) -> List[Dict[str, Any]]:
        """
        Get list of all exhibits in the notebook.

        Returns:
            List of exhibit metadata dictionaries
        """
        if not self.notebook_config:
            return []

        return [
            {
                'id': exhibit.id,
                'type': exhibit.type.value if hasattr(exhibit.type, 'value') else str(exhibit.type),
                'title': exhibit.title if hasattr(exhibit, 'title') else exhibit.id,
                'source': exhibit.source if hasattr(exhibit, 'source') else None
            }
            for exhibit in self.notebook_config.exhibits
        ]

    def get_notebook_metadata(self) -> Dict[str, Any]:
        """
        Get notebook metadata.

        Returns:
            Dictionary with notebook metadata
        """
        if not self.notebook_config or not self.notebook_config.notebook:
            return {}

        nb = self.notebook_config.notebook
        return {
            'id': nb.id,
            'title': nb.title,
            'description': nb.description,
            'author': nb.author,
            'tags': nb.tags,
            'created': nb.created,
            'updated': nb.updated
        }
