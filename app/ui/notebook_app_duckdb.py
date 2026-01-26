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

# Bootstrap: Add repo and src/ to path before importing de_funk
# This handles the case when streamlit is run from any directory
_current_file = Path(__file__).resolve()
_repo_root = None
for _parent in [_current_file.parent] + list(_current_file.parents):
    if (_parent / "src").exists() and (_parent / "configs").exists():
        _repo_root = _parent
        break
if _repo_root:
    # Add src/ first for de_funk.* imports
    _src_path = str(_repo_root / "src")
    if _src_path not in sys.path:
        sys.path.insert(0, _src_path)
    # Add repo root for app.* imports
    if str(_repo_root) not in sys.path:
        sys.path.insert(0, str(_repo_root))

from de_funk.utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

# Initialize logging FIRST - before any other imports that might log
from de_funk.config.logging import setup_logging, get_logger
setup_logging(repo_root=repo_root)
logger = get_logger(__name__)
logger.info("Streamlit app starting...")

from de_funk.core.context import RepoContext
from de_funk.models.registry import ModelRegistry
from de_funk.models.api.session import UniversalSession
from de_funk.notebook.managers import NotebookManager

# Import modular UI components
from app.ui.components.theme import apply_professional_theme
from app.ui.components.sidebar import SidebarNavigator, close_tab
from app.ui.components.filters import render_filters_section
from app.ui.components.notebook_view import render_notebook_exhibits
from app.ui.components.model_node_graph import render_model_node_graph, render_model_summary_cards


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

# Validate storage paths match DuckDB views on startup
if 'storage_validated' not in st.session_state:
    st.session_state.storage_validated = True
    ctx = st.session_state.repo_context
    configured_storage = ctx.storage.get('roots', {}).get('silver', '')

    # Check if configured storage path exists
    if configured_storage and not Path(configured_storage).exists():
        logger.warning(f"Configured storage path not accessible: {configured_storage}")
        # Check if local storage exists as fallback
        local_storage = ctx.repo / 'storage' / 'silver'
        if local_storage.exists():
            logger.info(f"Using local storage fallback: {local_storage}")
            st.session_state.storage_mismatch = {
                'configured': configured_storage,
                'actual': str(local_storage),
                'message': (
                    f"⚠️ **Storage Path Mismatch**\n\n"
                    f"Configured: `{configured_storage}` (not accessible)\n\n"
                    f"Using local: `{local_storage}`\n\n"
                    f"To use the configured storage, run:\n"
                    f"```bash\npython -m scripts.setup.setup_duckdb_views --update --storage-path {configured_storage}\n```"
                )
            }
        else:
            st.session_state.storage_mismatch = {
                'configured': configured_storage,
                'actual': None,
                'message': f"⚠️ **No storage found**\n\nConfigured path not accessible: `{configured_storage}`"
            }

if 'model_registry' not in st.session_state:
    ctx = st.session_state.repo_context
    st.session_state.model_registry = ModelRegistry(ctx.repo / "domains")

if 'universal_session' not in st.session_state:
    ctx = st.session_state.repo_context
    st.session_state.universal_session = UniversalSession(
        connection=ctx.connection,
        storage_cfg=ctx.storage,
        repo_root=ctx.repo
    )

if 'notebook_manager' not in st.session_state:
    ctx = st.session_state.repo_context
    notebooks_root = ctx.repo / "notebooks"
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
        self.notebooks_root = self.ctx.repo / "notebooks"
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
        # Show storage mismatch warning if detected
        if st.session_state.get('storage_mismatch'):
            with st.expander("⚠️ Storage Configuration Notice", expanded=False):
                st.markdown(st.session_state.storage_mismatch['message'])

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
        """Render filter editor for the active notebook with full CRUD capabilities."""
        import yaml
        from pathlib import Path

        active_notebook = self._get_active_notebook()
        if not active_notebook:
            st.warning("No active notebook")
            return

        notebook_id, notebook_path, notebook_config = active_notebook
        folder_path = notebook_path.parent

        # Header
        st.title("🔍 Filter Editor")
        st.markdown(f"**Notebook:** {notebook_config.notebook.title}")
        st.caption(f"File: `{notebook_path.name}`")
        st.divider()

        # Two main sections: Folder Filters (values) and Inline Filters (definitions)
        st.subheader("📁 Folder Filters")
        st.caption("Filter values shared by all notebooks in this folder (`.filter_context.yaml`)")
        self._render_folder_filter_editor(folder_path)

        st.divider()

        st.subheader("📝 Inline Filter Definitions")
        st.caption("Filter definitions in this notebook file (`$filter${...}` blocks)")

        # Tab for view/edit/add inline filters
        tab_view, tab_edit, tab_add = st.tabs(["📋 View", "✏️ Edit", "➕ Add"])

        with tab_view:
            self._render_filter_view(notebook_config)

        with tab_edit:
            self._render_filter_edit_tab(notebook_path, notebook_config)

        with tab_add:
            self._render_filter_add_tab(notebook_path)

        st.divider()

        # Close button
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("✅ Close Filter Editor", use_container_width=True, type="primary"):
                st.session_state.filter_editor_open = False
                st.rerun()

    def _render_folder_filter_editor(self, folder_path):
        """Render folder filter context editor (.filter_context.yaml)."""
        import yaml
        from pathlib import Path
        from de_funk.notebook.folder_context import FolderFilterContextManager

        context_file = folder_path / '.filter_context.yaml'

        # Load current content
        if context_file.exists():
            with open(context_file, 'r') as f:
                current_content = f.read()
        else:
            # Default template
            from datetime import datetime
            current_content = f"""# Folder Filter Context
# Filter values shared by all notebooks in this folder

filters:
  # Example: Set default ticker
  # ticker: AAPL
  #
  # Example: Set date range
  # trade_date:
  #   start: "2024-01-01"
  #   end: "2024-12-31"
  #
  # Example: Set multiple tickers
  # ticker:
  #   - AAPL
  #   - MSFT
  #   - GOOGL

metadata:
  created: "{datetime.now().isoformat()}"
  last_updated: "{datetime.now().isoformat()}"
  folder: "{folder_path.name}"
"""

        # Initialize session state for folder filter editor
        folder_key = f"folder_filter_edit_{folder_path.name}"
        if folder_key not in st.session_state:
            st.session_state[folder_key] = current_content

        # Show file path
        st.caption(f"File: `{context_file.relative_to(folder_path.parent) if context_file.exists() else context_file.name}`")

        # Editor
        edited_content = st.text_area(
            "Folder filter context (YAML)",
            value=st.session_state[folder_key],
            height=250,
            key=f"folder_filter_textarea_{folder_path.name}",
            label_visibility="collapsed"
        )
        st.session_state[folder_key] = edited_content

        # Buttons
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("💾 Save Folder Filters", key="save_folder_filters"):
                try:
                    # Validate YAML
                    parsed = yaml.safe_load(edited_content)
                    if parsed is None:
                        parsed = {'filters': {}, 'metadata': {}}

                    # Ensure folder exists
                    folder_path.mkdir(parents=True, exist_ok=True)

                    # Save to file
                    with open(context_file, 'w') as f:
                        f.write(edited_content)

                    # Clear cached folder context in notebook manager
                    if hasattr(self.notebook_manager, 'folder_context_manager'):
                        folder_key_cache = str(folder_path)
                        if folder_key_cache in self.notebook_manager.folder_context_manager._contexts:
                            del self.notebook_manager.folder_context_manager._contexts[folder_key_cache]

                    # Reload active notebook (clears filter state automatically)
                    self._reload_active_notebook()

                    st.success("Folder filters saved!")
                    st.rerun()
                except yaml.YAMLError as e:
                    st.error(f"Invalid YAML: {str(e)}")
                except Exception as e:
                    st.error(f"Error saving: {str(e)}")

        with col2:
            if st.button("🔄 Reset", key="reset_folder_filters"):
                st.session_state[folder_key] = current_content
                st.rerun()

        with col3:
            if context_file.exists():
                if st.button("🗑️ Delete File", key="delete_folder_filters", type="secondary"):
                    confirm_key = "confirm_delete_folder_filters"
                    if st.session_state.get(confirm_key, False):
                        try:
                            context_file.unlink()
                            if hasattr(self.notebook_manager, 'folder_context_manager'):
                                folder_key_cache = str(folder_path)
                                if folder_key_cache in self.notebook_manager.folder_context_manager._contexts:
                                    del self.notebook_manager.folder_context_manager._contexts[folder_key_cache]

                            # Reload active notebook (clears filter state automatically)
                            self._reload_active_notebook()
                            st.success("Folder filter file deleted!")
                            del st.session_state[folder_key]
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error deleting: {str(e)}")
                    else:
                        st.session_state[confirm_key] = True
                        st.warning("Click Delete again to confirm")
                        st.rerun()

        # Show parsed filters preview
        try:
            parsed = yaml.safe_load(edited_content)
            if parsed and parsed.get('filters'):
                with st.expander("Preview parsed filters", expanded=False):
                    st.json(parsed.get('filters', {}))
        except:
            pass

    def _render_filter_view(self, notebook_config):
        """View tab for filter editor."""
        # Check if notebook has filter collection
        if not hasattr(notebook_config, '_filter_collection') or not notebook_config._filter_collection:
            st.info("This notebook has no filters defined yet.")
            st.markdown("Use the **Add Filter** tab to create a new filter.")
            return

        filter_collection = notebook_config._filter_collection

        # Show each filter in an expandable section
        for filter_id, filter_config in filter_collection.filters.items():
            with st.expander(f"**{filter_config.label}** (`{filter_id}`)", expanded=False):
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
                    # Use code block for display to avoid JSON parse errors
                    default_val = filter_config.default
                    if isinstance(default_val, (dict, list)):
                        import json
                        st.code(json.dumps(default_val, indent=2), language="json")
                    elif default_val is not None:
                        st.code(str(default_val))
                    else:
                        st.caption("None")

                    if filter_config.source:
                        st.markdown("**Source:**")
                        st.code(f"{filter_config.source.model}.{filter_config.source.table}.{filter_config.source.column}")

                    st.markdown("**Operator:**")
                    st.code(filter_config.operator.value if filter_config.operator else "N/A")

    def _render_filter_edit_tab(self, notebook_path, notebook_config):
        """Edit tab for filter editor."""
        from pathlib import Path
        import yaml
        import re

        if not hasattr(notebook_config, '_filter_collection') or not notebook_config._filter_collection:
            st.info("No filters to edit. Use the Add Filter tab to create one.")
            return

        filter_collection = notebook_config._filter_collection
        filter_ids = list(filter_collection.filters.keys())

        # Select filter to edit
        selected_filter = st.selectbox(
            "Select filter to edit",
            options=filter_ids,
            format_func=lambda x: f"{filter_collection.filters[x].label} ({x})",
            key="filter_edit_select"
        )

        if selected_filter:
            filter_config = filter_collection.filters[selected_filter]

            # Build YAML representation
            filter_data = {
                'id': selected_filter,
                'label': filter_config.label,
                'type': filter_config.type.value,
            }

            if filter_config.multi is not None:
                filter_data['multi'] = filter_config.multi
            if filter_config.source:
                filter_data['source'] = {
                    'model': filter_config.source.model,
                    'table': filter_config.source.table,
                    'column': filter_config.source.column
                }
            if filter_config.default is not None:
                filter_data['default'] = filter_config.default
            if filter_config.operator:
                filter_data['operator'] = filter_config.operator.value
            if filter_config.help_text:
                filter_data['help_text'] = filter_config.help_text
            if filter_config.min_value is not None:
                filter_data['min_value'] = filter_config.min_value
            if filter_config.max_value is not None:
                filter_data['max_value'] = filter_config.max_value
            if filter_config.step is not None:
                filter_data['step'] = filter_config.step
            if filter_config.placeholder:
                filter_data['placeholder'] = filter_config.placeholder
            if filter_config.options:
                filter_data['options'] = filter_config.options

            yaml_content = yaml.dump(filter_data, default_flow_style=False, sort_keys=False)

            # Editor
            st.markdown("**Edit Filter YAML:**")
            edit_key = f"filter_edit_{selected_filter}"
            if edit_key not in st.session_state:
                st.session_state[edit_key] = yaml_content

            edited_yaml = st.text_area(
                "Filter definition",
                value=st.session_state[edit_key],
                height=300,
                key=f"filter_editor_{selected_filter}",
                label_visibility="collapsed"
            )
            st.session_state[edit_key] = edited_yaml

            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("💾 Save Changes", key=f"save_filter_{selected_filter}"):
                    try:
                        self._save_filter_changes(notebook_path, selected_filter, edited_yaml)
                        st.success(f"Filter '{selected_filter}' updated!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error saving filter: {str(e)}")

            with col2:
                if st.button("🔄 Reset", key=f"reset_filter_{selected_filter}"):
                    st.session_state[edit_key] = yaml_content
                    st.rerun()

            with col3:
                confirm_key = f"confirm_delete_{selected_filter}"
                if st.session_state.get(confirm_key, False):
                    # Show confirmation buttons
                    st.warning(f"Delete '{selected_filter}'?")
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("✓ Yes", key=f"confirm_yes_{selected_filter}", type="primary"):
                            try:
                                self._delete_filter(notebook_path, selected_filter)
                                del st.session_state[confirm_key]
                                # Clear selectbox selection since filter no longer exists
                                if "filter_edit_select" in st.session_state:
                                    del st.session_state["filter_edit_select"]
                                # Use toast for persistent feedback
                                st.toast(f"✅ Filter '{selected_filter}' deleted!", icon="🗑️")
                                # Keep filter editor open for multiple deletions
                                st.session_state.filter_editor_open = True
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error deleting filter: {str(e)}")
                    with c2:
                        if st.button("✗ No", key=f"confirm_no_{selected_filter}"):
                            del st.session_state[confirm_key]
                            st.rerun()
                else:
                    if st.button("🗑️ Delete Filter", key=f"delete_filter_{selected_filter}", type="secondary"):
                        st.session_state[confirm_key] = True
                        st.rerun()

    def _render_filter_add_tab(self, notebook_path):
        """Add tab for filter editor."""
        st.markdown("### Create New Filter")

        # Filter type selector
        filter_type = st.selectbox(
            "Filter Type",
            options=["select", "date_range", "slider", "text_search", "boolean", "number_range"],
            help="Choose the type of filter to create"
        )

        # Template based on type
        templates = {
            "select": """id: ticker
label: Stock Tickers
type: select
multi: true
source: {model: securities, table: dim_security, column: ticker}
default: []
operator: in
help_text: Select securities to analyze""",
            "date_range": """id: date_range
label: Date Range
type: date_range
operator: between
default: {start: "-30d", end: "today"}
help_text: Select a date range""",
            "slider": """id: price_min
label: Minimum Price
type: slider
min_value: 0
max_value: 1000
step: 10
default: 0
operator: gte
help_text: Filter by minimum price""",
            "text_search": """id: search
label: Search
type: text_search
operator: like
placeholder: Enter search term...
help_text: Search by text""",
            "boolean": """id: active_only
label: Active Only
type: boolean
default: false
help_text: Show only active items""",
            "number_range": """id: volume_range
label: Volume Range
type: number_range
min_value: 0
max_value: 100000000
step: 1000000
operator: between
help_text: Filter by trading volume"""
        }

        template = templates.get(filter_type, templates["select"])

        # Editor for new filter
        add_key = "new_filter_yaml"
        if add_key not in st.session_state or st.session_state.get("last_filter_type") != filter_type:
            st.session_state[add_key] = template
            st.session_state["last_filter_type"] = filter_type

        new_filter_yaml = st.text_area(
            "Filter YAML",
            value=st.session_state[add_key],
            height=250,
            key="new_filter_editor"
        )
        st.session_state[add_key] = new_filter_yaml

        col1, col2 = st.columns(2)
        with col1:
            if st.button("➕ Add Filter", type="primary"):
                try:
                    self._add_new_filter(notebook_path, new_filter_yaml)
                    st.success("Filter added successfully!")
                    # Reset the form
                    st.session_state[add_key] = template
                    st.rerun()
                except Exception as e:
                    st.error(f"Error adding filter: {str(e)}")

        with col2:
            if st.button("🔄 Reset to Template"):
                st.session_state[add_key] = template
                st.rerun()

        # Help section
        with st.expander("📖 Filter Properties Reference"):
            st.markdown("""
            **Common Properties:**
            - `id`: Unique identifier (required)
            - `label`: Display name (required)
            - `type`: Filter type (required)
            - `default`: Default value
            - `operator`: SQL operator (`in`, `eq`, `gte`, `lte`, `between`, `like`)
            - `help_text`: Help text for users

            **Select Filter:**
            - `multi`: Allow multiple selections (true/false)
            - `source`: Database source `{model: X, table: Y, column: Z}`
            - `options`: Static list of options

            **Slider/Number Range:**
            - `min_value`: Minimum value
            - `max_value`: Maximum value
            - `step`: Step increment

            **Text Search:**
            - `placeholder`: Placeholder text
            - `fuzzy_enabled`: Enable fuzzy matching
            """)

    def _save_filter_changes(self, notebook_path, filter_id: str, new_yaml: str):
        """Save changes to a filter in the notebook file."""
        import yaml
        import re
        from pathlib import Path

        path = Path(notebook_path)
        if not path.is_absolute():
            path = self.ctx.repo / path

        # Read current file
        with open(path, 'r') as f:
            content = f.read()

        # Parse new YAML to validate
        new_data = yaml.safe_load(new_yaml)
        if not new_data.get('id'):
            raise ValueError("Filter must have an 'id' field")

        # Find and replace the filter block
        # Pattern matches $filter${ ... } with the matching filter_id
        pattern = re.compile(
            r'\$filters?\$\{\s*\n(.*?)\n\}',
            re.MULTILINE | re.DOTALL
        )

        def replace_filter(match):
            filter_yaml = match.group(1)
            try:
                data = yaml.safe_load(filter_yaml)
                if data.get('id') == filter_id:
                    # This is the filter to replace
                    return f"$filter${{\n{new_yaml.strip()}\n}}"
            except:
                pass
            return match.group(0)

        updated_content = pattern.sub(replace_filter, content)

        # Write back
        with open(path, 'w') as f:
            f.write(updated_content)

        # Reload notebook
        self._reload_active_notebook()

    def _delete_filter(self, notebook_path, filter_id: str):
        """Delete a filter from the notebook file and folder context."""
        import yaml
        import re
        from pathlib import Path

        path = Path(notebook_path)
        if not path.is_absolute():
            path = self.ctx.repo / path

        # Read current file
        with open(path, 'r') as f:
            content = f.read()

        original_content = content

        # Find and remove the filter block
        pattern = re.compile(
            r'\$filters?\$\{\s*\n(.*?)\n\}\s*\n?',
            re.MULTILINE | re.DOTALL
        )

        def remove_filter(match):
            filter_yaml = match.group(1)
            try:
                data = yaml.safe_load(filter_yaml)
                if data.get('id') == filter_id:
                    return ''  # Remove this filter
            except:
                pass
            return match.group(0)

        updated_content = pattern.sub(remove_filter, content)

        # Clean up extra blank lines
        updated_content = re.sub(r'\n{3,}', '\n\n', updated_content)

        # Write back if changed
        if updated_content != original_content:
            with open(path, 'w') as f:
                f.write(updated_content)

        # Also remove from folder context if present
        folder_path = path.parent
        context_file = folder_path / '.filter_context.yaml'
        if context_file.exists():
            try:
                with open(context_file, 'r') as f:
                    folder_context = yaml.safe_load(f) or {}

                if 'filters' in folder_context and filter_id in folder_context['filters']:
                    del folder_context['filters'][filter_id]

                    # Write back
                    with open(context_file, 'w') as f:
                        yaml.dump(folder_context, f, default_flow_style=False, sort_keys=False)

                    # Clear cached folder context
                    if hasattr(self.notebook_manager, 'folder_context_manager'):
                        folder_key = str(folder_path)
                        if folder_key in self.notebook_manager.folder_context_manager._contexts:
                            del self.notebook_manager.folder_context_manager._contexts[folder_key]
            except Exception:
                pass  # Folder context update is best-effort

        # Reload notebook
        self._reload_active_notebook()

    def _add_new_filter(self, notebook_path, filter_yaml: str):
        """Add a new filter to the notebook file."""
        import yaml
        import re
        from pathlib import Path

        path = Path(notebook_path)
        if not path.is_absolute():
            path = self.ctx.repo / path

        # Validate YAML
        filter_data = yaml.safe_load(filter_yaml)
        if not filter_data.get('id'):
            raise ValueError("Filter must have an 'id' field")
        if not filter_data.get('label'):
            raise ValueError("Filter must have a 'label' field")
        if not filter_data.get('type'):
            raise ValueError("Filter must have a 'type' field")

        # Read current file
        with open(path, 'r') as f:
            content = f.read()

        # Find the position to insert (after front matter and existing filters)
        front_matter_pattern = re.compile(r'^---\s*\n.*?\n---\s*\n', re.MULTILINE | re.DOTALL)
        front_matter_match = front_matter_pattern.match(content)

        if front_matter_match:
            # Find existing filter blocks
            filter_pattern = re.compile(r'\$filters?\$\{\s*\n.*?\n\}', re.MULTILINE | re.DOTALL)
            filter_matches = list(filter_pattern.finditer(content))

            if filter_matches:
                # Insert after the last filter
                last_filter_end = filter_matches[-1].end()
                new_filter_block = f"\n\n$filter${{\n{filter_yaml.strip()}\n}}"
                updated_content = content[:last_filter_end] + new_filter_block + content[last_filter_end:]
            else:
                # Insert right after front matter
                insert_pos = front_matter_match.end()
                new_filter_block = f"\n$filter${{\n{filter_yaml.strip()}\n}}\n"
                updated_content = content[:insert_pos] + new_filter_block + content[insert_pos:]
        else:
            raise ValueError("Notebook must have front matter (---...---)")

        # Write back
        with open(path, 'w') as f:
            f.write(updated_content)

        # Reload notebook
        self._reload_active_notebook()

    def _reload_active_notebook(self, clear_filter_state: bool = True):
        """
        Reload the active notebook after file changes.

        Args:
            clear_filter_state: If True, clears filter session state to force reload
        """
        active_notebook = self._get_active_notebook()
        if active_notebook:
            notebook_id, notebook_path, _ = active_notebook

            # Clear filter session state so filters reload with fresh values
            if clear_filter_state:
                keys_to_delete = [k for k in st.session_state.keys() if k.startswith('filter_')]
                for key in keys_to_delete:
                    del st.session_state[key]

                # Force folder change detection
                if 'last_filter_folder' in st.session_state:
                    del st.session_state['last_filter_folder']

            # Reload the notebook config from file
            updated_config = self.notebook_manager.load_notebook(str(notebook_path))

            # Update the tab with new config
            for i, (tab_id, tab_path, tab_config) in enumerate(st.session_state.open_tabs):
                if tab_id == notebook_id:
                    st.session_state.open_tabs[i] = (tab_id, tab_path, updated_config)
                    break

            # Also update the notebook manager's current config
            self.notebook_manager.notebook_config = updated_config

            # Clear cached model sessions so they reload with new config
            if notebook_id in st.session_state.notebook_model_sessions:
                del st.session_state.notebook_model_sessions[notebook_id]

            # Reset current notebook id to force re-sync on next render
            st.session_state.current_notebook_id = None

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
            from de_funk.notebook.filters.context import FilterContext
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

        Uses content-based find/replace to save changes.
        Handles whitespace normalization for robust matching.

        Args:
            block_index: Index of the block (unused, kept for interface compatibility)
            new_content: New content for the block

        Raises:
            Exception: If save fails, to allow caller to handle
        """
        active_notebook = self._get_active_notebook()
        if not active_notebook:
            raise Exception("No active notebook")

        notebook_id, notebook_path, notebook_config = active_notebook

        # Get original content and new content from session state
        original_content = st.session_state.get('_content_to_replace', '')
        if not original_content:
            raise Exception("No original content found for replacement")

        try:
            from pathlib import Path
            import re
            path = Path(notebook_path)
            if not path.is_absolute():
                path = self.ctx.repo / path

            # Read current file content
            with open(path, 'r') as f:
                file_content = f.read()

            updated_content = None

            # Check if this is a grid block
            if original_content.strip().startswith('$grid$'):
                # Handle grid block replacement - find by markers
                updated_content = self._replace_grid_block(file_content, new_content)
            # Check if this is an exhibit block
            elif original_content.strip().startswith('$exhibits$') or original_content.strip().startswith('$exhibit$'):
                # Handle exhibit block replacement
                updated_content = self._replace_exhibit_block(file_content, original_content, new_content)
            elif original_content in file_content:
                # Try exact match first
                updated_content = file_content.replace(original_content, new_content, 1)
            else:
                # Try normalized matching (handle whitespace differences)
                # The content might have been stripped during parsing
                original_lines = original_content.strip().split('\n')
                if original_lines and original_lines[0].strip().startswith('#'):
                    header_line = original_lines[0].strip()

                    # Find the header in the file
                    file_lines = file_content.split('\n')
                    for i, line in enumerate(file_lines):
                        if line.strip() == header_line:
                            # Found the header, now find the extent of this section
                            # by looking for the next header of same or higher level
                            header_level = len(header_line) - len(header_line.lstrip('#'))
                            section_start = i
                            section_end = len(file_lines)

                            for j in range(i + 1, len(file_lines)):
                                next_line = file_lines[j].strip()
                                if next_line.startswith('#'):
                                    next_level = len(next_line) - len(next_line.lstrip('#'))
                                    if next_level <= header_level:
                                        section_end = j
                                        break

                            # Replace this section with new content
                            new_lines = file_lines[:section_start] + new_content.split('\n') + file_lines[section_end:]
                            updated_content = '\n'.join(new_lines)
                            break

            if updated_content is None:
                raise Exception("Could not find content to replace in file. Check debug info above.")

            # Write back
            with open(path, 'w') as f:
                f.write(updated_content)

            # Clear session state
            if '_content_to_replace' in st.session_state:
                del st.session_state['_content_to_replace']
            if '_new_content' in st.session_state:
                del st.session_state['_new_content']

            # Reload the notebook to reflect changes
            updated_config = self.notebook_manager.load_notebook(str(notebook_path))

            # Update the tab with new config
            for i, (tab_id, tab_path, tab_config) in enumerate(st.session_state.open_tabs):
                if tab_id == notebook_id:
                    st.session_state.open_tabs[i] = (tab_id, tab_path, updated_config)
                    break

            st.success("Section saved!")

        except Exception as e:
            # Re-raise to let the caller handle it
            raise

    def _replace_grid_block(self, file_content: str, new_content: str) -> str:
        """
        Replace a grid block in the file content by finding $grid$ and $/grid$ markers.

        Args:
            file_content: Full file content
            new_content: New grid content to replace with

        Returns:
            Updated file content, or None if not found
        """
        import re

        # Find the grid block: $grid${...} ... $/grid$
        # The pattern matches from $grid$ to $/grid$
        grid_pattern = re.compile(
            r'\$grid\$\{[^}]*\}.*?\$/grid\$',
            re.DOTALL
        )

        match = grid_pattern.search(file_content)
        if match:
            # Replace the entire grid section
            return file_content[:match.start()] + new_content + file_content[match.end():]

        return None

    def _replace_exhibit_block(self, file_content: str, original_content: str, new_content: str) -> str:
        """
        Replace an exhibit block in the file content.

        Finds the exhibit block by matching key properties (type, source, title) and replaces it.

        Args:
            file_content: Full file content
            original_content: Original exhibit content (generated YAML)
            new_content: New exhibit content to replace with

        Returns:
            Updated file content, or None if not found
        """
        import re
        import yaml

        # Parse the original content to extract key properties for matching
        # Original content looks like: $exhibits${\ntype: ...\nsource: ...\n}
        try:
            # Extract YAML from original content
            orig_match = re.search(r'\$exhibits?\$\{(.*)\}', original_content, re.DOTALL)
            if not orig_match:
                st.warning("Could not parse original exhibit content")
                return None
            # Use textwrap.dedent to properly remove common leading whitespace
            import textwrap
            orig_yaml = textwrap.dedent(orig_match.group(1)).strip()
            orig_data = yaml.safe_load(orig_yaml)
            if not orig_data:
                st.warning("Could not load original YAML")
                return None

            # Key properties to match (use multiple for better matching)
            match_type = orig_data.get('type', '')
            match_source = orig_data.get('source', '')
            match_title = orig_data.get('title', '')
            match_x = orig_data.get('x', '')
            match_y = orig_data.get('y', '')

        except Exception as e:
            st.warning(f"Error parsing original: {e}")
            return None

        # Find all exhibit blocks in file
        def find_matching_brace(text: str, start: int) -> int:
            depth = 0
            i = start
            while i < len(text):
                if text[i] == '{':
                    depth += 1
                elif text[i] == '}':
                    depth -= 1
                    if depth == 0:
                        return i
                i += 1
            return -1

        pattern = re.compile(r'\$(exhibits?)\$\{')
        candidates = []
        debug_info = []

        for match in pattern.finditer(file_content):
            brace_start = match.end() - 1
            brace_end = find_matching_brace(file_content, brace_start)
            if brace_end == -1:
                debug_info.append(f"No closing brace found at pos {match.start()}")
                continue

            # Extract this exhibit's YAML
            exhibit_yaml = file_content[brace_start + 1:brace_end]
            # Dedent the YAML - remove common leading whitespace from all lines
            import textwrap
            exhibit_yaml = textwrap.dedent(exhibit_yaml).strip()
            try:
                exhibit_data = yaml.safe_load(exhibit_yaml)
                if not exhibit_data:
                    debug_info.append(f"YAML parsed to None/empty")
                    continue

                file_type = exhibit_data.get('type', '')
                file_source = exhibit_data.get('source', '')
                file_title = exhibit_data.get('title', '')

                # Score how well this matches
                score = 0
                if file_type == match_type:
                    score += 10
                if match_source and file_source == match_source:
                    score += 5
                if match_title and file_title == match_title:
                    score += 5
                if match_x and exhibit_data.get('x', '') == match_x:
                    score += 2
                if match_y and exhibit_data.get('y', '') == match_y:
                    score += 2

                debug_info.append(f"Found: type='{file_type}', source='{file_source}', title='{file_title}' -> score={score}")

                if score > 0:
                    candidates.append((score, match.start(), brace_end + 1, exhibit_data))

            except Exception as e:
                debug_info.append(f"YAML parse error: {e}")
                continue

        # Show debug info
        if debug_info:
            st.info(f"Exhibits found in file: {len(debug_info)} blocks processed")
            with st.expander("File parsing debug", expanded=True):
                for info in debug_info:
                    st.write(info)

        if not candidates:
            st.warning(f"No matching exhibit found for type={match_type}, source={match_source}")
            return None

        # Use the best match
        candidates.sort(key=lambda x: -x[0])  # Sort by score descending
        best_score, block_start, block_end, _ = candidates[0]

        # Use the new content directly (it should already have $exhibits${...} wrapper)
        if new_content.strip().startswith('$exhibits$') or new_content.strip().startswith('$exhibit$'):
            replacement = new_content.strip()
        else:
            # Wrap it
            replacement = f"$exhibits${{\n{new_content.strip()}\n}}"

        return file_content[:block_start] + replacement + file_content[block_end:]

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
        Handles whitespace normalization for robust matching.

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
            import re

            path = Path(notebook_path)
            if not path.is_absolute():
                path = self.ctx.repo / path

            # Read current file content
            with open(path, 'r') as f:
                file_content = f.read()

            # Try exact match first
            if content_to_delete in file_content:
                updated_content = file_content.replace(content_to_delete, '', 1)
            else:
                # Try header-based matching (for nested sections)
                delete_lines = content_to_delete.strip().split('\n')
                if delete_lines and delete_lines[0].strip().startswith('#'):
                    header_line = delete_lines[0].strip()
                    header_level = len(header_line) - len(header_line.lstrip('#'))

                    # Find and remove the section
                    file_lines = file_content.split('\n')
                    found = False

                    for i, line in enumerate(file_lines):
                        if line.strip() == header_line:
                            # Found the header, find extent of section
                            section_start = i
                            section_end = len(file_lines)

                            for j in range(i + 1, len(file_lines)):
                                next_line = file_lines[j].strip()
                                if next_line.startswith('#'):
                                    next_level = len(next_line) - len(next_line.lstrip('#'))
                                    if next_level <= header_level:
                                        section_end = j
                                        break

                            # Remove this section
                            new_lines = file_lines[:section_start] + file_lines[section_end:]
                            updated_content = '\n'.join(new_lines)
                            found = True
                            break

                    if not found:
                        st.error(f"Could not find section '{header_line}' to delete")
                        return
                else:
                    st.error("Could not find content to delete in file")
                    return

            # Clean up extra blank lines
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

            from de_funk.notebook.parsers.markdown_parser import MarkdownNotebookParser
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
        """Render welcome screen with model graph visualization."""
        st.markdown("""
        <div style='text-align: center; padding: 2rem 2rem 1rem 2rem;'>
            <h1 style='font-size: 2.5rem; margin-bottom: 0.5rem;'>📊 Data Notebooks</h1>
            <p style='font-size: 1rem; color: #666; margin-bottom: 1rem;'>
                Modern, markdown-based analytics platform
            </p>
        </div>
        """, unsafe_allow_html=True)

        # Model Graph Visualization
        st.markdown("### 🗺️ Data Model Architecture")
        st.caption("Interactive visualization of available data models and their structure. Hover over nodes for details.")

        try:
            render_model_node_graph(
                self.model_registry,
                show_tables=True,
                height=800
            )
        except Exception as e:
            logger.warning(f"Could not render model graph: {e}", exc_info=True)
            # Fallback to summary cards with error message
            st.warning(f"Graph visualization unavailable: {e}")
            render_model_summary_cards(self.model_registry)

        st.divider()

        # Compact feature cards and get started
        col1, col2 = st.columns([2, 1])

        with col1:
            st.markdown("""
            **Features:** 📝 Markdown-first analysis · ⚡ DuckDB backend (10-100x faster) · 🎨 Professional themes
            """)

        with col2:
            st.markdown("""
            **Get Started:** Select a notebook from the sidebar →
            """)


def main():
    """Main application entry point."""
    app = NotebookVaultApp()
    app.run()


if __name__ == "__main__":
    main()
