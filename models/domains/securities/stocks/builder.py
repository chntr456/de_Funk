"""
StocksBuilder - Builder for the Stocks model.

Builds the stocks silver layer from bronze securities data.
Independent of other models - company linkage is at query time via ticker.

Build includes:
1. dim_stock dimension from bronze.company_reference
2. fact_stock_prices from bronze.securities_prices_daily
3. Technical indicators computed on fact_stock_prices (SMA, RSI, Bollinger Bands, etc.)
"""

from __future__ import annotations

from pathlib import Path
from typing import Type
import logging

from models.base.builder import BaseModelBuilder, BuilderRegistry, BuildResult

logger = logging.getLogger(__name__)


@BuilderRegistry.register
class StocksBuilder(BaseModelBuilder):
    """
    Builder for the Stocks model.

    Builds:
    - dim_stock: Stock dimension with ticker info
    - fact_stock_prices: Daily OHLCV data with technical indicators

    Dependencies:
    - temporal: For date dimension joins

    Technical Indicators:
    The post_build step computes technical indicators (SMA, RSI, Bollinger Bands, etc.)
    and adds them as columns to fact_stock_prices.
    """

    model_name = "stocks"
    depends_on = ["temporal"]  # Requires temporal for date dimension

    def get_model_class(self) -> Type:
        """Return the StocksModel class."""
        from models.domains.securities.stocks.model import StocksModel
        return StocksModel

    def pre_build(self) -> None:
        """Validate bronze data exists before building."""
        if self.context.verbose:
            logger.info(f"  Checking bronze data for {self.model_name}...")

        # Check for required bronze tables (use storage_config from context)
        bronze_root = Path(self.context.storage_config["roots"]["bronze"])

        required_paths = [
            bronze_root / "securities_prices_daily",  # Daily OHLCV
        ]

        missing = [p for p in required_paths if not p.exists()]
        if missing and not self.context.dry_run:
            logger.warning(f"  Missing bronze data: {[str(p) for p in missing]}")

    def post_build(self, result: BuildResult) -> None:
        """
        Compute technical indicators after building prices.

        This adds columns like sma_20, sma_50, sma_200, rsi_14, bollinger_*,
        volatility_*, volume_sma_20, volume_ratio to fact_stock_prices.
        """
        if not result.success:
            logger.warning("  Skipping technicals - build failed")
            return

        if self.context.dry_run:
            logger.info("  [DRY RUN] Would compute technical indicators")
            return

        # Get storage root from context
        silver_root = Path(self.context.storage_config["roots"]["silver"])
        storage_root = silver_root.parent  # Go from silver to storage root

        logger.info("  Computing technical indicators...")

        try:
            from scripts.build.compute_technicals import compute_technicals

            # Compute technicals in batches (default 500 tickers per batch)
            rows_processed = compute_technicals(
                storage_path=storage_root,
                batch_size=500,
                dry_run=False
            )

            if rows_processed > 0:
                logger.info(f"  ✓ Technical indicators computed ({rows_processed:,} rows)")
            else:
                logger.warning("  ⚠ No rows processed for technicals")

        except Exception as e:
            logger.error(f"  ✗ Failed to compute technicals: {e}")
            # Don't fail the whole build for technicals - prices are still valid
            # User can run compute_technicals manually if needed
