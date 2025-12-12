"""
YAML utility functions for notebook parsing.

Provides helpers for normalizing and parsing YAML content,
particularly for handling copy/paste indentation issues.
"""


def normalize_yaml_indentation(yaml_str: str) -> str:
    """
    Normalize YAML indentation to fix copy/paste issues.

    When YAML is copied from one location to another, it often has
    inconsistent indentation that breaks parsing. This function uses
    simple normalization - removing the common base indentation from all lines.

    This preserves:
    - Relative indentation for nested content
    - Flow-style lists like [1, 2, 3] (yaml.dump would convert these)
    - Original YAML formatting

    Args:
        yaml_str: Raw YAML string that may have inconsistent indentation

    Returns:
        Normalized YAML string with consistent indentation

    Example:
        Input (with base indentation from copy-paste):
            "  type: great_table\\n  title: My Table\\n  columns:\\n    - id: foo"
        Output (base indent removed):
            "type: great_table\\ntitle: My Table\\ncolumns:\\n  - id: foo"
    """
    if not yaml_str or not yaml_str.strip():
        return yaml_str

    # Convert tabs to spaces (2 spaces per tab - standard YAML indent)
    yaml_str = yaml_str.replace('\t', '  ')

    # Use simple normalization - just remove common base indent
    # This preserves flow-style lists like [1, 2, 3] that yaml.dump would break
    return _simple_normalize(yaml_str)


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
