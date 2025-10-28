"""
Graph query engine.

Builds and executes queries on notebook graphs.
"""

from typing import Dict, List, Optional, Any
from pyspark.sql import DataFrame, SparkSession
import pyspark.sql.functions as F

from ..schema import (
    GraphConfig,
    ModelReference,
    SourceReference,
    Dimension,
    Measure,
    MeasureType,
    AggregationType,
)
from .subgraph import NotebookGraph, GraphNode, GraphEdge
from .bridge_manager import BridgeManager
from ...model.api.session import ModelSession


class GraphQueryEngine:
    """
    Query engine for notebook graphs.

    Responsible for:
    - Loading model nodes into the notebook graph
    - Applying bridges between models
    - Executing queries with filters and aggregations
    """

    def __init__(self, spark: SparkSession, model_session: ModelSession):
        """
        Initialize query engine.

        Args:
            spark: Spark session
            model_session: Model session for accessing backend models
        """
        self.spark = spark
        self.model_session = model_session

    def build_graph(self, graph_config: GraphConfig) -> NotebookGraph:
        """
        Build a notebook graph from configuration.

        Args:
            graph_config: Graph configuration from YAML

        Returns:
            Notebook graph with loaded data
        """
        graph = NotebookGraph()

        # Load nodes from each model
        for model_ref in graph_config.models:
            self._load_model_nodes(graph, model_ref)

        # Apply bridges if specified
        if graph_config.bridges:
            bridge_manager = BridgeManager(graph_config.bridges)
            self._apply_bridges(graph, bridge_manager)

        # Validate graph
        errors = graph.validate()
        if errors:
            raise ValueError(f"Graph validation failed:\n" + "\n".join(errors))

        return graph

    def _load_model_nodes(
        self,
        graph: NotebookGraph,
        model_ref: ModelReference,
    ) -> None:
        """
        Load nodes from a model into the graph.

        Args:
            graph: Target notebook graph
            model_ref: Model reference
        """
        model_name = model_ref.name

        for node_name in model_ref.nodes:
            # Build fully qualified node ID
            node_id = f"{model_name}.{node_name}"

            # Load dataframe from model session
            # Try dimensions first, then facts, then paths
            df = None

            # Try as dimension
            try:
                df = self.model_session.get_dimension_df(model_name, node_name)
            except (KeyError, AttributeError):
                pass

            # Try as fact
            if df is None:
                try:
                    df = self.model_session.get_fact_df(model_name, node_name)
                except (KeyError, AttributeError):
                    pass

            # Try as silver path
            if df is None:
                try:
                    df = self.model_session.silver_path_df(f"{model_name}/{node_name}")
                except (KeyError, AttributeError):
                    pass

            if df is None:
                raise ValueError(
                    f"Could not load node {node_name} from model {model_name}"
                )

            # Add to graph
            graph.add_node(GraphNode(
                id=node_id,
                model=model_name,
                node=node_name,
                df=df,
            ))

    def _apply_bridges(
        self,
        graph: NotebookGraph,
        bridge_manager: BridgeManager,
    ) -> None:
        """
        Apply bridges to the graph.

        Args:
            graph: Notebook graph
            bridge_manager: Bridge manager
        """
        # Validate bridges
        available_sources = list(graph.nodes.keys())
        errors = bridge_manager.validate_bridges(available_sources)
        if errors:
            raise ValueError(f"Bridge validation failed:\n" + "\n".join(errors))

        # Add edges for each bridge
        for bridge in bridge_manager.bridges:
            graph.add_edge(GraphEdge(
                from_node=bridge.from_source,
                to_node=bridge.to_source,
                on=bridge.on,
                type=bridge.type,
            ))

    def query(
        self,
        graph: NotebookGraph,
        dimensions: List[str],
        measures: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> DataFrame:
        """
        Execute a query on the graph.

        Args:
            graph: Notebook graph
            dimensions: List of dimension IDs to group by
            measures: List of measure IDs to compute
            filters: Filter conditions

        Returns:
            Query result dataframe
        """
        # For now, this is a simplified implementation
        # In practice, you would:
        # 1. Identify which nodes are needed
        # 2. Find join paths
        # 3. Apply filters
        # 4. Execute aggregations
        # 5. Return result

        # TODO: Implement full query execution
        raise NotImplementedError("Full query execution not yet implemented")

    def get_node_df(
        self,
        graph: NotebookGraph,
        source: SourceReference,
        filters: Optional[Dict[str, Any]] = None,
    ) -> DataFrame:
        """
        Get a dataframe for a source reference.

        Args:
            graph: Notebook graph
            source: Source reference
            filters: Optional filters to apply

        Returns:
            Dataframe
        """
        node_id = f"{source.model}.{source.node}"
        node = graph.get_node(node_id)

        if node is None:
            raise ValueError(f"Node not found in graph: {node_id}")

        df = node.df

        # Apply source-level filters if specified
        if source.filter:
            for filter_expr in source.filter:
                df = df.filter(filter_expr)

        # Apply additional filters
        if filters:
            for col_name, value in filters.items():
                if isinstance(value, list):
                    df = df.filter(F.col(col_name).isin(value))
                else:
                    df = df.filter(F.col(col_name) == value)

        # Select column if specified
        if source.column:
            df = df.select(source.column)

        return df

    def resolve_dimension(
        self,
        graph: NotebookGraph,
        dimension: Dimension,
        filters: Optional[Dict[str, Any]] = None,
    ) -> DataFrame:
        """
        Resolve a dimension to a dataframe.

        Args:
            graph: Notebook graph
            dimension: Dimension definition
            filters: Optional filters

        Returns:
            Dataframe with dimension column
        """
        df = self.get_node_df(graph, dimension.source, filters)

        # Rename column if needed
        if dimension.source.column and dimension.source.column != dimension.id:
            df = df.withColumnRenamed(dimension.source.column, dimension.id)

        return df

    def resolve_measure(
        self,
        graph: NotebookGraph,
        measure: Measure,
        group_by: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> DataFrame:
        """
        Resolve a measure to a dataframe.

        Args:
            graph: Notebook graph
            measure: Measure definition
            group_by: Optional grouping dimensions
            filters: Optional filters

        Returns:
            Dataframe with measure column
        """
        if measure.type == MeasureType.SIMPLE:
            return self._resolve_simple_measure(graph, measure, group_by, filters)
        elif measure.type == MeasureType.WEIGHTED_AVERAGE:
            return self._resolve_weighted_average(graph, measure, group_by, filters)
        elif measure.type == MeasureType.CALCULATION:
            return self._resolve_calculation(graph, measure, group_by, filters)
        elif measure.type == MeasureType.WINDOW_FUNCTION:
            return self._resolve_window_function(graph, measure, group_by, filters)
        else:
            raise ValueError(f"Unsupported measure type: {measure.type}")

    def _resolve_simple_measure(
        self,
        graph: NotebookGraph,
        measure: Measure,
        group_by: Optional[List[str]],
        filters: Optional[Dict[str, Any]],
    ) -> DataFrame:
        """Resolve a simple aggregation measure."""
        df = self.get_node_df(graph, measure.source, filters)

        # Get aggregation function
        agg_col = measure.source.column
        agg_func = self._get_agg_function(measure.aggregation)

        if group_by:
            df = df.groupBy(group_by).agg(
                agg_func(agg_col).alias(measure.id)
            )
        else:
            df = df.agg(
                agg_func(agg_col).alias(measure.id)
            )

        return df

    def _resolve_weighted_average(
        self,
        graph: NotebookGraph,
        measure: Measure,
        group_by: Optional[List[str]],
        filters: Optional[Dict[str, Any]],
    ) -> DataFrame:
        """Resolve a weighted average measure."""
        # Get source dataframe
        # Assuming value and weight columns come from the same node
        node_id = f"{measure.value_column.model}.{measure.value_column.node}"
        node = graph.get_node(node_id)
        df = node.df

        if filters:
            for col_name, value in filters.items():
                if isinstance(value, list):
                    df = df.filter(F.col(col_name).isin(value))
                else:
                    df = df.filter(F.col(col_name) == value)

        # Calculate weighted average: sum(value * weight) / sum(weight)
        value_col = measure.value_column.column
        weight_col = measure.weight_column.column

        if group_by:
            df = df.groupBy(group_by).agg(
                (F.sum(F.col(value_col) * F.col(weight_col)) / F.sum(weight_col))
                .alias(measure.id)
            )
        else:
            df = df.agg(
                (F.sum(F.col(value_col) * F.col(weight_col)) / F.sum(weight_col))
                .alias(measure.id)
            )

        return df

    def _resolve_calculation(
        self,
        graph: NotebookGraph,
        measure: Measure,
        group_by: Optional[List[str]],
        filters: Optional[Dict[str, Any]],
    ) -> DataFrame:
        """Resolve a calculation measure."""
        # This is a complex operation that would require:
        # 1. Parse the expression
        # 2. Load all source columns
        # 3. Apply the calculation
        # 4. Aggregate if needed

        # For now, raise not implemented
        raise NotImplementedError("Calculation measures not yet implemented")

    def _resolve_window_function(
        self,
        graph: NotebookGraph,
        measure: Measure,
        group_by: Optional[List[str]],
        filters: Optional[Dict[str, Any]],
    ) -> DataFrame:
        """Resolve a window function measure."""
        df = self.get_node_df(graph, measure.source, filters)

        # Build window spec
        from pyspark.sql.window import Window

        window_spec = Window.partitionBy(measure.window.partition_by)
        window_spec = window_spec.orderBy(measure.window.order_by)

        if measure.window.rows_between:
            start, end = measure.window.rows_between
            window_spec = window_spec.rowsBetween(start, end)

        # Apply window function
        agg_func = self._get_agg_function(AggregationType(measure.function))
        source_col = measure.source.column

        df = df.withColumn(
            measure.id,
            agg_func(source_col).over(window_spec)
        )

        return df

    def _get_agg_function(self, aggregation: AggregationType):
        """Get Spark aggregation function."""
        mapping = {
            AggregationType.SUM: F.sum,
            AggregationType.AVG: F.avg,
            AggregationType.MIN: F.min,
            AggregationType.MAX: F.max,
            AggregationType.COUNT: F.count,
            AggregationType.STDDEV: F.stddev,
            AggregationType.VARIANCE: F.variance,
            AggregationType.FIRST: F.first,
            AggregationType.LAST: F.last,
        }
        return mapping.get(aggregation, F.sum)
