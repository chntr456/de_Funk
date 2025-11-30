"""
Error block renderer.

Handles rendering of error messages with expandable YAML content display.
"""

import streamlit as st
from typing import Dict, Any

from ..toggle_container import ToggleContainer


def render_error_block(block: Dict[str, Any], block_index: Any = 0):
    """
    Render an error block with YAML content display.

    Args:
        block: Error block with message and content
        block_index: Index of this block for unique keys
    """
    st.error(f"Error: {block['message']}")

    # Use ToggleContainer to show exhibit YAML
    with ToggleContainer(
        "Show exhibit YAML",
        expanded=False,
        container_id=f"error_yaml_{block_index}",
        style="minimal"
    ) as tc:
        if tc.is_open:
            st.code(block['content'], language='yaml')
