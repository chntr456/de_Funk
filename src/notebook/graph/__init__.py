"""
Graph query engine for notebooks.

Handles subgraph extraction, cross-model joins, and query building.
"""

from .query_engine import GraphQueryEngine
from .bridge_manager import BridgeManager
from .subgraph import NotebookGraph

__all__ = [
    "GraphQueryEngine",
    "BridgeManager",
    "NotebookGraph",
]
