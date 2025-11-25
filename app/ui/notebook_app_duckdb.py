"""
Professional notebook application with DuckDB backend.

Modern, streamlined UI with markdown notebooks.

Features:
- DuckDB backend (10-100x faster than Spark)
- Markdown notebooks with dynamic filters
- Database-driven filter options
- Professional design with dark/light themes
- Inline exhibit and filter syntax
- Collapsible sections with <details> tags

Usage:
    streamlit run app/ui/notebook_app_duckdb.py
"""

import streamlit as st
import sys
from pathlib import Path
from typing import Dict, Any

# Bootstrap: Add repo to path before importing utils.repo
# This handles the case when streamlit is run from any directory
_current_file = Path(__file__).resolve()
_repo_root = None
for _parent in [_current_file.parent] + list(_current_file.parents):
    if (_parent / "configs").exists() and (_parent / "core").exists():
        _repo_root = _parent
        break
if _repo_root and str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

from core.context import RepoContext
from models.registry import ModelRegistry
from models.api.session import UniversalSession
from app.notebook.managers import NotebookManager

# Import modular UI components
from app.ui.components.theme import apply_professional_theme
from app.ui.components.sidebar import SidebarNavigator, close_tab
from app.ui.components.filters import render_filters_section
from app.ui.components.notebook_view import render_notebook_exhibits


# Configure page
st.set_page_config(
    page_title="Data Notebooks",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


# Session state initialization
if 'open_tabs' not in st.session_state:
    st.session_state.open_tabs = []

if 'active_tab' not in st.session_state:
    st.session_state.active_tab = None

if 'edit_mode' not in st.session_state:
    st.session_state.edit_mode = {}

if 'block_edit_mode' not in st.session_state:
    st.session_state.block_edit_mode = {}  # Per-notebook block editing toggle

if 'markdown_content' not in st.session_state:
    st.session_state.markdown_content = {}

if 'theme' not in st.session_state:
    st.session_state.theme = 'dark'

if 'show_notebook_creator' not in st.session_state:
    st.session_state.show_notebook_creator = False

# Cache model sessions per notebook to avoid reinitializing
if 'notebook_model_sessions' not in st.session_state:
    st.session_state.notebook_model_sessions = {}

# Initialize app-level objects in session state (per-user, per-tab)
if 'repo_context' not in st.session_state:
    st.session_state.repo_context = RepoContext.from_repo_root(connection_type="duckdb")

if 'model_registry' not in st.session_state:
    ctx = st.session_state.repo_context
    st.session_state.model_registry = ModelRegistry(ctx.repo / "configs" / "models")

if 'universal_session' not in st.session_state:
    ctx = st.session_state.repo_context
    st.session_state.universal_session = UniversalSession(
        connection=ctx.connection,
        storage_cfg=ctx.storage,
        repo_root=ctx.repo
    )

if 'notebook_manager' not in st.session_state:
    ctx = st.session_state.repo_context
    notebooks_root = ctx.repo / "configs" / "notebooks"
    st.session_state.notebook_manager = NotebookManager(
        st.session_state.universal_session,
        ctx.repo,
        notebooks_root
    )

# Apply theme
apply_professional_theme()


class NotebookVaultApp:
    """Professional notebook application with modern UI."""

    def __init__(self):
        """Initialize application - uses session state objects."""
        self.ctx = st.session_state.repo_context
        self.model_registry = st.session_state.model_registry
        self.universal_session = st.session_state.universal_session
        self.notebook_manager = st.session_state.notebook_manager
        self.notebooks_root = self.ctx.repo / "configs" / "notebooks"
        self.notebooks_root.mkdir(parents=True, exist_ok=True)
        self.sidebar_nav = SidebarNavigator(self.notebooks_root, self.notebook_manager)

    def run(self):
        """Run the application."""
        # Professional header with controls
        self._render_header()

        # Sidebar: Navigation + Filters
        with st.sidebar:
            self.sidebar_nav.render()

            if st.session_state.active_tab:
                st.divider()
                active_notebook = self._get_active_notebook()
                if active_notebook:
                    self._render_filters(active_notebook[2])

        # Main content area
        self._render_main_content()

    def _render_header(self):
        """Render professional header with toolbar and tabs."""
        # Row 1: Block Edit, Filter, and Theme buttons on the right
        col_spacer, col_block, col_filter, col_theme = st.columns([0.7, 0.1, 0.1, 0.1])

        with col_block:
            # Block edit toggle (only if active notebook)
            if st.session_state.active_tab:
                active_notebook = self._get_active_notebook()
                if active_notebook:
                    notebook_id = active_notebook[0]
                    in_block_edit = st.session_state.block_edit_mode.get(notebook_id, False)

                    block_icon = "✏️" if in_block_edit else "📝"
                    block_help = "Exit edit mode" if in_block_edit else "Edit notebook blocks"

                    if st.button(block_icon, help=block_help, key="toolbar_block_edit", use_container_width=True):
                        st.session_state.block_edit_mode[notebook_id] = not in_block_edit
                        st.rerun()

        with col_filter:
            # Filter editor button (only if active notebook)
            if st.session_state.active_tab:
                active_notebook = self._get_active_notebook()
                if active_notebook:
                    # Initialize filter editor state
                    if 'filter_editor_open' not in st.session_state:
                        st.session_state.filter_editor_open = False

                    filter_icon = "🔍"
                    filter_help = "Edit filter definitions"

                    if st.button(filter_icon, help=filter_help, key="toolbar_filter", use_container_width=True):
                        st.session_state.filter_editor_open = not st.session_state.filter_editor_open
                        st.rerun()

        with col_theme:
            # Theme button
            theme_icon = "🌙" if st.session_state.theme == 'light' else "☀️"
            theme_help = "Dark mode" if st.session_state.theme == 'light' else "Light mode"

            if st.button(theme_icon, help=theme_help, key="toolbar_theme", use_container_width=True):
                st.session_state.theme = 'dark' if st.session_state.theme == 'light' else 'light'
                st.rerun()

        # Row 2: Tabs below (if any notebooks are open)
        if st.session_state.open_tabs:
            num_tabs = min(len(st.session_state.open_tabs), 6)
            tab_cols = st.columns(num_tabs)

            for i, (notebook_id, notebook_path, notebook_config) in enumerate(st.session_state.open_tabs[:num_tabs]):
                with tab_cols[i]:
                    is_active = st.session_state.active_tab == notebook_id
                    title = notebook_config.notebook.title

                    if len(title) > 28:
                        title = title[:25] + "..."

                    button_type = "primary" if is_active else "secondary"
                    tab_col, close_col = st.columns([0.92, 0.08])

                    with tab_col:
                        if st.button(
                            title,
                            key=f"tab_btn_{notebook_id}",
                            type=button_type,
                            use_container_width=True,
                            help=notebook_config.notebook.title
                        ):
                            if st.session_state.active_tab != notebook_id:
                                st.session_state.active_tab = notebook_id
                                st.rerun()

                    with close_col:
                        if st.button(
                            "✕",
                            key=f"close_tab_{notebook_id}",
                            help=f"Close {notebook_config.notebook.title}",
                            use_container_width=True
                        ):
                            close_tab(notebook_id)

            if len(st.session_state.open_tabs) > num_tabs:
                st.caption(f"+ {len(st.session_state.open_tabs) - num_tabs} more tabs (use sidebar)")

        st.divider()

    def _render_folder_filter_editor(self):
        """Render YAML editor for folder filter context file."""
        if not hasattr(self.notebook_manager, 'folder_context_manager'):
            st.warning("⚠️ Folder context manager not available")
            return

        folder_ctx_mgr = self.notebook_manager.folder_context_manager
        current_folder = self.notebook_manager.get_current_folder()

        if not current_folder:
            st.caption("_No notebook loaded_")
            return

        folder_name = current_folder.name
        context_file = folder_ctx_mgr.get_context_file_path(current_folder)
        file_exists = context_file.exists()

        # Header
        st.markdown(f"### 📁 Folder: {folder_name}")
        st.caption("_Filters shared by all notebooks in this folder_")

        # Show file status
        if file_exists:
            st.caption(f"✅ `.filter_context.yaml` exists")
        else:
            st.caption(f"ℹ️ No `.filter_context.yaml` yet (will be created on save)")

        # Show current filter values
        current_filters = folder_ctx_mgr.get_filters(current_folder)

        with st.expander("📊 Active Filters", expanded=True):
            if current_filters:
                for key, value in current_filters.items():
                    if isinstance(value, dict) and 'start' in value:
                        st.caption(f"**{key}**: {value.get('start')} to {value.get('end')}")
                    elif isinstance(value, list):
                        st.caption(f"**{key}**: {', '.join(map(str, value[:5]))}{'...' if len(value) > 5 else ''}")
                    else:
                        st.caption(f"**{key}**: `{value}`")
            else:
                st.info("📝 **No filters set**\n\nClick 'Edit Filter Context' below to add filters.\n\nExample:\n```yaml\nfilters:\n  ticker: AAPL\n  date_range:\n    start: 2024-10-01\n    end: 2024-11-01\n```")

        # Edit button
        filter_edit_key = f"filter_edit_{current_folder}"

        if filter_edit_key not in st.session_state:
            st.session_state[filter_edit_key] = False

        if not st.session_state[filter_edit_key]:
            # View mode - show edit button (prominent)
            st.button("✏️ Edit Filter Context",
                     key=f"btn_edit_{current_folder}",
                     use_container_width=True,
                     type="primary" if not current_filters else "secondary",
                     on_click=lambda: st.session_state.update({filter_edit_key: True}))
        else:
            # Edit mode - show YAML editor
            st.success("📝 **Editing** `.filter_context.yaml`")

            # Load current YAML content
            yaml_content = folder_ctx_mgr.get_context_yaml_content(current_folder)

            # Show helpful message if empty
            if not current_filters:
                st.info("💡 **Tip**: Add filters in YAML format below, then click Save")

            # YAML editor
            edited_yaml = st.text_area(
                "YAML Content",
                value=yaml_content,
                height=400,
                key=f"yaml_editor_{current_folder}",
                help="Edit filters in YAML format - changes apply to all notebooks in this folder"
            )

            # Buttons
            col1, col2, col3 = st.columns(3)

            with col1:
                if st.button("💾 Save", key=f"save_{current_folder}", use_container_width=True, type="primary"):
                    try:
                        # Validate YAML
                        import yaml
                        parsed = yaml.safe_load(edited_yaml)

                        if parsed and 'filters' in parsed:
                            st.success(f"✅ Valid YAML! Found {len(parsed['filters'])} filter(s)")

                        # Save
                        folder_ctx_mgr.save_context_yaml_content(current_folder, edited_yaml)

                        st.success("✅ Saved!")
                        st.session_state[filter_edit_key] = False
                        st.rerun()
                    except yaml.YAMLError as e:
                        st.error(f"❌ Invalid YAML syntax:\n```\n{str(e)}\n```")
                    except Exception as e:
                        st.error(f"❌ Error saving: {e}")

            with col2:
                if st.button("❌ Cancel", key=f"cancel_{current_folder}", use_container_width=True):
                    st.session_state[filter_edit_key] = False
                    st.rerun()

            with col3:
                if st.button("🗑️ Delete", key=f"delete_{current_folder}", use_container_width=True):
                    try:
                        folder_ctx_mgr.delete_context(current_folder)
                        st.success("✅ Deleted!")
                        st.session_state[filter_edit_key] = False
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

            # Show file location
            st.caption(f"📄 File: `{context_file.relative_to(context_file.parent.parent)}`")

    def _render_filter_context_info_OLD(self):
        """Render filter context information and controls."""
        # Check if folder context manager exists
        if not hasattr(self.notebook_manager, 'folder_context_manager'):
            st.warning("⚠️ Folder context manager not initialized")
            return

        try:
            folder_name = self.notebook_manager.get_folder_display_name()
            folder_ctx_mgr = self.notebook_manager.folder_context_manager
            current_folder = self.notebook_manager.get_current_folder()
        except Exception as e:
            st.error(f"Error accessing folder context: {e}")
            return

        if not current_folder:
            st.caption("_No notebook loaded_")
            return

        # Get global and folder-specific filters
        try:
            global_filters = folder_ctx_mgr.get_global_filters()
            folder_filters = folder_ctx_mgr.get_folder_specific_filters(current_folder)
        except Exception as e:
            st.error(f"Error loading filters: {e}")
            global_filters = {}
            folder_filters = {}

        # Filter context header
        st.markdown("### 🎛️ Filter Context")

        # EDITABLE CONTROLS SECTION
        st.markdown("#### ✏️ Edit Filters")

        # Global ticker filter
        with st.container():
            st.caption("🌍 **Global Filters** (shared across all folders)")

            # Ticker multi-select
            current_tickers = global_filters.get('ticker', global_filters.get('tickers', []))
            if not isinstance(current_tickers, list):
                current_tickers = [current_tickers] if current_tickers else []

            # Get ticker options from database
            ticker_options = self._get_available_tickers()

            new_tickers = st.multiselect(
                "🌍 Ticker Selection",
                options=ticker_options,
                default=current_tickers,
                key="global_ticker_edit",
                help="Select tickers - shared across all folders"
            )

            # Date range filter
            from datetime import datetime, timedelta
            current_date_range = global_filters.get('date_range', {})

            if isinstance(current_date_range, dict) and 'start' in current_date_range:
                default_start = current_date_range['start']
                default_end = current_date_range['end']
                if isinstance(default_start, str):
                    default_start = datetime.fromisoformat(default_start).date()
                elif isinstance(default_start, datetime):
                    default_start = default_start.date()
                if isinstance(default_end, str):
                    default_end = datetime.fromisoformat(default_end).date()
                elif isinstance(default_end, datetime):
                    default_end = default_end.date()
            else:
                default_start = (datetime.now() - timedelta(days=30)).date()
                default_end = datetime.now().date()

            col1, col2 = st.columns(2)
            with col1:
                start_date = st.date_input(
                    "🌍 Start Date",
                    value=default_start,
                    key="global_date_start"
                )
            with col2:
                end_date = st.date_input(
                    "🌍 End Date",
                    value=default_end,
                    key="global_date_end"
                )

            # Update button for global filters
            if st.button("💾 Save Global Filters", key="save_global", use_container_width=True):
                new_global = {}
                if new_tickers:
                    new_global['ticker'] = new_tickers[0] if len(new_tickers) == 1 else new_tickers
                    new_global['tickers'] = new_tickers
                if start_date and end_date:
                    new_global['date_range'] = {
                        'start': datetime.combine(start_date, datetime.min.time()),
                        'end': datetime.combine(end_date, datetime.min.time())
                    }

                folder_ctx_mgr.update_filters(current_folder, new_global, auto_save=True)
                st.success("✅ Global filters saved!")
                st.rerun()

        st.divider()

        # DISPLAY CURRENT VALUES (Read-only summary)
        st.markdown("#### 📊 Current Filter Values")

        # Global context section (read-only display)
        with st.expander("🌍 Global Context", expanded=bool(global_filters)):
            st.caption("_Shared across all folders_")

            if global_filters:
                for key, value in global_filters.items():
                    try:
                        if isinstance(value, dict) and 'start' in value:
                            st.caption(f"**{key}**: {value['start']} to {value['end']}")
                        elif isinstance(value, list):
                            st.caption(f"**{key}**: {', '.join(map(str, value[:3]))}{'...' if len(value) > 3 else ''}")
                        else:
                            st.caption(f"**{key}**: {value}")
                    except Exception as e:
                        st.caption(f"**{key}**: (error displaying)")
            else:
                st.caption("_No global filters set_")

            # Clear global filters button
            if global_filters and st.button("🗑️ Clear Global", key="clear_global", use_container_width=True):
                try:
                    folder_ctx_mgr.clear_global_filters()
                    st.success("✅ Global filters cleared!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error clearing: {e}")

        # Folder context section (read-only display)
        with st.expander(f"📁 {folder_name}", expanded=bool(folder_filters)):
            st.caption("_Shared within this folder only_")

            if folder_filters:
                for key, value in folder_filters.items():
                    try:
                        if isinstance(value, dict) and 'start' in value:
                            st.caption(f"**{key}**: {value['start']} to {value['end']}")
                        elif isinstance(value, list):
                            st.caption(f"**{key}**: {', '.join(map(str, value[:3]))}{'...' if len(value) > 3 else ''}")
                        else:
                            st.caption(f"**{key}**: {value}")
                    except Exception as e:
                        st.caption(f"**{key}**: (error displaying)")
            else:
                st.caption("_No folder-specific filters set_")

            # Control buttons row
            col1, col2 = st.columns(2)

            with col1:
                if folder_filters and st.button("🗑️ Folder", key="clear_folder", use_container_width=True):
                    try:
                        folder_ctx_mgr.clear_filters(current_folder)
                        st.success("✅ Folder cleared!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

            with col2:
                if (global_filters or folder_filters) and st.button("🗑️ All", key="clear_all", use_container_width=True):
                    try:
                        folder_ctx_mgr.clear_all_filters(current_folder)
                        st.success("✅ All cleared!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

    def _get_available_tickers(self):
        """Get list of available tickers from database."""
        try:
            # Try to get tickers from company model
            df = self.universal_session.get_table('company', 'dim_company')
            pdf = self.ctx.connection.to_pandas(df)
            if 'ticker' in pdf.columns:
                tickers = sorted(pdf['ticker'].dropna().unique().tolist())
                return tickers
        except Exception as e:
            st.caption(f"ℹ️ Could not load tickers from database: {e}")

        # Fallback to common tickers
        return ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'NVDA', 'JPM', 'V', 'WMT']

    def _render_filters(self, notebook_config):
        """Render filters for active notebook."""
        # Only support dynamic filters ($filter$ syntax in markdown)
        if (hasattr(notebook_config, '_filter_collection') and
            notebook_config._filter_collection and
            notebook_config._filter_collection.filters):
            from app.ui.components.dynamic_filters import render_dynamic_filters
            from app.ui.components.active_filters_display import render_active_filters_summary

            # CRITICAL: Sync session state to filters BEFORE rendering
            # This ensures filter changes from previous interactions are reflected
            self.notebook_manager._sync_session_state_to_filters()

            # Show active filter summary FIRST (above filters)
            render_active_filters_summary(notebook_config._filter_collection)
            st.divider()

            # Render filter widgets
            render_dynamic_filters(
                notebook_config._filter_collection,
                self.notebook_manager,
                self.ctx.connection,
                self.universal_session
            )
        else:
            st.info("ℹ️ No filters defined in this notebook.\n\nAdd filters using `$filter${...}` syntax in your markdown.")

    def _get_active_notebook(self):
        """Get the active notebook tuple."""
        return next(
            (tab for tab in st.session_state.open_tabs if tab[0] == st.session_state.active_tab),
            None
        )

    def _render_filter_editor(self):
        """Render filter editor for the active notebook."""
        active_notebook = self._get_active_notebook()
        if not active_notebook:
            st.warning("No active notebook")
            return

        notebook_id, notebook_path, notebook_config = active_notebook

        # Header
        st.title("🔍 Filter Editor")
        st.markdown(f"**Notebook:** {notebook_config.notebook.title}")
        st.caption(f"File: `{notebook_path.name}`")
        st.divider()

        # Check if notebook has filter collection
        if not hasattr(notebook_config, '_filter_collection') or not notebook_config._filter_collection:
            st.info("This notebook has no filters defined yet.")
            st.markdown("""
            **Add filters to your notebook** by editing the markdown file and adding `$filter${...}` blocks.

            Example:
            ```markdown
            $filter${
              id: ticker
              label: Stock Tickers
              type: select
              multi: true
              source: {model: company, table: fact_prices, column: ticker}
              help_text: Select stocks to analyze
            }
            ```
            """)
            return

        # Display current filters
        st.subheader("📋 Current Filter Definitions")

        filter_collection = notebook_config._filter_collection

        # Show each filter in an expandable section
        for filter_id, filter_config in filter_collection.filters.items():
            with st.expander(f"**{filter_config.label}** (`{filter_id}`)", expanded=True):
                col1, col2 = st.columns(2)

                with col1:
                    st.markdown("**Type:**")
                    st.code(filter_config.type.value)

                    st.markdown("**ID:**")
                    st.code(filter_id)

                    if filter_config.help_text:
                        st.markdown("**Help Text:**")
                        st.caption(filter_config.help_text)

                with col2:
                    st.markdown("**Default Value:**")
                    st.json(filter_config.default)

                    if filter_config.source:
                        st.markdown("**Source:**")
                        st.code(f"{filter_config.source.model}.{filter_config.source.table}.{filter_config.source.column}")

                    st.markdown("**Operator:**")
                    st.code(filter_config.operator.value if filter_config.operator else "N/A")

                # Show current value from session state
                filter_state = filter_collection.get_state(filter_id)
                if filter_state:
                    st.markdown("**Current Runtime Value:**")
                    session_key = f"filter_{filter_id}"
                    current_value = st.session_state.get(session_key, filter_state.current_value)
                    st.json(current_value)

        st.divider()

        # Instructions for editing
        st.subheader("✏️ How to Edit Filters")
        st.markdown("""
        To modify filter definitions:

        1. **Click the Edit button** (✏️) in the toolbar to switch to edit mode
        2. **Edit the `$filter${...}` blocks** directly in the markdown
        3. **Save your changes** to update the filters

        **Filter Properties:**
        - `id`: Unique identifier for the filter
        - `label`: Display name shown to users
        - `type`: Filter type (`select`, `date_range`, `slider`, `text_search`, `boolean`, `number_range`)
        - `multi`: (for select) Allow multiple selections
        - `source`: Database source for dynamic options `{model: X, table: Y, column: Z}`
        - `default`: Default value
        - `operator`: SQL operator (`in`, `eq`, `gte`, `lte`, `between`, `like`)
        - `help_text`: Help text shown to users
        - `min_value`, `max_value`, `step`: (for slider/number_range)
        - `placeholder`: Placeholder text
        """)

        # Example template
        with st.expander("📄 Filter Template"):
            st.code("""$filter${
  id: my_filter
  label: My Filter Label
  type: select
  multi: true
  source: {model: my_model, table: my_table, column: my_column}
  default: []
  operator: in
  help_text: Description of what this filter does
}""", language="markdown")

        st.divider()

        # Close button
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("✅ Close Filter Editor", use_container_width=True, type="primary"):
                st.session_state.filter_editor_open = False
                st.rerun()

    def _render_main_content(self):
        """Render main content area."""
        # Check if notebook creator is open
        if st.session_state.get('show_notebook_creator', False):
            self._render_notebook_creator()
            return

        # Check if graph viewer is open
        if st.session_state.get('show_graph_viewer', False):
            self._render_graph_viewer()
            return

        if not st.session_state.open_tabs:
            self._render_welcome()
            return

        # Check if filter editor is open
        if st.session_state.get('filter_editor_open', False):
            self._render_filter_editor()
            return

        # Render active notebook
        active_notebook = self._get_active_notebook()
        if active_notebook:
            self._render_notebook_content(active_notebook)

    def _render_notebook_creator(self):
        """Render the notebook creation form."""
        from app.ui.components.notebook_creator import render_notebook_creator

        # Header with close button
        col1, col2 = st.columns([0.9, 0.1])
        with col1:
            st.title("Create New Notebook")
        with col2:
            if st.button("✕", help="Close", key="close_creator"):
                st.session_state.show_notebook_creator = False
                st.rerun()

        st.divider()

        # Get available models
        try:
            available_models = list(self.model_registry.list_models())
        except Exception:
            available_models = []

        # Render the creator
        render_notebook_creator(
            notebooks_root=self.notebooks_root,
            available_models=available_models,
            on_create=self._handle_notebook_created
        )

    def _handle_notebook_created(self, notebook_path: Path):
        """
        Handle notebook creation callback.

        Opens the newly created notebook.

        Args:
            notebook_path: Path to the created notebook
        """
        # Close the creator
        st.session_state.show_notebook_creator = False

        # Open the new notebook
        notebook_id = str(notebook_path.relative_to(self.notebooks_root))

        try:
            notebook_config = self.notebook_manager.load_notebook(str(notebook_path))
            st.session_state.open_tabs.append((notebook_id, notebook_path, notebook_config))
            st.session_state.active_tab = notebook_id
            st.session_state.edit_mode[notebook_id] = True  # Open in edit mode
            st.rerun()
        except Exception as e:
            st.error(f"Error opening notebook: {str(e)}")

    def _render_graph_viewer(self):
        """Render full model graph viewer."""
        from app.ui.components.model_graph_viewer import (
            render_model_graph,
            render_graph_debug_panel,
            render_relationship_checker
        )

        # Header with close button
        col1, col2 = st.columns([0.9, 0.1])
        with col1:
            st.title("🔗 Model Dependency Graph")
        with col2:
            if st.button("✕", help="Close", key="close_graph_viewer"):
                st.session_state.show_graph_viewer = False
                st.rerun()

        # Get model graph from session
        if hasattr(self.notebook_manager, 'session') and hasattr(self.notebook_manager.session, 'model_graph'):
            model_graph = self.notebook_manager.session.model_graph

            # Render main graph visualization
            render_model_graph(model_graph)

            st.divider()

            # Render relationship checker
            render_relationship_checker(model_graph)

            st.divider()

            # Render debug panel (collapsed)
            render_graph_debug_panel(model_graph)
        else:
            st.error("Model graph not available")
            if st.button("Back to Notebooks"):
                st.session_state.show_graph_viewer = False
                st.rerun()

    def _render_notebook_content(self, notebook_tuple):
        """Render notebook content (edit or view mode)."""
        notebook_id, notebook_path, notebook_config = notebook_tuple

        # Ensure the notebook session is synced with this notebook
        # Cache model sessions per notebook to avoid expensive reinitializations
        if 'current_notebook_id' not in st.session_state:
            st.session_state.current_notebook_id = None

        if st.session_state.current_notebook_id != notebook_id:
            # Switching to a different notebook
            # Set the config (already parsed and loaded in sidebar)
            self.notebook_manager.notebook_config = notebook_config
            self.notebook_manager.current_notebook_path = notebook_path

            # CRITICAL: Update folder context WITHOUT calling load_notebook()
            # (load_notebook creates DuckDB connections which causes segfaults during render)
            new_folder = self.notebook_manager.folder_context_manager.get_folder_for_notebook(notebook_path)
            self.notebook_manager.current_folder = new_folder

            # Load folder filters for the new folder
            folder_filters = self.notebook_manager.folder_context_manager.get_filters(new_folder)

            # Reinitialize filter context with folder filters
            from app.notebook.filters.context import FilterContext
            self.notebook_manager.filter_context = FilterContext(self.notebook_manager.notebook_config.variables)
            if folder_filters:
                # Apply all folder filters (we'll use them even if not in notebook variables)
                for key, value in folder_filters.items():
                    try:
                        self.notebook_manager.filter_context.set(key, value)
                    except (ValueError, KeyError):
                        # Filter not in notebook variables - store it anyway for later use
                        if not hasattr(self.notebook_manager, '_extra_folder_filters'):
                            self.notebook_manager._extra_folder_filters = {}
                        self.notebook_manager._extra_folder_filters[key] = value

            # Check if we have cached model sessions for this notebook
            if notebook_id in st.session_state.notebook_model_sessions:
                # Restore cached model sessions
                self.notebook_manager.model_sessions = st.session_state.notebook_model_sessions[notebook_id]
            else:
                # Initialize model sessions for the first time
                self.notebook_manager._initialize_model_sessions()
                # Cache them for future switches
                st.session_state.notebook_model_sessions[notebook_id] = self.notebook_manager.model_sessions.copy()

            st.session_state.current_notebook_id = notebook_id

        # Render notebook content
        self._render_notebook_view(notebook_id, notebook_config)

    def _render_notebook_view(self, notebook_id, notebook_config):
        """Render notebook in view mode."""
        # Check if block editing is enabled
        block_edit_enabled = st.session_state.block_edit_mode.get(notebook_id, False)

        # Render notebook exhibits with editable flag
        render_notebook_exhibits(
            notebook_id,
            notebook_config,
            self.notebook_manager,
            self.ctx.connection,
            editable=block_edit_enabled,
            on_block_edit=self._handle_block_edit if block_edit_enabled else None,
            on_block_insert=self._handle_block_insert if block_edit_enabled else None,
            on_block_delete=self._handle_block_delete if block_edit_enabled else None,
            on_header_edit=self._handle_header_edit if block_edit_enabled else None
        )

    def _handle_block_edit(self, block_index: int, new_content: str):
        """
        Handle block edit from the renderer.

        Saves the updated block content to the notebook file.

        Args:
            block_index: Index of the block that was edited
            new_content: New content for the block
        """
        active_notebook = self._get_active_notebook()
        if not active_notebook:
            st.error("No active notebook")
            return

        notebook_id, notebook_path, notebook_config = active_notebook

        try:
            # Use the parser to save the block update
            from app.notebook.parsers.markdown_parser import MarkdownNotebookParser
            parser = MarkdownNotebookParser(self.ctx.repo)
            parser.save_block_update(str(notebook_path), block_index, new_content)

            # Reload the notebook to reflect changes
            updated_config = self.notebook_manager.load_notebook(str(notebook_path))

            # Update the tab with new config
            for i, (tab_id, tab_path, tab_config) in enumerate(st.session_state.open_tabs):
                if tab_id == notebook_id:
                    st.session_state.open_tabs[i] = (tab_id, tab_path, updated_config)
                    break

            st.success(f"Block {block_index} saved!")

        except Exception as e:
            st.error(f"Error saving block: {str(e)}")
            import traceback
            st.code(traceback.format_exc())

    def _handle_block_insert(self, after_index: int, block_type: str, content: str):
        """
        Handle block insert from the renderer.

        Inserts a new block. If after_index is 999, appends to end of file.

        Args:
            after_index: Index after which to insert (-1 for start, 999 for end)
            block_type: Type of block ('markdown', 'exhibit', 'collapsible')
            content: Content for the new block
        """
        active_notebook = self._get_active_notebook()
        if not active_notebook:
            st.error("No active notebook")
            return

        notebook_id, notebook_path, notebook_config = active_notebook

        try:
            from pathlib import Path
            path = Path(notebook_path)
            if not path.is_absolute():
                path = self.ctx.repo / path

            # Read current file content
            with open(path, 'r') as f:
                file_content = f.read()

            # Append new content to end of file
            new_content = f"\n\n{content}"
            updated_content = file_content.rstrip() + new_content

            # Write back
            with open(path, 'w') as f:
                f.write(updated_content)

            # Reload the notebook to reflect changes
            updated_config = self.notebook_manager.load_notebook(str(notebook_path))

            # Update the tab with new config
            for i, (tab_id, tab_path, tab_config) in enumerate(st.session_state.open_tabs):
                if tab_id == notebook_id:
                    st.session_state.open_tabs[i] = (tab_id, tab_path, updated_config)
                    break

            st.success(f"New section added!")

        except Exception as e:
            st.error(f"Error inserting block: {str(e)}")
            import traceback
            st.code(traceback.format_exc())

    def _handle_block_delete(self, block_index: int):
        """
        Handle block delete from the renderer.

        Uses content stored in session state to find and remove the section.

        Args:
            block_index: Index of the block (unused, kept for interface compatibility)
        """
        active_notebook = self._get_active_notebook()
        if not active_notebook:
            st.error("No active notebook")
            return

        notebook_id, notebook_path, notebook_config = active_notebook

        # Get content to delete from session state
        content_to_delete = st.session_state.get('_content_to_delete', '')
        if not content_to_delete:
            st.error("No content selected for deletion")
            return

        try:
            from pathlib import Path
            path = Path(notebook_path)
            if not path.is_absolute():
                path = self.ctx.repo / path

            # Read current file content
            with open(path, 'r') as f:
                file_content = f.read()

            # Find and remove the content
            # Try exact match first
            if content_to_delete in file_content:
                updated_content = file_content.replace(content_to_delete, '', 1)
                # Clean up extra blank lines
                import re
                updated_content = re.sub(r'\n{3,}', '\n\n', updated_content)
                updated_content = updated_content.strip() + '\n'

                # Write back
                with open(path, 'w') as f:
                    f.write(updated_content)

                # Clear the session state
                if '_content_to_delete' in st.session_state:
                    del st.session_state['_content_to_delete']

                # Reload the notebook to reflect changes
                updated_config = self.notebook_manager.load_notebook(str(notebook_path))

                # Update the tab with new config
                for i, (tab_id, tab_path, tab_config) in enumerate(st.session_state.open_tabs):
                    if tab_id == notebook_id:
                        st.session_state.open_tabs[i] = (tab_id, tab_path, updated_config)
                        break

                st.success("Section deleted!")
            else:
                st.error("Could not find content to delete in file")

        except Exception as e:
            st.error(f"Error deleting block: {str(e)}")
            import traceback
            st.code(traceback.format_exc())

    def _handle_header_edit(self, block_index: int, new_header: str):
        """
        Handle header edit from the renderer.

        Updates the header text in the markdown block while preserving
        the header level and rest of the content.

        Args:
            block_index: Index of the block containing the header
            new_header: New header text (without # symbols)
        """
        active_notebook = self._get_active_notebook()
        if not active_notebook:
            st.error("No active notebook")
            return

        notebook_id, notebook_path, notebook_config = active_notebook

        try:
            # Get the current block content
            blocks = notebook_config._content_blocks
            if block_index >= len(blocks):
                st.error("Invalid block index")
                return

            block = blocks[block_index]
            if block['type'] != 'markdown':
                return

            content = block.get('content', '')
            lines = content.split('\n')

            # Find and update the header line
            for i, line in enumerate(lines):
                if line.strip().startswith('#'):
                    # Get the current header level (number of #)
                    header_prefix = ''
                    for char in line:
                        if char == '#':
                            header_prefix += '#'
                        elif char == ' ':
                            header_prefix += ' '
                            break
                        else:
                            break

                    # Create new header with same level
                    lines[i] = header_prefix + new_header
                    break

            # Save the updated content
            new_content = '\n'.join(lines)

            from app.notebook.parsers.markdown_parser import MarkdownNotebookParser
            parser = MarkdownNotebookParser(self.ctx.repo)
            parser.save_block_update(str(notebook_path), block_index, new_content)

            # Reload the notebook
            updated_config = self.notebook_manager.load_notebook(str(notebook_path))

            # Update the tab
            for i, (tab_id, tab_path, tab_config) in enumerate(st.session_state.open_tabs):
                if tab_id == notebook_id:
                    st.session_state.open_tabs[i] = (tab_id, tab_path, updated_config)
                    break

            st.success("Header updated!")

        except Exception as e:
            st.error(f"Error updating header: {str(e)}")
            import traceback
            st.code(traceback.format_exc())

    def _render_welcome(self):
        """Render welcome screen."""
        st.markdown("""
        <div style='text-align: center; padding: 4rem 2rem;'>
            <h1 style='font-size: 3rem; margin-bottom: 1rem;'>📊 Welcome to Data Notebooks</h1>
            <p style='font-size: 1.2rem; color: #666; margin-bottom: 2rem;'>
                Modern, markdown-based analytics platform
            </p>
        </div>
        """, unsafe_allow_html=True)

        # Feature cards
        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("""
            ### 📝 Markdown First
            Write analysis in natural markdown with embedded visualizations and dynamic filters.
            """)

        with col2:
            st.markdown("""
            ### ⚡ Lightning Fast
            DuckDB backend provides instant queries - 10-100x faster than traditional systems.
            """)

        with col3:
            st.markdown("""
            ### 🎨 Professional
            Modern, clean interface with dark/light themes and responsive design.
            """)

        st.divider()

        st.markdown("""
        ### 🚀 Get Started

        1. **Select a notebook** from the sidebar
        2. **Apply filters** to explore your data
        3. **Edit markdown** to customize your analysis
        4. **Share insights** with your team

        <div style='text-align: center; margin-top: 2rem;'>
            <p style='color: #888;'>Select a notebook from the sidebar to begin →</p>
        </div>
        """, unsafe_allow_html=True)


def main():
    """Main application entry point."""
    app = NotebookVaultApp()
    app.run()


if __name__ == "__main__":
    main()
