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
from pathlib import Path
from typing import Dict, Any

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

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

if 'markdown_content' not in st.session_state:
    st.session_state.markdown_content = {}

if 'theme' not in st.session_state:
    st.session_state.theme = 'dark'

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
                    # Show folder filter context editor
                    try:
                        self._render_folder_filter_editor()
                    except Exception as e:
                        st.error(f"Filter context error: {e}")
                        import traceback
                        st.code(traceback.format_exc())

                    st.divider()

                    self._render_filters(active_notebook[2])

        # Main content area
        self._render_main_content()

    def _render_header(self):
        """Render professional header with toolbar and tabs."""
        # Row 1: Edit and Theme buttons on the right
        col_spacer, col_edit, col_theme = st.columns([0.8, 0.1, 0.1])

        with col_edit:
            # Edit button (only if active notebook)
            if st.session_state.active_tab:
                active_notebook = self._get_active_notebook()
                if active_notebook:
                    notebook_id = active_notebook[0]
                    in_edit_mode = st.session_state.edit_mode.get(notebook_id, False)

                    button_label = "👁️" if in_edit_mode else "✏️"
                    button_help = "View mode" if in_edit_mode else "Edit markdown"

                    if st.button(button_label, help=button_help, key="toolbar_edit", use_container_width=True):
                        st.session_state.edit_mode[notebook_id] = not in_edit_mode
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
            # Calculate number of tabs to show (max 6 since we have full width)
            num_tabs = min(len(st.session_state.open_tabs), 6)

            # Create columns for tabs
            tab_cols = st.columns(num_tabs)

            # Render tab buttons
            for i, (notebook_id, notebook_path, notebook_config) in enumerate(st.session_state.open_tabs[:num_tabs]):
                with tab_cols[i]:
                    is_active = st.session_state.active_tab == notebook_id
                    title = notebook_config.notebook.title

                    # Truncate long titles
                    if len(title) > 18:
                        title = title[:15] + "..."

                    button_type = "primary" if is_active else "secondary"

                    if st.button(
                        title,
                        key=f"tab_btn_{notebook_id}",
                        type=button_type,
                        use_container_width=True,
                        help=notebook_config.notebook.title
                    ):
                        # Switch to this notebook
                        if st.session_state.active_tab != notebook_id:
                            st.session_state.active_tab = notebook_id
                            st.rerun()

            # Show indicator if more tabs exist
            if len(st.session_state.open_tabs) > num_tabs:
                st.caption(f"+ {len(st.session_state.open_tabs) - num_tabs} more tabs (use sidebar)")

        st.divider()

    def _render_folder_filter_editor(self):
        """Render YAML editor for folder filter context file."""
        if not hasattr(self.notebook_manager, 'folder_context_manager'):
            return

        folder_ctx_mgr = self.notebook_manager.folder_context_manager
        current_folder = self.notebook_manager.get_current_folder()

        if not current_folder:
            return

        folder_name = current_folder.name
        context_file = folder_ctx_mgr.get_context_file_path(current_folder)

        # Header
        st.markdown(f"### 📁 {folder_name}")
        st.caption("_Filter context shared by all notebooks in this folder_")

        # Show current filter values
        current_filters = folder_ctx_mgr.get_filters(current_folder)

        with st.expander("📊 Current Filter Values", expanded=bool(current_filters)):
            if current_filters:
                for key, value in current_filters.items():
                    if isinstance(value, dict):
                        st.caption(f"**{key}**: {value}")
                    elif isinstance(value, list):
                        st.caption(f"**{key}**: {', '.join(map(str, value[:5]))}{'...' if len(value) > 5 else ''}")
                    else:
                        st.caption(f"**{key}**: {value}")
            else:
                st.caption("_No filters set_")

        # Edit button
        filter_edit_key = f"filter_edit_{current_folder}"

        if filter_edit_key not in st.session_state:
            st.session_state[filter_edit_key] = False

        if not st.session_state[filter_edit_key]:
            # View mode - show edit button
            if st.button("✏️ Edit Filter Context", key=f"btn_edit_{current_folder}", use_container_width=True):
                st.session_state[filter_edit_key] = True
                st.rerun()
        else:
            # Edit mode - show YAML editor
            st.info("📝 Editing .filter_context.yaml")

            # Load current YAML content
            yaml_content = folder_ctx_mgr.get_context_yaml_content(current_folder)

            # YAML editor
            edited_yaml = st.text_area(
                "YAML Content",
                value=yaml_content,
                height=300,
                key=f"yaml_editor_{current_folder}",
                help="Edit the filter context YAML file"
            )

            # Buttons
            col1, col2, col3 = st.columns(3)

            with col1:
                if st.button("💾 Save", key=f"save_{current_folder}", use_container_width=True):
                    try:
                        # Validate YAML
                        import yaml
                        yaml.safe_load(edited_yaml)

                        # Save
                        folder_ctx_mgr.save_context_yaml_content(current_folder, edited_yaml)

                        st.success("✅ Saved!")
                        st.session_state[filter_edit_key] = False
                        st.rerun()
                    except yaml.YAMLError as e:
                        st.error(f"Invalid YAML: {e}")
                    except Exception as e:
                        st.error(f"Error saving: {e}")

            with col2:
                if st.button("❌ Cancel", key=f"cancel_{current_folder}", use_container_width=True):
                    st.session_state[filter_edit_key] = False
                    st.rerun()

            with col3:
                if st.button("🗑️ Clear", key=f"clear_{current_folder}", use_container_width=True):
                    try:
                        folder_ctx_mgr.clear_filters(current_folder)
                        st.success("✅ Cleared!")
                        st.session_state[filter_edit_key] = False
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

            # Show file location
            st.caption(f"📄 File: `{context_file}`")

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
        # Check for dynamic filters (new system)
        if (hasattr(notebook_config, '_filter_collection') and
            notebook_config._filter_collection and
            notebook_config._filter_collection.filters):
            from app.ui.components.dynamic_filters import render_dynamic_filters
            render_dynamic_filters(
                notebook_config._filter_collection,
                self.notebook_manager,
                self.ctx.connection,
                self.universal_session
            )
        elif notebook_config.variables:
            # Old filter system (backward compat)
            render_filters_section(
                notebook_config,
                self.notebook_manager,
                self.ctx.connection,
                self.universal_session
            )

    def _get_active_notebook(self):
        """Get the active notebook tuple."""
        return next(
            (tab for tab in st.session_state.open_tabs if tab[0] == st.session_state.active_tab),
            None
        )

    def _render_main_content(self):
        """Render main content area."""
        if not st.session_state.open_tabs:
            self._render_welcome()
            return

        # Render active notebook
        active_notebook = self._get_active_notebook()
        if active_notebook:
            self._render_notebook_content(active_notebook)

    def _render_notebook_content(self, notebook_tuple):
        """Render notebook content (edit or view mode)."""
        notebook_id, notebook_path, notebook_config = notebook_tuple

        # Ensure the notebook session is synced with this notebook
        # Cache model sessions per notebook to avoid expensive reinitializations
        if 'current_notebook_id' not in st.session_state:
            st.session_state.current_notebook_id = None

        if st.session_state.current_notebook_id != notebook_id:
            # Switching to a different notebook
            self.notebook_manager.notebook_config = notebook_config

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

        # Check edit mode
        in_edit_mode = st.session_state.edit_mode.get(notebook_id, False)

        if in_edit_mode:
            # Edit mode
            self._render_edit_mode(notebook_id, notebook_path, notebook_config)
        else:
            # View mode
            self._render_view_mode(notebook_id, notebook_config)

    def _render_edit_mode(self, notebook_id, notebook_path, notebook_config):
        """Render notebook in edit mode."""
        # Header
        st.info("📝 **Editing Markdown Notebook** - Changes save automatically")

        # Load current content
        if notebook_id not in st.session_state.markdown_content:
            with open(notebook_path, 'r') as f:
                st.session_state.markdown_content[notebook_id] = f.read()

        # Editor
        edited_content = st.text_area(
            "Markdown Content",
            value=st.session_state.markdown_content[notebook_id],
            height=600,
            key=f"editor_{notebook_id}",
            help="Edit your notebook content. Save with Ctrl+S (auto-save enabled)"
        )

        # Auto-save on change
        if edited_content != st.session_state.markdown_content[notebook_id]:
            st.session_state.markdown_content[notebook_id] = edited_content

        # Save button
        col1, col2, col3 = st.columns([0.2, 0.6, 0.2])
        with col1:
            if st.button("💾 Save", use_container_width=True):
                with open(notebook_path, 'w') as f:
                    f.write(edited_content)
                st.success("✅ Saved successfully!")
                # Reload notebook
                st.session_state.edit_mode[notebook_id] = False
                st.rerun()

        with col3:
            if st.button("Cancel", use_container_width=True):
                st.session_state.edit_mode[notebook_id] = False
                st.rerun()

    def _render_view_mode(self, notebook_id, notebook_config):
        """Render notebook in view mode."""
        # Render notebook exhibits
        render_notebook_exhibits(
            notebook_id,
            notebook_config,
            self.notebook_manager,
            self.ctx.connection
        )

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
