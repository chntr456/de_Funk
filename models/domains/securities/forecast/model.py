"""
ForecastModel - Time series forecasting for securities.

This model generates price and volume forecasts using ARIMA, Prophet,
and Random Forest models trained on historical stock data.
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple
from pathlib import Path

from models.base.forecast_model import TimeSeriesForecastModel


class ForecastModel(TimeSeriesForecastModel):
    """
    Securities forecast model.

    Forecasts stock prices and volumes using multiple ML models.
    Data is sourced from the stocks model (fact_stock_prices).

    Usage:
        from models.domains.securities.forecast import ForecastModel

        model = ForecastModel(connection, storage_cfg, model_cfg)
        model.set_session(session)  # Required for cross-model access

        # Run forecasts for a ticker
        results = model.run_forecast_for_ticker('AAPL')
    """

    def get_source_model_name(self) -> str:
        """Source model for training data."""
        return 'stocks'

    def get_source_table_name(self) -> str:
        """Source table for training data."""
        return 'fact_stock_prices'

    def get_entity_column(self) -> str:
        """Column identifying the entity (ticker)."""
        return 'ticker'

    def get_date_column(self) -> str:
        """Column for the date/timestamp."""
        return 'trade_date'

    def run_forecast_for_ticker(
        self,
        ticker: str,
        model_configs: Optional[list] = None
    ) -> dict:
        """
        Run forecasts for a specific ticker.

        This is an alias for run_forecast_for_entity that uses ticker terminology.

        Args:
            ticker: Stock ticker symbol
            model_configs: Optional list of model config names to run

        Returns:
            Results dictionary with forecasts_generated, models_trained, errors
        """
        return self.run_forecast_for_entity(
            entity_id=ticker,
            model_configs=model_configs
        )
