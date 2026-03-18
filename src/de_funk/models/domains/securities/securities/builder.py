"""
SecuritiesBuilder - Builder for the master Securities model.

Builds the normalized securities silver layer:
- dim_security: Master security dimension for all tradable instruments
- fact_security_prices: Unified OHLCV price data

Bronze tables defined in domains/securities/securities.md storage.bronze.tables.
"""

from __future__ import annotations

from typing import Type
import logging

from de_funk.models.base.builder import BaseModelBuilder, BuilderRegistry, BuildResult

logger = logging.getLogger(__name__)


@BuilderRegistry.register
class SecuritiesBuilder(BaseModelBuilder):
    """
    Builder for the master Securities model.

    Builds:
    - dim_security: Master security dimension (all tradable instruments)
    - fact_security_prices: Unified OHLCV for all securities

    Dependencies:
    - temporal: For date dimension joins

    Required bronze tables (from domains/securities/securities.md):
    - alpha_vantage/listing_status (all US tickers)
    - alpha_vantage/time_series_daily_adjusted (OHLCV prices)

    Build order: This model builds BEFORE stocks, etfs, options, futures
    since they FK to dim_security.
    """

    model_name = "securities.master"
    depends_on = ["temporal"]  # Securities depends only on temporal

    def get_model_class(self) -> Type:
        """Return the SecuritiesModel class."""
        from de_funk.models.domains.securities.securities.model import SecuritiesModel
        return SecuritiesModel

    def post_build(self, result: BuildResult) -> None:
        """Log build statistics after completion."""
        if result.success and self.context.verbose:
            logger.info(f"  Securities build complete: {result.dimensions} dims, {result.facts} facts")

            # Log security counts by type
            try:
                if hasattr(self, 'model') and self.model:
                    counts = self.model.get_security_count_by_type()
                    if counts:
                        logger.info(f"  Securities by type: {counts}")
            except Exception as e:
                logger.debug(f"Could not get security counts: {e}")
