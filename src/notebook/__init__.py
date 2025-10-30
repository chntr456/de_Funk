"""
Notebook module for YAML-based financial modeling notebooks.

This module provides declarative notebook capabilities with:
- Model-centric data definitions
- Complex measures and aggregations
- Dynamic exhibits and visualizations
- Sophisticated filtering
"""

from .schema import (
    NotebookConfig,
    GraphConfig,
    ModelReference,
    Bridge,
    Variable,
    Dimension,
    Measure,
    Exhibit,
)
from .parser import NotebookParser

# NotebookSession is deprecated - use NotebookService from src.services instead
# from .api.notebook_session import NotebookSession

__all__ = [
    "NotebookConfig",
    "GraphConfig",
    "ModelReference",
    "Bridge",
    "Variable",
    "Dimension",
    "Measure",
    "Exhibit",
    "NotebookParser",
]
