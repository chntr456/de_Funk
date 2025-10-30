"""Chart exhibit implementations (placeholder)."""

from .base import BaseExhibit


class LineChartExhibit(BaseExhibit):
    """Line chart exhibit."""

    def render(self, df, **kwargs):
        """Render line chart. Implemented in Streamlit app."""
        raise NotImplementedError("Rendering handled by Streamlit app")


class BarChartExhibit(BaseExhibit):
    """Bar chart exhibit."""

    def render(self, df, **kwargs):
        """Render bar chart. Implemented in Streamlit app."""
        raise NotImplementedError("Rendering handled by Streamlit app")


class ScatterChartExhibit(BaseExhibit):
    """Scatter chart exhibit."""

    def render(self, df, **kwargs):
        """Render scatter chart. Implemented in Streamlit app."""
        raise NotImplementedError("Rendering handled by Streamlit app")


class DualAxisChartExhibit(BaseExhibit):
    """Dual axis chart exhibit."""

    def render(self, df, **kwargs):
        """Render dual axis chart. Implemented in Streamlit app."""
        raise NotImplementedError("Rendering handled by Streamlit app")
