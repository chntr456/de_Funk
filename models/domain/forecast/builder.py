"""
ForecastBuilder - Builder for time series forecast models.

Unlike standard model builders that transform Bronze → Silver,
ForecastBuilder runs ML training on Silver data (from stocks model)
and writes predictions to the forecast Silver layer.

This builder integrates forecast execution into the standard build pipeline.
"""

from __future__ import annotations

from typing import Type, List, Optional
from pathlib import Path
from datetime import datetime
import logging

from models.base.builder import BaseModelBuilder, BuilderRegistry, BuildResult

logger = logging.getLogger(__name__)


@BuilderRegistry.register
class ForecastBuilder(BaseModelBuilder):
    """
    Builder for the Forecast model.

    Executes time series forecasting using ARIMA, Prophet, and RandomForest
    on stock price data from the stocks model.

    Output:
    - fact_forecasts: Predictions with confidence intervals
    - fact_forecast_metrics: Model accuracy metrics (RMSE, MAE, MAPE, R²)
    - fact_model_registry: Trained model metadata

    Dependencies:
    - stocks: For price data (fact_stock_prices)
    """

    model_name = "forecast"
    depends_on = ["stocks"]

    def get_model_class(self) -> Type:
        """Return the CompanyForecastModel class."""
        from models.domain.forecast.company_forecast_model import CompanyForecastModel
        return CompanyForecastModel

    def pre_build(self) -> None:
        """Validate stocks Silver data exists before building."""
        if self.context.verbose:
            logger.info(f"  Checking stocks Silver data for {self.model_name}...")

        # Check for required Silver tables
        silver_root = Path(self.context.storage_config["roots"]["silver"])
        stocks_prices = silver_root / "stocks" / "facts" / "fact_stock_prices"

        if not stocks_prices.exists() and not self.context.dry_run:
            logger.warning(f"  Missing stocks Silver data: {stocks_prices}")
            logger.warning("  Run stocks build first: python -m scripts.build.build_models --models stocks")

    def build(self) -> BuildResult:
        """
        Execute forecast training and prediction.

        Unlike standard models, this doesn't use graph.yaml transformations.
        Instead, it runs ML training on Silver data.

        Returns:
            BuildResult with forecast statistics
        """
        start_time = datetime.now()

        # Validate first
        is_valid, errors = self.validate()
        if not is_valid:
            return BuildResult(
                model_name=self.model_name,
                success=False,
                error="; ".join(errors)
            )

        try:
            # Pre-build hook
            self.pre_build()

            if self.context.dry_run:
                logger.info(f"[DRY RUN] Would run forecast pipeline for {self.model_name}")
                return BuildResult(
                    model_name=self.model_name,
                    success=True,
                    duration_seconds=0.0
                )

            # Run the forecast pipeline
            results = self._run_forecast_pipeline()

            # Calculate duration
            duration = (datetime.now() - start_time).total_seconds()

            # Create result
            result = BuildResult(
                model_name=self.model_name,
                success=results.get('tickers_failed', 0) == 0,
                dimensions=0,  # Forecast has no dimensions
                facts=3,  # fact_forecasts, fact_forecast_metrics, fact_model_registry
                rows_written=results.get('total_forecasts', 0),
                duration_seconds=duration,
                warnings=results.get('errors', [])[:5] if results.get('errors') else []
            )

            # Post-build hook
            self.post_build(result)

            return result

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(f"Forecast build failed: {e}")
            return BuildResult(
                model_name=self.model_name,
                success=False,
                error=str(e),
                duration_seconds=duration
            )

    def _run_forecast_pipeline(self) -> dict:
        """
        Run the forecast pipeline for configured tickers.

        Returns:
            Dictionary with pipeline results
        """
        from config.model_loader import ModelConfigLoader
        from core.connection import ConnectionFactory
        from models.api.session import UniversalSession
        from datapipelines.base.progress_tracker import StepProgressTracker

        # Suppress verbose ML logging
        import logging
        logging.getLogger('cmdstanpy').setLevel(logging.ERROR)
        logging.getLogger('prophet').setLevel(logging.WARNING)

        # Get model class and config
        model_class = self.get_model_class()
        model_config = self.get_model_config()

        # Create connection wrapper
        spark_connection = ConnectionFactory.create("spark", spark_session=self.spark)

        # Create universal session for cross-model access
        session = UniversalSession(
            connection=spark_connection,
            storage_cfg=self.storage_config,
            repo_root=self.repo_root
        )

        # Initialize forecast model
        forecast_model = model_class(
            connection=spark_connection,
            storage_cfg=self.storage_config,
            model_cfg=model_config,
            params={},
            quiet=True  # Use minimal output
        )
        forecast_model.set_session(session)

        # Get tickers to forecast
        tickers = self._get_forecast_tickers()
        if not tickers:
            logger.warning("No tickers available for forecasting")
            return {
                'tickers_processed': 0,
                'tickers_failed': 0,
                'total_forecasts': 0,
                'total_models': 0,
                'errors': ['No tickers with price data available']
            }

        logger.info(f"Running forecasts for {len(tickers)} tickers")

        # Get model configs to run (from YAML)
        ml_models = model_config.get('ml_models', {})
        model_names = list(ml_models.keys()) if ml_models else None

        # Track results
        results = {
            'tickers_processed': 0,
            'tickers_failed': 0,
            'total_forecasts': 0,
            'total_models': 0,
            'errors': []
        }

        # Initialize progress tracker
        tracker = StepProgressTracker(
            total_steps=len(tickers),
            description="Forecasting",
            silent=not self.context.verbose
        )

        for i, ticker in enumerate(tickers, 1):
            tracker.update(i, f"Forecasting {ticker}...")

            try:
                ticker_results = forecast_model.run_forecast_for_ticker(
                    ticker=ticker,
                    model_configs=model_names
                )

                results['tickers_processed'] += 1
                results['total_forecasts'] += ticker_results.get('forecasts_generated', 0)
                results['total_models'] += ticker_results.get('models_trained', 0)

                if ticker_results.get('errors'):
                    results['errors'].extend(ticker_results['errors'])

                tracker.step_complete(f"{ticker} ✓ ({ticker_results.get('models_trained', 0)} models)")

            except Exception as e:
                error_msg = f"{ticker}: {str(e)}"
                logger.error(f"Forecast failed for {ticker}: {e}")
                tracker.step_complete(f"{ticker} ✗")
                results['tickers_failed'] += 1
                results['errors'].append(error_msg)

        tracker.finish(success=results['tickers_failed'] == 0)

        return results

    def _get_forecast_tickers(self) -> List[str]:
        """
        Get tickers to forecast from stocks Silver layer.

        Uses max_tickers from context if set, otherwise gets top 10 by volume.

        Returns:
            List of ticker symbols
        """
        from pyspark.sql import functions as F
        from pyspark.sql.window import Window

        # Determine ticker limit
        max_tickers = self.context.max_tickers or 10  # Default to 10 for forecasts

        # Get stocks Silver path
        silver_root = Path(self.storage_config["roots"]["silver"])
        prices_path = silver_root / "stocks" / "facts" / "fact_stock_prices"

        if not prices_path.exists():
            logger.warning(f"Stocks prices not found at {prices_path}")
            return []

        try:
            df = self.spark.read.parquet(str(prices_path))

            # Get top tickers by volume (proxy for activity/importance)
            window = Window.partitionBy("ticker").orderBy(F.col("trade_date").desc())

            tickers_df = (
                df.filter(F.col("close").isNotNull() & F.col("volume").isNotNull() & (F.col("volume") > 0))
                .withColumn("rn", F.row_number().over(window))
                .filter(F.col("rn") == 1)
                .withColumn("market_cap_proxy", F.col("close") * F.col("volume"))
                .orderBy(F.col("market_cap_proxy").desc())
                .select("ticker")
                .limit(max_tickers)
            )

            tickers = [row.ticker for row in tickers_df.collect()]
            logger.info(f"Selected top {len(tickers)} tickers for forecasting")
            return tickers

        except Exception as e:
            logger.error(f"Error getting forecast tickers: {e}")
            return []

    def post_build(self, result: BuildResult) -> None:
        """Log forecast statistics after completion."""
        if result.success and self.context.verbose:
            logger.info(f"  Forecast complete: {result.rows_written} forecasts generated")
        if result.warnings:
            for warning in result.warnings[:3]:
                logger.warning(f"  {warning}")
