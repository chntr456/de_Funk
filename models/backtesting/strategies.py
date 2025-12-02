"""
Trading Strategies for Backtesting.

Provides:
- Strategy: Abstract base class for strategies
- MomentumStrategy: Buy winners, sell losers
- ForecastStrategy: Trade based on forecast predictions
- BuyAndHoldStrategy: Simple buy and hold benchmark
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np

from config.logging import get_logger

logger = get_logger(__name__)


class Strategy(ABC):
    """
    Abstract base class for trading strategies.

    Subclasses must implement generate_signals() which returns
    a list of trade signals based on historical data and current state.
    """

    def __init__(self, name: str = None, params: Dict[str, Any] = None):
        """
        Initialize strategy.

        Args:
            name: Strategy name
            params: Strategy parameters
        """
        self.name = name or self.__class__.__name__
        self.params = params or {}

    @abstractmethod
    def generate_signals(
        self,
        train_data: pd.DataFrame,
        current_prices: Dict[str, float],
        positions: Dict[str, Any],
        date: datetime
    ) -> List[Dict[str, Any]]:
        """
        Generate trading signals based on data and current state.

        Args:
            train_data: Historical price data (training window)
            current_prices: Current prices by ticker
            positions: Current positions
            date: Current date

        Returns:
            List of signal dicts with keys:
            - ticker: str
            - action: 'buy', 'sell', or 'close'
            - strength: float (optional, for sizing)
            - reason: str (optional, for logging)
        """
        pass


class BuyAndHoldStrategy(Strategy):
    """
    Simple buy and hold benchmark strategy.

    Buys equally weighted positions in all tickers and holds.
    """

    def __init__(self, tickers: List[str] = None, **kwargs):
        """
        Initialize buy and hold strategy.

        Args:
            tickers: List of tickers to buy (optional, uses all if not specified)
        """
        super().__init__(name="BuyAndHold", **kwargs)
        self.tickers = tickers
        self._initialized = False

    def generate_signals(
        self,
        train_data: pd.DataFrame,
        current_prices: Dict[str, float],
        positions: Dict[str, Any],
        date: datetime
    ) -> List[Dict[str, Any]]:
        """Generate buy signals for all tickers on first day."""
        if self._initialized:
            return []

        self._initialized = True

        # Determine tickers to buy
        tickers = self.tickers or list(current_prices.keys())

        signals = []
        for ticker in tickers:
            if ticker in current_prices and ticker not in positions:
                signals.append({
                    'ticker': ticker,
                    'action': 'buy',
                    'reason': 'buy_and_hold_init'
                })

        logger.debug(f"BuyAndHold: generated {len(signals)} buy signals")
        return signals


class MomentumStrategy(Strategy):
    """
    Momentum strategy - buy recent winners, avoid losers.

    Parameters:
        lookback_days: Period for momentum calculation (default 20)
        top_n: Number of top performers to hold (default 5)
        rebalance_days: Days between rebalancing (default 5)
        threshold: Minimum return to consider (default 0)
    """

    def __init__(
        self,
        lookback_days: int = 20,
        top_n: int = 5,
        rebalance_days: int = 5,
        threshold: float = 0.0,
        **kwargs
    ):
        super().__init__(name="Momentum", **kwargs)
        self.lookback_days = lookback_days
        self.top_n = top_n
        self.rebalance_days = rebalance_days
        self.threshold = threshold
        self._last_rebalance: Optional[datetime] = None
        self._days_since_rebalance = 0

    def generate_signals(
        self,
        train_data: pd.DataFrame,
        current_prices: Dict[str, float],
        positions: Dict[str, Any],
        date: datetime
    ) -> List[Dict[str, Any]]:
        """Generate momentum signals."""
        # Check if we should rebalance
        self._days_since_rebalance += 1

        if self._last_rebalance is not None:
            if self._days_since_rebalance < self.rebalance_days:
                return []

        self._last_rebalance = date
        self._days_since_rebalance = 0

        # Calculate momentum for each ticker
        momentum_scores = {}

        for ticker in train_data['ticker'].unique():
            ticker_data = train_data[train_data['ticker'] == ticker].copy()
            ticker_data = ticker_data.sort_values('date')

            if len(ticker_data) < self.lookback_days:
                continue

            # Get lookback period data
            recent_data = ticker_data.tail(self.lookback_days)

            # Calculate return
            start_price = recent_data['close'].iloc[0]
            end_price = recent_data['close'].iloc[-1]

            if start_price > 0:
                momentum = (end_price - start_price) / start_price
                momentum_scores[ticker] = momentum

        if not momentum_scores:
            return []

        # Rank by momentum
        sorted_tickers = sorted(
            momentum_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        # Select top N above threshold
        top_tickers = [
            t for t, m in sorted_tickers[:self.top_n]
            if m >= self.threshold
        ]

        signals = []

        # Close positions not in top tickers
        for ticker in list(positions.keys()):
            if ticker not in top_tickers:
                signals.append({
                    'ticker': ticker,
                    'action': 'close',
                    'reason': f'momentum_exit (not in top {self.top_n})'
                })

        # Open positions in top tickers
        for ticker in top_tickers:
            if ticker not in positions and ticker in current_prices:
                signals.append({
                    'ticker': ticker,
                    'action': 'buy',
                    'strength': momentum_scores.get(ticker, 0),
                    'reason': f'momentum_entry (rank in top {self.top_n})'
                })

        logger.debug(
            f"Momentum: {len(signals)} signals, "
            f"top tickers: {top_tickers[:3]}..."
        )

        return signals


class ForecastStrategy(Strategy):
    """
    Strategy based on forecast predictions.

    Buys when forecast predicts price increase, sells when predicts decrease.

    Parameters:
        forecast_model: ForecastModel instance for generating predictions
        model_name: Which forecast model to use (e.g., 'arima_7d')
        threshold: Minimum predicted return to trade (default 1%)
        hold_days: Days to hold position before reassessing (default 5)
    """

    def __init__(
        self,
        forecast_model=None,
        model_name: str = 'arima_7d',
        threshold: float = 0.01,
        hold_days: int = 5,
        **kwargs
    ):
        super().__init__(name="Forecast", **kwargs)
        self.forecast_model = forecast_model
        self.model_name = model_name
        self.threshold = threshold
        self.hold_days = hold_days
        self._position_ages: Dict[str, int] = {}
        self._cached_forecasts: Dict[str, float] = {}
        self._last_forecast_date: Optional[datetime] = None

    def set_forecast_model(self, model) -> None:
        """Set the forecast model."""
        self.forecast_model = model

    def _generate_forecasts(
        self,
        train_data: pd.DataFrame,
        tickers: List[str],
        current_prices: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Generate forecasts for all tickers.

        Returns dict of ticker -> predicted return
        """
        predictions = {}

        if self.forecast_model is None:
            # Simple momentum-based fallback if no model
            for ticker in tickers:
                ticker_data = train_data[train_data['ticker'] == ticker]
                if len(ticker_data) >= 5:
                    recent = ticker_data.sort_values('date').tail(5)
                    start = recent['close'].iloc[0]
                    end = recent['close'].iloc[-1]
                    if start > 0:
                        predictions[ticker] = (end - start) / start
            return predictions

        # Use forecast model
        for ticker in tickers:
            try:
                ticker_data = train_data[train_data['ticker'] == ticker]
                if len(ticker_data) < 30:
                    continue

                # Get forecast
                result = self.forecast_model.run_forecast_for_ticker(
                    ticker=ticker,
                    model_configs=[self.model_name]
                )

                # Get predicted price from forecast
                # This would need to be adapted based on actual forecast model output
                if result.get('forecasts_generated', 0) > 0:
                    # Placeholder: use simple momentum as fallback
                    recent = ticker_data.sort_values('date').tail(5)
                    start = recent['close'].iloc[0]
                    end = recent['close'].iloc[-1]
                    if start > 0:
                        predictions[ticker] = (end - start) / start

            except Exception as e:
                logger.debug(f"Forecast failed for {ticker}: {e}")
                continue

        return predictions

    def generate_signals(
        self,
        train_data: pd.DataFrame,
        current_prices: Dict[str, float],
        positions: Dict[str, Any],
        date: datetime
    ) -> List[Dict[str, Any]]:
        """Generate signals based on forecasts."""
        # Update position ages
        for ticker in positions:
            self._position_ages[ticker] = self._position_ages.get(ticker, 0) + 1

        # Clean up ages for closed positions
        for ticker in list(self._position_ages.keys()):
            if ticker not in positions:
                del self._position_ages[ticker]

        # Regenerate forecasts periodically (e.g., every 5 days)
        if (self._last_forecast_date is None or
            (date - self._last_forecast_date).days >= self.hold_days):

            self._cached_forecasts = self._generate_forecasts(
                train_data,
                list(current_prices.keys()),
                current_prices
            )
            self._last_forecast_date = date

        signals = []

        # Check existing positions
        for ticker, position in positions.items():
            age = self._position_ages.get(ticker, 0)

            # Check if holding period is over
            if age >= self.hold_days:
                predicted_return = self._cached_forecasts.get(ticker, 0)

                # Close if forecast is negative or below threshold
                if predicted_return < self.threshold:
                    signals.append({
                        'ticker': ticker,
                        'action': 'close',
                        'reason': f'forecast_exit (pred={predicted_return:.2%})'
                    })
                    self._position_ages[ticker] = 0

        # Check for new positions
        for ticker, predicted_return in self._cached_forecasts.items():
            if ticker not in positions and predicted_return >= self.threshold:
                if ticker in current_prices:
                    signals.append({
                        'ticker': ticker,
                        'action': 'buy',
                        'strength': predicted_return,
                        'reason': f'forecast_entry (pred={predicted_return:.2%})'
                    })

        logger.debug(f"Forecast: {len(signals)} signals")
        return signals
