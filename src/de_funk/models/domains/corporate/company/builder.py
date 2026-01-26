"""
CompanyBuilder - Builder for the Company model.

Builds the company silver layer from bronze company overview data.
Bronze tables are defined in domains/corporate/company.md storage.bronze.tables.
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

    Required bronze tables (from domains/corporate/company.md):
    - alpha_vantage/company_overview
    """

    model_name = "company"
    depends_on = ["temporal"]  # Requires temporal for date dimension

    def get_model_class(self) -> Type:
        """Return the CompanyModel class."""
        from models.domains.corporate.company.model import CompanyModel
        return CompanyModel

    # pre_build inherited from BaseModelBuilder - reads required tables from config

    def post_build(self, result: BuildResult) -> None:
        """Log build statistics after completion."""
        if result.success and self.context.verbose:
            logger.info(f"  Company build complete: {result.dimensions} dims, {result.facts} facts")
