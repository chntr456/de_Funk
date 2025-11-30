"""
Markdown parsing utilities for notebook content.

Handles:
- Header level detection
- Splitting content by headers
- Building nested tree structures from header hierarchy
"""

import re
from typing import Dict, Any, List


def get_header_level(content: str) -> int:
    """
    Get the header level from markdown content.

    Args:
        content: Markdown content string

    Returns:
        Header level (1-6) or 0 if no header
    """
    lines = content.strip().split('\n')
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('#'):
            # Count the number of # symbols
            level = 0
            for char in stripped:
                if char == '#':
                    level += 1
                else:
                    break
            return min(level, 6)
    return 0


def split_markdown_by_headers(content: str) -> List[Dict[str, Any]]:
    """
    Split markdown content into separate blocks at each header.

    For example:
        "# Title\ncontent\n## Sub\nmore"
    Becomes:
        [
            {'type': 'markdown', 'content': '# Title\ncontent'},
            {'type': 'markdown', 'content': '## Sub\nmore'}
        ]
    """
    if not content or not content.strip():
        return []

    # Pattern to match headers at start of line
    header_pattern = re.compile(r'^(#{1,6})\s+', re.MULTILINE)

    blocks = []
    lines = content.split('\n')
    current_block_lines = []

    for line in lines:
        # Check if this line starts with a header
        if header_pattern.match(line):
            # Save previous block if any
            if current_block_lines:
                block_content = '\n'.join(current_block_lines).strip()
                if block_content:
                    blocks.append({
                        'type': 'markdown',
                        'content': block_content
                    })
            # Start new block with this header
            current_block_lines = [line]
        else:
            current_block_lines.append(line)

    # Don't forget the last block
    if current_block_lines:
        block_content = '\n'.join(current_block_lines).strip()
        if block_content:
            blocks.append({
                'type': 'markdown',
                'content': block_content
            })

    return blocks


def build_header_tree(content_blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Build a tree structure from content blocks based on header levels.

    First splits markdown blocks by headers, then builds nested structure:
    - H1 creates top-level sections
    - H2 nests under H1
    - H3 nests under H2
    - etc.

    Args:
        content_blocks: Flat list of content blocks

    Returns:
        List of blocks with 'children' for nested content
    """
    if not content_blocks:
        return []

    # First, split markdown blocks by headers
    split_blocks = []
    for block in content_blocks:
        if block['type'] == 'markdown':
            # Split this markdown block by headers
            sub_blocks = split_markdown_by_headers(block.get('content', ''))
            split_blocks.extend(sub_blocks)
        else:
            # Keep non-markdown blocks as-is
            split_blocks.append(block)

    # Add header level and index info to each block
    blocks_with_levels = []
    for i, block in enumerate(split_blocks):
        block_copy = block.copy()
        block_copy['_index'] = i

        if block['type'] == 'markdown':
            level = get_header_level(block.get('content', ''))
            block_copy['_header_level'] = level
        else:
            block_copy['_header_level'] = 0  # Non-markdown blocks have no header

        blocks_with_levels.append(block_copy)

    # Build tree structure
    root = {'children': [], '_header_level': 0}
    stack = [root]  # Stack of parent nodes

    for block in blocks_with_levels:
        level = block['_header_level']

        if level == 0:
            # Non-header content: add to current parent
            parent = stack[-1]
            if 'children' not in parent:
                parent['children'] = []
            parent['children'].append(block)
        else:
            # Header: find appropriate parent level
            # Pop stack until we find a parent with level < current level
            while len(stack) > 1 and stack[-1].get('_header_level', 0) >= level:
                stack.pop()

            parent = stack[-1]
            if 'children' not in parent:
                parent['children'] = []

            # Add this block as a child
            block['children'] = []
            parent['children'].append(block)

            # Push this block onto stack (it can have children)
            stack.append(block)

    return root.get('children', [])


def extract_header_text(content: str) -> str:
    """
    Extract header text from markdown content.

    Args:
        content: Markdown content string

    Returns:
        Header text without # symbols, or first line if no header
    """
    lines = content.strip().split('\n')
    if lines:
        first_line = lines[0]
        if first_line.startswith('#'):
            return first_line.lstrip('#').strip()
        return first_line[:50] + '...' if len(first_line) > 50 else first_line
    return 'Content'


def gather_section_content(block: Dict[str, Any], include_exhibits: bool = False) -> str:
    """
    Gather all text content from a section including nested children.

    Used for section editing to get the full markdown content.

    Args:
        block: Block with optional children
        include_exhibits: Whether to include exhibit syntax in output

    Returns:
        Combined markdown content string
    """
    parts = []

    # Add this block's content if markdown
    if block.get('type') == 'markdown':
        parts.append(block.get('content', ''))

    elif block.get('type') == 'exhibit' and include_exhibits:
        # Convert exhibit back to $exhibits${...} syntax
        from .utils import exhibit_to_syntax
        exhibit = block.get('exhibit')
        if exhibit:
            parts.append(exhibit_to_syntax(exhibit))

    # Recursively gather children
    for child in block.get('children', []):
        child_content = gather_section_content(child, include_exhibits)
        if child_content:
            parts.append(child_content)

    return '\n\n'.join(parts)


def count_section_exhibits(block: Dict[str, Any]) -> int:
    """
    Count the number of exhibits in a section including nested children.

    Args:
        block: Block with optional children

    Returns:
        Number of exhibits in this section
    """
    count = 0

    if block.get('type') == 'exhibit':
        count += 1

    for child in block.get('children', []):
        count += count_section_exhibits(child)

    return count
