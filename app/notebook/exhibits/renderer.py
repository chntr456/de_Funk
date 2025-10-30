"""
Exhibit renderer placeholder.

This module will contain the main exhibit rendering logic.
For now, rendering is handled directly in the Streamlit app.
"""

from typing import Any, Dict
from pyspark.sql import DataFrame

from ..schema import Exhibit, ExhibitType


class ExhibitRenderer:
    """
    Renders exhibits in Streamlit.

    This is a placeholder for future expansion when we want to
    decouple rendering logic from the UI layer.
    """

    def __init__(self):
        """Initialize renderer."""
        self.renderers = {}

    def render(self, exhibit: Exhibit, df: DataFrame) -> Any:
        """
        Render an exhibit.

        Args:
            exhibit: Exhibit configuration
            df: Data for the exhibit

        Returns:
            Rendered exhibit component
        """
        # Future: Dispatch to specific renderer based on exhibit type
        raise NotImplementedError("Use the Streamlit app for rendering")
