"""
TemporalBuilder - Builder for the Temporal (calendar) model.

Builds the temporal silver layer with self-generated calendar data.
This is a foundational model with no dependencies - it generates
dim_calendar directly without needing bronze layer data.
"""

from __future__ import annotations

from typing import Type
import logging

from models.base.builder import BaseModelBuilder, BuilderRegistry, BuildResult

logger = logging.getLogger(__name__)


@BuilderRegistry.register
class TemporalBuilder(BaseModelBuilder):
    """
    Builder for the Temporal model.

    Builds:
    - dim_calendar: Calendar dimension with date attributes

    Dependencies:
    - None (foundational model)

    Note: This model is SELF-GENERATING - it creates the calendar
    dimension directly without needing bronze layer data.
    """

    model_name = "temporal"
    depends_on = []  # No dependencies - foundational model

    def get_model_class(self) -> Type:
        """Return the TemporalModel class."""
        from models.domains.foundation.temporal.model import TemporalModel
        return TemporalModel

    def pre_build(self) -> None:
        """Pre-build hook - no bronze validation needed."""
        if self.context.verbose:
            logger.info(f"  Temporal is self-generating (no bronze dependency)")

    def post_build(self, result: BuildResult) -> None:
        """Log build statistics after completion."""
        if result.success and self.context.verbose:
            logger.info(f"  Temporal build complete: {result.dimensions} dims, {result.facts} facts")
