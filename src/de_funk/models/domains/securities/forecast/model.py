"""
ForecastModel - Time series forecasting for securities.

This model generates price and volume forecasts using ARIMA, Prophet,
and Random Forest models trained on historical stock data.
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple
from pathlib import Path

from de_funk.models.base.forecast_model import TimeSeriesForecastModel


class ForecastModel(TimeSeriesForecastModel):
    """
    Securities forecast model.

    Forecasts stock prices and volumes using multiple ML models.
    Data is sourced from the stocks model (fact_stock_prices).

    Usage:
        from de_funk.models.domains.securities.forecast import ForecastModel

        model = ForecastModel(connection, storage_cfg, model_cfg)
        model.set_session(session)  # Required for cross-model access

        # Run forecasts for a ticker
        results = model.run_forecast_for_ticker('AAPL')
    """

    def get_source_model_name(self) -> str:
        """Source model for training data."""
        return 'securities.stocks'

    def get_source_table_name(self) -> str:
        """Source table for training data."""
        return 'fact_stock_prices'

    def get_entity_column(self) -> str:
        """Column identifying the entity (ticker)."""
        return 'ticker'

    def get_date_column(self) -> str:
        """
        Column for the date/timestamp.

        Note: fact_stock_prices uses date_id (integer FK to dim_calendar),
        but get_training_data() converts this to trade_date for ML training.
        We return 'trade_date' since that's what the training data provides.
        """
        return 'trade_date'

    def get_training_data(self, entity_id: str, date_from=None, date_to=None, lookback_days=None):
        """
        Get training data for forecasting.

        Overrides base to handle stocks model specifics:
        - fact_stock_prices uses security_id/date_id (not ticker/trade_date)
        - Need to join dim_stock for ticker and convert date_id to trade_date

        Args:
            entity_id: Ticker symbol to forecast
            date_from: Start date (optional)
            date_to: End date (optional)
            lookback_days: Number of days to look back

        Returns:
            DataFrame with columns including 'ticker', 'trade_date', 'close', etc.
        """
        if not self.session:
            raise RuntimeError(
                f"{self.__class__.__name__} requires session for cross-model access. "
                "Call set_session() first."
            )

        # Calculate date_from from lookback_days if provided
        if lookback_days:
            from datetime import datetime, timedelta
            date_from = (datetime.now() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')

        # Load stocks model
        source_model = self.session.load_model('securities.stocks')

        # Get fact and dimension tables
        fact_df = source_model.get_table('fact_stock_prices')
        dim_df = source_model.get_table('dim_stock')

        # Join fact with dim to get ticker
        if self.backend == 'spark':
            from pyspark.sql import functions as F

            # fact_stock_prices now has ticker column directly (no join needed for ticker)
            # Just filter by ticker and security_id to ensure we have matching dim data
            df = fact_df.alias('f').join(
                dim_df.select('security_id').alias('d'),
                F.col('f.security_id') == F.col('d.security_id'),
                'inner'
            ).select('f.*')

            # Filter by ticker (now directly in fact_stock_prices)
            df = df.filter(F.col('ticker') == entity_id)

            # Convert date_id to trade_date (date_id is YYYYMMDD integer)
            df = df.withColumn(
                'trade_date',
                F.to_date(F.col('date_id').cast('string'), 'yyyyMMdd')
            )

            # Filter by date if specified
            if date_from:
                date_from_int = int(date_from.replace('-', ''))
                df = df.filter(F.col('date_id') >= date_from_int)
            if date_to:
                date_to_int = int(date_to.replace('-', ''))
                df = df.filter(F.col('date_id') <= date_to_int)

            # CRITICAL: Deduplicate by date_id to prevent "duplicate keys" error
            # This can happen if dim_stock has duplicate security_id entries
            df = df.dropDuplicates(['date_id'])

            # Order by date
            df = df.orderBy('date_id')

        else:
            # DuckDB/pandas path
            import pandas as pd

            # Convert to pandas if needed
            if hasattr(fact_df, 'df'):
                fact_pdf = fact_df.df()
            elif isinstance(fact_df, pd.DataFrame):
                fact_pdf = fact_df
            else:
                fact_pdf = pd.DataFrame(fact_df)

            if hasattr(dim_df, 'df'):
                dim_pdf = dim_df.df()
            elif isinstance(dim_df, pd.DataFrame):
                dim_pdf = dim_df
            else:
                dim_pdf = pd.DataFrame(dim_df)

            # Merge to get ticker
            df = fact_pdf.merge(
                dim_pdf[['security_id', 'ticker']],
                on='security_id',
                how='inner'
            )

            # Filter by ticker
            df = df[df['ticker'] == entity_id]

            # Convert date_id to trade_date
            df['trade_date'] = pd.to_datetime(df['date_id'].astype(str), format='%Y%m%d')

            # Filter by date
            if date_from:
                date_from_int = int(date_from.replace('-', ''))
                df = df[df['date_id'] >= date_from_int]
            if date_to:
                date_to_int = int(date_to.replace('-', ''))
                df = df[df['date_id'] <= date_to_int]

            # CRITICAL: Deduplicate by date_id to prevent "duplicate keys" error
            df = df.drop_duplicates(subset=['date_id'])

            # Order by date
            df = df.sort_values('date_id')

        return df

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
