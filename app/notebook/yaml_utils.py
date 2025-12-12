"""
YAML utility functions for notebook parsing.

Provides helpers for normalizing and parsing YAML content,
particularly for handling copy/paste indentation issues.
"""


def normalize_yaml_indentation(yaml_str: str) -> str:
    """
    Normalize YAML indentation to fix copy/paste issues.

    When YAML is copied from one location to another, it often has
    extra leading whitespace that breaks parsing. This function:
    1. Detects the minimum indentation across all non-empty lines
    2. Removes that base indentation while preserving relative indentation
    3. Handles mixed tabs/spaces by converting tabs to spaces

    Args:
        yaml_str: Raw YAML string that may have inconsistent indentation

    Returns:
        Normalized YAML string with consistent indentation

    Example:
        Input (with 4-space base indent):
            "    type: great_table\\n    title: My Table\\n      columns:\\n        - id: col1"
        Output (base indent removed):
            "type: great_table\\ntitle: My Table\\n  columns:\\n    - id: col1"
    """
    if not yaml_str or not yaml_str.strip():
        return yaml_str

    # Convert tabs to spaces (4 spaces per tab)
    yaml_str = yaml_str.replace('\t', '    ')

    lines = yaml_str.split('\n')

    # Find minimum indentation (ignoring empty lines and comment-only lines)
    min_indent = float('inf')
    for line in lines:
        stripped = line.lstrip()
        if stripped and not stripped.startswith('#'):
            indent = len(line) - len(stripped)
            min_indent = min(min_indent, indent)

    # If no valid lines found, return as-is
    if min_indent == float('inf'):
        return yaml_str

    # Remove base indentation from all lines
    normalized_lines = []
    for line in lines:
        if line.strip():  # Non-empty line
            # Remove the base indentation
            if len(line) >= min_indent:
                normalized_lines.append(line[int(min_indent):])
            else:
                normalized_lines.append(line.lstrip())
        else:
            normalized_lines.append('')  # Preserve empty lines

    return '\n'.join(normalized_lines)
