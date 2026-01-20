"""
Session state initialization and management.

Centralizes all session state initialization for the notebook application,
making it easier to understand and maintain the application state.
"""

import streamlit as st
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List


@dataclass
class AppState:
    """
    Application state container.

    Provides type-safe access to session state values.
    """
    open_tabs: List[str] = field(default_factory=list)
    active_tab: Optional[str] = None
    edit_mode: Dict[str, bool] = field(default_factory=dict)
    block_edit_mode: Dict[str, bool] = field(default_factory=dict)
    markdown_content: Dict[str, str] = field(default_factory=dict)
    theme: str = 'dark'
    show_notebook_creator: bool = False
    notebook_model_sessions: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_session_state(cls) -> 'AppState':
        """Load state from Streamlit session state."""
        return cls(
            open_tabs=st.session_state.get('open_tabs', []),
            active_tab=st.session_state.get('active_tab'),
            edit_mode=st.session_state.get('edit_mode', {}),
            block_edit_mode=st.session_state.get('block_edit_mode', {}),
            markdown_content=st.session_state.get('markdown_content', {}),
            theme=st.session_state.get('theme', 'dark'),
            show_notebook_creator=st.session_state.get('show_notebook_creator', False),
            notebook_model_sessions=st.session_state.get('notebook_model_sessions', {}),
        )

    def to_session_state(self):
        """Sync state back to Streamlit session state."""
        st.session_state.open_tabs = self.open_tabs
        st.session_state.active_tab = self.active_tab
        st.session_state.edit_mode = self.edit_mode
        st.session_state.block_edit_mode = self.block_edit_mode
        st.session_state.markdown_content = self.markdown_content
        st.session_state.theme = self.theme
        st.session_state.show_notebook_creator = self.show_notebook_creator
        st.session_state.notebook_model_sessions = self.notebook_model_sessions


def init_session_state():
    """
    Initialize all session state variables.

    Call this at the start of the application to ensure all
    required session state variables exist.
    """
    # UI state
    if 'open_tabs' not in st.session_state:
        st.session_state.open_tabs = []

    if 'active_tab' not in st.session_state:
        st.session_state.active_tab = None

    if 'edit_mode' not in st.session_state:
        st.session_state.edit_mode = {}

    if 'block_edit_mode' not in st.session_state:
        st.session_state.block_edit_mode = {}

    if 'markdown_content' not in st.session_state:
        st.session_state.markdown_content = {}

    if 'theme' not in st.session_state:
        st.session_state.theme = 'dark'

    if 'show_notebook_creator' not in st.session_state:
        st.session_state.show_notebook_creator = False

    # Cache model sessions per notebook
    if 'notebook_model_sessions' not in st.session_state:
        st.session_state.notebook_model_sessions = {}


def init_app_objects(repo_root: Path):
    """
    Initialize application-level objects in session state.

    These are the core objects used throughout the application:
    - RepoContext: Repository configuration
    - ModelRegistry: Model discovery
    - UniversalSession: Query engine
    - NotebookManager: Notebook loading/parsing

    Args:
        repo_root: Path to repository root
    """
    from core.context import RepoContext
    from models.registry import ModelRegistry
    from models.api.session import UniversalSession
    from app.notebook.managers import NotebookManager

    if 'repo_context' not in st.session_state:
        st.session_state.repo_context = RepoContext.from_repo_root(connection_type="duckdb")

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
        notebooks_root = ctx.repo / "configs" / "notebooks"
        st.session_state.notebook_manager = NotebookManager(
            st.session_state.universal_session,
            ctx.repo,
            notebooks_root
        )


def get_app_state() -> AppState:
    """Get typed application state from session state."""
    return AppState.from_session_state()


def get_repo_context():
    """Get repository context from session state."""
    return st.session_state.get('repo_context')


def get_universal_session():
    """Get universal session from session state."""
    return st.session_state.get('universal_session')


def get_notebook_manager():
    """Get notebook manager from session state."""
    return st.session_state.get('notebook_manager')


def get_model_registry():
    """Get model registry from session state."""
    return st.session_state.get('model_registry')
