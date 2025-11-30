"""
Inline editor for markdown content.

Provides simple inline editing for non-header markdown content.
"""

import streamlit as st
from typing import Optional, Callable

from ..blocks.text import render_markdown_content


def render_inline_editor(
    block_index: int,
    content: str,
    on_edit: Optional[Callable[[int, str], None]] = None
):
    """
    Render an inline editor for non-header markdown content.

    Args:
        block_index: Index of the block
        content: Markdown content
        on_edit: Callback when content is saved
    """
    edit_key = f"inline_edit_{block_index}"

    if edit_key not in st.session_state:
        st.session_state[edit_key] = False

    col_content, col_edit = st.columns([0.95, 0.05])

    with col_edit:
        if st.session_state[edit_key]:
            if st.button("✕", key=f"cancel_inline_{block_index}", help="Cancel"):
                st.session_state[edit_key] = False
                st.rerun()
        else:
            if st.button("✏️", key=f"edit_inline_{block_index}", help="Edit"):
                st.session_state[edit_key] = True
                st.rerun()

    with col_content:
        if st.session_state[edit_key]:
            edited = st.text_area(
                "Edit",
                value=content,
                height=150,
                key=f"inline_editor_{block_index}",
                label_visibility="collapsed"
            )
            if st.button("💾 Save", key=f"save_inline_{block_index}"):
                if on_edit:
                    on_edit(block_index, edited)
                st.session_state[edit_key] = False
                st.rerun()
        else:
            render_markdown_content(content)
