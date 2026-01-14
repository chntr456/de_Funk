"""
StocksBuilder - Builder for the Stocks model.

Builds the stocks silver layer from bronze securities data.
Independent of other models - company linkage is at query time via ticker.
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
    - None: Builds independently from Bronze - linked to company via ticker at query time
    """

    model_name = "stocks"
    depends_on = []  # No build-time dependencies

    def get_model_class(self) -> Type:
        """Return the StocksModel class."""
        from models.domains.securities.stocks.model import StocksModel
        return StocksModel

    def pre_build(self) -> None:
        """Validate bronze data exists before building."""
        if self.context.verbose:
            logger.info(f"  Checking bronze data for {self.model_name}...")

        # Check for required bronze tables (use storage_config from context)
        from pathlib import Path
        bronze_root = Path(self.context.storage_config["roots"]["bronze"])

        required_paths = [
            bronze_root / "securities_prices_daily",  # Daily OHLCV
        ]

        missing = [p for p in required_paths if not p.exists()]
        if missing and not self.context.dry_run:
            logger.warning(f"  Missing bronze data: {[str(p) for p in missing]}")

    def post_build(self, result: BuildResult) -> None:
        """Log build statistics after completion."""
        if result.success and self.context.verbose:
            logger.info(f"  Stocks build complete: {result.dimensions} dims, {result.facts} facts")
