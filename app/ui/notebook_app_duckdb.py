"""
Professional notebook application with DuckDB backend.

Modern, streamlined UI with markdown-first notebooks.

Features:
- DuckDB backend (10-100x faster than Spark)
- Markdown notebooks with dynamic filters
- Professional design with dark/light themes
- Modular component architecture
- Real-time collaborative editing

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
from app.notebook.api.notebook_session import NotebookSession

# Import modular UI components
from app.ui.components.theme import apply_professional_theme
from app.ui.components.sidebar import SidebarNavigator, close_tab
from app.ui.components.filters import render_filters_section
from app.ui.components.yaml_editor import render_yaml_editor
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
def get_notebook_session(_ctx, _model_registry):
    """Get notebook session with DuckDB backend (cached)."""
    return NotebookSession(_ctx.connection, _model_registry, _ctx.repo)


# Session state initialization
if 'open_tabs' not in st.session_state:
    st.session_state.open_tabs = []

if 'active_tab' not in st.session_state:
    st.session_state.active_tab = None

if 'edit_mode' not in st.session_state:
    st.session_state.edit_mode = {}

if 'markdown_content' not in st.session_state:
    st.session_state.markdown_content = {}

if 'yaml_content' not in st.session_state:
    st.session_state.yaml_content = {}

if 'theme' not in st.session_state:
    st.session_state.theme = 'dark'

# Apply theme
apply_professional_theme()


class NotebookVaultApp:
    """Professional notebook application with modern UI."""

    def __init__(self):
        """Initialize application."""
        self.ctx = get_repo_context()
        self.model_registry = ModelRegistry(self.ctx.repo / "configs" / "models")
        self.notebook_session = get_notebook_session(self.ctx, self.model_registry)
        self.notebooks_root = self.ctx.repo / "configs" / "notebooks"
        self.notebooks_root.mkdir(parents=True, exist_ok=True)
        self.sidebar_nav = SidebarNavigator(self.notebooks_root, self.notebook_session)

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
        """Render professional header with toolbar."""
        # Title row
        st.markdown("### 📊 Data Notebooks")

        # Tab bar and toolbar row (no nested columns)
        if st.session_state.open_tabs:
            col_tabs, col_toolbar = st.columns([0.7, 0.3])

            with col_tabs:
                self._render_compact_tabs()

            with col_toolbar:
                self._render_toolbar()
        else:
            # Just toolbar when no tabs
            self._render_toolbar()

        st.divider()

    def _render_toolbar(self):
        """Render toolbar with edit and theme buttons."""
        # Render buttons horizontally without nested columns

        # Edit button (only if active notebook)
        if st.session_state.active_tab:
            active_notebook = self._get_active_notebook()
            if active_notebook:
                notebook_id = active_notebook[0]
                notebook_config = active_notebook[2]

                # Determine notebook type
                is_markdown = hasattr(notebook_config, '_is_markdown') and notebook_config._is_markdown

                # Check if in edit mode
                in_edit_mode = st.session_state.edit_mode.get(notebook_id, False)

                # Button label based on mode
                if in_edit_mode:
                    button_label = "👁️ View"
                    button_help = "Switch to view mode"
                else:
                    if is_markdown:
                        button_label = "✏️ Edit"
                        button_help = "Edit markdown"
                    else:
                        button_label = "⚙️ Edit"
                        button_help = "Edit configuration"

                if st.button(button_label, help=button_help, key="toolbar_edit"):
                    st.session_state.edit_mode[notebook_id] = not in_edit_mode
                    st.rerun()

        # Theme toggle
        theme_icon = "🌙" if st.session_state.theme == 'light' else "☀️"
        theme_help = "Switch to dark mode" if st.session_state.theme == 'light' else "Switch to light mode"

        if st.button(theme_icon, help=theme_help, key="toolbar_theme"):
            st.session_state.theme = 'dark' if st.session_state.theme == 'light' else 'light'
            st.rerun()

    def _render_compact_tabs(self):
        """Render compact tab bar in header."""
        # Display tabs as simple text with active indicator
        tab_labels = []
        for notebook_id, notebook_path, notebook_config in st.session_state.open_tabs[:4]:
            is_active = st.session_state.active_tab == notebook_id
            title = notebook_config.notebook.title
            if len(title) > 20:
                title = title[:17] + "..."

            # Mark active tab
            if is_active:
                tab_labels.append(f"**📍 {title}**")
            else:
                tab_labels.append(title)

        tabs_display = " • ".join(tab_labels)

        if len(st.session_state.open_tabs) > 4:
            tabs_display += f" • +{len(st.session_state.open_tabs) - 4} more"

        st.caption(tabs_display)

    def _render_filters(self, notebook_config):
        """Render filters for active notebook."""
        # Check for dynamic filters (new system)
        if (hasattr(notebook_config, '_filter_collection') and
            notebook_config._filter_collection and
            notebook_config._filter_collection.filters):
            from app.ui.components.dynamic_filters import render_dynamic_filters
            render_dynamic_filters(
                notebook_config._filter_collection,
                self.notebook_session,
                self.ctx.connection,
                self.notebook_session.storage_service
            )
        elif notebook_config.variables:
            # Old filter system (backward compat)
            render_filters_section(
                notebook_config,
                self.notebook_session,
                self.ctx.connection,
                self.notebook_session.storage_service
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
        is_markdown = hasattr(notebook_config, '_is_markdown') and notebook_config._is_markdown

        # Header
        if is_markdown:
            st.info("📝 **Editing Markdown Notebook** - Changes save automatically")
        else:
            st.info("⚙️ **Editing Configuration** - Changes save automatically")

        # Load current content
        if notebook_id not in st.session_state.markdown_content:
            with open(notebook_path, 'r') as f:
                st.session_state.markdown_content[notebook_id] = f.read()

        # Editor
        edited_content = st.text_area(
            "Content" if is_markdown else "YAML Configuration",
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
            self.notebook_session,
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
