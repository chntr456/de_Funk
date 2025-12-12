"""
YAML utility functions for notebook parsing.

Provides helpers for normalizing and parsing YAML content,
particularly for handling copy/paste indentation issues.
"""

import yaml
import re


def normalize_yaml_indentation(yaml_str: str) -> str:
    """
    Normalize YAML indentation to fix copy/paste issues.

    When YAML is copied from one location to another, it often has
    inconsistent indentation that breaks parsing. This function tries
    multiple strategies to fix the indentation.

    Strategies (in order):
    1. Simple normalization (remove base indent) - if that parses, use it
    2. Smart key realignment - detect misaligned sibling keys and fix them
    3. Return original if nothing works

    Args:
        yaml_str: Raw YAML string that may have inconsistent indentation

    Returns:
        Normalized YAML string with consistent indentation
    """
    if not yaml_str or not yaml_str.strip():
        return yaml_str

    # Convert tabs to spaces (2 spaces per tab - standard YAML indent)
    yaml_str = yaml_str.replace('\t', '  ')

    # Strategy 1: Simple normalization - remove base indent
    simple_result = _simple_normalize(yaml_str)
    if _is_valid_yaml(simple_result):
        return simple_result

    # Strategy 2: Smart key realignment
    smart_result = _smart_realign_keys(yaml_str)
    if _is_valid_yaml(smart_result):
        return smart_result

    # Strategy 3: Return simple normalization even if invalid
    # (let the parser show the error)
    return simple_result


def _is_valid_yaml(yaml_str: str) -> bool:
    """Check if YAML string is valid."""
    try:
        yaml.safe_load(yaml_str)
        return True
    except yaml.YAMLError:
        return False


def _simple_normalize(yaml_str: str) -> str:
    """
    Simple normalization: remove minimum base indentation from all lines.
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


def _smart_realign_keys(yaml_str: str) -> str:
    """
    Smart key realignment: detect and fix misaligned sibling keys.

    This handles the common case where copy-paste creates content like:
        type: great_table
            title: My Title
            source: my.source

    Where title/source should be siblings of type, not children.
    """
    lines = yaml_str.split('\n')
    if not lines:
        return yaml_str

    # First, remove base indent
    base_normalized = _simple_normalize(yaml_str)
    lines = base_normalized.split('\n')

    # Pattern for top-level keys (key: value or key: followed by newline)
    key_pattern = re.compile(r'^(\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:')

    # Find the first key's indentation - this is our target for top-level
    first_key_indent = None
    for line in lines:
        match = key_pattern.match(line)
        if match:
            first_key_indent = len(match.group(1))
            break

    if first_key_indent is None:
        return base_normalized

    # Known top-level exhibit keys that should all be at the same level
    top_level_keys = {
        'type', 'source', 'title', 'description', 'height', 'options',
        'x', 'y', 'x_axis', 'y_axis', 'color', 'size', 'legend', 'interactive',
        'metrics', 'measure_selector', 'dimension_selector',
        'columns', 'pagination', 'page_size', 'download', 'sortable', 'searchable',
        'sort', 'theme', 'spanners', 'rows', 'row_striping', 'source_note',
        'footnotes', 'subtitle', 'calculated_columns', 'scroll', 'max_height',
        'grid_cell', 'filters', 'weighting', 'aggregate_by', 'group_by',
        'collapsible', 'collapsible_title', 'nest_in_expander',
        'actual_column', 'predicted_column', 'confidence_bounds',
        'export_html', 'export_png', 'layout', 'component', 'params'
    }

    # Track context: are we inside a nested structure?
    result_lines = []
    current_top_key = None  # Track which top-level key we're under
    nested_base_indent = None  # Indent of nested content under current key

    for line in lines:
        stripped = line.strip()

        # Empty lines pass through
        if not stripped:
            result_lines.append(line)
            continue

        match = key_pattern.match(line)
        if match:
            indent = len(match.group(1))
            key = match.group(2)

            # Is this a known top-level key?
            if key in top_level_keys:
                # Reset to first key's indent level
                new_line = ' ' * first_key_indent + line.lstrip()
                result_lines.append(new_line)
                current_top_key = key
                nested_base_indent = None  # Reset nested tracking
            else:
                # Unknown key - keep relative to current context
                result_lines.append(line)
        else:
            # Not a key line (could be list item, continuation, etc.)
            # Keep as-is for now
            result_lines.append(line)

    return '\n'.join(result_lines)
