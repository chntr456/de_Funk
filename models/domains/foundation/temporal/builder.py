"""
TemporalBuilder - Builder for the Temporal (calendar) model.

Builds the temporal silver layer from seeded calendar data.
This is a foundational model with no dependencies.
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

    Note: Requires calendar_seed to be seeded first via:
        python -m scripts.seed.seed_calendar --storage-path /shared/storage
    """

    model_name = "temporal"
    depends_on = []  # No dependencies - foundational model

    def get_model_class(self) -> Type:
        """Return the TemporalModel class."""
        from models.domains.foundation.temporal.model import TemporalModel
        return TemporalModel

    def pre_build(self) -> None:
        """Validate bronze data exists before building."""
        if self.context.verbose:
            logger.info(f"  Checking bronze data for {self.model_name}...")

        # Check for required bronze tables (use storage_config from context)
        from pathlib import Path
        bronze_root = Path(self.context.storage_config["roots"]["bronze"])

        calendar_seed_path = bronze_root / "calendar_seed"

        if not calendar_seed_path.exists() and not self.context.dry_run:
            logger.warning(
                f"  Missing bronze data: {calendar_seed_path}\n"
                f"  Run: python -m scripts.seed.seed_calendar --storage-path {bronze_root.parent}"
            )

    def post_build(self, result: BuildResult) -> None:
        """Log build statistics after completion."""
        if result.success and self.context.verbose:
            logger.info(f"  Temporal build complete: {result.dimensions} dims, {result.facts} facts")
