"""
Utility functions for markdown rendering.

Contains helper functions for:
- Converting exhibits to syntax strings
- Converting collapsible blocks to editable format
- Other markdown-related utilities
"""

from typing import Dict, Any
import yaml


class IndentedDumper(yaml.SafeDumper):
    """Custom YAML dumper that properly indents list items."""
    pass


def _represent_list(dumper, data):
    """Represent lists with proper indentation for nested dicts."""
    return dumper.represent_sequence('tag:yaml.org,2002:seq', data, flow_style=False)


def _represent_dict(dumper, data):
    """Represent dicts with proper indentation."""
    return dumper.represent_mapping('tag:yaml.org,2002:map', data, flow_style=False)


# Register custom representers
IndentedDumper.add_representer(list, _represent_list)
IndentedDumper.add_representer(dict, _represent_dict)


def dump_yaml_indented(data: Dict, indent: int = 2) -> str:
    """
    Dump YAML with proper indentation for nested structures.

    This ensures list items have their properties properly indented:

    columns:
      - id: value
        label: value    # Properly indented under the list item

    Args:
        data: Dictionary to dump
        indent: Indentation level (default 2)

    Returns:
        Properly formatted YAML string
    """
    # Use custom dumper with proper settings
    output = yaml.dump(
        data,
        Dumper=IndentedDumper,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        indent=indent,
        width=120
    )

    # Post-process to fix list item indentation
    # PyYAML produces:
    #   key:
    #   - id: value
    #     label: value
    #
    # We need:
    #   key:
    #     - id: value
    #       label: value
    #
    # This adds indent spaces after each "- " sequence item marker

    lines = output.split('\n')
    result = []
    in_list_context = False
    list_indent = 0

    for i, line in enumerate(lines):
        stripped = line.lstrip()

        # Check if this line starts a list item
        if stripped.startswith('- '):
            # Find current indentation
            current_indent = len(line) - len(stripped)
            # Add extra indent to list marker
            result.append(' ' * indent + line)
            in_list_context = True
            list_indent = current_indent
        elif in_list_context and stripped and not stripped.startswith('-'):
            # This is a continuation of a list item (properties after the first)
            current_indent = len(line) - len(stripped)
            if current_indent > 0:
                # Add extra indent to align with the indented list
                result.append(' ' * indent + line)
            else:
                # Back to root level, exit list context
                in_list_context = False
                result.append(line)
        else:
            if stripped == '' or (stripped and not stripped.startswith(' ') and ':' in stripped):
                # Empty line or new top-level key - might exit list context
                if stripped and ':' in stripped and not stripped.startswith('-'):
                    in_list_context = False
            result.append(line)

    return '\n'.join(result)


def exhibit_to_syntax(exhibit) -> str:
    """
    Convert an Exhibit object to $exhibits${} syntax.

    Preserves all exhibit properties by building a YAML-compatible dictionary.

    Args:
        exhibit: Exhibit object from schema

    Returns:
        String in $exhibits${...} format
    """
    if not exhibit:
        return ''

    # Build dictionary from exhibit properties
    data = {}

    # Required fields
    data['type'] = exhibit.type.value

    # Basic fields
    if exhibit.title:
        data['title'] = exhibit.title
    if exhibit.description:
        data['description'] = exhibit.description
    if exhibit.source:
        data['source'] = exhibit.source

    # Filters - can be dict with operator/value
    if exhibit.filters:
        data['filters'] = exhibit.filters

    # Axis configurations
    if exhibit.x_axis:
        if exhibit.x_axis.dimension:
            data['x'] = exhibit.x_axis.dimension
        elif exhibit.x_axis.measure:
            data['x'] = exhibit.x_axis.measure
        if exhibit.x_axis.label and exhibit.x_axis.label != data.get('x'):
            data['x_label'] = exhibit.x_axis.label

    if exhibit.y_axis:
        if exhibit.y_axis.measure:
            data['y'] = exhibit.y_axis.measure
        elif exhibit.y_axis.measures:
            data['y'] = exhibit.y_axis.measures
        if exhibit.y_axis.label:
            data['y_label'] = exhibit.y_axis.label

    if exhibit.y_axis_left:
        if exhibit.y_axis_left.measure:
            data['y2'] = exhibit.y_axis_left.measure
        if exhibit.y_axis_left.label:
            data['y2_label'] = exhibit.y_axis_left.label

    # Chart styling
    if exhibit.color_by:
        data['color'] = exhibit.color_by
    if exhibit.size_by:
        data['size'] = exhibit.size_by
    if not exhibit.legend:  # Only include if False (True is default)
        data['legend'] = False
    if not exhibit.interactive:  # Only include if False (True is default)
        data['interactive'] = False

    # Metric cards
    if exhibit.metrics:
        metrics_list = []
        for m in exhibit.metrics:
            metric_dict = {'measure': m.measure, 'label': m.label}
            if m.aggregation:
                metric_dict['aggregation'] = m.aggregation.value
            metrics_list.append(metric_dict)
        data['metrics'] = metrics_list

    # Measure selector
    if exhibit.measure_selector:
        ms = exhibit.measure_selector
        ms_dict = {'available_measures': ms.available_measures}
        if ms.default_measures:
            ms_dict['default_measures'] = ms.default_measures
        if ms.label:
            ms_dict['label'] = ms.label
        if not ms.allow_multiple:  # Only if False
            ms_dict['allow_multiple'] = False
        if ms.selector_type != 'checkbox':
            ms_dict['selector_type'] = ms.selector_type
        if ms.help_text:
            ms_dict['help_text'] = ms.help_text
        data['measure_selector'] = ms_dict

    # Dimension selector
    if exhibit.dimension_selector:
        ds = exhibit.dimension_selector
        ds_dict = {'available_dimensions': ds.available_dimensions}
        if ds.default_dimension:
            ds_dict['default_dimension'] = ds.default_dimension
        if ds.label:
            ds_dict['label'] = ds.label
        if ds.selector_type != 'radio':
            ds_dict['selector_type'] = ds.selector_type
        if ds.help_text:
            ds_dict['help_text'] = ds.help_text
        if ds.applies_to != 'color':
            ds_dict['applies_to'] = ds.applies_to
        data['dimension_selector'] = ds_dict

    # Collapsible settings
    if exhibit.collapsible:
        data['collapsible'] = True
        if exhibit.collapsible_title:
            data['collapsible_title'] = exhibit.collapsible_title
        if not exhibit.collapsible_expanded:
            data['collapsible_expanded'] = False
    if not exhibit.nest_in_expander:
        data['nest_in_expander'] = False

    # Weighted aggregate configurations
    if exhibit.weighting:
        w = exhibit.weighting
        weight_dict = {'method': w.method.value if hasattr(w.method, 'value') else w.method}
        if hasattr(w, 'column') and w.column:
            weight_dict['column'] = w.column
        if w.expression:
            weight_dict['expression'] = w.expression
        data['weighting'] = weight_dict
    if exhibit.aggregate_by:
        data['aggregate_by'] = exhibit.aggregate_by
    if exhibit.value_measures:
        data['value_measures'] = exhibit.value_measures
    if exhibit.group_by:
        data['group_by'] = exhibit.group_by
    if exhibit.aggregations:
        data['aggregations'] = exhibit.aggregations

    # Table configurations
    if exhibit.columns:
        data['columns'] = exhibit.columns
    if exhibit.pagination:
        data['pagination'] = True
    if exhibit.page_size != 50:
        data['page_size'] = exhibit.page_size
    if exhibit.download:
        data['download'] = True
    if not exhibit.sortable:  # Only if False (True is default)
        data['sortable'] = False
    if exhibit.searchable:
        data['searchable'] = True

    # Sort configuration
    if exhibit.sort:
        data['sort'] = {'by': exhibit.sort.by, 'order': exhibit.sort.order}

    # Custom component
    if exhibit.component:
        data['component'] = exhibit.component
    if exhibit.params:
        data['params'] = exhibit.params

    # Additional options
    if exhibit.options:
        data['options'] = exhibit.options

    # Forecast chart specific
    if exhibit.actual_column:
        data['actual_column'] = exhibit.actual_column
    if exhibit.predicted_column:
        data['predicted_column'] = exhibit.predicted_column
    if exhibit.confidence_bounds:
        data['confidence_bounds'] = exhibit.confidence_bounds

    # Great Tables specific fields
    if exhibit.theme:
        data['theme'] = exhibit.theme
    if exhibit.spanners:
        data['spanners'] = exhibit.spanners
    if exhibit.rows:
        data['rows'] = exhibit.rows
    if hasattr(exhibit, 'row_striping') and not exhibit.row_striping:
        data['row_striping'] = False
    if exhibit.source_note:
        data['source_note'] = exhibit.source_note
    if exhibit.footnotes:
        data['footnotes'] = exhibit.footnotes
    if exhibit.subtitle:
        data['subtitle'] = exhibit.subtitle
    if exhibit.calculated_columns:
        data['calculated_columns'] = exhibit.calculated_columns
    if exhibit.export_html:
        data['export_html'] = True
    if exhibit.export_png:
        data['export_png'] = True

    # Convert to YAML string with proper indentation
    yaml_content = dump_yaml_indented(data)
    # Indent each line for the $exhibits${} wrapper
    indented = '\n'.join('  ' + line for line in yaml_content.strip().split('\n'))
    return f"$exhibits${{\n{indented}\n}}"


def exhibit_to_yaml(exhibit) -> str:
    """
    Convert exhibit to YAML format for editing.

    Uses _raw_data if available for perfect round-trip serialization,
    otherwise rebuilds from parsed fields.

    Args:
        exhibit: Exhibit object

    Returns:
        YAML string representation
    """
    if not exhibit:
        return ''

    # Use raw data if available for perfect round-trip
    if hasattr(exhibit, '_raw_data') and exhibit._raw_data:
        return dump_yaml_indented(exhibit._raw_data)

    # Otherwise, rebuild from parsed fields
    data = {
        'type': exhibit.type.value,
    }

    if exhibit.title:
        data['title'] = exhibit.title
    if exhibit.description:
        data['description'] = exhibit.description
    if exhibit.source:
        data['source'] = exhibit.source

    # Axis configurations (shorthand)
    if exhibit.x_axis:
        data['x'] = exhibit.x_axis.dimension or exhibit.x_axis.measure
    if exhibit.y_axis:
        data['y'] = exhibit.y_axis.measure or exhibit.y_axis.measures

    if exhibit.color_by:
        data['color'] = exhibit.color_by

    # Great Tables specific fields
    if exhibit.theme:
        data['theme'] = exhibit.theme
    if exhibit.sort:
        if hasattr(exhibit.sort, 'by'):
            data['sort'] = {'by': exhibit.sort.by, 'order': exhibit.sort.order}
        else:
            data['sort'] = exhibit.sort

    # Columns - preserve structure for Great Tables
    if exhibit.columns:
        data['columns'] = exhibit.columns

    # Spanners
    if exhibit.spanners:
        data['spanners'] = exhibit.spanners

    # Rows configuration
    if exhibit.rows:
        data['rows'] = exhibit.rows

    # Row striping (only if False, True is default)
    if hasattr(exhibit, 'row_striping') and not exhibit.row_striping:
        data['row_striping'] = False

    # Source note and footnotes
    if exhibit.source_note:
        data['source_note'] = exhibit.source_note
    if exhibit.footnotes:
        data['footnotes'] = exhibit.footnotes

    # Subtitle
    if exhibit.subtitle:
        data['subtitle'] = exhibit.subtitle

    # Calculated columns
    if exhibit.calculated_columns:
        data['calculated_columns'] = exhibit.calculated_columns

    # Export options
    if exhibit.export_html:
        data['export_html'] = True
    if exhibit.export_png:
        data['export_png'] = True

    # Metrics for metric_cards
    if exhibit.metrics:
        metrics_list = []
        for m in exhibit.metrics:
            metric_dict = {'measure': m.measure}
            if m.label:
                metric_dict['label'] = m.label
            if m.aggregation:
                metric_dict['aggregation'] = m.aggregation.value
            metrics_list.append(metric_dict)
        data['metrics'] = metrics_list

    # Measure selector
    if exhibit.measure_selector:
        ms = exhibit.measure_selector
        ms_dict = {'available_measures': ms.available_measures}
        if ms.default_measures:
            ms_dict['default_measures'] = ms.default_measures
        if ms.label:
            ms_dict['label'] = ms.label
        data['measure_selector'] = ms_dict

    # Dimension selector
    if exhibit.dimension_selector:
        ds = exhibit.dimension_selector
        ds_dict = {'available_dimensions': ds.available_dimensions}
        if ds.default_dimension:
            ds_dict['default_dimension'] = ds.default_dimension
        if ds.label:
            ds_dict['label'] = ds.label
        data['dimension_selector'] = ds_dict

    # Weighted aggregate configurations
    if exhibit.weighting:
        data['weighting'] = exhibit.weighting
    if exhibit.aggregate_by:
        data['aggregate_by'] = exhibit.aggregate_by
    if exhibit.value_measures:
        data['value_measures'] = exhibit.value_measures
    if exhibit.group_by:
        data['group_by'] = exhibit.group_by

    # Forecast chart specific
    if exhibit.actual_column:
        data['actual_column'] = exhibit.actual_column
    if exhibit.predicted_column:
        data['predicted_column'] = exhibit.predicted_column
    if exhibit.confidence_bounds:
        data['confidence_bounds'] = exhibit.confidence_bounds

    # Collapsible settings
    if exhibit.collapsible:
        data['collapsible'] = True
        if exhibit.collapsible_title:
            data['collapsible_title'] = exhibit.collapsible_title

    # Additional options
    if exhibit.options:
        data.update(exhibit.options)

    return dump_yaml_indented(data)


def collapsible_to_editable(block: Dict[str, Any]) -> str:
    """
    Convert a collapsible block to editable markdown format.

    Uses HTML details/summary tags for collapsible sections.

    Args:
        block: Collapsible block with summary and content

    Returns:
        Markdown string with HTML details syntax
    """
    summary = block.get('summary', 'Details')
    content_blocks = block.get('content', [])

    parts = [f'<details>\n<summary>{summary}</summary>\n']

    for inner in content_blocks:
        if inner.get('type') == 'markdown':
            parts.append(inner.get('content', ''))
        elif inner.get('type') == 'exhibit':
            exhibit = inner.get('exhibit')
            if exhibit:
                parts.append(exhibit_to_syntax(exhibit))

    parts.append('\n</details>')

    return '\n\n'.join(parts)


def get_default_block_content(block_type: str) -> str:
    """
    Get default content for a new block of the given type.

    Args:
        block_type: Type of block ('markdown', 'exhibit', 'collapsible')

    Returns:
        Default content string for the block type
    """
    defaults = {
        'markdown': '## New Section\n\nEnter your content here.',
        'exhibit': '''$exhibits${
  type: line_chart
  title: "New Chart"
  source: "model.table"
  x: date
  y: value
}''',
        'collapsible': '''<details>
<summary>Click to expand</summary>

Content goes here.

</details>''',
    }

    return defaults.get(block_type, '# New Block\n\nContent here.')
