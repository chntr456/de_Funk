"""
YAML utility functions for notebook parsing.

Provides helpers for normalizing and parsing YAML content,
particularly for handling copy/paste indentation issues.
"""

import re


def normalize_yaml_indentation(yaml_str: str) -> str:
    """
    Normalize YAML indentation to fix copy/paste issues.

    When YAML is copied from one location to another, it often has
    inconsistent indentation that breaks parsing. This function:
    1. Converts tabs to spaces
    2. Detects top-level YAML keys and aligns them
    3. Preserves relative indentation for nested content
    4. Handles edge cases like first-line-extra-indent

    Args:
        yaml_str: Raw YAML string that may have inconsistent indentation

    Returns:
        Normalized YAML string with consistent indentation

    Example:
        Input (inconsistent indent from copy-paste):
            "  type: great_table\\ntitle: My Table"
        Output (aligned):
            "type: great_table\\ntitle: My Table"
    """
    if not yaml_str or not yaml_str.strip():
        return yaml_str

    # Convert tabs to spaces (4 spaces per tab)
    yaml_str = yaml_str.replace('\t', '    ')

    lines = yaml_str.split('\n')

    # Pattern for top-level YAML keys (word followed by colon at start of content)
    top_level_key_pattern = re.compile(r'^(\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:')

    # First pass: identify top-level keys and their indents
    key_indents = []
    for i, line in enumerate(lines):
        match = top_level_key_pattern.match(line)
        if match:
            indent = len(match.group(1))
            key_indents.append((i, indent))

    # If no keys found, fall back to simple normalization
    if not key_indents:
        return _simple_normalize(yaml_str)

    # Find the minimum indent among top-level keys
    min_key_indent = min(indent for _, indent in key_indents)

    # Calculate adjustment needed for each line based on its top-level key
    # Lines between keys inherit the adjustment from the previous key
    normalized_lines = []
    current_adjustment = 0

    for i, line in enumerate(lines):
        if not line.strip():
            normalized_lines.append('')
            continue

        # Check if this line is a top-level key
        match = top_level_key_pattern.match(line)
        if match:
            current_indent = len(match.group(1))
            # Adjust this key to the minimum indent level
            current_adjustment = current_indent - min_key_indent
            if current_adjustment > 0:
                normalized_lines.append(line[current_adjustment:])
            elif current_adjustment < 0:
                # Line has less indent than minimum - add spaces (shouldn't happen often)
                normalized_lines.append(' ' * (-current_adjustment) + line)
            else:
                normalized_lines.append(line)
        else:
            # Non-key line: apply the current adjustment
            if current_adjustment > 0 and len(line) >= current_adjustment:
                # Check if line actually has the expected indent
                if line[:current_adjustment].strip() == '':
                    normalized_lines.append(line[current_adjustment:])
                else:
                    normalized_lines.append(line.lstrip())
            elif current_adjustment < 0:
                normalized_lines.append(' ' * (-current_adjustment) + line)
            else:
                normalized_lines.append(line)

    result = '\n'.join(normalized_lines)

    # Final pass: remove any remaining base indentation
    return _simple_normalize(result)


def _simple_normalize(yaml_str: str) -> str:
    """
    Simple normalization: remove minimum base indentation from all lines.

    This is the fallback for when we can't detect top-level keys.
    """
    if not yaml_str or not yaml_str.strip():
        return yaml_str

    lines = yaml_str.split('\n')

    # Find minimum indentation (ignoring empty lines and comments)
    min_indent = float('inf')
    for line in lines:
        stripped = line.lstrip()
        if stripped and not stripped.startswith('#'):
            indent = len(line) - len(stripped)
            min_indent = min(min_indent, indent)

    if min_indent == float('inf') or min_indent == 0:
        return yaml_str

    # Remove base indentation
    normalized_lines = []
    for line in lines:
        if line.strip():
            if len(line) >= min_indent:
                normalized_lines.append(line[int(min_indent):])
            else:
                normalized_lines.append(line.lstrip())
        else:
            normalized_lines.append('')

    return '\n'.join(normalized_lines)
