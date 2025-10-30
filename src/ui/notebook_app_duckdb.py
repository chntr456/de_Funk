"""
Professional notebook application with DuckDB backend (Optimized).

This version uses modular UI components for clean, maintainable code.

Features:
- DuckDB backend (10-100x faster than Spark)
- Modular UI components (from Phase 4 refactoring)
- Directory tree navigation
- Multiple notebook tabs
- Toggle between YAML edit and rendered view
- Professional themes (light/dark)

Usage:
    streamlit run src/ui/notebook_app_professional.py
"""

import streamlit as st
from pathlib import Path
from typing import Dict, Any

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.orchestration.context import RepoContext
from src.core import ModelRegistry
from src.notebook.api.notebook_session import NotebookSession

# Import modular UI components (Phase 4)
from src.ui.components.theme import apply_professional_theme
from src.ui.components.sidebar import SidebarNavigator, close_tab
from src.ui.components.filters import render_filters_section
from src.ui.components.yaml_editor import render_yaml_editor
from src.ui.components.notebook_view import render_notebook_exhibits


# Configure page
st.set_page_config(
    page_title="Notebook Platform",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource
def get_repo_context():
    """
    Get repository context configured for notebook UI.

    Uses DuckDB for 10-100x faster queries compared to Spark.
    Perfect for interactive notebook rendering.

    NO SPARK - DuckDB only!
    """
    return RepoContext.from_repo_root(connection_type="duckdb")


@st.cache_resource
def get_model_registry(_ctx):
    """Get model registry (cached)."""
    models_dir = _ctx.repo / "configs" / "notebooks"
    return ModelRegistry(models_dir)


@st.cache_resource
def get_notebook_session(_ctx, _model_registry):
    """
    Get notebook session with DuckDB backend (cached).

    This session uses StorageService with DuckDB for instant queries.
    """
    return NotebookSession(_ctx.connection, _model_registry, _ctx.repo)


# Session state initialization
if 'open_tabs' not in st.session_state:
    st.session_state.open_tabs = []  # List of (notebook_id, notebook_path, notebook_config)

if 'active_tab' not in st.session_state:
    st.session_state.active_tab = None

if 'edit_mode' not in st.session_state:
    st.session_state.edit_mode = {}  # Dict of notebook_id -> bool

if 'yaml_content' not in st.session_state:
    st.session_state.yaml_content = {}  # Dict of notebook_id -> yaml string

if 'theme' not in st.session_state:
    st.session_state.theme = 'light'  # 'light' or 'dark'

# Apply theme
apply_professional_theme(st.session_state.theme)


class NotebookVaultApp:
    """Enhanced notebook application with vault-style navigation and DuckDB backend."""

    def __init__(self):
        """Initialize application with DuckDB backend."""
        self.ctx = get_repo_context()
        self.model_registry = ModelRegistry(self.ctx.repo / "configs" / "models")
        self.notebook_session = get_notebook_session(self.ctx, self.model_registry)
        self.notebooks_root = self.ctx.repo / "configs" / "notebooks"
        self.notebooks_root.mkdir(parents=True, exist_ok=True)

        # Initialize sidebar navigator
        self.sidebar_nav = SidebarNavigator(self.notebooks_root, self.notebook_session)

    def run(self):
        """Run the application."""
        # Theme toggle in top-right
        col1, col2 = st.columns([0.95, 0.05])
        with col2:
            theme_icon = "🌙" if st.session_state.theme == 'light' else "☀️"
            if st.button(theme_icon, help="Toggle theme", key="theme_toggle"):
                st.session_state.theme = 'dark' if st.session_state.theme == 'light' else 'light'
                st.rerun()

        # Sidebar: Directory tree + filters
        with st.sidebar:
            self.sidebar_nav.render()

            # Show filters if a notebook is active
            if st.session_state.active_tab:
                st.divider()
                active_notebook = self._get_active_notebook()
                if active_notebook:
                    _, _, notebook_config = active_notebook
                    render_filters_section(notebook_config, self.notebook_session)

        # Main content: Tabs
        self._render_main_content()

    def _get_active_notebook(self):
        """Get the active notebook tuple."""
        return next(
            (tab for tab in st.session_state.open_tabs if tab[0] == st.session_state.active_tab),
            None
        )

    def _render_main_content(self):
        """Render main content area with tabs."""
        if not st.session_state.open_tabs:
            self._render_welcome()
            return

        # Render tab bar
        tab_names = [f"{tab[2].notebook.title}" for tab in st.session_state.open_tabs]
        cols = st.columns([0.9, 0.1] * len(st.session_state.open_tabs))

        for i, (notebook_id, notebook_path, notebook_config) in enumerate(st.session_state.open_tabs):
            with cols[i * 2]:
                is_active = st.session_state.active_tab == notebook_id
                if st.button(
                    notebook_config.notebook.title,
                    key=f"tab_{notebook_id}",
                    type="primary" if is_active else "secondary",
                    use_container_width=True,
                ):
                    st.session_state.active_tab = notebook_id
                    st.rerun()

            with cols[i * 2 + 1]:
                if st.button("✕", key=f"close_{notebook_id}"):
                    close_tab(notebook_id)
                    st.rerun()

        st.divider()

        # Render active notebook
        active_notebook = self._get_active_notebook()
        if active_notebook:
            self._render_notebook_content(active_notebook)

    def _render_notebook_content(self, notebook_tuple):
        """Render the content of a notebook using modular components."""
        notebook_id, notebook_path, notebook_config = notebook_tuple

        # Toggle between edit and view mode
        col1, col2 = st.columns([0.1, 0.9])

        with col1:
            edit_mode = st.session_state.edit_mode.get(notebook_id, False)
            if st.button("📝 Edit" if not edit_mode else "📊 View", key=f"toggle_{notebook_id}"):
                st.session_state.edit_mode[notebook_id] = not edit_mode
                st.rerun()

        with col2:
            st.title(notebook_config.notebook.title)
            if notebook_config.notebook.description:
                st.caption(notebook_config.notebook.description)

        st.divider()

        # Render based on mode using modular components
        if st.session_state.edit_mode.get(notebook_id, False):
            # Use YAML editor component
            render_yaml_editor(notebook_id, notebook_path, self.notebook_session)
        else:
            # Use notebook view component (renders exhibits)
            render_notebook_exhibits(notebook_id, notebook_config, self.notebook_session, self.ctx.connection)

    def _render_welcome(self):
        """Render welcome screen."""
        st.title("📊 Notebook Platform (DuckDB-Powered)")

        st.markdown("""
        ## Professional Financial Modeling Environment

        ### Features

        **📁 Notebook Library**
        - Organized directory structure
        - Multi-tab interface
        - Quick navigation

        **⚡ DuckDB Backend**
        - **10-100x faster** than Spark
        - Instant queries (~50-200ms)
        - No JVM overhead
        - Perfect for interactive notebooks

        **📝 YAML Configuration**
        - Inline YAML editor
        - Real-time validation
        - Hot reload

        **🎛️ Dynamic Filtering**
        - Time-based filters
        - Multi-select dimensions
        - Context-aware filtering

        **📊 Interactive Exhibits**
        - Metric cards with smart formatting
        - Line and bar charts
        - Data tables with export
        - Theme-aware visualizations

        **🎨 Professional Design**
        - Light/dark themes
        - Clean, minimal interface
        - Consulting-grade appearance

        ---

        **Get Started:** Select a notebook from the sidebar →

        **Performance:** Powered by DuckDB for instant queries!
        """)


def main():
    """Main entry point."""
    app = NotebookVaultApp()
    app.run()


if __name__ == "__main__":
    main()
