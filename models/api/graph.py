"""
ModelGraph - NetworkX-based model dependency and relationship management.

Manages the graph of model dependencies and cross-model relationships using NetworkX.
This provides:
- Relationship checking (direct and transitive)
- Path finding for cross-model joins
- Topological sorting for build order
- Cycle detection for validation
- Graph visualization capabilities

Similar to how DBT, Airflow, and Prefect manage DAGs.
"""

import networkx as nx
from typing import Dict, List, Optional, Set, Tuple, Any
from pathlib import Path
import yaml


class ModelGraph:
    """
    Model dependency graph using NetworkX.

    Manages relationships between models and tables within the data platform.
    Supports both:
    - Model-level dependencies (e.g., forecast depends on company)
    - Table-level edges (e.g., forecast.fact_forecasts → company.fact_prices)
    """

    def __init__(self):
        """Initialize empty directed graph."""
        self.graph = nx.DiGraph()
        self._model_configs: Dict[str, Dict] = {}

    def build_from_registry(self, model_registry) -> None:
        """
        Build graph from ModelRegistry.

        Parses all model configs and builds the dependency graph.

        Args:
            model_registry: ModelRegistry instance with loaded models
        """
        self.graph.clear()
        self._model_configs.clear()

        # Get all model configs
        for model_name in model_registry.list_models():
            try:
                # Get raw config dict (not ModelConfig object)
                model_config = model_registry.get_model_config(model_name)
                self._model_configs[model_name] = model_config
            except Exception:
                continue

        # Build graph from configs
        self._build_graph_from_configs()

        # Validate DAG property
        self.validate_no_cycles()

    def build_from_config_dir(self, config_dir: Path) -> None:
        """
        Build graph directly from config directory.

        Useful for validation without loading full models.

        Args:
            config_dir: Path to configs/models/ directory
        """
        self.graph.clear()
        self._model_configs.clear()

        # Load all model configs
        config_path = Path(config_dir)
        for yaml_file in config_path.glob("*.yaml"):
            try:
                with open(yaml_file, 'r') as f:
                    config = yaml.safe_load(f)
                    model_name = config.get('model')
                    if model_name:
                        self._model_configs[model_name] = config
            except Exception:
                continue

        # Build graph from configs
        self._build_graph_from_configs()

        # Validate DAG property
        self.validate_no_cycles()

    def _build_graph_from_configs(self) -> None:
        """Build NetworkX graph from parsed model configs."""
        # Add all models as nodes
        for model_name in self._model_configs.keys():
            self.graph.add_node(model_name, type='model')

        # Add dependency edges from depends_on
        for model_name, config in self._model_configs.items():
            depends_on = config.get('depends_on', [])
            for dependency in depends_on:
                self.graph.add_edge(
                    model_name,
                    dependency,
                    type='dependency',
                    source='depends_on'
                )

        # Add edges from graph.edges in config
        for model_name, config in self._model_configs.items():
            graph_config = config.get('graph', {})
            edges = graph_config.get('edges', {})

            # Handle edges as dict (keyed by edge name) or list
            if isinstance(edges, dict):
                edge_list = list(edges.values())
            else:
                edge_list = edges if edges else []

            for edge in edge_list:
                from_node = edge.get('from', '')
                to_node = edge.get('to', '')

                # Parse node references (may be "table" or "model.table")
                from_model = model_name  # Default to current model
                to_model = self._extract_model_from_node(to_node)

                if to_model and to_model != model_name:
                    # Cross-model edge
                    self.graph.add_edge(
                        from_model,
                        to_model,
                        type='cross_model_edge',
                        source='graph.edges',
                        from_table=from_node,
                        to_table=to_node,
                        join_condition=edge.get('on', []),
                        join_type=edge.get('type', 'left'),
                        description=edge.get('description', '')
                    )

    def _extract_model_from_node(self, node_ref: str) -> Optional[str]:
        """
        Extract model name from node reference.

        Args:
            node_ref: Node reference (e.g., "company.fact_prices" or "fact_prices")

        Returns:
            Model name or None if local reference
        """
        if '.' in node_ref:
            return node_ref.split('.')[0]
        return None

    # ============================================================
    # RELATIONSHIP QUERIES
    # ============================================================

    def are_related(self, model_a: str, model_b: str) -> bool:
        """
        Check if two models are related (direct or transitive).

        Args:
            model_a: Source model
            model_b: Target model

        Returns:
            True if there's a path from model_a to model_b
        """
        if model_a not in self.graph or model_b not in self.graph:
            return False

        # Check if path exists (handles both direct and transitive)
        return nx.has_path(self.graph, model_a, model_b)

    def get_dependencies(self, model_name: str, transitive: bool = False) -> Set[str]:
        """
        Get dependencies for a model.

        Args:
            model_name: Model to get dependencies for
            transitive: If True, include transitive dependencies

        Returns:
            Set of model names this model depends on
        """
        if model_name not in self.graph:
            return set()

        if transitive:
            # Get all reachable nodes (transitive closure)
            return set(nx.descendants(self.graph, model_name))
        else:
            # Get direct dependencies only
            return set(self.graph.successors(model_name))

    def get_dependents(self, model_name: str, transitive: bool = False) -> Set[str]:
        """
        Get models that depend on this model.

        Args:
            model_name: Model to get dependents for
            transitive: If True, include transitive dependents

        Returns:
            Set of model names that depend on this model
        """
        if model_name not in self.graph:
            return set()

        if transitive:
            # Get all nodes that can reach this one
            return set(nx.ancestors(self.graph, model_name))
        else:
            # Get direct dependents only
            return set(self.graph.predecessors(model_name))

    def get_join_path(self, model_a: str, model_b: str) -> Optional[List[str]]:
        """
        Find shortest path between two models.

        Useful for determining how to join across models.

        Args:
            model_a: Source model
            model_b: Target model

        Returns:
            List of model names forming the path, or None if no path exists
        """
        if model_a not in self.graph or model_b not in self.graph:
            return None

        try:
            return nx.shortest_path(self.graph, model_a, model_b)
        except nx.NetworkXNoPath:
            return None

    def get_edge_metadata(self, model_a: str, model_b: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata about the edge between two models.

        Args:
            model_a: Source model
            model_b: Target model

        Returns:
            Dictionary with edge attributes, or None if no edge exists
        """
        if not self.graph.has_edge(model_a, model_b):
            return None

        return dict(self.graph.edges[model_a, model_b])

    # ============================================================
    # BUILD ORDER & VALIDATION
    # ============================================================

    def get_build_order(self) -> List[str]:
        """
        Get topological sort of models for build order.

        Returns models in the order they should be built (dependencies first).

        Returns:
            List of model names in build order

        Raises:
            ValueError: If graph contains cycles
        """
        if not nx.is_directed_acyclic_graph(self.graph):
            raise ValueError("Cannot determine build order: graph contains cycles")

        return list(nx.topological_sort(self.graph))

    def validate_no_cycles(self) -> None:
        """
        Validate that graph is a DAG (no cycles).

        Raises:
            ValueError: If cycles are detected
        """
        if not nx.is_directed_acyclic_graph(self.graph):
            cycles = list(nx.simple_cycles(self.graph))
            cycle_strs = [' → '.join(cycle + [cycle[0]]) for cycle in cycles]
            raise ValueError(
                f"Model dependency graph contains cycles:\n" +
                "\n".join(f"  - {c}" for c in cycle_strs)
            )

    def get_depth(self, model_name: str) -> int:
        """
        Get depth of model in dependency tree.

        Depth 0 = no dependencies (core/base models)
        Higher depth = more dependencies

        Args:
            model_name: Model to get depth for

        Returns:
            Depth in dependency tree
        """
        if model_name not in self.graph:
            return 0

        dependencies = self.get_dependencies(model_name, transitive=True)
        if not dependencies:
            return 0

        # Depth is length of longest path from any root
        depths = []
        for dep in dependencies:
            if self.get_dependencies(dep, transitive=False):
                continue  # Not a root
            path = self.get_join_path(model_name, dep)
            if path:
                depths.append(len(path) - 1)

        return max(depths) if depths else 0

    # ============================================================
    # GRAPH METRICS
    # ============================================================

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get graph metrics for monitoring and debugging.

        Returns:
            Dictionary with graph statistics
        """
        return {
            'num_models': self.graph.number_of_nodes(),
            'num_relationships': self.graph.number_of_edges(),
            'is_dag': nx.is_directed_acyclic_graph(self.graph),
            'is_connected': nx.is_weakly_connected(self.graph),
            'num_components': nx.number_weakly_connected_components(self.graph),
            'density': nx.density(self.graph),
            'models': list(self.graph.nodes()),
        }

    def get_model_stats(self, model_name: str) -> Dict[str, Any]:
        """
        Get statistics for a specific model.

        Args:
            model_name: Model to analyze

        Returns:
            Dictionary with model statistics
        """
        if model_name not in self.graph:
            return {}

        return {
            'model': model_name,
            'direct_dependencies': list(self.get_dependencies(model_name, transitive=False)),
            'all_dependencies': list(self.get_dependencies(model_name, transitive=True)),
            'direct_dependents': list(self.get_dependents(model_name, transitive=False)),
            'all_dependents': list(self.get_dependents(model_name, transitive=True)),
            'depth': self.get_depth(model_name),
            'in_degree': self.graph.in_degree(model_name),
            'out_degree': self.graph.out_degree(model_name),
        }

    # ============================================================
    # VISUALIZATION
    # ============================================================

    def to_dict(self) -> Dict[str, Any]:
        """
        Export graph to dictionary format for visualization.

        Returns:
            Dictionary with nodes and edges
        """
        return {
            'nodes': [
                {
                    'id': node,
                    'label': node,
                    **self.graph.nodes[node]
                }
                for node in self.graph.nodes()
            ],
            'edges': [
                {
                    'source': u,
                    'target': v,
                    **self.graph.edges[u, v]
                }
                for u, v in self.graph.edges()
            ]
        }

    def to_mermaid(self) -> str:
        """
        Generate Mermaid diagram syntax for visualization.

        Returns:
            Mermaid flowchart syntax
        """
        lines = ["graph TD"]

        # Add nodes
        for node in self.graph.nodes():
            lines.append(f"    {node}[{node}]")

        # Add edges
        for u, v, data in self.graph.edges(data=True):
            edge_type = data.get('type', 'dependency')
            label = data.get('description', edge_type)
            lines.append(f"    {u} -->|{label}| {v}")

        return "\n".join(lines)

    def __repr__(self) -> str:
        """String representation of graph."""
        metrics = self.get_metrics()
        return (
            f"ModelGraph(models={metrics['num_models']}, "
            f"relationships={metrics['num_relationships']}, "
            f"is_dag={metrics['is_dag']})"
        )
