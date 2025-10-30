"""Table exhibit implementations (placeholder)."""

from .base import BaseExhibit


class DataTableExhibit(BaseExhibit):
    """Data table exhibit."""

    def render(self, df, **kwargs):
        """Render data table. Implemented in Streamlit app."""
        raise NotImplementedError("Rendering handled by Streamlit app")
