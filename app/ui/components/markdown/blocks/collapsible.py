"""
Collapsible section renderer.

Handles rendering of collapsible/expandable sections using
ToggleContainer to avoid Streamlit nesting issues.
"""

import streamlit as st
from typing import Dict, Any

from ..toggle_container import ToggleContainer
from .text import render_markdown_block
from .error import render_error_block


def render_collapsible_section(block: Dict[str, Any], notebook_session, connection, block_index: int = 0):
    """
    Render a collapsible section using ToggleContainer.

    Uses ToggleContainer instead of st.expander to avoid nesting issues.

    Args:
        block: Content block with summary and inner content
        notebook_session: NotebookSession for data retrieval
        connection: DataConnection for converting to pandas
        block_index: Index of this block for unique keys
    """
    summary = block['summary']
    inner_blocks = block['content']

    # Use ToggleContainer for collapsible sections (no nesting issues)
    with ToggleContainer(
        summary,
        expanded=False,
        container_id=f"collapsible_{block_index}",
        style="default"
    ) as tc:
        if tc.is_open:
            # Render inner content blocks
            for inner_idx, inner_block in enumerate(inner_blocks):
                inner_type = inner_block['type']

                if inner_type == 'markdown':
                    # No need for in_collapsible flag with ToggleContainer
                    render_markdown_block(
                        inner_block['content'],
                        in_collapsible=True,
                        block_index=f"{block_index}_{inner_idx}"
                    )

                elif inner_type == 'exhibit':
                    # Import here to avoid circular imports
                    from .exhibit import render_exhibit_block
                    render_exhibit_block(inner_block, notebook_session, connection, in_collapsible=True)

                elif inner_type == 'error':
                    render_error_block(inner_block, block_index=f"{block_index}_{inner_idx}")
