"""
CompanyBuilder - Builder for the Company model.

Builds the company silver layer from bronze company overview data.
This is a foundational model with no dependencies.
"""

from __future__ import annotations

from typing import Type, List
import logging

from models.base.builder import BaseModelBuilder, BuilderRegistry, BuildResult

logger = logging.getLogger(__name__)


@BuilderRegistry.register
class CompanyBuilder(BaseModelBuilder):
    """
    Builder for the Company model.

    Builds:
    - dim_company: Company dimension with fundamentals

    Dependencies:
    - None (foundational model)
    """

    model_name = "company"
    depends_on = []  # No dependencies - foundational model

    def get_model_class(self) -> Type:
        """Return the CompanyModel class."""
        from models.domain.company.model import CompanyModel
        return CompanyModel

    def pre_build(self) -> None:
        """Validate bronze data exists before building."""
        if self.context.verbose:
            logger.info(f"  Checking bronze data for {self.model_name}...")

        # Check for required bronze tables (paths from storage.json)
        bronze_root = self.repo_root / "storage" / "bronze"

        required_paths = [
            bronze_root / "company_reference",  # Company data from OVERVIEW
        ]

        missing = [p for p in required_paths if not p.exists()]
        if missing and not self.context.dry_run:
            logger.warning(f"  Missing bronze data: {[str(p) for p in missing]}")

    def post_build(self, result: BuildResult) -> None:
        """Log build statistics after completion."""
        if result.success and self.context.verbose:
            logger.info(f"  Company build complete: {result.dimensions} dims, {result.facts} facts")
