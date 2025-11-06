"""
Markdown notebook parser.

Parses markdown-based notebooks with YAML front matter, filters section,
and embedded exhibits using the $exhibits${...} syntax.
"""

import re
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

from .schema import (
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
)
from .filters.dynamic import (
    FilterConfig,
    FilterType,
    FilterOperator,
    FilterSource,
    FilterCollection,
)
from .markdown_parser_filter_helpers import parse_filter


@dataclass
class MarkdownNotebook:
    """Parsed markdown notebook structure."""
    front_matter: Dict[str, Any]
    filters: Dict[str, Variable]
    exhibits: List[Tuple[str, Exhibit]]  # List of (markdown_content, exhibit) pairs
    content_blocks: List[Dict[str, Any]]  # List of {type: 'markdown'|'exhibit', content: ...}


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
        self.repo_root = repo_root or Path.cwd()

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

    def parse_markdown(self, content: str) -> NotebookConfig:
        """
        Parse markdown content into NotebookConfig.

        Args:
            content: Markdown content string

        Returns:
            NotebookConfig object
        """
        # Extract front matter
        front_matter = self._extract_front_matter(content)
        if not front_matter:
            raise ValueError("Markdown notebook must have YAML front matter (---\\n...\\n---)")

        # Remove front matter from content
        content = self.FRONT_MATTER_PATTERN.sub('', content, count=1)

        # Extract filters (new $filter${} syntax)
        filter_collection = self._extract_dynamic_filters(content)

        # Remove filter blocks from content (they don't render in notebook view)
        content = self.FILTER_PATTERN.sub('', content)

        # Extract exhibits and build content structure
        exhibits, content_blocks = self._extract_exhibits(content)

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

    def _extract_exhibits(self, content: str) -> Tuple[List[Exhibit], List[Dict[str, Any]]]:
        """
        Extract exhibits from markdown content and handle collapsible sections.

        Returns:
            Tuple of (exhibits list, content_blocks list)
        """
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
                self._add_content_with_collapsibles(
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
            self._add_content_with_collapsibles(
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
    ):
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
                    exhibit_id = f"exhibit_{len(exhibits)}"

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

    def _parse_exhibit(self, exhibit_yaml: str, exhibit_id: str) -> Exhibit:
        """
        Parse exhibit YAML into Exhibit object.

        Supports streamlined syntax:
        - x, y instead of x_axis, y_axis
        - Simplified metric definitions
        """
        data = yaml.safe_load(exhibit_yaml)

        exhibit_type = ExhibitType(data['type'])

        # Parse streamlined axis parameters
        x_axis = None
        if 'x' in data:
            x_axis = AxisConfig(
                dimension=data['x'],
                label=data.get('x_label', data['x'])
            )

        y_axis = None
        if 'y' in data:
            y_axis = AxisConfig(
                measure=data['y'],
                label=data.get('y_label', data['y'])
            )

        y_axis_left = None
        if 'y2' in data:
            y_axis_left = y_axis
            y_axis = AxisConfig(
                measure=data['y2'],
                label=data.get('y2_label', data['y2'])
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
            from .schema import SortConfig
            sort = SortConfig(
                by=data['sort']['by'],
                order=data['sort'].get('order', 'asc')
            )

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
            # Weighted aggregate fields
            weighting=data.get('weighting'),
            aggregate_by=data.get('aggregate_by'),
            value_measures=data.get('value_measures'),
            group_by=data.get('group_by'),
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
            options=data.get('options'),
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

        return config
