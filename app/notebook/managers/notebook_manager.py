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

from typing import Dict, List, Optional, Any, Union
from pathlib import Path
import pandas as pd

from ..schema import NotebookConfig, Exhibit, ExhibitType, ColumnReference
from ..parsers import NotebookParser, MarkdownNotebookParser
from ..filters.context import FilterContext
from ..folder_context import FolderFilterContextManager
from models.api.session import UniversalSession
from models.registry import ModelRegistry
from core.session.filters import FilterEngine


def _extract_field(ref: Any) -> Optional[str]:
    """Extract field name from ColumnReference or return string as-is."""
    if ref is None:
        return None
    if isinstance(ref, ColumnReference):
        return ref.field
    return str(ref)


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
        if repo_root is None:
            from utils.repo import get_repo_root
            repo_root = get_repo_root()
        self.repo_root = repo_root

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

        # Extract required columns from exhibit config (for auto-join support)
        required_columns = self._extract_required_columns(exhibit)

        # Build filters BEFORE get_table for filter pushdown optimization
        filters = self._build_filters(exhibit)

        # Determine if we need aggregation based on dimension selector
        group_by, aggregations = self._determine_aggregation(exhibit)

        # Get data from UniversalSession with filters, auto-join, and aggregation
        # Passing filters here allows the session to push them down into the SQL query
        # BEFORE the expensive join and aggregation operations
        df = self.session.get_table(
            model_name,
            table_name,
            required_columns=required_columns if required_columns else None,
            filters=filters,  # FILTER PUSHDOWN: Apply filters BEFORE join/aggregation
            group_by=group_by,
            aggregations=aggregations
        )

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

    def _extract_required_columns(self, exhibit: Exhibit) -> Optional[List[str]]:
        """
        Extract all columns required by an exhibit.

        This enables auto-join functionality - the system can automatically
        join tables to get columns that don't exist in the base table.

        Args:
            exhibit: Exhibit configuration

        Returns:
            List of column names needed, or None if can't determine
        """
        required_cols = set()

        # Add x-axis column (ColumnReference object)
        x_col = None
        if hasattr(exhibit, 'x_axis') and exhibit.x_axis and hasattr(exhibit.x_axis, 'dimension'):
            x_col = _extract_field(exhibit.x_axis.dimension)
            if x_col:
                required_cols.add(x_col)

        # If x-axis is date_id (integer FK), also request calendar's date column
        # This enables human-readable date display via auto-join to temporal.dim_calendar
        if x_col == 'date_id':
            required_cols.add('date')  # Will trigger auto-join to temporal.dim_calendar

        # Add y-axis columns (ColumnReference objects)
        if hasattr(exhibit, 'y_axis') and exhibit.y_axis:
            if hasattr(exhibit.y_axis, 'measures') and exhibit.y_axis.measures:
                for m in exhibit.y_axis.measures:
                    field = _extract_field(m)
                    if field:
                        required_cols.add(field)
            elif hasattr(exhibit.y_axis, 'measure') and exhibit.y_axis.measure:
                # Handle both single measure and list of measures
                if isinstance(exhibit.y_axis.measure, list):
                    for m in exhibit.y_axis.measure:
                        field = _extract_field(m)
                        if field:
                            required_cols.add(field)
                else:
                    field = _extract_field(exhibit.y_axis.measure)
                    if field:
                        required_cols.add(field)

        # Add dimension selector dimensions
        if hasattr(exhibit, 'dimension_selector') and exhibit.dimension_selector:
            dim_selector = exhibit.dimension_selector
            if hasattr(dim_selector, 'available_dimensions'):
                for d in dim_selector.available_dimensions:
                    field = _extract_field(d)
                    if field:
                        required_cols.add(field)

        # Add measure selector measures
        if hasattr(exhibit, 'measure_selector') and exhibit.measure_selector:
            measure_selector = exhibit.measure_selector
            if hasattr(measure_selector, 'available_measures'):
                for m in measure_selector.available_measures:
                    field = _extract_field(m)
                    if field:
                        required_cols.add(field)

        # Add color_by column (ColumnReference object)
        if hasattr(exhibit, 'color_by') and exhibit.color_by:
            field = _extract_field(exhibit.color_by)
            if field:
                required_cols.add(field)

        # Add metric columns (for metric_cards)
        if hasattr(exhibit, 'metrics') and exhibit.metrics:
            for metric in exhibit.metrics:
                # Handle both 'column' (new format) and 'measure' (legacy)
                col_ref = getattr(metric, 'column', None) or getattr(metric, 'measure', None)
                if col_ref:
                    field = _extract_field(col_ref)
                    if field:
                        # Handle model.table.column format
                        if '.' in field:
                            field = field.split('.')[-1]
                        required_cols.add(field)

        # Add aggregate_by column (for aggregations)
        if hasattr(exhibit, 'aggregate_by') and exhibit.aggregate_by:
            agg_col = exhibit.aggregate_by
            if '.' in agg_col:
                agg_col = agg_col.split('.')[-1]
            required_cols.add(agg_col)

        # Add columns from data_table/great_table exhibits
        # These have a 'columns' attribute with column definitions
        if hasattr(exhibit, 'columns') and exhibit.columns:
            for col in exhibit.columns:
                # Handle different column formats:
                # 1. ColumnReference object -> extract field
                # 2. String with model.table.column format -> extract last part
                # 3. String: "ticker" -> add directly
                # 4. Dict: {id: "ticker", label: "Ticker"} -> extract id
                # 5. Object with id attr: GTColumnConfig -> extract id
                field = _extract_field(col)
                if field:
                    # Handle model.table.column format - extract just the column name
                    if '.' in field:
                        field = field.split('.')[-1]
                    required_cols.add(field)
                elif isinstance(col, dict) and 'id' in col:
                    col_id = col['id']
                    if '.' in col_id:
                        col_id = col_id.split('.')[-1]
                    required_cols.add(col_id)
                elif hasattr(col, 'id') and col.id:
                    col_id = col.id
                    if '.' in col_id:
                        col_id = col_id.split('.')[-1]
                    required_cols.add(col_id)

        # Add sort column if specified (for data_table/great_table)
        if hasattr(exhibit, 'sort') and exhibit.sort:
            sort_config = exhibit.sort
            if isinstance(sort_config, dict) and 'by' in sort_config:
                sort_col = sort_config['by']
                if '.' in sort_col:
                    sort_col = sort_col.split('.')[-1]
                required_cols.add(sort_col)
            elif hasattr(sort_config, 'by') and sort_config.by:
                sort_col = sort_config.by
                if '.' in sort_col:
                    sort_col = sort_col.split('.')[-1]
                required_cols.add(sort_col)

        # CRITICAL: Add filter columns so auto-join can bring them in
        # Without this, filters on columns that don't exist in the base table
        # (like ticker from dim_company when querying fact_income_statement)
        # get silently skipped by FilterEngine
        filter_columns = self._get_filter_columns_for_exhibit(exhibit)
        if filter_columns:
            required_cols.update(filter_columns)

        return list(required_cols) if required_cols else None

    def _get_filter_columns_for_exhibit(self, exhibit: Exhibit) -> set:
        """
        Get filter columns that need to be fetched for this exhibit.

        When a filter targets a column that doesn't exist in the base table
        (e.g., ticker filter applied to fact_income_statement which only has company_id),
        we need to include that column in required_columns so auto-join brings it in.

        Only includes filter columns when there's a valid join path:
        - Filter from same table as exhibit → include
        - Filter from dimension, exhibit is fact that references it → include
        - Filter from fact, exhibit is dimension → SKIP (no valid join path)

        Args:
            exhibit: Exhibit configuration

        Returns:
            Set of filter column names to add to required_columns
        """
        filter_columns = set()

        if not self.notebook_config or not hasattr(self.notebook_config, '_filter_collection'):
            return filter_columns

        filter_collection = self.notebook_config._filter_collection
        if not filter_collection:
            return filter_columns

        # Get exhibit's source model and table for relationship checking
        exhibit_model = None
        exhibit_table = None
        if hasattr(exhibit, 'source') and exhibit.source:
            try:
                exhibit_model, exhibit_table = self._parse_source(exhibit.source)
            except (ValueError, AttributeError):
                pass

        # Get active filters and add their columns
        # NOTE: Only includes filters that have an explicit source.column.
        # UI-only filters (like start_date, end_date) are translated to date ranges
        # later and don't need to be in required_columns.
        active_filters = filter_collection.get_active_filters()
        for filter_id, value in active_filters.items():
            if value is None:
                continue

            filter_config = filter_collection.get_filter(filter_id)
            if not filter_config:
                # No config - skip (don't add filter_id as column, it might be a UI parameter)
                continue

            # Only include filters that have an explicit source column
            # UI-only filters (start_date, end_date) are handled via date range translation
            if not filter_config.source or not filter_config.source.column:
                continue

            # Check if this filter should apply to this exhibit's model
            if exhibit_model:
                filter_model = filter_config.source.model
                filter_table = filter_config.source.table
                filter_column = filter_config.source.column

                # Only include if same model or related models
                if not self.session.should_apply_cross_model_filter(filter_model, exhibit_model):
                    continue

                # Check if there's a valid join path
                # Case 1: Same table - always include
                if filter_table == exhibit_table:
                    filter_columns.add(filter_column)
                    continue

                # Case 2: Filter is from dimension, exhibit is fact - valid join
                # (facts can join TO dimensions via FK)
                filter_is_dim = filter_table and filter_table.startswith('dim_')
                exhibit_is_fact = exhibit_table and exhibit_table.startswith('fact_')
                if filter_is_dim and exhibit_is_fact:
                    filter_columns.add(filter_column)
                    continue

                # Case 3: Filter is from fact, exhibit is dimension - NO valid join
                # (dimensions don't join TO facts - that's a one-to-many)
                filter_is_fact = filter_table and filter_table.startswith('fact_')
                exhibit_is_dim = exhibit_table and exhibit_table.startswith('dim_')
                if filter_is_fact and exhibit_is_dim:
                    # Skip - no valid join path from dimension to fact
                    continue

                # Case 4: Both dimensions - include (may or may not join)
                if filter_is_dim and exhibit_is_dim:
                    filter_columns.add(filter_column)
                    continue

                # Default: include and let auto-join figure it out
                filter_columns.add(filter_column)

        return filter_columns

    def _determine_aggregation(self, exhibit: Exhibit) -> tuple[Optional[List[str]], Optional[Dict[str, str]]]:
        """
        Determine if data needs aggregation based on exhibit configuration or dimension selector.

        Checks for aggregation configuration in this order:
        1. Explicit group_by and aggregations fields in exhibit YAML
        2. Smart defaults: If aggregations specified but group_by is not, auto-detect from x-axis and color_by
        3. Dynamic dimension selector (for UI-driven aggregation)

        Args:
            exhibit: Exhibit configuration

        Returns:
            Tuple of (group_by, aggregations):
                - group_by: List of columns to group by (None if no aggregation)
                - aggregations: Dict of measure -> agg function (None to use defaults)

        Examples:
            # Aggregate across all tickers (one line)
            aggregations: {close: avg}
            group_by: [trade_date]

            # Split by ticker (one line per ticker)
            aggregations: {close: avg}
            group_by: [trade_date, ticker]
            color_by: ticker
        """
        aggregations = getattr(exhibit, 'aggregations', None)

        # Note: aggregations can be either dict format {col: agg} or list format
        # [{column: col, aggregation: agg, label: alias}, ...]. The list format
        # supports multiple aggregations per column and custom labels.
        # aggregation.py handles both formats.

        # First, check for explicit group_by configuration
        if hasattr(exhibit, 'group_by') and exhibit.group_by:
            group_by_cols = exhibit.group_by if isinstance(exhibit.group_by, list) else [exhibit.group_by]
            print(f"📊 Using explicit aggregation config: group_by={group_by_cols}, aggregations={aggregations}")
            return (group_by_cols, aggregations)

        # Second, check if aggregations defined without group_by (smart defaults)
        if aggregations:
            group_by_cols = []

            # Always include x-axis in group_by for time-series aggregation (ColumnReference)
            if hasattr(exhibit, 'x_axis') and exhibit.x_axis and hasattr(exhibit.x_axis, 'dimension'):
                x_field = _extract_field(exhibit.x_axis.dimension)
                if x_field:
                    group_by_cols.append(x_field)

            # If color_by is specified, include it in group_by to split the visualization
            # This allows one line/bar per dimension value (e.g., one line per ticker)
            if hasattr(exhibit, 'color_by') and exhibit.color_by:
                color_field = _extract_field(exhibit.color_by)
                if color_field and color_field not in group_by_cols:
                    group_by_cols.append(color_field)

            if group_by_cols:
                print(f"📊 Using smart default aggregation: group_by={group_by_cols}, aggregations={aggregations}")
                return (group_by_cols, aggregations)

        # Fall back to dimension selector logic
        # Check if exhibit has dimension selector
        if not (hasattr(exhibit, 'dimension_selector') and exhibit.dimension_selector):
            return (None, None)

        # Get the selected dimension from session state
        try:
            from app.ui.components.exhibits.dimension_selector import get_selected_dimension
            selected_dimension = get_selected_dimension(exhibit.id)

            if not selected_dimension:
                # No dimension selected yet, use default
                if hasattr(exhibit.dimension_selector, 'default_dimension'):
                    selected_dimension = exhibit.dimension_selector.default_dimension
                else:
                    return (None, None)
        except Exception as e:
            print(f"Warning: Could not get selected dimension: {e}")
            return (None, None)

        # Determine base grain from source table
        # For fact tables, typically ticker is the base grain
        # For dimension changes (ticker → exchange_name), we need aggregation
        base_grain_columns = ['ticker', 'company_id']  # Common base grain identifiers

        # If selected dimension is the base grain, no aggregation needed
        if selected_dimension in base_grain_columns:
            return (None, None)

        # Dimension changed to higher level - need aggregation
        # Group by: x-axis (time/category) + selected dimension
        group_by_cols = []

        # Add x-axis column (ColumnReference)
        if hasattr(exhibit, 'x_axis') and exhibit.x_axis and hasattr(exhibit.x_axis, 'dimension'):
            x_field = _extract_field(exhibit.x_axis.dimension)
            if x_field:
                group_by_cols.append(x_field)

        # Add selected dimension
        if selected_dimension:
            group_by_cols.append(selected_dimension)

        if not group_by_cols:
            # No grouping columns identified
            return (None, None)

        print(f"📊 Dimension selector: aggregating from base grain to {selected_dimension}")

        # Let UniversalSession infer aggregations from measure metadata
        # (avg for prices, sum for volumes, etc.)
        return (group_by_cols, None)

    # ============================================================
    # REMOVED: _models_are_related
    #
    # This method has been removed and replaced with
    # session.should_apply_cross_model_filter() which centralizes
    # cross-model filter validation logic in UniversalSession.
    #
    # See GRAPH_REFACTOR_SCAN.md for details.
    # ============================================================

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

                # Check if filter should apply based on model relationships or column existence
                if exhibit_model and filter_config.source:
                    filter_model = filter_config.source.model
                    filter_column = filter_config.source.column

                    # Check if filter should be applied:
                    # 1. Same model or related models via graph (relationship check)
                    # 2. OR the filter column exists in the target table (direct column match)
                    if not self.session.should_apply_cross_model_filter(filter_model, exhibit_model):
                        # No relationship declared - check if column exists in target table
                        # This handles cases like ticker filter from company applying to stocks
                        try:
                            _, exhibit_table = self._parse_source(exhibit.source)
                            if not self.session.column_exists_in_table(exhibit_model, exhibit_table, filter_column):
                                # Column doesn't exist in target table - skip this filter
                                continue
                        except (ValueError, AttributeError):
                            # Can't determine target table - skip filter to be safe
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
            except Exception:
                # If mapping fails, continue with original filters
                pass

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
