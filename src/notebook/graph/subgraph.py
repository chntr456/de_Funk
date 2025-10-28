"""
Notebook subgraph representation.

Represents a subgraph of the backend graph for a specific notebook.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from pyspark.sql import DataFrame


@dataclass
class GraphNode:
    """Represents a node in the notebook graph."""
    id: str
    model: str
    node: str  # Node ID in the model
    df: Optional[DataFrame] = None
    tags: List[str] = field(default_factory=list)


@dataclass
class GraphEdge:
    """Represents an edge (relationship) in the notebook graph."""
    from_node: str
    to_node: str
    on: List[str]  # Join conditions like ["ticker=ticker"]
    type: str = "left"  # Join type


class NotebookGraph:
    """
    Represents the data subgraph for a notebook.

    A notebook graph is a subgraph extracted from backend models,
    containing only the nodes and edges needed for the notebook's exhibits.
    """

    def __init__(self):
        """Initialize empty graph."""
        self.nodes: Dict[str, GraphNode] = {}
        self.edges: List[GraphEdge] = []
        self._adjacency: Dict[str, List[str]] = {}

    def add_node(self, node: GraphNode) -> None:
        """
        Add a node to the graph.

        Args:
            node: Graph node to add
        """
        self.nodes[node.id] = node
        if node.id not in self._adjacency:
            self._adjacency[node.id] = []

    def add_edge(self, edge: GraphEdge) -> None:
        """
        Add an edge to the graph.

        Args:
            edge: Graph edge to add
        """
        if edge.from_node not in self.nodes:
            raise ValueError(f"Source node not found: {edge.from_node}")
        if edge.to_node not in self.nodes:
            raise ValueError(f"Target node not found: {edge.to_node}")

        self.edges.append(edge)
        self._adjacency[edge.from_node].append(edge.to_node)

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        """
        Get a node by ID.

        Args:
            node_id: Node ID

        Returns:
            Graph node or None if not found
        """
        return self.nodes.get(node_id)

    def get_neighbors(self, node_id: str) -> List[str]:
        """
        Get neighboring nodes.

        Args:
            node_id: Node ID

        Returns:
            List of neighbor node IDs
        """
        return self._adjacency.get(node_id, [])

    def get_edges_from(self, node_id: str) -> List[GraphEdge]:
        """
        Get all edges from a node.

        Args:
            node_id: Node ID

        Returns:
            List of edges
        """
        return [e for e in self.edges if e.from_node == node_id]

    def get_edges_to(self, node_id: str) -> List[GraphEdge]:
        """
        Get all edges to a node.

        Args:
            node_id: Node ID

        Returns:
            List of edges
        """
        return [e for e in self.edges if e.to_node == node_id]

    def find_path(self, from_node: str, to_node: str) -> Optional[List[str]]:
        """
        Find a path between two nodes using BFS.

        Args:
            from_node: Starting node ID
            to_node: Target node ID

        Returns:
            List of node IDs forming the path, or None if no path exists
        """
        if from_node not in self.nodes or to_node not in self.nodes:
            return None

        if from_node == to_node:
            return [from_node]

        visited: Set[str] = set()
        queue: List[tuple] = [(from_node, [from_node])]

        while queue:
            current, path = queue.pop(0)
            if current in visited:
                continue

            visited.add(current)

            for neighbor in self.get_neighbors(current):
                if neighbor == to_node:
                    return path + [neighbor]

                if neighbor not in visited:
                    queue.append((neighbor, path + [neighbor]))

        return None

    def get_subgraph(self, node_ids: List[str]) -> 'NotebookGraph':
        """
        Extract a subgraph containing only specified nodes.

        Args:
            node_ids: List of node IDs to include

        Returns:
            New NotebookGraph containing only specified nodes and their edges
        """
        subgraph = NotebookGraph()

        # Add nodes
        for node_id in node_ids:
            if node_id in self.nodes:
                subgraph.add_node(self.nodes[node_id])

        # Add edges between included nodes
        for edge in self.edges:
            if edge.from_node in node_ids and edge.to_node in node_ids:
                subgraph.add_edge(edge)

        return subgraph

    def validate(self) -> List[str]:
        """
        Validate the graph structure.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Check for orphaned edges
        for edge in self.edges:
            if edge.from_node not in self.nodes:
                errors.append(f"Edge references missing source node: {edge.from_node}")
            if edge.to_node not in self.nodes:
                errors.append(f"Edge references missing target node: {edge.to_node}")

        # Check for nodes without dataframes (when needed)
        for node_id, node in self.nodes.items():
            if node.df is None:
                errors.append(f"Node has no DataFrame: {node_id}")

        return errors

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"NotebookGraph(nodes={len(self.nodes)}, edges={len(self.edges)})"
        )
