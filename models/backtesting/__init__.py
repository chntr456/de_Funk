"""
Backtesting Module - Walk-forward validation for forecasting models.

Provides:
- BacktestEngine: Core engine for running backtests
- Strategy: Base class for trading strategies
- Built-in strategies: MomentumStrategy, ForecastStrategy
- Metrics: Performance and risk metrics calculation
"""
from __future__ import annotations

from models.backtesting.backtest_engine import (
    BacktestEngine,
    BacktestConfig,
    BacktestResult,
    Position,
    Trade,
)
from models.backtesting.strategies import (
    Strategy,
    MomentumStrategy,
    ForecastStrategy,
    BuyAndHoldStrategy,
)
from models.backtesting.metrics import BacktestMetrics

__all__ = [
    'BacktestEngine',
    'BacktestConfig',
    'BacktestResult',
    'Position',
    'Trade',
    'Strategy',
    'MomentumStrategy',
    'ForecastStrategy',
    'BuyAndHoldStrategy',
    'BacktestMetrics',
]
