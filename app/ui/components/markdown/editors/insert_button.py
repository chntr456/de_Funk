"""
Insert block button component.

Provides UI for inserting new blocks into the notebook.
"""

import streamlit as st
from typing import Optional, Callable

from ..utils import get_default_block_content


def render_insert_block_button(
    after_index: int,
    on_insert: Optional[Callable[[int, str, str], None]] = None
):
    """
    Render an insert block button with type selection.

    Args:
        after_index: Index after which to insert the new block
        on_insert: Callback when block is inserted (after_index, block_type, content)
    """
    insert_key = f"insert_menu_{after_index}"

    if insert_key not in st.session_state:
        st.session_state[insert_key] = False

    # Small button to show insert options
    col_spacer, col_btn = st.columns([0.95, 0.05])

    with col_btn:
        if st.button("➕", key=f"show_insert_{after_index}", help="Insert block"):
            st.session_state[insert_key] = not st.session_state[insert_key]
            st.rerun()

    if st.session_state[insert_key]:
        st.markdown("---")
        st.markdown("**Insert new block:**")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            if st.button("📝 Markdown", key=f"insert_md_{after_index}", use_container_width=True):
                if on_insert:
                    on_insert(after_index, 'markdown', get_default_block_content('markdown'))
                st.session_state[insert_key] = False
                st.rerun()

        with col2:
            if st.button("📊 Exhibit", key=f"insert_ex_{after_index}", use_container_width=True):
                if on_insert:
                    on_insert(after_index, 'exhibit', get_default_block_content('exhibit'))
                st.session_state[insert_key] = False
                st.rerun()

        with col3:
            if st.button("📁 Collapsible", key=f"insert_col_{after_index}", use_container_width=True):
                if on_insert:
                    on_insert(after_index, 'collapsible', get_default_block_content('collapsible'))
                st.session_state[insert_key] = False
                st.rerun()

        with col4:
            if st.button("Cancel", key=f"cancel_insert_{after_index}", use_container_width=True):
                st.session_state[insert_key] = False
                st.rerun()

        st.markdown("---")
