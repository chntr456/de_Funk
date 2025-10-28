"""
Exhibit system for notebook visualizations.

Provides dynamic, interactive visualizations.
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
]
