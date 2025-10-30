"""Layout manager for organizing exhibits (placeholder)."""

from typing import List
from ..schema import Section


class LayoutManager:
    """
    Manages exhibit layout in sections.

    This is a placeholder for future expansion.
    """

    def __init__(self, sections: List[Section]):
        """Initialize layout manager."""
        self.sections = sections

    def render(self):
        """Render layout. Implemented in Streamlit app."""
        raise NotImplementedError("Rendering handled by Streamlit app")
