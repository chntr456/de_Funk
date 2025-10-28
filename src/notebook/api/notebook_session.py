"""
Notebook session for executing and rendering notebooks.

This is the main entry point for working with YAML notebooks.
"""

from typing import Dict, List, Optional, Any
from pathlib import Path
from pyspark.sql import DataFrame, SparkSession
import pyspark.sql.functions as F

from ..schema import NotebookConfig, Exhibit, Dimension, Measure
from ..parser import NotebookParser
from ..graph.query_engine import GraphQueryEngine
from ..graph.subgraph import NotebookGraph
from ..measures.engine import MeasureEngine
from ..filters.context import FilterContext
from ..filters.engine import FilterEngine
from ...model.api.session import ModelSession


class NotebookSession:
    """
    Session for executing a YAML notebook.

    Provides:
    - Notebook loading and parsing
    - Graph construction from backend models
    - Filter management
    - Measure computation
    - Exhibit data preparation
    """

    def __init__(
        self,
        spark: SparkSession,
        model_session: ModelSession,
        repo_root: Optional[Path] = None,
    ):
        """
        Initialize notebook session.

        Args:
            spark: Spark session
            model_session: Model session for accessing backend models
            repo_root: Repository root for resolving paths
        """
        self.spark = spark
        self.model_session = model_session
        self.repo_root = repo_root or Path.cwd()

        self.parser = NotebookParser(repo_root)
        self.query_engine = GraphQueryEngine(spark, model_session)
        self.filter_engine = FilterEngine()

        # State
        self.notebook: Optional[NotebookConfig] = None
        self.graph: Optional[NotebookGraph] = None
        self.filter_context: Optional[FilterContext] = None
        self.measure_engine: Optional[MeasureEngine] = None

    def load_notebook(self, notebook_path: str) -> NotebookConfig:
        """
        Load a notebook from YAML file.

        Args:
            notebook_path: Path to notebook YAML

        Returns:
            Parsed notebook configuration
        """
        self.notebook = self.parser.parse_file(notebook_path)
        self._initialize_session()
        return self.notebook

    def load_notebook_from_dict(self, notebook_dict: Dict[str, Any]) -> NotebookConfig:
        """
        Load a notebook from dictionary.

        Args:
            notebook_dict: Notebook configuration dictionary

        Returns:
            Parsed notebook configuration
        """
        self.notebook = self.parser.parse_dict(notebook_dict)
        self._initialize_session()
        return self.notebook

    def _initialize_session(self):
        """Initialize session components after notebook is loaded."""
        if not self.notebook:
            raise ValueError("No notebook loaded")

        # Build graph
        self.graph = self.query_engine.build_graph(self.notebook.graph)

        # Initialize filter context
        self.filter_context = FilterContext(self.notebook.variables)

        # Initialize measure engine
        self.measure_engine = MeasureEngine(self.graph)

    def get_filter_context(self) -> FilterContext:
        """Get the current filter context."""
        if not self.filter_context:
            raise ValueError("Session not initialized. Load a notebook first.")
        return self.filter_context

    def update_filters(self, values: Dict[str, Any]):
        """
        Update filter values.

        Args:
            values: Dictionary of variable_id -> value
        """
        if not self.filter_context:
            raise ValueError("Session not initialized")
        self.filter_context.update(values)

    def get_exhibit_data(
        self,
        exhibit_id: str,
        custom_filters: Optional[Dict[str, Any]] = None,
    ) -> DataFrame:
        """
        Get data for an exhibit.

        Args:
            exhibit_id: Exhibit ID
            custom_filters: Optional custom filters to apply

        Returns:
            DataFrame ready for exhibit rendering
        """
        if not self.notebook or not self.graph:
            raise ValueError("Session not initialized")

        # Find exhibit
        exhibit = self._find_exhibit(exhibit_id)
        if not exhibit:
            raise ValueError(f"Exhibit not found: {exhibit_id}")

        # Create exhibit-specific filter context
        exhibit_context = self.filter_context.create_exhibit_context(
            exhibit.filters
        )

        # Apply custom filters if provided
        if custom_filters:
            exhibit_context.update(custom_filters)

        # Get required dimensions and measures
        dimensions = self._get_exhibit_dimensions(exhibit)
        measures = self._get_exhibit_measures(exhibit)

        # Build dataframe with dimensions and measures
        df = self._build_exhibit_dataframe(
            exhibit,
            dimensions,
            measures,
            exhibit_context,
        )

        return df

    def _find_exhibit(self, exhibit_id: str) -> Optional[Exhibit]:
        """Find an exhibit by ID."""
        for exhibit in self.notebook.exhibits:
            if exhibit.id == exhibit_id:
                return exhibit
        return None

    def _get_exhibit_dimensions(self, exhibit: Exhibit) -> List[Dimension]:
        """Get dimensions required for an exhibit."""
        dimensions = []
        dim_ids = set()

        # Collect dimension IDs from exhibit config
        if exhibit.x_axis and exhibit.x_axis.dimension:
            dim_ids.add(exhibit.x_axis.dimension)
        if exhibit.color_by:
            dim_ids.add(exhibit.color_by)
        if exhibit.columns:
            for col in exhibit.columns:
                # Check if it's a dimension
                for dim in self.notebook.dimensions:
                    if dim.id == col:
                        dim_ids.add(col)

        # Find dimension definitions
        for dim_id in dim_ids:
            for dim in self.notebook.dimensions:
                if dim.id == dim_id:
                    dimensions.append(dim)

        return dimensions

    def _get_exhibit_measures(self, exhibit: Exhibit) -> List[Measure]:
        """Get measures required for an exhibit."""
        measures = []
        measure_ids = set()

        # Collect measure IDs
        if exhibit.y_axis:
            if exhibit.y_axis.measure:
                measure_ids.add(exhibit.y_axis.measure)
            if exhibit.y_axis.measures:
                measure_ids.update(exhibit.y_axis.measures)

        if exhibit.y_axis_left and exhibit.y_axis_left.measures:
            measure_ids.update(exhibit.y_axis_left.measures)
        if exhibit.y_axis_right and exhibit.y_axis_right.measures:
            measure_ids.update(exhibit.y_axis_right.measures)

        if exhibit.metrics:
            for metric in exhibit.metrics:
                measure_ids.add(metric.measure)

        if exhibit.columns:
            for col in exhibit.columns:
                # Check if it's a measure
                for measure in self.notebook.measures:
                    if measure.id == col:
                        measure_ids.add(col)

        # Find measure definitions
        for measure_id in measure_ids:
            for measure in self.notebook.measures:
                if measure.id == measure_id:
                    measures.append(measure)

        return measures

    def _build_exhibit_dataframe(
        self,
        exhibit: Exhibit,
        dimensions: List[Dimension],
        measures: List[Measure],
        filter_context: FilterContext,
    ) -> DataFrame:
        """
        Build a dataframe for an exhibit with dimensions and measures.

        This is a simplified implementation. In production, you would:
        1. Identify which graph nodes are needed
        2. Build join paths
        3. Apply filters
        4. Compute measures
        5. Return result
        """
        # Handle exhibits without dimensions (like metric cards)
        if not dimensions and measures:
            # For metric cards with just measures, compute each measure separately
            # and combine them
            measure_dfs = []
            for measure in measures:
                if not measure.source:
                    continue

                # Get the source dataframe
                df = self.query_engine.get_node_df(
                    self.graph,
                    measure.source,
                )

                # Apply filters using FilterEngine
                # Build column mapping for this measure's source
                column_mapping = {}
                if measure.source.column:
                    # Map filter variables to actual column names
                    # For now, assume direct mapping
                    pass

                df = self.filter_engine.apply_filters(df, filter_context, column_mapping)

                # Compute the measure (aggregate)
                df_measure = self.query_engine.resolve_measure(
                    self.graph,
                    measure,
                    group_by=None,  # No grouping for metrics
                    filters=None,  # Already filtered above
                )
                measure_dfs.append(df_measure)

            # Combine all measures into one row
            if measure_dfs:
                result = measure_dfs[0]
                for df_measure in measure_dfs[1:]:
                    result = result.crossJoin(df_measure)
                return result
            else:
                return self.spark.createDataFrame([], schema="")

        # For exhibits with dimensions
        if not dimensions:
            raise ValueError(f"Exhibit {exhibit.id} has no dimensions or measures")

        primary_dim = dimensions[0]
        df = self.query_engine.get_node_df(
            self.graph,
            primary_dim.source,
        )

        # Apply filters
        # Build column mapping (dimension_id -> column_name in source)
        column_mapping = {}
        for dim in dimensions:
            if dim.source.column:
                column_mapping[dim.id] = dim.source.column

        df = self.filter_engine.apply_filters(df, filter_context, column_mapping)

        # Compute measures
        # This is simplified - in production you'd handle different measure types
        for measure in measures:
            if measure.source:
                # Add measure column
                df = self.query_engine.resolve_measure(
                    self.graph,
                    measure,
                    group_by=[d.id for d in dimensions] if dimensions else None,
                    filters=None,  # Already filtered above
                )

        # Select and rename columns
        select_cols = []
        for dim in dimensions:
            if dim.source.column and dim.source.column != dim.id:
                select_cols.append(F.col(dim.source.column).alias(dim.id))
            else:
                select_cols.append(dim.id)

        for measure in measures:
            select_cols.append(measure.id)

        if select_cols:
            df = df.select(select_cols)

        return df

    def get_dimension_values(
        self,
        dimension_id: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Any]:
        """
        Get unique values for a dimension (for filter options).

        Args:
            dimension_id: Dimension ID
            filters: Optional filters to apply

        Returns:
            List of unique values
        """
        # Find dimension
        dimension = None
        for dim in self.notebook.dimensions:
            if dim.id == dimension_id:
                dimension = dim
                break

        if not dimension:
            raise ValueError(f"Dimension not found: {dimension_id}")

        # Get dataframe
        df = self.query_engine.get_node_df(self.graph, dimension.source)

        # Apply filters if provided
        if filters:
            temp_context = FilterContext(self.notebook.variables)
            temp_context.update(filters)
            df = self.filter_engine.apply_filters(df, temp_context)

        # Get unique values
        column_name = dimension.source.column or dimension.id
        return self.filter_engine.get_unique_values(df, column_name)

    def get_notebook_info(self) -> Dict[str, Any]:
        """
        Get notebook metadata and summary.

        Returns:
            Dictionary with notebook information
        """
        if not self.notebook:
            raise ValueError("No notebook loaded")

        return {
            'id': self.notebook.notebook.id,
            'title': self.notebook.notebook.title,
            'description': self.notebook.notebook.description,
            'author': self.notebook.notebook.author,
            'dimensions': len(self.notebook.dimensions),
            'measures': len(self.notebook.measures),
            'exhibits': len(self.notebook.exhibits),
            'sections': len(self.notebook.layout),
        }

    def __repr__(self) -> str:
        """String representation."""
        if self.notebook:
            return f"NotebookSession(notebook={self.notebook.notebook.id})"
        return "NotebookSession(no notebook loaded)"
