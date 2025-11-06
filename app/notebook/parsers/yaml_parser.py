"""
YAML notebook parser.

Parses and validates YAML notebook files into structured configurations.
"""

import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import re

from .schema import (
    NotebookConfig,
    NotebookMetadata,
    GraphConfig,
    ModelReference,
    Bridge,
    SourceReference,
    Variable,
    VariableType,
    Dimension,
    Measure,
    MeasureType,
    AggregationType,
    WindowConfig,
    Exhibit,
    ExhibitType,
    AxisConfig,
    ComparisonConfig,
    MetricConfig,
    SortConfig,
    LayoutConfig,
    Section,
    ExportConfig,
    DateRangeDefault,
)


class NotebookParser:
    """Parser for YAML notebook files."""

    def __init__(self, repo_root: Optional[Path] = None):
        """
        Initialize parser.

        Args:
            repo_root: Repository root path for resolving relative paths
        """
        self.repo_root = repo_root or Path.cwd()

    def parse_file(self, notebook_path: str) -> NotebookConfig:
        """
        Parse a notebook YAML file.

        Args:
            notebook_path: Path to notebook YAML file

        Returns:
            NotebookConfig object
        """
        path = Path(notebook_path)
        if not path.is_absolute():
            path = self.repo_root / path

        with open(path, 'r') as f:
            data = yaml.safe_load(f)

        return self.parse_dict(data)

    def parse_dict(self, data: Dict[str, Any]) -> NotebookConfig:
        """
        Parse a notebook dictionary.

        Args:
            data: Dictionary from YAML

        Returns:
            NotebookConfig object
        """
        # Parse dimensions and measures if present (backward compatibility)
        dimensions = None
        if 'dimensions' in data and data['dimensions']:
            dimensions = self._parse_dimensions(data['dimensions'])

        measures = None
        if 'measures' in data and data['measures']:
            measures = self._parse_measures(data['measures'])

        # Parse graph if present (backward compatibility with old format)
        graph = None
        if 'graph' in data and data['graph']:
            graph = self._parse_graph(data['graph'])
        else:
            # Create empty graph for new simplified format
            graph = GraphConfig(models=[], bridges=[])

        return NotebookConfig(
            version=data['version'],
            notebook=self._parse_metadata(data['notebook']),
            graph=graph,
            variables=self._parse_variables(data.get('variables', {})),
            exhibits=self._parse_exhibits(data.get('exhibits', [])),
            layout=self._parse_layout(data.get('layout', [])),
            dimensions=dimensions,
            measures=measures,
            exports=self._parse_exports(data.get('exports', [])),
        )

    def _parse_metadata(self, data: Dict[str, Any]) -> NotebookMetadata:
        """Parse notebook metadata."""
        return NotebookMetadata(
            id=data['id'],
            title=data['title'],
            description=data.get('description'),
            author=data.get('author'),
            created=data.get('created'),
            updated=data.get('updated'),
            tags=data.get('tags'),
        )

    def _parse_graph(self, data: Dict[str, Any]) -> GraphConfig:
        """Parse graph configuration."""
        models = [
            ModelReference(
                name=m['name'],
                config=m['config'],
                nodes=m['nodes'],
            )
            for m in data.get('models', [])
        ]

        bridges = None
        if 'bridges' in data:
            bridges = [
                Bridge(
                    from_source=b['from'],
                    to_source=b['to'],
                    on=b['on'],
                    type=b.get('type', 'left'),
                    description=b.get('description'),
                )
                for b in data['bridges']
            ]

        return GraphConfig(models=models, bridges=bridges)

    def _parse_source_reference(self, data: Dict[str, Any]) -> SourceReference:
        """Parse source reference."""
        return SourceReference(
            model=data['model'],
            node=data['node'],
            column=data.get('column'),
            filter=data.get('filter'),
        )

    def _parse_variables(self, data: Dict[str, Any]) -> Dict[str, Variable]:
        """Parse variables."""
        variables = {}
        for var_id, var_data in data.items():
            var_type = VariableType(var_data['type'])

            # Parse default value
            default = var_data.get('default')
            if var_type == VariableType.DATE_RANGE and isinstance(default, dict):
                default = DateRangeDefault(
                    start=default['start'],
                    end=default['end'],
                )

            # Parse source if present
            source = None
            if 'source' in var_data:
                source = self._parse_source_reference(var_data['source'])

            variables[var_id] = Variable(
                id=var_id,
                type=var_type,
                display_name=var_data['display_name'],
                default=default,
                source=source,
                description=var_data.get('description'),
                format=var_data.get('format'),
                options=var_data.get('options'),
            )

        return variables

    def _parse_dimensions(self, data: List[Dict[str, Any]]) -> List[Dimension]:
        """Parse dimensions."""
        return [
            Dimension(
                id=d['id'],
                source=self._parse_source_reference(d['source']),
                display_name=d['display_name'],
                type=d['type'],
                format=d.get('format'),
            )
            for d in data
        ]

    def _parse_measures(self, data: List[Dict[str, Any]]) -> List[Measure]:
        """Parse measures."""
        measures = []
        for m in data:
            measure_type = MeasureType(m.get('type', 'simple'))

            # Parse aggregation
            aggregation = None
            if 'aggregation' in m:
                aggregation = AggregationType(m['aggregation'])

            # Parse source
            source = None
            if 'source' in m:
                source = self._parse_source_reference(m['source'])

            # Parse weighted average fields
            value_column = None
            weight_column = None
            if measure_type == MeasureType.WEIGHTED_AVERAGE:
                value_column = self._parse_source_reference(m['value_column'])
                weight_column = self._parse_source_reference(m['weight_column'])

            # Parse calculation fields
            expression = m.get('expression')
            sources = None
            if 'sources' in m:
                sources = {
                    key: self._parse_source_reference(val)
                    for key, val in m['sources'].items()
                }

            # Parse window function
            function = m.get('function')
            window = None
            if 'window' in m:
                w = m['window']
                window = WindowConfig(
                    partition_by=w['partition_by'],
                    order_by=w['order_by'],
                    rows_between=w.get('rows_between'),
                    range_between=w.get('range_between'),
                )

            measures.append(Measure(
                id=m['id'],
                display_name=m['display_name'],
                type=measure_type,
                source=source,
                aggregation=aggregation,
                format=m.get('format'),
                value_column=value_column,
                weight_column=weight_column,
                expression=expression,
                sources=sources,
                function=function,
                window=window,
            ))

        return measures

    def _parse_axis_config(self, data: Dict[str, Any]) -> AxisConfig:
        """Parse axis configuration."""
        source = None
        if 'source' in data:
            source = self._parse_source_reference(data['source'])

        return AxisConfig(
            dimension=data.get('dimension'),
            measure=data.get('measure'),
            measures=data.get('measures'),
            label=data.get('label'),
            scale=data.get('scale'),
            source=source,
        )

    def _parse_exhibits(self, data: List[Dict[str, Any]]) -> List[Exhibit]:
        """Parse exhibits."""
        exhibits = []
        for e in data:
            exhibit_type = ExhibitType(e['type'])

            # Parse axis configurations
            x_axis = None
            if 'x_axis' in e:
                x_axis = self._parse_axis_config(e['x_axis'])

            y_axis = None
            if 'y_axis' in e:
                y_axis = self._parse_axis_config(e['y_axis'])

            y_axis_left = None
            if 'y_axis_left' in e:
                y_axis_left = self._parse_axis_config(e['y_axis_left'])

            y_axis_right = None
            if 'y_axis_right' in e:
                y_axis_right = self._parse_axis_config(e['y_axis_right'])

            # Parse metrics
            metrics = None
            if 'metrics' in e:
                metrics = []
                for m in e['metrics']:
                    comparison = None
                    if 'comparison' in m:
                        c = m['comparison']
                        comparison = ComparisonConfig(
                            period=c['period'],
                            label=c['label'],
                        )
                    metrics.append(MetricConfig(
                        measure=m['measure'],
                        comparison=comparison,
                    ))

            # Parse sort
            sort = None
            if 'sort' in e:
                s = e['sort']
                sort = SortConfig(
                    by=s['by'],
                    order=s.get('order', 'asc'),
                )

            # Parse layout
            layout = None
            if 'layout' in e:
                l = e['layout']
                layout = LayoutConfig(
                    columns=l.get('columns'),
                    rows=l.get('rows'),
                )

            exhibits.append(Exhibit(
                id=e['id'],
                type=exhibit_type,
                title=e['title'],
                description=e.get('description'),
                source=e.get('source'),
                filters=e.get('filters'),
                x_axis=x_axis,
                y_axis=y_axis,
                y_axis_left=y_axis_left,
                y_axis_right=y_axis_right,
                color_by=e.get('color_by'),
                size_by=e.get('size_by'),
                legend=e.get('legend', True),
                interactive=e.get('interactive', True),
                metrics=metrics,
                # Weighted aggregate fields
                weighting=e.get('weighting'),
                aggregate_by=e.get('aggregate_by'),
                value_measures=e.get('value_measures'),
                group_by=e.get('group_by'),
                # Table fields
                columns=e.get('columns'),
                pagination=e.get('pagination', False),
                page_size=e.get('page_size', 50),
                download=e.get('download', False),
                sortable=e.get('sortable', True),
                searchable=e.get('searchable', False),
                sort=sort,
                layout=layout,
                component=e.get('component'),
                params=e.get('params'),
                options=e.get('options'),
            ))

        return exhibits

    def _parse_layout(self, data: List[Dict[str, Any]]) -> List[Section]:
        """Parse layout sections."""
        return [
            Section(
                title=s.get('section', {}).get('title') if 'section' in s else s.get('title'),
                exhibits=s.get('section', {}).get('exhibits', []) if 'section' in s else s.get('exhibits', []),
                columns=s.get('section', {}).get('columns', 1) if 'section' in s else s.get('columns', 1),
                description=s.get('section', {}).get('description') if 'section' in s else s.get('description'),
            )
            for s in data
        ]

    def _parse_exports(self, data: List[Dict[str, Any]]) -> Optional[List[ExportConfig]]:
        """Parse export configurations."""
        if not data:
            return None

        return [
            ExportConfig(
                id=e['id'],
                type=e['type'],
                title=e['title'],
                include=e['include'],
                format=e.get('format'),
            )
            for e in data
        ]


class DateResolver:
    """Resolves relative date expressions."""

    @staticmethod
    def resolve(date_expr: str, reference_date: Optional[datetime] = None) -> datetime:
        """
        Resolve a date expression.

        Supports:
        - ISO dates: "2024-01-01"
        - "today"
        - Relative: "-30d", "-1w", "-6m", "-1y"

        Args:
            date_expr: Date expression
            reference_date: Reference date (defaults to today)

        Returns:
            Resolved datetime
        """
        if reference_date is None:
            reference_date = datetime.now()

        # Handle "today"
        if date_expr.lower() == "today":
            return reference_date

        # Handle ISO date
        if re.match(r'^\d{4}-\d{2}-\d{2}$', date_expr):
            return datetime.fromisoformat(date_expr)

        # Handle relative dates
        match = re.match(r'^([+-]?\d+)([dwmy])$', date_expr)
        if match:
            amount = int(match.group(1))
            unit = match.group(2)

            if unit == 'd':
                return reference_date + timedelta(days=amount)
            elif unit == 'w':
                return reference_date + timedelta(weeks=amount)
            elif unit == 'm':
                # Approximate month as 30 days
                return reference_date + timedelta(days=amount * 30)
            elif unit == 'y':
                # Approximate year as 365 days
                return reference_date + timedelta(days=amount * 365)

        raise ValueError(f"Invalid date expression: {date_expr}")


class VariableResolver:
    """Resolves variable references in filters."""

    @staticmethod
    def resolve(filter_value: str, variables: Dict[str, Variable]) -> str:
        """
        Resolve variable references in filter values.

        Args:
            filter_value: Filter value (may contain $variable_name)
            variables: Available variables

        Returns:
            Resolved value
        """
        if filter_value.startswith('$'):
            var_name = filter_value[1:]
            if var_name not in variables:
                raise ValueError(f"Unknown variable: {var_name}")
            return var_name
        return filter_value
