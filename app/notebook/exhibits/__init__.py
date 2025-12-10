"""
Exhibit system for notebook visualizations.

Provides dynamic, interactive visualizations and the exhibit type registry.
"""

from .base import BaseExhibit
from .renderer import ExhibitRenderer
from .metrics import MetricCardsExhibit
from .charts import (
    LineChartExhibit,
    BarChartExhibit,
    ScatterChartExhibit,
    DualAxisChartExhibit,
)
from .tables import DataTableExhibit
from .layout import LayoutManager
from .registry import (
    ExhibitTypeRegistry,
    ExhibitTypeConfig,
    get_exhibit_registry,
)

__all__ = [
    "BaseExhibit",
    "ExhibitRenderer",
    "MetricCardsExhibit",
    "LineChartExhibit",
    "BarChartExhibit",
    "ScatterChartExhibit",
    "DualAxisChartExhibit",
    "DataTableExhibit",
    "LayoutManager",
    # Registry
    "ExhibitTypeRegistry",
    "ExhibitTypeConfig",
    "get_exhibit_registry",
]
