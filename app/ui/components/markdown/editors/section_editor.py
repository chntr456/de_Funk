"""
Section editor for markdown notebooks.

Handles editing of sections including headers, nested content, and exhibits.
"""

import streamlit as st
from typing import Dict, Any, List, Optional, Callable


def render_section_editor(
    block_index: int,
    content: str,
    header_line: str,
    on_edit: Optional[Callable[[int, str], None]] = None,
    children: Optional[List[Dict[str, Any]]] = None,
    exhibit_count: int = 0
):
    """
    Render an editor for a section (header + body + nested content).

    When a section has children (nested headers), the editor shows the full
    grouped content so the user sees everything together. Exhibits within
    the section are shown as $exhibits${} syntax for editing.

    Args:
        block_index: Index of the block
        content: Full content including header, nested sections, and exhibits
        header_line: The header line (e.g., "# Title")
        on_edit: Callback when content is saved
        children: List of child blocks (for info display)
        exhibit_count: Number of exhibits in this section
    """
    edit_key = f"edit_section_{block_index}"
    content_key = f"section_content_{block_index}"
    original_key = f"section_original_{block_index}"

    # Store content in session state
    if content_key not in st.session_state:
        st.session_state[content_key] = content
    # Store original content for find/replace
    if original_key not in st.session_state:
        st.session_state[original_key] = content

    # Show header info
    has_children = children and len(children) > 0
    info_parts = []
    if has_children:
        info_parts.append(f"{len(children)} subsection(s)")
    if exhibit_count > 0:
        info_parts.append(f"{exhibit_count} exhibit(s)")

    if info_parts:
        st.markdown(f"**Edit Section** *({', '.join(info_parts)})*")
        st.caption("Tip: Edit all content including nested headers and exhibits here.")
        if exhibit_count > 0:
            st.caption("Exhibits are shown as `$exhibits${...}` syntax and will be rendered after saving.")
    else:
        st.markdown("**Edit Section**")

    # Calculate height based on content
    line_count = content.count('\n') + 1
    height = min(max(150, line_count * 20), 400)

    edited_content = st.text_area(
        "Content",
        value=st.session_state[content_key],
        height=height,
        key=f"section_editor_{block_index}",
        label_visibility="collapsed"
    )
    st.session_state[content_key] = edited_content

    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 Save", key=f"save_section_{block_index}", use_container_width=True):
            if on_edit:
                # Store original content for replacement in handler
                st.session_state['_content_to_replace'] = st.session_state.get(original_key, content)
                st.session_state['_new_content'] = edited_content
                on_edit(block_index, edited_content)
            st.session_state[edit_key] = False
            if content_key in st.session_state:
                del st.session_state[content_key]
            if original_key in st.session_state:
                del st.session_state[original_key]
            st.rerun()

    with col2:
        if st.button("Cancel", key=f"cancel_section_{block_index}", use_container_width=True):
            st.session_state[edit_key] = False
            if content_key in st.session_state:
                del st.session_state[content_key]
            if original_key in st.session_state:
                del st.session_state[original_key]
            st.rerun()
