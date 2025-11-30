"""
CSS styles for markdown rendering.

Provides custom styling for markdown content including:
- Code blocks with syntax highlighting
- Enhanced tables
- Improved blockquotes
- Better spacing and typography
"""

import streamlit as st


# CSS for markdown content rendering
MARKDOWN_STYLES = """
<style>
/* Code blocks */
.codehilite {
    background-color: #f6f8fa;
    border-radius: 6px;
    padding: 16px;
    overflow: auto;
}

/* Tables */
table {
    border-collapse: collapse;
    width: 100%;
    margin: 1rem 0;
}

th {
    background-color: rgba(28, 131, 225, 0.1);
    font-weight: 600;
    padding: 12px;
    text-align: left;
    border-bottom: 2px solid #1c83e1;
}

td {
    padding: 8px 12px;
    border-bottom: 1px solid #e1e4e8;
}

/* Blockquotes */
blockquote {
    border-left: 4px solid #1c83e1;
    padding-left: 1rem;
    margin-left: 0;
    color: #586069;
}

/* Headers spacing */
h1, h2, h3, h4, h5, h6 {
    margin-top: 1.5rem;
    margin-bottom: 0.5rem;
}

/* Lists */
ul, ol {
    padding-left: 2rem;
    margin: 0.5rem 0;
}

li {
    margin: 0.25rem 0;
}

/* Links */
a {
    color: #1c83e1;
    text-decoration: none;
}

a:hover {
    text-decoration: underline;
}

/* Horizontal rules */
hr {
    border: none;
    border-top: 1px solid #e1e4e8;
    margin: 1.5rem 0;
}

/* Inline code */
code {
    background-color: rgba(175, 184, 193, 0.2);
    padding: 0.2em 0.4em;
    border-radius: 3px;
    font-family: 'Courier New', monospace;
    font-size: 85%;
}

/* Paragraphs */
p {
    margin: 0.75rem 0;
    line-height: 1.6;
}
</style>
"""

# Block type icons for rendering
BLOCK_ICONS = {
    'markdown': '📝',
    'exhibit': '📊',
    'collapsible': '📁',
    'header': '📑',
    'error': '⚠️',
    'default': '📄',
}

# Badge colors for block types
BLOCK_BADGE_COLORS = {
    'markdown': '#28a745',
    'exhibit': '#007bff',
    'collapsible': '#6c757d',
    'error': '#dc3545',
    'default': '#17a2b8',
}


def apply_markdown_styles():
    """
    Apply custom CSS styles for markdown rendering.

    Enhances the default Streamlit markdown styling with:
    - Improved code blocks
    - Enhanced tables
    - Better spacing
    """
    st.markdown(MARKDOWN_STYLES, unsafe_allow_html=True)


def get_block_icon(block_type: str) -> str:
    """Get the icon for a block type."""
    return BLOCK_ICONS.get(block_type, BLOCK_ICONS['default'])


def get_block_badge_color(block_type: str) -> str:
    """Get the badge color for a block type."""
    return BLOCK_BADGE_COLORS.get(block_type, BLOCK_BADGE_COLORS['default'])
