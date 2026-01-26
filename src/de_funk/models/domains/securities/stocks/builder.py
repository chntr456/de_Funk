"""
StocksBuilder - Builder for the Stocks model.

Builds the stocks silver layer with normalized architecture:
- dim_stock FKs to securities.dim_security (master security dimension)
- fact_dividends and fact_splits as time-series corporate actions
- fact_stock_technicals computed from securities.fact_security_prices

Bronze tables are defined in domains/securities/stocks.md storage.bronze.tables.
"""

from __future__ import annotations

from pathlib import Path
from typing import Type
import logging

from de_funk.models.base.builder import BaseModelBuilder, BuilderRegistry, BuildResult

logger = logging.getLogger(__name__)


@BuilderRegistry.register
class StocksBuilder(BaseModelBuilder):
    """
    Builder for the Stocks model (normalized architecture).

    Builds:
    - dim_stock: Stock dimension (FKs to securities.dim_security and corporate.dim_company)
    - fact_dividends: Dividend distribution history (time-series)
    - fact_splits: Stock split history (time-series)
    - fact_stock_technicals: Technical indicators (computed post-build)

    Dependencies:
    - temporal: For date dimension joins
    - securities: For master dim_security and unified fact_security_prices
    - corporate: For company linkage (optional FK)

    Required bronze tables (from domains/securities/stocks.md):
    - alpha_vantage/listing_status (stock dimension)
    - alpha_vantage/dividends (dividend history)
    - alpha_vantage/splits (split history)

    Note: OHLCV prices are in securities.fact_security_prices (unified).
    Technical indicators are computed from those prices in post_build.
    """

    model_name = "stocks"
    depends_on = ["temporal", "securities", "corporate"]  # Normalized architecture

    def get_model_class(self) -> Type:
        """Return the StocksModel class."""
        from de_funk.models.domains.securities.stocks.model import StocksModel
        return StocksModel

    # pre_build inherited from BaseModelBuilder - reads required tables from config

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
            from de_funk.models.domains.securities.stocks.technicals import compute_technicals

            # Compute technicals using native Spark windowing (no batching needed)
            # CRITICAL: Pass spark session to avoid compute_technicals creating its own
            # session and stopping it (which would kill the shared session for subsequent builds)
            rows_processed = compute_technicals(
                storage_path=storage_root,
                dry_run=False,
                spark=self.spark
            )

            if rows_processed > 0:
                logger.info(f"  ✓ Technical indicators computed ({rows_processed:,} rows)")
            else:
                logger.warning("  ⚠ No rows processed for technicals")

        except Exception as e:
            logger.error(f"  ✗ Failed to compute technicals: {e}")
            # Don't fail the whole build for technicals - prices are still valid
            # User can run compute_technicals manually if needed
