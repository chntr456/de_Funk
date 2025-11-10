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

        # Initialize markdown parser (only format supported)
        self.markdown_parser = MarkdownNotebookParser(self.repo_root)

        # Folder-based filter context management
        if notebooks_root is None:
            notebooks_root = self.repo_root / "configs" / "notebooks"
        self.folder_context_manager = FolderFilterContextManager(notebooks_root)

        # Notebook state
        self.notebook_config: Optional[NotebookConfig] = None
        self.current_notebook_path: Optional[Path] = None
        self.current_folder: Optional[Path] = None
        self.filter_context: Optional[FilterContext] = None  # Legacy compatibility (deprecated)
        self.model_sessions: Dict[str, Any] = {}

    def load_notebook(self, notebook_path: str) -> NotebookConfig:
        """
        Load and parse a markdown notebook.

        Only markdown format with $filter${...} syntax is supported.
        YAML notebook format has been deprecated.

        Handles folder context switching - if notebook is in a different folder,
        switches to that folder's filter context.

        Args:
            notebook_path: Path to notebook file (.md)

        Returns:
            NotebookConfig object

        Raises:
            ValueError: If notebook file format is unsupported
        """
        path = Path(notebook_path).resolve()

        # Only support markdown format
        if path.suffix in ['.md', '.markdown']:
            # Parse markdown notebook
            self.notebook_config = self.markdown_parser.parse_file(notebook_path)
        else:
            raise ValueError(
                f"Unsupported notebook format: {path.suffix}. "
                "Only markdown format (.md, .markdown) is supported. "
                "YAML notebooks have been deprecated - please convert to markdown with $filter${...} syntax."
            )

        # Track notebook path and folder
        new_folder = self.folder_context_manager.get_folder_for_notebook(path)
        folder_changed = self.folder_context_manager.has_context_changed(new_folder, self.current_folder)

        self.current_notebook_path = path
        self.current_folder = new_folder

        # Load folder-based filter context
        folder_filters = self.folder_context_manager.get_filters(new_folder)

        # UNIFIED FILTER MERGE: Combine notebook filters + folder context into ONE collection
        # Folder context supersedes notebook defaults (no duplicates)
        self._merge_filters_unified(folder_filters)

        # CRITICAL: Sync session state values back into FilterCollection
        # This ensures user-selected filter values persist across reruns
        self._sync_session_state_to_filters()

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

    def _merge_filters_unified(self, folder_filters: Dict[str, Any]):
        """
        Merge folder context with notebook filters into ONE unified collection.

        Strategy:
        1. For notebook filters: Override value if exists in folder context (folder supersedes)
        2. For folder-only filters: Add to collection as new filters
        3. Result: Single _filter_collection with all merged filters (no duplicates)

        Args:
            folder_filters: Dictionary of folder context filters
        """
        # Ensure we have a filter collection (create if needed for YAML notebooks)
        if not hasattr(self.notebook_config, '_filter_collection') or not self.notebook_config._filter_collection:
            from app.notebook.filters.dynamic import FilterCollection
            self.notebook_config._filter_collection = FilterCollection()

        filter_collection = self.notebook_config._filter_collection

        if not folder_filters:
            return

        # Track which folder filters we've processed
        processed_folder_filters = set()

        # Phase 1: Update notebook filters with folder values (folder supersedes notebook defaults)
        for filter_id in list(filter_collection.filters.keys()):
            if filter_id in folder_filters:
                # Folder context supersedes notebook default
                filter_state = filter_collection.get_state(filter_id)
                if filter_state:
                    filter_state.current_value = folder_filters[filter_id]
                processed_folder_filters.add(filter_id)

        # Phase 2: Add folder-only filters (not in notebook) so they appear in sidebar
        for filter_id, value in folder_filters.items():
            if filter_id not in processed_folder_filters:
                # Create FilterConfig for folder-only filter
                filter_config = self._create_filter_config_from_value(filter_id, value)
                filter_collection.add_filter(filter_config)
                # Set the current value
                filter_state = filter_collection.get_state(filter_id)
                if filter_state:
                    filter_state.current_value = value

    def _sync_session_state_to_filters(self):
        """
        Sync Streamlit session state values back into FilterCollection.

        This is critical for ensuring filter values persist across reruns.
        When a filter is changed in the UI:
        1. Value is stored in st.session_state['filter_{filter_id}']
        2. Page reruns, notebook reloads, FilterCollection recreated
        3. This method syncs session state values back into FilterCollection
        4. Exhibits can now see the updated filter values via get_active_filters()

        Priority order for filter values:
        1. Session state (user interaction) - HIGHEST priority
        2. FilterState.current_value (folder context + notebook defaults)
        """
        if not hasattr(self.notebook_config, '_filter_collection') or not self.notebook_config._filter_collection:
            return

        try:
            import streamlit as st
        except ImportError:
            # Not running in Streamlit context
            return

        filter_collection = self.notebook_config._filter_collection

        # Sync each filter from session state
        for filter_id in filter_collection.filters.keys():
            session_key = f"filter_{filter_id}"

            # Check if this filter has a value in session state
            if session_key in st.session_state:
                session_value = st.session_state[session_key]

                # Update FilterState with session value (user interaction supersedes all)
                filter_state = filter_collection.get_state(filter_id)
                if filter_state:
                    filter_state.current_value = session_value

    def _create_filter_config_from_value(self, filter_id: str, value: Any):
        """
        Auto-create FilterConfig from folder context value.

        Infers filter type from value structure.

        Args:
            filter_id: Filter identifier
            value: Filter value (used to infer type)

        Returns:
            FilterConfig object
        """
        from app.notebook.filters.dynamic import FilterConfig, FilterType, FilterOperator

        # Generate friendly label
        label = filter_id.replace('_', ' ').title()

        # Infer type from value
        if isinstance(value, list):
            # Multi-select
            return FilterConfig(
                id=filter_id,
                type=FilterType.SELECT,
                label=label,
                multi=True,
                options=value,
                default=value
            )
        elif isinstance(value, dict):
            if 'start' in value and 'end' in value:
                # Date range
                return FilterConfig(
                    id=filter_id,
                    type=FilterType.DATE_RANGE,
                    label=label,
                    default=value
                )
            elif 'min' in value or 'max' in value:
                # Number range
                return FilterConfig(
                    id=filter_id,
                    type=FilterType.NUMBER_RANGE,
                    label=label,
                    default=value
                )
            else:
                # Generic dict - treat as text
                return FilterConfig(
                    id=filter_id,
                    type=FilterType.TEXT_SEARCH,
                    label=label,
                    default=str(value)
                )
        elif isinstance(value, (int, float)):
            # Number slider with min threshold
            return FilterConfig(
                id=filter_id,
                type=FilterType.SLIDER,
                label=label,
                min_value=0,
                max_value=int(value * 10) if value > 0 else 100,
                default=value,
                operator=FilterOperator.GREATER_EQUAL
            )
        elif isinstance(value, bool):
            # Boolean toggle
            return FilterConfig(
                id=filter_id,
                type=FilterType.BOOLEAN,
                label=label,
                default=value
            )
        else:
            # Text search fallback
            return FilterConfig(
                id=filter_id,
                type=FilterType.TEXT_SEARCH,
                label=label,
                default=str(value) if value else ""
            )

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

    def _models_are_related(self, model_a: str, model_b: str) -> bool:
        """
        Check if two models have a declared relationship.

        Uses NetworkX-based ModelGraph for efficient relationship checking.
        Handles both direct and transitive dependencies.

        Args:
            model_a: First model name (e.g., "forecast")
            model_b: Second model name (e.g., "company")

        Returns:
            True if models are related (direct or transitive), False otherwise
        """
        # Use the NetworkX-based ModelGraph from session
        if hasattr(self.session, 'model_graph'):
            return self.session.model_graph.are_related(model_a, model_b)

        # Fallback: assume not related if graph not available
        return False

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
        Build filters for an exhibit from UNIFIED filter collection.

        All filters (notebook + folder) are now merged in _filter_collection,
        so this method is simplified to a single source of truth.

        Filters are applied based on DECLARED MODEL RELATIONSHIPS:
        - Same model filters always apply
        - Cross-model filters apply if relationship exists (depends_on or graph edge)
        - This ensures graph structure is respected and prevents arbitrary cross-model contamination

        Args:
            exhibit: Exhibit configuration

        Returns:
            Dictionary of filters (column_name -> filter_value) for FilterEngine
        """
        filters = {}

        # Get exhibit's source model for relationship checking
        exhibit_model = None
        if hasattr(exhibit, 'source') and exhibit.source:
            try:
                exhibit_model, _ = self._parse_source(exhibit.source)
            except (ValueError, AttributeError):
                pass

        # Single source of truth: _filter_collection (contains merged notebook + folder filters)
        if (self.notebook_config and
            hasattr(self.notebook_config, '_filter_collection') and
            self.notebook_config._filter_collection):

            # Get active filters from unified collection
            filter_collection = self.notebook_config._filter_collection
            active_filters = filter_collection.get_active_filters()

            # Convert filter values to FilterEngine format
            from app.notebook.filters.dynamic import FilterType, FilterOperator

            for filter_id, value in active_filters.items():
                if value is None:
                    continue

                filter_config = filter_collection.get_filter(filter_id)
                if not filter_config:
                    # No config - use raw value (global filter)
                    filters[filter_id] = value
                    continue

                # Check if filter should apply based on model relationships
                if exhibit_model and filter_config.source:
                    filter_model = filter_config.source.model

                    # Same model - always apply
                    if filter_model == exhibit_model:
                        pass  # Apply filter

                    # Cross-model - check if relationship exists
                    elif not self._models_are_related(exhibit_model, filter_model):
                        # No relationship declared - skip this filter
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

        # Apply exhibit-level filters (override notebook/folder filters)
        if hasattr(exhibit, 'filters') and exhibit.filters:
            filters.update(exhibit.filters)

        # Apply automatic column mappings from graph metadata
        # This allows tables with different date columns to use standard filters
        # Example: fact_forecast_metrics uses metric_date, but filter is trade_date
        # The mapping {'trade_date': 'metric_date'} is extracted from graph edges
        if exhibit.source:
            try:
                model_name, table_name = self._parse_source(exhibit.source)
                # Get automatic mappings from UniversalSession based on graph edges
                column_mappings = self.session.get_filter_column_mappings(model_name, table_name)

                # DEBUG
                print(f"DEBUG: Exhibit source: {exhibit.source}")
                print(f"DEBUG: Model: {model_name}, Table: {table_name}")
                print(f"DEBUG: Column mappings: {column_mappings}")
                print(f"DEBUG: Filters before mapping: {filters}")

                if column_mappings:
                    # Remap filter columns
                    mapped_filters = {}
                    for filter_column, filter_value in filters.items():
                        if filter_column in column_mappings:
                            # Use mapped column name
                            mapped_column = column_mappings[filter_column]
                            mapped_filters[mapped_column] = filter_value
                        else:
                            # Keep original column name
                            mapped_filters[filter_column] = filter_value
                    filters = mapped_filters
                    print(f"DEBUG: Filters after mapping: {filters}")
            except Exception as e:
                # If mapping fails, continue with original filters
                print(f"DEBUG: Mapping failed with error: {e}")
                import traceback
                traceback.print_exc()

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
