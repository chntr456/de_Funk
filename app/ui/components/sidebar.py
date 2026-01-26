"""
Sidebar navigation component.

Provides directory tree navigation for notebooks with tab management.
"""

import streamlit as st
from pathlib import Path
from typing import List, Dict, Optional


class SidebarNavigator:
    """Handles sidebar navigation and notebook discovery."""

    def __init__(self, notebooks_root: Path, notebook_session):
        """
        Initialize sidebar navigator.

        Args:
            notebooks_root: Root directory containing markdown notebook files
            notebook_session: NotebookSession for loading notebooks
        """
        self.notebooks_root = notebooks_root
        self.notebook_session = notebook_session

    def render(self):
        """Render sidebar navigation."""
        # Header with New Notebook button
        col1, col2 = st.columns([0.7, 0.3])
        with col1:
            st.header("📚 Notebooks")
        with col2:
            if st.button("➕", key="new_nb_btn", help="Create new notebook"):
                st.session_state.show_notebook_creator = True
                st.rerun()

        # Scan for notebooks
        notebooks = self._scan_notebooks()

        if not notebooks:
            st.info("No notebooks found. Create a `.md` file in `notebooks/`")
            return

        # Group by directory
        grouped = self._group_by_directory(notebooks)

        # Render tree
        for folder, files in sorted(grouped.items()):
            if folder == ".":
                # Root level files
                for file_path in sorted(files):
                    self._render_notebook_item(file_path)
            else:
                # Folder with files
                with st.expander(f"📁 {folder}", expanded=True):
                    for file_path in sorted(files):
                        self._render_notebook_item(file_path)

        # Add model graph viewer at bottom of sidebar
        st.divider()
        self._render_model_graph_section()

    def _render_model_graph_section(self):
        """Render model graph info in sidebar."""
        with st.expander("🔗 Model Graph", expanded=False):
            # Get model graph from session
            if hasattr(self.notebook_session, 'session') and hasattr(self.notebook_session.session, 'model_graph'):
                model_graph = self.notebook_session.session.model_graph
                metrics = model_graph.get_metrics()

                # Show basic metrics
                st.metric("Models", metrics['num_models'])
                st.metric("Dependencies", metrics['num_dependencies'])
                st.metric("Is DAG", "✓" if metrics['is_dag'] else "✗")

                if st.button("View Full Graph", use_container_width=True):
                    st.session_state.show_graph_viewer = True
            else:
                st.info("Graph not available")

    def _scan_notebooks(self) -> List[Path]:
        """Scan for markdown notebook files."""
        md_notebooks = list(self.notebooks_root.rglob("*.md"))

        # Filter out README and other documentation files
        md_notebooks = [p for p in md_notebooks if not p.name.upper().startswith('README')]

        return md_notebooks

    def _group_by_directory(self, notebooks: List[Path]) -> Dict[str, List[Path]]:
        """Group notebooks by their parent directory."""
        grouped = {}
        for notebook_path in notebooks:
            # Get relative path from notebooks root
            rel_path = notebook_path.relative_to(self.notebooks_root)

            if len(rel_path.parts) == 1:
                # Root level
                folder = "."
            else:
                # In a subfolder
                folder = rel_path.parts[0]

            if folder not in grouped:
                grouped[folder] = []
            grouped[folder].append(notebook_path)

        return grouped

    def _render_notebook_item(self, notebook_path: Path):
        """Render a single notebook item in the tree."""
        notebook_id = str(notebook_path.relative_to(self.notebooks_root))
        notebook_name = notebook_path.stem

        # Check if already open
        is_open = any(tab[0] == notebook_id for tab in st.session_state.open_tabs)
        is_active = st.session_state.active_tab == notebook_id

        # Determine icon based on file type
        if notebook_path.suffix == '.md':
            base_icon = "📝"  # Markdown icon
        else:
            base_icon = "📄"  # YAML icon

        # Style based on state
        if is_active:
            icon = "📖"
            label = f"**{notebook_name}**"
        elif is_open:
            icon = base_icon
            label = f"*{notebook_name}*"
        else:
            icon = base_icon
            label = notebook_name

        # Click to open/activate
        if st.button(f"{icon} {label}", key=f"nav_{notebook_id}", use_container_width=True):
            self._open_notebook(notebook_id, notebook_path)

    def _open_notebook(self, notebook_id: str, notebook_path: Path):
        """Open a notebook (or switch to it if already open)."""
        # Check if already open
        existing_tab = next((tab for tab in st.session_state.open_tabs if tab[0] == notebook_id), None)

        if existing_tab:
            # ALWAYS reload from disk to get fresh content
            # This ensures any file changes are picked up
            try:
                notebook_config = self.notebook_session.load_notebook(str(notebook_path))
                # Update the existing tab with fresh config
                for i, (tab_id, tab_path, _) in enumerate(st.session_state.open_tabs):
                    if tab_id == notebook_id:
                        st.session_state.open_tabs[i] = (tab_id, tab_path, notebook_config)
                        break
                # Clear any cached editor state for this notebook to force fresh content
                _clear_editor_state(notebook_id)
                st.session_state.active_tab = notebook_id
                st.rerun()
            except Exception as e:
                st.error(f"Error reloading notebook: {str(e)}")
        else:
            # Load the notebook (first time opening)
            try:
                notebook_config = self.notebook_session.load_notebook(str(notebook_path))
                st.session_state.open_tabs.append((notebook_id, notebook_path, notebook_config))
                st.session_state.active_tab = notebook_id
                st.session_state.edit_mode[notebook_id] = False
                st.rerun()

            except Exception as e:
                st.error(f"Error loading notebook: {str(e)}")


def _clear_editor_state(notebook_id: str):
    """
    Clear all cached editor state for a notebook.

    This is necessary when reloading a notebook from disk to ensure fresh content
    is used instead of stale session state. The flat_renderer caches editor content
    in session state with keys like 'edit_content_{block_id}', and this can persist
    even across app restarts if the browser tab remains open.

    Args:
        notebook_id: ID of the notebook to clear state for
    """
    import logging
    logger = logging.getLogger(__name__)

    # Keys to clear: patterns used by flat_renderer.py for editor caching
    patterns_to_clear = [
        'edit_content_',
        'edit_original_',
        'edit_formatted_',
        'stored_orig_',
        'save_error_',
        'textarea_',
    ]

    keys_to_delete = []
    for key in list(st.session_state.keys()):
        # Check if key matches any of our patterns
        for pattern in patterns_to_clear:
            if key.startswith(pattern):
                keys_to_delete.append(key)
                break

    # Also clear the edit states dict entries for this notebook's blocks
    if 'flat_renderer_edit_states' in st.session_state:
        edit_states = st.session_state['flat_renderer_edit_states']
        blocks_to_clear = [k for k in edit_states.keys() if 'block_' in k]
        for block_key in blocks_to_clear:
            del edit_states[block_key]

    # Delete the collected keys
    for key in keys_to_delete:
        del st.session_state[key]

    if keys_to_delete:
        logger.debug(f"Cleared {len(keys_to_delete)} editor state keys for notebook reload")


def close_tab(notebook_id: str):
    """
    Close a notebook tab and clean up its resources.

    Args:
        notebook_id: ID of the notebook to close
    """
    # Remove from open tabs
    st.session_state.open_tabs = [
        tab for tab in st.session_state.open_tabs if tab[0] != notebook_id
    ]

    # Clear edit mode
    if notebook_id in st.session_state.edit_mode:
        del st.session_state.edit_mode[notebook_id]

    # Clear markdown content
    if notebook_id in st.session_state.markdown_content:
        del st.session_state.markdown_content[notebook_id]

    # Clear cached model sessions to free memory
    if notebook_id in st.session_state.notebook_model_sessions:
        del st.session_state.notebook_model_sessions[notebook_id]

    # Switch active tab
    if st.session_state.active_tab == notebook_id:
        if st.session_state.open_tabs:
            st.session_state.active_tab = st.session_state.open_tabs[-1][0]
        else:
            st.session_state.active_tab = None
            st.session_state.current_notebook_id = None

    st.rerun()
