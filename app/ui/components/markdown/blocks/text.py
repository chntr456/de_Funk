"""
Text and markdown block renderers.

Handles rendering of markdown content with proper formatting,
code highlighting, and toggle container wrapping.
"""

import streamlit as st
import markdown
from typing import Any

from ..toggle_container import ToggleContainer


def render_markdown_content(content: str):
    """
    Render markdown content directly (without additional toggle wrapper).

    Args:
        content: Markdown content string
    """
    md = markdown.Markdown(
        extensions=[
            'extra',
            'codehilite',
            'nl2br',
            'sane_lists',
            'toc',
        ]
    )
    html = md.convert(content)
    st.markdown(html, unsafe_allow_html=True)


def render_markdown_block(content: str, in_collapsible: bool = False, block_index: Any = 0):
    """
    Render a markdown content block.

    Text paragraphs are wrapped in a ToggleContainer (not expander) to enable
    a clean view of just exhibits and headers (unless already inside a
    collapsible section).

    Uses ToggleContainer instead of st.expander to avoid nesting issues.

    Supports:
    - Standard markdown (headers, bold, italic, lists, etc.)
    - HTML tags (for collapsible sections)
    - Code blocks
    - Tables
    - Links and images

    Args:
        content: Markdown content string
        in_collapsible: True if already rendering inside a collapsible section
        block_index: Index of this block for unique keys
    """
    # Check if this content is substantial text (more than just a header)
    lines = content.strip().split('\n')
    non_empty_lines = [l for l in lines if l.strip()]

    # Detect if this is a header-only block (just 1-2 lines starting with #)
    is_header_only = (
        len(non_empty_lines) <= 2 and
        any(line.strip().startswith('#') for line in non_empty_lines)
    )

    # Configure markdown extensions
    md = markdown.Markdown(
        extensions=[
            'extra',          # Tables, fenced code, etc.
            'codehilite',     # Syntax highlighting
            'nl2br',          # Newline to <br>
            'sane_lists',     # Better list handling
            'toc',            # Table of contents
        ]
    )

    # Convert markdown to HTML
    html = md.convert(content)

    # If it's just a header, render directly
    if is_header_only:
        st.markdown(html, unsafe_allow_html=True)
    elif in_collapsible:
        # Already inside a collapsible section - render directly
        st.markdown(html, unsafe_allow_html=True)
    else:
        # Wrap text paragraphs in ToggleContainer for clean view
        with ToggleContainer(
            "Details",
            expanded=False,
            container_id=f"md_details_{block_index}",
            icon_open="📄",
            icon_closed="📄",
            style="minimal"
        ) as tc:
            if tc.is_open:
                st.markdown(html, unsafe_allow_html=True)
