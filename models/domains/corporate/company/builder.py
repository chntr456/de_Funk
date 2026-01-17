"""
CompanyBuilder - Builder for the Company model.

Builds the company silver layer from bronze company overview data.
Uses bronze.alpha_vantage.company_overview (COMPANY_OVERVIEW endpoint).
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
    - temporal: For date dimension joins
    """

    model_name = "company"
    depends_on = ["temporal"]  # Requires temporal for date dimension

    def get_model_class(self) -> Type:
        """Return the CompanyModel class."""
        from models.domains.corporate.company.model import CompanyModel
        return CompanyModel

    def pre_build(self) -> None:
        """Validate bronze data exists before building."""
        if self.context.verbose:
            logger.info(f"  Checking bronze data for {self.model_name}...")

        # Check for required bronze tables (use storage_config from context)
        # Bronze structure: bronze/{provider}/{endpoint}
        from pathlib import Path
        bronze_root = Path(self.context.storage_config["roots"]["bronze"])

        # Reads from company_overview (COMPANY_OVERVIEW endpoint with rich attributes)
        required_paths = [
            bronze_root / "alpha_vantage" / "company_overview",  # Company data from COMPANY_OVERVIEW
        ]

        missing = [p for p in required_paths if not p.exists()]
        if missing and not self.context.dry_run:
            logger.warning(f"  Missing bronze data: {[str(p) for p in missing]}")

    def post_build(self, result: BuildResult) -> None:
        """Log build statistics after completion."""
        if result.success and self.context.verbose:
            logger.info(f"  Company build complete: {result.dimensions} dims, {result.facts} facts")
