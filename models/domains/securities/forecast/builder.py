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

        Args:
            limit: Optional limit on number of tickers (top by market cap proxy)

        Returns:
            List of ticker symbols
        """
        from pyspark.sql import functions as F
        from pyspark.sql.window import Window
        from models.api.dal import Table, StorageRouter

        # Create router for table reads (handles Delta session issues)
        router = StorageRouter(self.storage_config, self.repo_root)

        # Strategy 1: Get tickers from dim_stock dimension (new schema)
        try:
            dim_table = Table(self.spark, router, "silver.stocks/dims/dim_stock")
            dim_df = dim_table.read()

            if "ticker" in dim_df.columns:
                if limit:
                    # Join with prices to get market cap proxy for sorting
                    prices_table = Table(self.spark, router, "silver.stocks/facts/fact_stock_prices")
                    prices_df = prices_table.read()

                    # Join dim_stock with prices using security_id
                    if "security_id" in dim_df.columns and "security_id" in prices_df.columns:
                        # Get latest price per security
                        window = Window.partitionBy("security_id").orderBy(F.col("date_id").desc())
                        latest_prices = (
                            prices_df.filter(F.col("close").isNotNull() & F.col("volume").isNotNull())
                            .withColumn("rn", F.row_number().over(window))
                            .filter(F.col("rn") == 1)
                            .withColumn("market_cap_proxy", F.col("close") * F.col("volume"))
                            .select("security_id", "market_cap_proxy")
                        )

                        # Join and sort by market cap
                        tickers_df = (
                            dim_df.join(latest_prices, "security_id", "inner")
                            .orderBy(F.col("market_cap_proxy").desc())
                            .select("ticker")
                            .limit(limit)
                        )
                        return [row["ticker"] for row in tickers_df.collect()]

                    # Fallback: just return first N tickers from dimension
                    return [row["ticker"] for row in dim_df.select("ticker").limit(limit).collect()]
                else:
                    return [row["ticker"] for row in dim_df.select("ticker").distinct().collect()]

        except Exception as e:
            logger.warning(f"Failed to read from dim_stock: {e}")

        # Strategy 2: Fallback to old schema with ticker column in prices
        try:
            prices_table = Table(self.spark, router, "silver.stocks/facts/fact_stock_prices")
            df = prices_table.read()

            # Check if ticker column exists (old schema)
            if "ticker" not in df.columns:
                logger.warning("No ticker column in prices and dim_stock not available")
                return []

            if limit:
                window = Window.partitionBy("ticker").orderBy(F.col("trade_date").desc())
                tickers_df = (
                    df.filter(F.col("close").isNotNull() & F.col("volume").isNotNull())
                    .withColumn("rn", F.row_number().over(window))
                    .filter(F.col("rn") == 1)
                    .withColumn("market_cap_proxy", F.col("close") * F.col("volume"))
                    .orderBy(F.col("market_cap_proxy").desc())
                    .select("ticker")
                    .limit(limit)
                )
                return [row["ticker"] for row in tickers_df.collect()]
            else:
                return [row["ticker"] for row in df.select("ticker").distinct().collect()]

        except Exception as e:
            logger.error(f"Failed to get tickers: {e}")
            return []

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

            # Create session for cross-model access
            session = UniversalSession(
                spark=self.spark,
                storage_cfg=self.storage_config,
                repo_root=self.repo_root
            )

            forecast_model = ForecastModel(
                connection=self.spark,
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
                    result = forecast_model.run_forecast_for_ticker(
                        ticker=ticker,
                        model_configs=models_to_run
                    )
                    total_forecasts += result.get("forecasts_generated", 0)
                    total_models += result.get("models_trained", 0)

                    if result.get("errors"):
                        errors.extend(result["errors"])

                except Exception as e:
                    errors.append(f"{ticker}: {str(e)[:50]}")
                    logger.warning(f"Forecast failed for {ticker}: {e}")

            duration = (datetime.now() - start_time).total_seconds()

            # Log summary
            logger.info(
                f"Forecast complete: {total_models} models trained, "
                f"{total_forecasts} forecasts generated, {len(errors)} errors"
            )

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
        - ML model configurations are valid
        """
        # Check for price data
        tickers = self.get_available_tickers(limit=1)
        if not tickers:
            logger.warning("No price data available. Build stocks model first.")
            return False

        # Check ML model configs
        ml_config = self.get_forecast_config()
        if not ml_config:
            logger.warning("No ML models configured in forecast.md")
            return False

        return True
