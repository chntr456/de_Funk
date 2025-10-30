"""
Base exhibit class.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional
from pyspark.sql import DataFrame

from ..schema import Exhibit


class BaseExhibit(ABC):
    """
    Base class for all exhibits.

    Exhibits are responsible for rendering visualizations in the UI.
    """

    def __init__(self, config: Exhibit):
        """
        Initialize exhibit.

        Args:
            config: Exhibit configuration
        """
        self.config = config

    @abstractmethod
    def render(self, df: DataFrame, **kwargs) -> Any:
        """
        Render the exhibit.

        Args:
            df: Source dataframe with dimensions and measures
            **kwargs: Additional rendering options

        Returns:
            Rendered exhibit (Streamlit component, Plotly figure, etc.)
        """
        pass

    def get_required_columns(self) -> list:
        """
        Get list of required columns for this exhibit.

        Returns:
            List of column names
        """
        columns = []

        # Add dimension columns
        if self.config.x_axis and self.config.x_axis.dimension:
            columns.append(self.config.x_axis.dimension)
        if self.config.color_by:
            columns.append(self.config.color_by)
        if self.config.size_by:
            columns.append(self.config.size_by)

        # Add measure columns
        if self.config.y_axis:
            if self.config.y_axis.measure:
                columns.append(self.config.y_axis.measure)
            if self.config.y_axis.measures:
                columns.extend(self.config.y_axis.measures)

        if self.config.y_axis_left and self.config.y_axis_left.measures:
            columns.extend(self.config.y_axis_left.measures)
        if self.config.y_axis_right and self.config.y_axis_right.measures:
            columns.extend(self.config.y_axis_right.measures)

        # Add table columns
        if self.config.columns:
            columns.extend(self.config.columns)

        return list(set(columns))  # Remove duplicates
