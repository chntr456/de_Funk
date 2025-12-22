"""
StocksBuilder - Builder for the Stocks model.

Builds the stocks silver layer from bronze securities data.
Depends on the company model being built first.
"""

from __future__ import annotations

from typing import Type, List
import logging

from models.base.builder import BaseModelBuilder, BuilderRegistry, BuildResult

logger = logging.getLogger(__name__)


@BuilderRegistry.register
class StocksBuilder(BaseModelBuilder):
    """
    Builder for the Stocks model.

    Builds:
    - dim_stock: Stock dimension with ticker info
    - fact_stock_prices: Daily OHLCV data

    Dependencies:
    - company: For company linkage via CIK
    """

    model_name = "stocks"
    depends_on = ["company"]

    def get_model_class(self) -> Type:
        """Return the StocksModel class."""
        from models.domain.stocks.model import StocksModel
        return StocksModel

    def pre_build(self) -> None:
        """Validate bronze data exists before building."""
        if self.context.verbose:
            logger.info(f"  Checking bronze data for {self.model_name}...")

        # Check for required bronze tables
        bronze_root = self.repo_root / "storage" / "bronze" / "alpha_vantage"

        required_paths = [
            bronze_root / "time_series_daily",
            bronze_root / "company_overview",
        ]

        missing = [p for p in required_paths if not p.exists()]
        if missing and not self.context.dry_run:
            logger.warning(f"  Missing bronze data: {[str(p) for p in missing]}")

    def post_build(self, result: BuildResult) -> None:
        """Log build statistics after completion."""
        if result.success and self.context.verbose:
            logger.info(f"  Stocks build complete: {result.dimensions} dims, {result.facts} facts")
