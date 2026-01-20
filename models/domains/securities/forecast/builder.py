"""
ForecastBuilder - Builder for securities forecast model.

Unlike other builders that load from Bronze → Silver, ForecastBuilder
GENERATES predictions using ML models trained on stocks data.

This integrates forecasting into the standard build pipeline while
maintaining the separation between:
- Generic time series capabilities (TimeSeriesForecastModel)
- Domain-specific configuration (ticker as entity, stocks as source)
"""
from __future__ import annotations

from typing import Type, List, Optional, Dict, Any
from datetime import datetime

from models.base.builder import BaseModelBuilder, BuildResult, BuildContext
from config.logging import get_logger

logger = get_logger(__name__)


class ForecastBuilder(BaseModelBuilder):
    """
    Builder for securities forecast model.

    Forecast is special:
    - Doesn't load from Bronze → Silver transformation
    - GENERATES predictions using ML models
    - Depends on stocks model being built first
    - Can be run as part of silver build OR standalone

    Build modes:
    - full: Train all models for all tickers (slow, comprehensive)
    - incremental: Only forecast tickers with new data since last run
    - sample: Train on subset for testing (uses max_tickers from context)
    """

    model_name = "forecast"
    depends_on = ["temporal", "stocks"]

    # Default forecast configuration
    DEFAULT_MODELS = ["arima_7d", "prophet_7d"]  # Fast models for pipeline builds
    FULL_MODELS = ["arima_7d", "arima_30d", "prophet_7d", "prophet_30d", "random_forest_14d"]

    def __init__(self, context: BuildContext):
        """Initialize builder with context."""
        super().__init__(context)
        self._forecast_models = None
        self._max_tickers = context.max_tickers

    def get_model_class(self) -> Type:
        """Return ForecastModel class."""
        from models.domains.securities.forecast import ForecastModel
        return ForecastModel

    def get_forecast_config(self) -> Dict[str, Any]:
        """
        Get forecast configuration from markdown front matter.

        Returns:
            ML models configuration from forecast.md
        """
        model_config = self.get_model_config()
        return model_config.get("ml_models", {})

    def get_available_tickers(self, limit: Optional[int] = None) -> List[str]:
        """
        Get tickers with price data available for forecasting.

        Uses StocksModel to access the normalized silver layer properly,
        rather than doing raw Delta reads.

        Args:
            limit: Optional limit on number of tickers (top by market cap)

        Returns:
            List of ticker symbols
        """
        try:
            # Use StocksModel to access the silver layer properly
            # This handles the normalized schema (security_id/date_id FKs)
            stocks_model = self._get_stocks_model()

            if limit:
                # Try to get top stocks by market cap
                try:
                    top_stocks = stocks_model.get_top_by_market_cap(limit=limit)
                    if self.spark:
                        return [row["ticker"] for row in top_stocks.select("ticker").collect()]
                    else:
                        return top_stocks["ticker"].tolist()
                except Exception as market_cap_err:
                    # market_cap column may not exist - fall back to random sample
                    logger.warning(f"market_cap not available, using random sample: {market_cap_err}")
                    all_tickers = stocks_model.list_tickers(active_only=False)
                    return all_tickers[:limit] if len(all_tickers) > limit else all_tickers
            else:
                # Get all tickers
                return stocks_model.list_tickers(active_only=False)

        except Exception as e:
            logger.error(f"Failed to get tickers from StocksModel: {e}")
            return []

    def _get_stocks_model(self):
        """
        Get or create a StocksModel instance for reading silver layer.

        Returns:
            StocksModel instance configured with current Spark session
        """
        # CRITICAL: Ensure Spark session is active before any Delta reads
        # The session may have become unregistered between builder executions
        self._ensure_active_session()

        from models.domains.securities.stocks.model import StocksModel
        from core.connection import get_spark_connection

        # Create connection wrapper
        connection = get_spark_connection(self.spark)

        # Load stocks model config
        from config.domain_loader import ModelConfigLoader
        domains_dir = self.repo_root / "domains"
        loader = ModelConfigLoader(domains_dir)
        stocks_config = loader.load_model_config("stocks")

        # Instantiate model
        return StocksModel(
            connection=connection,
            storage_cfg=self.storage_config,
            model_cfg=stocks_config,
            params={},
            repo_root=self.repo_root
        )

    def build(self) -> BuildResult:
        """
        Build forecast model by generating predictions.

        This is different from other builders:
        - Doesn't transform Bronze → Silver
        - Trains ML models and generates predictions
        - Stores forecasts and metrics to Silver layer
        """
        start_time = datetime.now()

        # Ensure Spark session is active for Delta Lake 4.x
        self._ensure_active_session()

        if self.context.dry_run:
            return BuildResult(
                model_name=self.model_name,
                success=True,
                dimensions=1,  # dim_model_registry
                facts=3,  # fact_forecast_price, fact_forecast_volume, fact_forecast_metrics
                rows_written=0,
                duration_seconds=0.0
            )

        try:
            # Get tickers to forecast
            max_tickers = self._max_tickers or 10  # Default to 10 for pipeline builds
            tickers = self.get_available_tickers(limit=max_tickers)

            if not tickers:
                return BuildResult(
                    model_name=self.model_name,
                    success=False,
                    error="No tickers available for forecasting. Build stocks model first."
                )

            logger.info(f"Forecasting {len(tickers)} tickers")

            # Get model configuration
            model_config = self.get_model_config()
            ml_models_config = model_config.get("ml_models", {})

            # Select models to run (use default fast models for pipeline)
            models_to_run = self.DEFAULT_MODELS
            available_models = list(ml_models_config.keys())
            models_to_run = [m for m in models_to_run if m in available_models]

            if not models_to_run:
                models_to_run = available_models[:2]  # First 2 if defaults not available

            logger.info(f"Using forecast models: {models_to_run}")

            # Create forecast model instance
            from models.domains.securities.forecast import ForecastModel
            from models.api.session import UniversalSession
            from core.connection import get_spark_connection

            # Create connection wrapper for Spark session
            connection = get_spark_connection(self.spark)

            # Create session for cross-model access
            session = UniversalSession(
                connection=connection,
                storage_cfg=self.storage_config,
                repo_root=self.repo_root
            )

            forecast_model = ForecastModel(
                connection=connection,
                storage_cfg=self.storage_config,
                model_cfg=model_config,
                repo_root=self.repo_root,
                quiet=True
            )
            forecast_model.set_session(session)

            # Run forecasts
            total_forecasts = 0
            total_models = 0
            errors = []

            for ticker in tickers:
                try:
                    logger.info(f"  Processing ticker: {ticker}")
                    result = forecast_model.run_forecast_for_ticker(
                        ticker=ticker,
                        model_configs=models_to_run
                    )
                    total_forecasts += result.get("forecasts_generated", 0)
                    total_models += result.get("models_trained", 0)

                    # Log validation results
                    validation = result.get("validation", {})
                    if validation:
                        row_count = validation.get("metrics", {}).get("row_count", 0)
                        logger.info(f"    Data: {row_count} rows")
                        if validation.get("warnings"):
                            for w in validation["warnings"]:
                                logger.warning(f"    {w}")

                    if result.get("errors"):
                        errors.extend(result["errors"])
                        for err in result["errors"]:
                            logger.warning(f"    Error: {err}")

                except Exception as e:
                    errors.append(f"{ticker}: {str(e)[:100]}")
                    logger.warning(f"Forecast failed for {ticker}: {e}")

            duration = (datetime.now() - start_time).total_seconds()

            # Log summary
            logger.info(
                f"Forecast complete: {total_models} models trained, "
                f"{total_forecasts} forecasts generated, {len(errors)} errors"
            )

            # Log first few errors for debugging
            if errors:
                logger.warning("First 5 errors:")
                for err in errors[:5]:
                    logger.warning(f"  - {err}")

            return BuildResult(
                model_name=self.model_name,
                success=True,
                dimensions=1,  # dim_model_registry
                facts=3,  # fact_forecast_price, fact_forecast_volume, fact_forecast_metrics
                rows_written=total_forecasts,
                duration_seconds=duration,
                warnings=errors[:5] if errors else []  # First 5 errors as warnings
            )

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(f"Forecast build failed: {e}", exc_info=True)
            return BuildResult(
                model_name=self.model_name,
                success=False,
                error=str(e)[:200],
                duration_seconds=duration
            )

    def validate(self) -> bool:
        """
        Validate that forecast can be built.

        Checks:
        - Stocks model has been built (has price data)
        - Source tables have required columns and data
        - ML model configurations are valid
        """
        from models.domains.securities.forecast.data_validator import StocksSourceValidator

        # Check for price data
        tickers = self.get_available_tickers(limit=1)
        if not tickers:
            logger.warning("No price data available. Build stocks model first.")
            return False

        # Validate source tables
        try:
            stocks_model = self._get_stocks_model()

            # Validate dim_stock
            dim_df = stocks_model.get_table('dim_stock')
            dim_validator = StocksSourceValidator(dim_df, 'dim_stock')
            dim_report = dim_validator.validate()

            if not dim_report.is_valid:
                logger.warning(f"dim_stock validation failed:\n{dim_report.summary()}")
                return False

            logger.info(f"  dim_stock: {dim_report.metrics.get('row_count', 0)} stocks")

            # Validate fact_stock_prices
            fact_df = stocks_model.get_table('fact_stock_prices')
            fact_validator = StocksSourceValidator(fact_df, 'fact_stock_prices')
            fact_report = fact_validator.validate()

            if not fact_report.is_valid:
                logger.warning(f"fact_stock_prices validation failed:\n{fact_report.summary()}")
                return False

            logger.info(f"  fact_stock_prices: {fact_report.metrics.get('row_count', 0)} prices")

        except Exception as e:
            logger.warning(f"Source validation failed: {e}")
            return False

        # Check ML model configs
        ml_config = self.get_forecast_config()
        if not ml_config:
            logger.warning("No ML models configured in forecast.md")
            return False

        return True
