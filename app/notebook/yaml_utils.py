"""
YAML utility functions for notebook parsing.

Provides helpers for normalizing and parsing YAML content,
particularly for handling copy/paste indentation issues.
"""

import yaml


def normalize_yaml_indentation(yaml_str: str) -> str:
    """
    Normalize YAML indentation to fix copy/paste issues.

    When YAML is copied from one location to another, it often has
    inconsistent indentation that breaks parsing. This function tries
    multiple strategies:

    1. First, try to parse and re-dump the YAML (fixes any valid but messy YAML)
    2. If that fails, try simple normalization (remove common base indent)
    3. Preserves relative indentation for nested content

    Args:
        yaml_str: Raw YAML string that may have inconsistent indentation

    Returns:
        Normalized YAML string with consistent indentation

    Example:
        Input (wildly inconsistent indent from copy-paste):
            "  type: great_table\\n      title: My Table\\n  columns:\\n        - id: foo"
        Output (clean):
            "type: great_table\\ntitle: My Table\\ncolumns:\\n  - id: foo"
    """
    if not yaml_str or not yaml_str.strip():
        return yaml_str

    # Convert tabs to spaces (2 spaces per tab - standard YAML indent)
    yaml_str = yaml_str.replace('\t', '  ')

    # Strategy 1: Try to parse and re-dump for perfectly clean output
    try:
        # First do simple normalization to help parsing
        simple_normalized = _simple_normalize(yaml_str)
        data = yaml.safe_load(simple_normalized)
        if data and isinstance(data, dict):
            # Re-dump with consistent formatting
            # Use default_flow_style=False for block style
            # Use sort_keys=False to preserve order
            clean_yaml = yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)
            return clean_yaml.strip()
    except yaml.YAMLError:
        pass  # Fall through to simpler strategies

    # Strategy 2: Simple normalization - just remove common base indent
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
