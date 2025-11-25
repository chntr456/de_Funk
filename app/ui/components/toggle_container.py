"""
Toggle Container component for notebook UI.

Replaces st.expander with a custom toggle-based container that:
- Avoids nested expander issues
- Provides better control over appearance
- Supports any nesting depth
- Uses session state for persistent toggle state
- Supports collapse/expand all functionality
"""

import streamlit as st
from typing import Optional, Callable, Any, List
import hashlib


# Registry key for tracking toggle containers per context (e.g., notebook)
TOGGLE_REGISTRY_KEY = "toggle_container_registry"


def _get_toggle_key(container_id: str) -> str:
    """Generate a unique session state key for a toggle container."""
    return f"toggle_container_{container_id}"


def _register_toggle(context: str, toggle_key: str):
    """Register a toggle container in the registry for collapse/expand all."""
    if TOGGLE_REGISTRY_KEY not in st.session_state:
        st.session_state[TOGGLE_REGISTRY_KEY] = {}

    if context not in st.session_state[TOGGLE_REGISTRY_KEY]:
        st.session_state[TOGGLE_REGISTRY_KEY][context] = set()

    st.session_state[TOGGLE_REGISTRY_KEY][context].add(toggle_key)


def clear_toggle_registry(context: str = None):
    """Clear the toggle registry for a context or all contexts."""
    if TOGGLE_REGISTRY_KEY not in st.session_state:
        return

    if context:
        if context in st.session_state[TOGGLE_REGISTRY_KEY]:
            st.session_state[TOGGLE_REGISTRY_KEY][context] = set()
    else:
        st.session_state[TOGGLE_REGISTRY_KEY] = {}


def expand_all(context: str = "default"):
    """Expand all toggle containers for a given context."""
    if TOGGLE_REGISTRY_KEY not in st.session_state:
        return

    registry = st.session_state[TOGGLE_REGISTRY_KEY]
    if context in registry:
        for toggle_key in registry[context]:
            st.session_state[toggle_key] = True


def collapse_all(context: str = "default"):
    """Collapse all toggle containers for a given context."""
    if TOGGLE_REGISTRY_KEY not in st.session_state:
        return

    registry = st.session_state[TOGGLE_REGISTRY_KEY]
    if context in registry:
        for toggle_key in registry[context]:
            st.session_state[toggle_key] = False


def render_expand_collapse_buttons(context: str = "default", key_suffix: str = ""):
    """
    Render expand/collapse all buttons.

    Args:
        context: The context (e.g., notebook_id) to operate on
        key_suffix: Optional suffix for button keys to ensure uniqueness
    """
    col1, col2, col3 = st.columns([0.15, 0.15, 0.7])

    with col1:
        if st.button("⊞ Expand All", key=f"expand_all_{context}_{key_suffix}",
                     help="Expand all sections", use_container_width=True):
            expand_all(context)
            st.rerun()

    with col2:
        if st.button("⊟ Collapse All", key=f"collapse_all_{context}_{key_suffix}",
                     help="Collapse all sections", use_container_width=True):
            collapse_all(context)
            st.rerun()


def _generate_container_id(label: str, context: str = "") -> str:
    """Generate a unique container ID from label and context."""
    content = f"{label}_{context}"
    return hashlib.md5(content.encode()).hexdigest()[:8]


def toggle_container(
    label: str,
    expanded: bool = False,
    container_id: Optional[str] = None,
    icon_open: str = "▼",
    icon_closed: str = "▶",
    show_border: bool = True,
    indent: bool = True,
    key_prefix: str = ""
) -> bool:
    """
    Create a toggle container that can be expanded/collapsed.

    Unlike st.expander, this component:
    - Can be nested without UI issues
    - Provides consistent styling
    - Uses explicit session state management

    Args:
        label: Display label for the toggle header
        expanded: Default expanded state (only used if no state exists)
        container_id: Unique ID for this container (auto-generated if not provided)
        icon_open: Icon to show when expanded
        icon_closed: Icon to show when collapsed
        show_border: Whether to show a border around the container
        indent: Whether to indent the content
        key_prefix: Optional prefix for the session state key

    Returns:
        bool: Whether the container is currently expanded (use to conditionally render content)

    Example:
        ```python
        if toggle_container("Click to expand", expanded=True):
            st.write("This content is inside the toggle container")

            # Nested toggle containers work fine
            if toggle_container("Nested section", container_id="nested_1"):
                st.write("Nested content")
        ```
    """
    # Generate container ID if not provided
    if container_id is None:
        container_id = _generate_container_id(label, key_prefix)

    # Create unique key for this container
    toggle_key = _get_toggle_key(f"{key_prefix}_{container_id}")

    # Initialize state if not exists
    if toggle_key not in st.session_state:
        st.session_state[toggle_key] = expanded

    is_expanded = st.session_state[toggle_key]

    # Render toggle header
    icon = icon_open if is_expanded else icon_closed

    # Use columns for layout: icon+label on left, toggle fills the row
    col1, col2 = st.columns([0.95, 0.05])

    with col1:
        # Clickable header
        if st.button(
            f"{icon} {label}",
            key=f"toggle_btn_{key_prefix}_{container_id}",
            use_container_width=True,
            type="secondary"
        ):
            st.session_state[toggle_key] = not is_expanded
            st.rerun()

    return st.session_state[toggle_key]


def toggle_section(
    label: str,
    content_func: Callable[[], Any],
    expanded: bool = False,
    container_id: Optional[str] = None,
    key_prefix: str = "",
    show_border: bool = True
) -> None:
    """
    Render a toggle section with content provided by a function.

    This is a convenience wrapper that handles the conditional rendering.

    Args:
        label: Display label for the toggle header
        content_func: Function that renders the content when expanded
        expanded: Default expanded state
        container_id: Unique ID for this container
        key_prefix: Optional prefix for the session state key
        show_border: Whether to show a border around content

    Example:
        ```python
        def render_my_content():
            st.write("Hello")
            st.chart(data)

        toggle_section("My Section", render_my_content, expanded=True)
        ```
    """
    if toggle_container(label, expanded=expanded, container_id=container_id, key_prefix=key_prefix):
        if show_border:
            with st.container():
                st.markdown("""
                <style>
                .toggle-content {
                    border-left: 2px solid #4a4a4a;
                    padding-left: 1rem;
                    margin-left: 0.5rem;
                    margin-bottom: 1rem;
                }
                </style>
                """, unsafe_allow_html=True)
                content_func()
        else:
            content_func()


class ToggleContainer:
    """
    Context manager for toggle containers with automatic state management.

    Provides a cleaner API for creating toggle containers with nested content.

    Example:
        ```python
        with ToggleContainer("Section Title", expanded=True) as tc:
            if tc.is_open:
                st.write("Content here")

                # Nested containers work perfectly
                with ToggleContainer("Nested", container_id="nested") as nested:
                    if nested.is_open:
                        st.write("Nested content")
        ```
    """

    # Class-level counter for generating unique IDs
    _counter = 0

    def __init__(
        self,
        label: str,
        expanded: bool = False,
        container_id: Optional[str] = None,
        icon_open: str = "▼",
        icon_closed: str = "▶",
        key_prefix: str = "",
        style: str = "default",  # "default", "minimal", "card", "section"
        context: str = "default"  # Context for collapse/expand all
    ):
        """
        Initialize a toggle container.

        Args:
            label: Display label for the toggle header
            expanded: Default expanded state
            container_id: Unique ID (auto-generated if not provided)
            icon_open: Icon when expanded
            icon_closed: Icon when collapsed
            key_prefix: Prefix for session state keys
            style: Visual style ("default", "minimal", "card", "section")
            context: Context for grouping toggles (used by collapse/expand all)
        """
        self.label = label
        self.expanded = expanded
        self.icon_open = icon_open
        self.icon_closed = icon_closed
        self.key_prefix = key_prefix
        self.style = style
        self.context = context

        # Generate unique ID
        if container_id is None:
            ToggleContainer._counter += 1
            self.container_id = f"tc_{ToggleContainer._counter}_{_generate_container_id(label, key_prefix)}"
        else:
            self.container_id = container_id

        self.toggle_key = _get_toggle_key(f"{key_prefix}_{self.container_id}")
        self.is_open = False
        self._container = None

        # Register this toggle for collapse/expand all functionality
        _register_toggle(self.context, self.toggle_key)

    def __enter__(self):
        """Enter the context manager, render header and determine state."""
        # Initialize state if not exists
        if self.toggle_key not in st.session_state:
            st.session_state[self.toggle_key] = self.expanded

        self.is_open = st.session_state[self.toggle_key]

        # Render toggle header based on style
        self._render_header()

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the context manager."""
        # Add bottom spacing if content was rendered
        if self.is_open and self.style == "card":
            st.markdown("<div style='margin-bottom: 1rem;'></div>", unsafe_allow_html=True)
        return False

    def _render_header(self):
        """Render the toggle header based on style."""
        icon = self.icon_open if self.is_open else self.icon_closed

        if self.style == "minimal":
            # Minimal style - just text with icon
            if st.button(
                f"{icon} {self.label}",
                key=f"toggle_btn_{self.container_id}",
                type="secondary",
                use_container_width=True
            ):
                st.session_state[self.toggle_key] = not self.is_open
                st.rerun()

        elif self.style == "card":
            # Card style with background
            st.markdown(f"""
            <style>
            .toggle-card-header {{
                background: linear-gradient(135deg, rgba(28, 131, 225, 0.1) 0%, rgba(28, 131, 225, 0.05) 100%);
                border-radius: 8px 8px {'0 0' if self.is_open else '8px 8px'};
                padding: 0.5rem 1rem;
                margin-bottom: {'0' if self.is_open else '0.5rem'};
                border: 1px solid rgba(28, 131, 225, 0.2);
                {'border-bottom: none;' if self.is_open else ''}
            }}
            .toggle-card-content {{
                border: 1px solid rgba(28, 131, 225, 0.2);
                border-top: none;
                border-radius: 0 0 8px 8px;
                padding: 1rem;
                margin-bottom: 0.5rem;
            }}
            </style>
            """, unsafe_allow_html=True)

            if st.button(
                f"{icon} {self.label}",
                key=f"toggle_btn_{self.container_id}",
                type="secondary",
                use_container_width=True
            ):
                st.session_state[self.toggle_key] = not self.is_open
                st.rerun()

        elif self.style == "section":
            # Section style - clean separator for notebook sections
            col1, col2 = st.columns([0.05, 0.95])
            with col1:
                # Small toggle indicator
                if st.button(
                    icon,
                    key=f"toggle_icon_{self.container_id}",
                    type="secondary"
                ):
                    st.session_state[self.toggle_key] = not self.is_open
                    st.rerun()
            with col2:
                # Section label (clickable)
                if st.button(
                    self.label,
                    key=f"toggle_btn_{self.container_id}",
                    type="secondary",
                    use_container_width=True
                ):
                    st.session_state[self.toggle_key] = not self.is_open
                    st.rerun()

        else:
            # Default style
            if st.button(
                f"{icon} {self.label}",
                key=f"toggle_btn_{self.container_id}",
                type="secondary",
                use_container_width=True
            ):
                st.session_state[self.toggle_key] = not self.is_open
                st.rerun()

    def toggle(self):
        """Manually toggle the container state."""
        st.session_state[self.toggle_key] = not st.session_state.get(self.toggle_key, self.expanded)

    def open(self):
        """Open the container."""
        st.session_state[self.toggle_key] = True

    def close(self):
        """Close the container."""
        st.session_state[self.toggle_key] = False


def apply_toggle_styles():
    """
    Apply global CSS styles for toggle containers.

    Call this once at the start of your app to apply consistent styling.
    """
    st.markdown("""
    <style>
    /* Toggle container button styling */
    .stButton > button[kind="secondary"] {
        text-align: left !important;
        justify-content: flex-start !important;
        font-weight: 500;
        transition: background-color 0.2s ease;
    }

    .stButton > button[kind="secondary"]:hover {
        background-color: rgba(28, 131, 225, 0.1);
    }

    /* Toggle content indentation */
    .toggle-content-indent {
        margin-left: 1.5rem;
        padding-left: 1rem;
        border-left: 2px solid rgba(28, 131, 225, 0.3);
    }

    /* Nested toggle spacing */
    .toggle-nested {
        margin-top: 0.5rem;
    }
    </style>
    """, unsafe_allow_html=True)


def collapsible_markdown(content: str, label: str = "Show details", expanded: bool = False, container_id: Optional[str] = None):
    """
    Render markdown content in a collapsible toggle container.

    Args:
        content: Markdown content to render
        label: Toggle label
        expanded: Default state
        container_id: Unique ID
    """
    with ToggleContainer(label, expanded=expanded, container_id=container_id, style="minimal") as tc:
        if tc.is_open:
            st.markdown(content)


def collapsible_code(code: str, language: str = "python", label: str = "Show code", expanded: bool = False, container_id: Optional[str] = None):
    """
    Render code in a collapsible toggle container.

    Args:
        code: Code content
        language: Code language for syntax highlighting
        label: Toggle label
        expanded: Default state
        container_id: Unique ID
    """
    with ToggleContainer(label, expanded=expanded, container_id=container_id, style="minimal") as tc:
        if tc.is_open:
            st.code(code, language=language)
