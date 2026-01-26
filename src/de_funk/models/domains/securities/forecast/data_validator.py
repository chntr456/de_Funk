"""
ForecastDataValidator - Data validation for securities forecasting.

Validates that training data from stocks model meets requirements for
ARIMA, Prophet, and RandomForest forecasting models.

Usage:
    from models.domains.securities.forecast.data_validator import ForecastDataValidator

    validator = ForecastDataValidator(training_df, ticker='AAPL')
    report = validator.validate()

    if not report.is_valid:
        print(report.summary())
        # Handle validation failure
"""
from __future__ import annotations

from typing import List, Optional, Dict, Any
from models.base.data_validator import DataValidator, ValidationReport

import logging

logger = logging.getLogger(__name__)


class ForecastDataValidator(DataValidator):
    """
    Validator for forecast training data.

    Validates:
    - Required columns for ML training (ticker, trade_date, close, etc.)
    - Minimum data points for meaningful forecasting
    - Price data quality (no negative prices, reasonable ranges)
    - Time series continuity (gaps detection)
    - Technical indicators availability
    """

    # Minimum data points for different model types
    MIN_POINTS_ARIMA = 30
    MIN_POINTS_PROPHET = 60
    MIN_POINTS_RF = 90

    def __init__(
        self,
        df: Any,
        ticker: str,
        model_type: str = 'all',
        lookback_days: int = 60,
        backend: str = 'auto'
    ):
        """
        Initialize forecast data validator.

        Args:
            df: Training data DataFrame
            ticker: Ticker being validated
            model_type: 'arima', 'prophet', 'random_forest', or 'all'
            lookback_days: Expected lookback window
            backend: 'spark', 'pandas', or 'auto'
        """
        super().__init__(df, backend)
        self.ticker = ticker
        self.model_type = model_type.lower()
        self.lookback_days = lookback_days

    def get_required_columns(self) -> List[str]:
        """Required columns for forecast training."""
        return ['ticker', 'trade_date', 'close']

    def get_optional_columns(self) -> List[str]:
        """Optional columns that improve forecast quality."""
        return [
            'open', 'high', 'low', 'volume', 'adjusted_close',
            'sma_20', 'sma_50', 'rsi_14', 'volatility_20d',
            'daily_return'
        ]

    def get_numeric_columns(self) -> List[str]:
        """Columns that should be numeric."""
        return ['close', 'open', 'high', 'low', 'volume']

    def get_date_column(self) -> Optional[str]:
        """Date column for time series validation."""
        return 'trade_date'

    def get_entity_column(self) -> Optional[str]:
        """Entity column (ticker)."""
        return 'ticker'

    def get_valid_ranges(self) -> Dict[str, tuple]:
        """Valid ranges for price columns."""
        return {
            'close': (0.001, 1_000_000),  # Prices should be positive
            'open': (0.001, 1_000_000),
            'high': (0.001, 1_000_000),
            'low': (0.001, 1_000_000),
            'volume': (0, None),  # Volume >= 0
            'rsi_14': (0, 100),  # RSI is 0-100
        }

    def get_min_rows(self) -> int:
        """Minimum rows based on model type."""
        if self.model_type == 'arima':
            return self.MIN_POINTS_ARIMA
        elif self.model_type == 'prophet':
            return self.MIN_POINTS_PROPHET
        elif self.model_type == 'random_forest':
            return self.MIN_POINTS_RF
        else:
            # For 'all', use minimum that satisfies all models
            return self.MIN_POINTS_ARIMA

    def get_null_thresholds(self) -> Dict[str, float]:
        """Allowed null percentages."""
        return {
            'ticker': 0.0,  # No nulls allowed
            'trade_date': 0.0,
            'close': 0.0,  # Close price required
            'open': 0.05,  # 5% nulls OK for other prices
            'high': 0.05,
            'low': 0.05,
            'volume': 0.10,  # 10% nulls OK for volume
        }

    def validate(self) -> ValidationReport:
        """
        Run all validations including forecast-specific checks.

        Returns:
            ValidationReport with forecast-specific validations
        """
        # Run base validations
        report = super().validate()

        # Add forecast-specific validations if base passed
        if report.is_valid:
            self._validate_ticker_match(report)
            self._validate_price_consistency(report)
            self._validate_model_requirements(report)
            self._validate_recent_data(report)

        return report

    def _validate_ticker_match(self, report: ValidationReport):
        """Validate all data is for the expected ticker."""
        if 'ticker' not in self.columns:
            return

        if self.backend == 'spark':
            from pyspark.sql import functions as F
            tickers = [row.ticker for row in self.df.select('ticker').distinct().collect()]
        else:
            tickers = self.df['ticker'].unique().tolist()

        if len(tickers) > 1:
            report.add_error(
                'quality',
                f"Multiple tickers in data: {tickers}. Expected only '{self.ticker}'",
                expected=self.ticker,
                found=tickers
            )
        elif len(tickers) == 1 and tickers[0] != self.ticker:
            report.add_error(
                'quality',
                f"Ticker mismatch: expected '{self.ticker}', found '{tickers[0]}'",
                expected=self.ticker,
                found=tickers[0]
            )

        report.metrics['ticker'] = self.ticker

    def _validate_price_consistency(self, report: ValidationReport):
        """Validate OHLC price relationships."""
        required = {'open', 'high', 'low', 'close'}
        if not required.issubset(self.columns):
            return

        if self.backend == 'spark':
            from pyspark.sql import functions as F

            # Check high >= low
            invalid_hl = self.df.filter(F.col('high') < F.col('low')).count()
            if invalid_hl > 0:
                report.add_warning(
                    'quality',
                    f"{invalid_hl} rows have high < low (data quality issue)",
                    invalid_rows=invalid_hl
                )

            # Check high >= open, close
            invalid_ho = self.df.filter(
                (F.col('high') < F.col('open')) | (F.col('high') < F.col('close'))
            ).count()
            if invalid_ho > 0:
                report.add_warning(
                    'quality',
                    f"{invalid_ho} rows have high < open or close",
                    invalid_rows=invalid_ho
                )

            # Check low <= open, close
            invalid_lo = self.df.filter(
                (F.col('low') > F.col('open')) | (F.col('low') > F.col('close'))
            ).count()
            if invalid_lo > 0:
                report.add_warning(
                    'quality',
                    f"{invalid_lo} rows have low > open or close",
                    invalid_rows=invalid_lo
                )
        else:
            # Pandas checks
            invalid_hl = (self.df['high'] < self.df['low']).sum()
            if invalid_hl > 0:
                report.add_warning('quality', f"{invalid_hl} rows have high < low")

            invalid_ho = ((self.df['high'] < self.df['open']) |
                         (self.df['high'] < self.df['close'])).sum()
            if invalid_ho > 0:
                report.add_warning('quality', f"{invalid_ho} rows have high < open or close")

    def _validate_model_requirements(self, report: ValidationReport):
        """Validate specific model requirements."""
        row_count = self.row_count

        # ARIMA requirements
        if self.model_type in ('arima', 'all'):
            if row_count < self.MIN_POINTS_ARIMA:
                report.add_error(
                    'coverage',
                    f"ARIMA requires {self.MIN_POINTS_ARIMA}+ points, only {row_count} available",
                    required=self.MIN_POINTS_ARIMA,
                    actual=row_count
                )
            report.metrics['arima_eligible'] = row_count >= self.MIN_POINTS_ARIMA

        # Prophet requirements
        if self.model_type in ('prophet', 'all'):
            if row_count < self.MIN_POINTS_PROPHET:
                level = 'error' if self.model_type == 'prophet' else 'warning'
                if level == 'error':
                    report.add_error(
                        'coverage',
                        f"Prophet requires {self.MIN_POINTS_PROPHET}+ points, only {row_count}",
                        required=self.MIN_POINTS_PROPHET,
                        actual=row_count
                    )
                else:
                    report.add_warning(
                        'coverage',
                        f"Prophet requires {self.MIN_POINTS_PROPHET}+ points, only {row_count}",
                        required=self.MIN_POINTS_PROPHET,
                        actual=row_count
                    )
            report.metrics['prophet_eligible'] = row_count >= self.MIN_POINTS_PROPHET

        # RandomForest requirements
        if self.model_type in ('random_forest', 'rf', 'all'):
            if row_count < self.MIN_POINTS_RF:
                level = 'error' if self.model_type in ('random_forest', 'rf') else 'warning'
                if level == 'error':
                    report.add_error(
                        'coverage',
                        f"RandomForest requires {self.MIN_POINTS_RF}+ points, only {row_count}",
                        required=self.MIN_POINTS_RF,
                        actual=row_count
                    )
                else:
                    report.add_warning(
                        'coverage',
                        f"RandomForest requires {self.MIN_POINTS_RF}+ points, only {row_count}",
                        required=self.MIN_POINTS_RF,
                        actual=row_count
                    )
            report.metrics['rf_eligible'] = row_count >= self.MIN_POINTS_RF

    def _validate_recent_data(self, report: ValidationReport):
        """Validate data includes recent dates."""
        date_col = self.get_date_column()
        if date_col not in self.columns:
            return

        from datetime import datetime, timedelta

        if self.backend == 'spark':
            from pyspark.sql import functions as F
            max_date = self.df.agg(F.max(date_col)).collect()[0][0]
        else:
            max_date = self.df[date_col].max()

        # Convert to datetime if needed
        if hasattr(max_date, 'date'):
            max_date = max_date.date()
        elif isinstance(max_date, str):
            max_date = datetime.strptime(max_date, '%Y-%m-%d').date()

        today = datetime.now().date()
        days_stale = (today - max_date).days if max_date else 999

        report.metrics['most_recent_date'] = str(max_date)
        report.metrics['days_stale'] = days_stale

        if days_stale > 30:
            report.add_warning(
                'coverage',
                f"Data is {days_stale} days stale (last date: {max_date})",
                most_recent=str(max_date),
                days_stale=days_stale
            )


class StocksSourceValidator(DataValidator):
    """
    Validator for stocks Silver layer data (source for forecasting).

    Validates the stocks model tables before ForecastBuilder reads them.
    """

    def __init__(self, df: Any, table_name: str, backend: str = 'auto'):
        """
        Initialize stocks source validator.

        Args:
            df: Stocks table DataFrame
            table_name: 'dim_stock' or 'fact_stock_prices'
            backend: 'spark', 'pandas', or 'auto'
        """
        super().__init__(df, backend)
        self.table_name = table_name

    def get_required_columns(self) -> List[str]:
        """Required columns based on table."""
        if self.table_name == 'dim_stock':
            return ['security_id', 'ticker']
        elif self.table_name == 'fact_stock_prices':
            return ['security_id', 'date_id', 'close']
        return []

    def get_optional_columns(self) -> List[str]:
        """Optional columns."""
        if self.table_name == 'dim_stock':
            return ['market_cap', 'shares_outstanding', 'sector', 'industry']
        elif self.table_name == 'fact_stock_prices':
            return ['open', 'high', 'low', 'volume', 'rsi_14', 'sma_20', 'sma_50']
        return []

    def get_numeric_columns(self) -> List[str]:
        """Numeric columns."""
        if self.table_name == 'fact_stock_prices':
            return ['close', 'open', 'high', 'low', 'volume']
        return []

    def get_date_column(self) -> Optional[str]:
        """Date column."""
        if self.table_name == 'fact_stock_prices':
            return 'date_id'  # Integer date
        return None

    def get_entity_column(self) -> Optional[str]:
        """Entity column."""
        return 'security_id'

    def get_min_rows(self) -> int:
        """Minimum rows."""
        if self.table_name == 'dim_stock':
            return 1  # At least one stock
        elif self.table_name == 'fact_stock_prices':
            return 30  # At least 30 price points
        return 1
