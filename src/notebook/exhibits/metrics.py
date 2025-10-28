"""Metric cards exhibit implementation (placeholder)."""

from .base import BaseExhibit


class MetricCardsExhibit(BaseExhibit):
    """Metric cards exhibit - shows summary metrics."""

    def render(self, df, **kwargs):
        """Render metric cards. Implemented in Streamlit app."""
        raise NotImplementedError("Rendering handled by Streamlit app")
