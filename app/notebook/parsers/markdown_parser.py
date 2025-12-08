"""
Markdown notebook parser.

Parses markdown-based notebooks with YAML front matter, filters section,
and embedded exhibits using the $exhibits${...} syntax.
"""

import logging
import re
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

from ..schema import (
    NotebookConfig,
    NotebookMetadata,
    GraphConfig,
    ModelReference,
    Variable,
    VariableType,
    Exhibit,
    ExhibitType,
    AxisConfig,
    MetricConfig,
    Section,
    DateRangeDefault,
    AggregationType,
    MeasureSelectorConfig,
    DimensionSelectorConfig,
)
from ..filters.dynamic import (
    FilterConfig,
    FilterType,
    FilterOperator,
    FilterSource,
    FilterCollection,
)
from ..markdown_parser_filter_helpers import parse_filter


@dataclass
class BlockPosition:
    """Tracks the source position of a content block in the original markdown."""
    start: int  # Start character offset in original content
    end: int    # End character offset in original content
    block_type: str  # Type of block (markdown, exhibit, collapsible)


@dataclass
class MarkdownNotebook:
    """Parsed markdown notebook structure."""
    front_matter: Dict[str, Any]
    filters: Dict[str, Variable]
    exhibits: List[Tuple[str, Exhibit]]  # List of (markdown_content, exhibit) pairs
    content_blocks: List[Dict[str, Any]]  # List of {type: 'markdown'|'exhibit', content: ...}
    block_positions: Optional[List[BlockPosition]] = None  # Source positions for editing


class MarkdownNotebookParser:
    """Parser for markdown-based notebooks."""

    # Regex patterns
    FRONT_MATTER_PATTERN = re.compile(r'^---\s*\n(.*?)\n---\s*\n', re.MULTILINE | re.DOTALL)
    FILTER_PATTERN = re.compile(r'\$filters?\$\{\s*\n(.*?)\n\}', re.MULTILINE | re.DOTALL)
    EXHIBIT_PATTERN = re.compile(r'\$exhibits?\$\{\s*\n(.*?)\n\}', re.MULTILINE | re.DOTALL)
    DETAILS_PATTERN = re.compile(r'<details>\s*<summary>(.*?)</summary>\s*(.*?)</details>', re.MULTILINE | re.DOTALL)

    def __init__(self, repo_root: Optional[Path] = None):
        """
        Initialize parser.

        Args:
            repo_root: Repository root path for resolving relative paths
        """
        if repo_root is None:
            from utils.repo import get_repo_root
            repo_root = get_repo_root()
        self.repo_root = repo_root

    def parse_file(self, notebook_path: str) -> NotebookConfig:
        """
        Parse a markdown notebook file.

        Args:
            notebook_path: Path to markdown notebook file

        Returns:
            NotebookConfig object
        """
        path = Path(notebook_path)
        if not path.is_absolute():
            path = self.repo_root / path

        with open(path, 'r') as f:
            content = f.read()

        return self.parse_markdown(content)

    def parse_markdown(self, content: str, track_positions: bool = True) -> NotebookConfig:
        """
        Parse markdown content into NotebookConfig.

        Args:
            content: Markdown content string
            track_positions: Whether to track block positions for editing

        Returns:
            NotebookConfig object
        """
        # Store original content for position tracking and editing
        self._original_content = content

        # Extract front matter
        front_matter = self._extract_front_matter(content)
        if not front_matter:
            raise ValueError("Markdown notebook must have YAML front matter (---\\n...\\n---)")

        # Find where front matter ends
        front_matter_match = self.FRONT_MATTER_PATTERN.match(content)
        self._content_start_offset = front_matter_match.end() if front_matter_match else 0

        # Remove front matter from content
        content_without_front_matter = self.FRONT_MATTER_PATTERN.sub('', content, count=1)

        # Extract filters (new $filter${} syntax)
        filter_collection = self._extract_dynamic_filters(content_without_front_matter)

        # Remove filter blocks from content (they don't render in notebook view)
        content_for_parsing = self.FILTER_PATTERN.sub('', content_without_front_matter)

        # Extract exhibits and build content structure (with positions if requested)
        exhibits, content_blocks = self._extract_exhibits(content_for_parsing, track_positions=track_positions)

        # Build NotebookConfig
        return self._build_config(front_matter, filter_collection, exhibits, content_blocks)

    def _extract_front_matter(self, content: str) -> Optional[Dict[str, Any]]:
        """Extract and parse YAML front matter."""
        match = self.FRONT_MATTER_PATTERN.match(content)
        if not match:
            return None

        yaml_content = match.group(1)
        return yaml.safe_load(yaml_content)

    def _extract_dynamic_filters(self, content: str) -> FilterCollection:
        """
        Extract filters using $filter${...} syntax.

        Returns:
            FilterCollection with all parsed filters
        """
        filter_collection = FilterCollection()

        # Find all filter blocks
        for match in self.FILTER_PATTERN.finditer(content):
            filter_yaml = match.group(1)

            try:
                filter_config = parse_filter(filter_yaml)
                filter_collection.add_filter(filter_config)
            except Exception as e:
                # Log error but continue parsing
                print(f"Error parsing filter: {str(e)}")
                continue

        return filter_collection

    def _old_parse_filter_default(self, default_str: str, var_type: VariableType) -> Any:
        """Parse default value based on variable type."""
        if var_type == VariableType.DATE_RANGE:
            # Format: "2024-01-01 to 2024-01-05"
            parts = default_str.split(' to ')
            if len(parts) == 2:
                return DateRangeDefault(start=parts[0].strip(), end=parts[1].strip())
            return DateRangeDefault(start=default_str, end=default_str)

        elif var_type == VariableType.MULTI_SELECT:
            # Format: "AAPL, GOOGL, MSFT"
            return [v.strip() for v in default_str.split(',')]

        elif var_type == VariableType.NUMBER:
            try:
                return float(default_str) if '.' in default_str else int(default_str)
            except ValueError:
                return 0

        elif var_type == VariableType.BOOLEAN:
            return default_str.lower() in ('true', 'yes', '1')

        else:
            return default_str

    def _old_parse_filter_options(self, default_str: str, var_type: VariableType) -> Optional[List[Any]]:
        """Parse options for multi_select filters."""
        if var_type == VariableType.MULTI_SELECT:
            return [v.strip() for v in default_str.split(',')]
        return None

    def _extract_exhibits(self, content: str, track_positions: bool = True) -> Tuple[List[Exhibit], List[Dict[str, Any]]]:
        """
        Extract exhibits from markdown content and handle collapsible sections.

        Args:
            content: Markdown content to parse
            track_positions: Whether to track source positions for editing

        Returns:
            Tuple of (exhibits list, content_blocks list)
        """
        # Initialize position tracking
        self._block_positions = [] if track_positions else None
        # First, process collapsible sections (details tags)
        # Replace them with placeholders and extract their content
        collapsible_sections = {}
        section_counter = 0

        def replace_details(match):
            nonlocal section_counter
            summary = match.group(1).strip()
            inner_content = match.group(2).strip()
            placeholder = f"__COLLAPSIBLE_{section_counter}__"
            collapsible_sections[placeholder] = {
                'summary': summary,
                'content': inner_content
            }
            section_counter += 1
            return placeholder

        # Replace all <details> tags with placeholders
        processed_content = self.DETAILS_PATTERN.sub(replace_details, content)

        # Now extract exhibits and build content blocks
        exhibits = []
        content_blocks = []
        exhibit_counter = 0

        # Process the content with placeholders
        last_pos = 0
        for match in self.EXHIBIT_PATTERN.finditer(processed_content):
            # Add markdown content before exhibit
            markdown_content = processed_content[last_pos:match.start()].strip()
            if markdown_content:
                # Check if this markdown contains collapsible section placeholders
                exhibit_counter = self._add_content_with_collapsibles(
                    markdown_content,
                    collapsible_sections,
                    content_blocks,
                    exhibits,
                    exhibit_counter
                )

            # Parse exhibit
            exhibit_yaml = match.group(1)
            exhibit_id = f"exhibit_{exhibit_counter}"
            exhibit_counter += 1

            try:
                exhibit = self._parse_exhibit(exhibit_yaml, exhibit_id)
                exhibits.append(exhibit)

                # Add exhibit reference to content blocks
                content_blocks.append({
                    'type': 'exhibit',
                    'id': exhibit_id,
                    'exhibit': exhibit
                })
            except Exception as e:
                # Add error block
                content_blocks.append({
                    'type': 'error',
                    'message': f"Error parsing exhibit: {str(e)}",
                    'content': exhibit_yaml
                })

            last_pos = match.end()

        # Add remaining markdown content
        remaining_content = processed_content[last_pos:].strip()
        if remaining_content:
            exhibit_counter = self._add_content_with_collapsibles(
                remaining_content,
                collapsible_sections,
                content_blocks,
                exhibits,
                exhibit_counter
            )

        return exhibits, content_blocks

    def _add_content_with_collapsibles(
        self,
        content: str,
        collapsible_sections: Dict[str, Dict[str, str]],
        content_blocks: List[Dict[str, Any]],
        exhibits: List[Exhibit],
        exhibit_counter: int
    ) -> int:
        """
        Add content blocks, processing any collapsible section placeholders.
        """
        # Split content by collapsible placeholders
        parts = []
        current_pos = 0

        for placeholder in collapsible_sections.keys():
            idx = content.find(placeholder)
            if idx != -1:
                # Add content before placeholder
                if idx > current_pos:
                    before = content[current_pos:idx].strip()
                    if before:
                        parts.append(('markdown', before))

                # Add collapsible section
                section_data = collapsible_sections[placeholder]
                parts.append(('collapsible', section_data))
                current_pos = idx + len(placeholder)

        # Add remaining content
        if current_pos < len(content):
            remaining = content[current_pos:].strip()
            if remaining:
                parts.append(('markdown', remaining))

        # If no collapsible sections found, just add as markdown
        if not parts and content:
            parts.append(('markdown', content))

        # Add parts to content blocks
        for part_type, part_data in parts:
            if part_type == 'markdown':
                content_blocks.append({
                    'type': 'markdown',
                    'content': part_data
                })
            elif part_type == 'collapsible':
                # Parse the inner content for exhibits
                inner_content = part_data['content']
                inner_exhibits = []
                inner_blocks = []
                inner_counter = len(exhibits)  # Start from current count

                # Extract exhibits from inner content
                last_pos = 0
                for match in self.EXHIBIT_PATTERN.finditer(inner_content):
                    # Add markdown before exhibit
                    md_before = inner_content[last_pos:match.start()].strip()
                    if md_before:
                        inner_blocks.append({
                            'type': 'markdown',
                            'content': md_before
                        })

                    # Parse exhibit
                    exhibit_yaml = match.group(1)
                    exhibit_id = f"exhibit_{inner_counter}"
                    inner_counter += 1

                    try:
                        exhibit = self._parse_exhibit(exhibit_yaml, exhibit_id)
                        exhibits.append(exhibit)
                        inner_exhibits.append(exhibit)

                        inner_blocks.append({
                            'type': 'exhibit',
                            'id': exhibit_id,
                            'exhibit': exhibit
                        })
                    except Exception as e:
                        inner_blocks.append({
                            'type': 'error',
                            'message': f"Error parsing exhibit: {str(e)}",
                            'content': exhibit_yaml
                        })

                    last_pos = match.end()

                # Add remaining content
                remaining = inner_content[last_pos:].strip()
                if remaining:
                    inner_blocks.append({
                        'type': 'markdown',
                        'content': remaining
                    })

                # Add collapsible block with inner content
                content_blocks.append({
                    'type': 'collapsible',
                    'summary': part_data['summary'],
                    'content': inner_blocks
                })

        return len(exhibits)  # Return updated counter

    def _validate_exhibit_params(self, data: Dict[str, Any], exhibit_id: str) -> None:
        """
        Validate exhibit parameters and raise clear errors for invalid configs.

        Valid parameters:
        - Common: type, source, title, height, options, description
        - Charts: x, y, color, size (shorthand) OR x_axis, y_axis (full dict format)
        - Selectors: measure_selector, dimension_selector (for dynamic selection)
        - metric_cards: metrics
        - table: columns, pagination, etc.
        """
        exhibit_type = data.get('type')
        if not exhibit_type:
            raise ValueError(f"Exhibit '{exhibit_id}': Missing required 'type' field")

        # Define valid parameters for clean exhibit definitions
        valid_common = {'type', 'source', 'title', 'height', 'options', 'description'}
        valid_chart_shorthand = {'x', 'y', 'color', 'size', 'legend', 'interactive'}
        valid_chart_full = {'x_axis', 'y_axis', 'y_axis_left', 'y_axis_right', 'color_by', 'size_by'}
        valid_metric = {'metrics'}
        valid_table = {'columns', 'pagination', 'page_size', 'download', 'sortable', 'searchable'}
        valid_selectors = {'measure_selector', 'dimension_selector'}
        valid_advanced = {
            'collapsible', 'collapsible_title', 'collapsible_expanded', 'nest_in_expander',
            'weighting', 'aggregate_by', 'value_measures', 'group_by', 'aggregations',
            'sort', 'layout', 'component', 'params', 'filters',
            'x_label', 'y_label', 'y2', 'y2_label',
            'actual_column', 'predicted_column', 'confidence_bounds'
        }

        all_valid = (valid_common | valid_chart_shorthand | valid_chart_full |
                     valid_metric | valid_table | valid_selectors | valid_advanced)

        # Internal AxisConfig params that should NOT be at root level
        # These belong inside x_axis/y_axis dicts, not at root
        internal_axis_params = {'dimension', 'measure', 'measures', 'label', 'scale'}

        # Check for internal params being used at root (common mistake after bad save)
        used_internal = set(data.keys()) & internal_axis_params
        if used_internal:
            raise ValueError(
                f"Exhibit '{exhibit_id}': Invalid root-level parameters: {used_internal}\n"
                f"These belong inside axis configs. Use one of these formats:\n\n"
                f"SHORTHAND (recommended):\n"
                f"  x: trade_date\n"
                f"  y: close          # single measure\n"
                f"  y: [close, open]  # multiple measures\n"
                f"  color: ticker\n\n"
                f"FULL FORMAT (for advanced options):\n"
                f"  y_axis:\n"
                f"    measures: [close, open, high]\n"
                f"    label: Price\n"
                f"    scale: log\n\n"
                f"DYNAMIC SELECTORS:\n"
                f"  measure_selector:\n"
                f"    available_measures: [close, open, high, low, volume]\n"
                f"    default_measures: [close]\n"
                f"  dimension_selector:\n"
                f"    available_dimensions: [ticker, sector]\n"
                f"    default_dimension: ticker"
            )

        # Check for unknown params
        unknown = set(data.keys()) - all_valid
        if unknown:
            logger.warning(f"Exhibit '{exhibit_id}': Unknown parameters ignored: {unknown}")

        # Validate required fields by type
        chart_types = {'line_chart', 'bar_chart', 'scatter_chart', 'area_chart'}
        if exhibit_type in chart_types:
            has_y = 'y' in data or 'y_axis' in data
            has_selector = 'measure_selector' in data
            if not has_y and not has_selector:
                raise ValueError(
                    f"Exhibit '{exhibit_id}' (type: {exhibit_type}): Missing measure specification.\n"
                    f"Charts require one of:\n"
                    f"  - y: column_name           # static measure\n"
                    f"  - y: [col1, col2]          # multiple measures\n"
                    f"  - y_axis: {{measures: [...]}}  # full format\n"
                    f"  - measure_selector: {{...}}    # dynamic selection"
                )

    def _parse_exhibit(self, exhibit_yaml: str, exhibit_id: str) -> Exhibit:
        """
        Parse exhibit YAML into Exhibit object.

        Supports streamlined syntax:
        - x, y instead of x_axis, y_axis
        - Simplified metric definitions
        """
        data = yaml.safe_load(exhibit_yaml)

        # Validate exhibit parameters
        self._validate_exhibit_params(data, exhibit_id)

        exhibit_type = ExhibitType(data['type'])

        # Parse streamlined axis parameters
        x_axis = None
        if 'x' in data:
            # Shorthand syntax: x: dimension_name
            x_axis = AxisConfig(
                dimension=data['x'],
                label=data.get('x_label', data['x'])
            )
        elif 'x_axis' in data and isinstance(data['x_axis'], dict):
            # Full syntax: x_axis: {dimension: ..., label: ...}
            x_axis = AxisConfig(
                dimension=data['x_axis'].get('dimension'),
                measure=data['x_axis'].get('measure'),
                measures=data['x_axis'].get('measures'),
                label=data['x_axis'].get('label'),
                scale=data['x_axis'].get('scale')
            )

        y_axis = None
        if 'y' in data:
            # Shorthand syntax: y: measure_name (or list of measures)
            # For label, only use data['y'] if it's a string (not a list)
            default_label = data['y'] if isinstance(data['y'], str) else None
            y_axis = AxisConfig(
                measure=data['y'],
                label=data.get('y_label', default_label)
            )
        elif 'y_axis' in data and isinstance(data['y_axis'], dict):
            # Full syntax: y_axis: {measures: [...], label: ...}
            y_axis = AxisConfig(
                dimension=data['y_axis'].get('dimension'),
                measure=data['y_axis'].get('measure'),
                measures=data['y_axis'].get('measures'),
                label=data['y_axis'].get('label'),
                scale=data['y_axis'].get('scale')
            )

        y_axis_left = None
        if 'y2' in data:
            y_axis_left = y_axis
            # For label, only use data['y2'] if it's a string (not a list)
            default_y2_label = data['y2'] if isinstance(data['y2'], str) else None
            y_axis = AxisConfig(
                measure=data['y2'],
                label=data.get('y2_label', default_y2_label)
            )

        # Parse metrics for metric_cards
        metrics = None
        if 'metrics' in data:
            metrics = []
            for m in data['metrics']:
                if isinstance(m, dict):
                    agg = None
                    if 'aggregation' in m:
                        agg = AggregationType(m['aggregation'])
                    metrics.append(MetricConfig(
                        measure=m['measure'],
                        label=m.get('label', m['measure']),
                        aggregation=agg
                    ))

        # Parse sort configuration
        sort = None
        if 'sort' in data and isinstance(data['sort'], dict):
            from ..schema import SortConfig
            sort = SortConfig(
                by=data['sort']['by'],
                order=data['sort'].get('order', 'asc')
            )

        # Parse measure selector configuration
        measure_selector = None
        if 'measure_selector' in data and isinstance(data['measure_selector'], dict):
            ms_data = data['measure_selector']
            measure_selector = MeasureSelectorConfig(
                available_measures=ms_data['available_measures'],
                default_measures=ms_data.get('default_measures'),
                label=ms_data.get('label'),
                allow_multiple=ms_data.get('allow_multiple', True),
                selector_type=ms_data.get('selector_type', 'checkbox'),
                help_text=ms_data.get('help_text')
            )

        # Parse dimension selector configuration
        dimension_selector = None
        if 'dimension_selector' in data and isinstance(data['dimension_selector'], dict):
            ds_data = data['dimension_selector']
            dimension_selector = DimensionSelectorConfig(
                available_dimensions=ds_data['available_dimensions'],
                default_dimension=ds_data.get('default_dimension'),
                label=ds_data.get('label'),
                selector_type=ds_data.get('selector_type', 'radio'),
                help_text=ds_data.get('help_text'),
                applies_to=ds_data.get('applies_to', 'color')
            )

        # Collect any unknown/extra properties into options dict
        # This preserves custom properties like 'limit' that aren't in the schema
        known_keys = {
            'type', 'title', 'description', 'source', 'filters',
            'x', 'y', 'x_axis', 'y_axis', 'y2', 'x_label', 'y_label', 'y2_label',
            'color', 'size', 'legend', 'interactive',
            'metrics', 'measure_selector', 'dimension_selector',
            'collapsible', 'collapsible_title', 'collapsible_expanded', 'nest_in_expander',
            'weighting', 'aggregate_by', 'value_measures', 'group_by', 'aggregations',
            'columns', 'pagination', 'page_size', 'download', 'sortable', 'searchable',
            'sort', 'layout', 'component', 'params', 'options',
            'actual_column', 'predicted_column', 'confidence_bounds'
        }
        extra_options = {k: v for k, v in data.items() if k not in known_keys}
        options = data.get('options', {}) or {}
        if extra_options:
            options.update(extra_options)

        return Exhibit(
            id=exhibit_id,
            type=exhibit_type,
            title=data.get('title', ''),
            description=data.get('description'),
            source=data.get('source'),
            filters=data.get('filters'),
            x_axis=x_axis,
            y_axis=y_axis,
            y_axis_left=y_axis_left,
            y_axis_right=None,
            color_by=data.get('color'),
            size_by=data.get('size'),
            legend=data.get('legend', True),
            interactive=data.get('interactive', True),
            metrics=metrics,
            measure_selector=measure_selector,
            dimension_selector=dimension_selector,
            # Collapsible configuration
            collapsible=data.get('collapsible', False),
            collapsible_title=data.get('collapsible_title'),
            collapsible_expanded=data.get('collapsible_expanded', True),
            nest_in_expander=data.get('nest_in_expander', True),
            # Weighted aggregate fields
            weighting=data.get('weighting'),
            aggregate_by=data.get('aggregate_by'),
            value_measures=data.get('value_measures'),
            group_by=data.get('group_by'),
            aggregations=data.get('aggregations'),
            # Table fields
            columns=data.get('columns'),
            pagination=data.get('pagination', False),
            page_size=data.get('page_size', 50),
            download=data.get('download', False),
            sortable=data.get('sortable', True),
            searchable=data.get('searchable', False),
            sort=sort,
            layout=None,
            component=data.get('component'),
            params=data.get('params'),
            options=options if options else None,
            # Forecast chart specific
            actual_column=data.get('actual_column'),
            predicted_column=data.get('predicted_column'),
            confidence_bounds=data.get('confidence_bounds'),
            # Store raw data for 1:1 round-trip serialization
            _raw_data=data,
        )

    def _build_config(
        self,
        front_matter: Dict[str, Any],
        filter_collection: FilterCollection,
        exhibits: List[Exhibit],
        content_blocks: List[Dict[str, Any]]
    ) -> NotebookConfig:
        """Build NotebookConfig from parsed components."""

        # Build metadata
        metadata = NotebookMetadata(
            id=front_matter['id'],
            title=front_matter['title'],
            description=front_matter.get('description'),
            author=front_matter.get('author'),
            created=front_matter.get('created'),
            updated=front_matter.get('updated'),
            tags=front_matter.get('tags'),
        )

        # Build graph config (for model initialization)
        models = front_matter.get('models', [])
        graph = GraphConfig(
            models=[
                ModelReference(
                    name=model,
                    config=f"configs/models/{model}.yaml",
                    nodes=[]
                )
                for model in models
            ],
            bridges=None
        )

        # Build simple layout (one section per exhibit)
        layout = [
            Section(
                title=None,
                exhibits=[exhibit.id],
                columns=1
            )
            for exhibit in exhibits
        ]

        # Convert filter collection to old variables format for backward compat
        # (will be phased out)
        variables = {}

        config = NotebookConfig(
            version="2.0",  # Markdown format version
            notebook=metadata,
            graph=graph,
            variables=variables,
            exhibits=exhibits,
            layout=layout,
            dimensions=None,
            measures=None,
            exports=None,
            _content_blocks=content_blocks,
            _is_markdown=True,
            _filter_collection=filter_collection
        )

        # Store block positions in config for editing
        if hasattr(self, '_block_positions') and self._block_positions:
            config._block_positions = self._block_positions

        return config

    def update_block_content(
        self,
        notebook_path: str,
        block_index: int,
        new_content: str
    ) -> str:
        """
        Update a specific content block in a notebook file.

        Reconstructs the markdown file with the updated block content.

        Args:
            notebook_path: Path to the notebook file
            block_index: Index of the block to update
            new_content: New content for the block

        Returns:
            The updated full markdown content

        Raises:
            ValueError: If block_index is invalid
        """
        path = Path(notebook_path)
        if not path.is_absolute():
            path = self.repo_root / path

        with open(path, 'r') as f:
            original_content = f.read()

        # Re-parse to get current blocks
        config = self.parse_markdown(original_content, track_positions=True)

        if not hasattr(config, '_content_blocks') or not config._content_blocks:
            raise ValueError("No content blocks found in notebook")

        if block_index < 0 or block_index >= len(config._content_blocks):
            raise ValueError(f"Invalid block index: {block_index}")

        # Reconstruct the markdown
        updated_content = self._reconstruct_markdown(
            original_content,
            config._content_blocks,
            block_index,
            new_content
        )

        return updated_content

    def save_block_update(
        self,
        notebook_path: str,
        block_index: int,
        new_content: str
    ) -> None:
        """
        Update a specific block and save to file.

        Args:
            notebook_path: Path to the notebook file
            block_index: Index of the block to update
            new_content: New content for the block
        """
        path = Path(notebook_path)
        if not path.is_absolute():
            path = self.repo_root / path

        updated_content = self.update_block_content(str(path), block_index, new_content)

        with open(path, 'w') as f:
            f.write(updated_content)

    def _reconstruct_markdown(
        self,
        original_content: str,
        content_blocks: List[Dict[str, Any]],
        updated_block_index: int,
        new_content: str
    ) -> str:
        """
        Reconstruct the markdown file with an updated block.

        This is a simplified approach that reconstructs the file from
        the content blocks rather than trying to patch the original.

        Args:
            original_content: Original markdown content
            content_blocks: List of content blocks
            updated_block_index: Index of block to update
            new_content: New content for the block

        Returns:
            Reconstructed markdown content
        """
        # Extract front matter
        front_matter_match = self.FRONT_MATTER_PATTERN.match(original_content)
        front_matter = original_content[:front_matter_match.end()] if front_matter_match else ""

        # Extract filter blocks (we want to preserve them)
        content_after_front = original_content[front_matter_match.end():] if front_matter_match else original_content
        filter_blocks = []
        for match in self.FILTER_PATTERN.finditer(content_after_front):
            filter_blocks.append(f"$filter${{\n{match.group(1)}\n}}")

        # Build the new content
        parts = [front_matter.rstrip()]

        # Add filter blocks after front matter
        for fb in filter_blocks:
            parts.append(fb)

        # Add each content block
        for i, block in enumerate(content_blocks):
            block_type = block['type']

            if i == updated_block_index:
                # Use new content for the updated block
                if block_type == 'markdown':
                    parts.append(new_content)
                elif block_type == 'exhibit':
                    # For exhibits, new_content should be the YAML
                    parts.append(f"$exhibits${{\n{new_content}\n}}")
                elif block_type == 'collapsible':
                    # Preserve collapsible structure
                    parts.append(self._reconstruct_collapsible_block(block, new_content))
            else:
                # Use original content
                if block_type == 'markdown':
                    parts.append(block.get('content', ''))
                elif block_type == 'exhibit':
                    parts.append(self._reconstruct_exhibit_block(block))
                elif block_type == 'collapsible':
                    parts.append(self._reconstruct_collapsible_block(block))
                elif block_type == 'error':
                    # Preserve error blocks as original YAML
                    parts.append(f"$exhibits${{\n{block.get('content', '')}\n}}")

        return '\n\n'.join(parts)

    def _reconstruct_exhibit_block(self, block: Dict[str, Any]) -> str:
        """Reconstruct an exhibit block as $exhibits${...} syntax."""
        exhibit = block.get('exhibit')
        if not exhibit:
            return ""

        # Convert exhibit back to YAML-like format
        yaml_parts = [f"type: {exhibit.type.value}"]

        if exhibit.title:
            yaml_parts.append(f"title: {exhibit.title}")
        if exhibit.description:
            yaml_parts.append(f"description: {exhibit.description}")
        if exhibit.source:
            yaml_parts.append(f"source: {exhibit.source}")

        # X/Y axis
        if exhibit.x_axis and exhibit.x_axis.dimension:
            yaml_parts.append(f"x: {exhibit.x_axis.dimension}")
        if exhibit.y_axis:
            if exhibit.y_axis.measure:
                yaml_parts.append(f"y: {exhibit.y_axis.measure}")
            elif exhibit.y_axis.measures:
                yaml_parts.append(f"y: [{', '.join(exhibit.y_axis.measures)}]")

        if exhibit.color_by:
            yaml_parts.append(f"color: {exhibit.color_by}")

        yaml_content = '\n'.join(f"  {line}" for line in yaml_parts)
        return f"$exhibits${{\n{yaml_content}\n}}"

    def _reconstruct_collapsible_block(
        self,
        block: Dict[str, Any],
        new_content: Optional[str] = None
    ) -> str:
        """Reconstruct a collapsible block as <details> HTML."""
        summary = block.get('summary', 'Details')
        inner_blocks = block.get('content', [])

        inner_parts = []
        for inner_block in inner_blocks:
            inner_type = inner_block['type']
            if inner_type == 'markdown':
                inner_parts.append(inner_block.get('content', ''))
            elif inner_type == 'exhibit':
                inner_parts.append(self._reconstruct_exhibit_block(inner_block))

        inner_content = new_content if new_content else '\n\n'.join(inner_parts)

        return f"<details>\n<summary>{summary}</summary>\n\n{inner_content}\n\n</details>"

    def get_block_raw_content(self, block: Dict[str, Any]) -> str:
        """
        Get the raw content of a block for editing.

        Args:
            block: Content block

        Returns:
            Raw content string suitable for editing
        """
        block_type = block['type']

        if block_type == 'markdown':
            return block.get('content', '')
        elif block_type == 'exhibit':
            return self._reconstruct_exhibit_block(block)
        elif block_type == 'collapsible':
            return self._reconstruct_collapsible_block(block)
        elif block_type == 'error':
            return block.get('content', '')

        return ''

    def insert_block(
        self,
        notebook_path: str,
        after_index: int,
        block_type: str,
        content: str
    ) -> None:
        """
        Insert a new block after the specified index.

        Args:
            notebook_path: Path to the notebook file
            after_index: Index after which to insert (-1 for start)
            block_type: Type of block ('markdown', 'exhibit', 'collapsible')
            content: Content for the new block
        """
        path = Path(notebook_path)
        if not path.is_absolute():
            path = self.repo_root / path

        with open(path, 'r') as f:
            original_content = f.read()

        # Re-parse to get current blocks
        config = self.parse_markdown(original_content, track_positions=True)

        if not hasattr(config, '_content_blocks'):
            config._content_blocks = []

        # Build new block markdown
        if block_type == 'markdown':
            new_block_md = content
        elif block_type == 'exhibit':
            new_block_md = f"$exhibits${{\n{content}\n}}"
        elif block_type == 'collapsible':
            # First line is summary, rest is content
            lines = content.split('\n', 1)
            summary = lines[0] if lines else "Details"
            inner = lines[1] if len(lines) > 1 else ""
            new_block_md = f"<details>\n<summary>{summary}</summary>\n\n{inner}\n\n</details>"
        else:
            new_block_md = content

        # Reconstruct with new block inserted
        updated_content = self._reconstruct_with_insert(
            original_content,
            config._content_blocks,
            after_index,
            new_block_md
        )

        with open(path, 'w') as f:
            f.write(updated_content)

    def delete_block(
        self,
        notebook_path: str,
        block_index: int
    ) -> None:
        """
        Delete a block at the specified index.

        Args:
            notebook_path: Path to the notebook file
            block_index: Index of block to delete
        """
        path = Path(notebook_path)
        if not path.is_absolute():
            path = self.repo_root / path

        with open(path, 'r') as f:
            original_content = f.read()

        # Re-parse to get current blocks
        config = self.parse_markdown(original_content, track_positions=True)

        if not hasattr(config, '_content_blocks') or not config._content_blocks:
            raise ValueError("No content blocks found in notebook")

        if block_index < 0 or block_index >= len(config._content_blocks):
            raise ValueError(f"Invalid block index: {block_index}")

        # Reconstruct without the deleted block
        updated_content = self._reconstruct_with_delete(
            original_content,
            config._content_blocks,
            block_index
        )

        with open(path, 'w') as f:
            f.write(updated_content)

    def _reconstruct_with_insert(
        self,
        original_content: str,
        content_blocks: List[Dict[str, Any]],
        after_index: int,
        new_block_md: str
    ) -> str:
        """
        Reconstruct markdown with a new block inserted.

        Args:
            original_content: Original markdown content
            content_blocks: List of content blocks
            after_index: Index after which to insert (-1 for start)
            new_block_md: Markdown content for new block

        Returns:
            Reconstructed markdown content
        """
        # Extract front matter
        front_matter_match = self.FRONT_MATTER_PATTERN.match(original_content)
        front_matter = original_content[:front_matter_match.end()] if front_matter_match else ""

        # Extract filter blocks
        content_after_front = original_content[front_matter_match.end():] if front_matter_match else original_content
        filter_blocks = []
        for match in self.FILTER_PATTERN.finditer(content_after_front):
            filter_blocks.append(f"$filter${{\n{match.group(1)}\n}}")

        # Build parts list
        parts = [front_matter.rstrip()]

        # Add filter blocks
        for fb in filter_blocks:
            parts.append(fb)

        # Add content blocks with new block inserted
        for i, block in enumerate(content_blocks):
            # Insert new block after after_index
            if i == after_index + 1 or (after_index == -1 and i == 0):
                if after_index == -1:
                    # Insert at start
                    parts.append(new_block_md)
                    parts.append(self._block_to_markdown(block))
                else:
                    parts.append(self._block_to_markdown(block))
            else:
                parts.append(self._block_to_markdown(block))

            # Insert after current block if it matches after_index
            if i == after_index:
                parts.append(new_block_md)

        # Handle insert at end
        if after_index >= len(content_blocks) - 1 and after_index != -1:
            parts.append(new_block_md)

        # Handle empty notebook
        if not content_blocks and after_index == -1:
            parts.append(new_block_md)

        return '\n\n'.join(parts)

    def _reconstruct_with_delete(
        self,
        original_content: str,
        content_blocks: List[Dict[str, Any]],
        delete_index: int
    ) -> str:
        """
        Reconstruct markdown with a block deleted.

        Args:
            original_content: Original markdown content
            content_blocks: List of content blocks
            delete_index: Index of block to delete

        Returns:
            Reconstructed markdown content
        """
        # Extract front matter
        front_matter_match = self.FRONT_MATTER_PATTERN.match(original_content)
        front_matter = original_content[:front_matter_match.end()] if front_matter_match else ""

        # Extract filter blocks
        content_after_front = original_content[front_matter_match.end():] if front_matter_match else original_content
        filter_blocks = []
        for match in self.FILTER_PATTERN.finditer(content_after_front):
            filter_blocks.append(f"$filter${{\n{match.group(1)}\n}}")

        # Build parts list
        parts = [front_matter.rstrip()]

        # Add filter blocks
        for fb in filter_blocks:
            parts.append(fb)

        # Add content blocks except deleted one
        for i, block in enumerate(content_blocks):
            if i != delete_index:
                parts.append(self._block_to_markdown(block))

        return '\n\n'.join(parts)

    def _block_to_markdown(self, block: Dict[str, Any]) -> str:
        """Convert a content block back to markdown."""
        block_type = block['type']

        if block_type == 'markdown':
            return block.get('content', '')
        elif block_type == 'exhibit':
            return self._reconstruct_exhibit_block(block)
        elif block_type == 'collapsible':
            return self._reconstruct_collapsible_block(block)
        elif block_type == 'error':
            return f"$exhibits${{\n{block.get('content', '')}\n}}"

        return ''
