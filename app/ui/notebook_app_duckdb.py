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


@st.cache_resource
def get_repo_context():
    """Get repository context with DuckDB backend."""
    return RepoContext.from_repo_root(connection_type="duckdb")


@st.cache_resource
def get_model_registry(_ctx):
    """Get model registry (cached)."""
    models_dir = _ctx.repo / "configs" / "models"
    return ModelRegistry(models_dir)


@st.cache_resource
def get_universal_session(_ctx):
    """Get UniversalSession with DuckDB backend (cached)."""
    return UniversalSession(
        connection=_ctx.connection,
        storage_cfg=_ctx.storage,
        repo_root=_ctx.repo
    )


@st.cache_resource
def get_notebook_manager(_universal_session, _repo):
    """Get NotebookManager (cached)."""
    return NotebookManager(_universal_session, _repo)


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

# Apply theme
apply_professional_theme()


class NotebookVaultApp:
    """Professional notebook application with modern UI."""

    def __init__(self):
        """Initialize application."""
        self.ctx = get_repo_context()
        self.model_registry = ModelRegistry(self.ctx.repo / "configs" / "models")
        self.universal_session = get_universal_session(self.ctx)
        self.notebook_manager = get_notebook_manager(self.universal_session, self.ctx.repo)
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
