"""
Backtest Metrics - Performance and risk metrics calculation.

Calculates:
- Total return, annualized return
- Sharpe ratio, Sortino ratio
- Max drawdown, Calmar ratio
- Win rate, profit factor
- Various risk-adjusted metrics
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional
import pandas as pd
import numpy as np

from config.logging import get_logger

logger = get_logger(__name__)


@dataclass
class BacktestMetrics:
    """
    Calculate and store backtest performance metrics.

    Usage:
        metrics = BacktestMetrics(equity_df, trades)
        print(f"Sharpe: {metrics.sharpe_ratio:.2f}")
        print(f"Max DD: {metrics.max_drawdown:.2%}")
    """

    def __init__(
        self,
        equity_curve: pd.DataFrame,
        trades: List = None,
        risk_free_rate: float = 0.05,
        trading_days_per_year: int = 252
    ):
        """
        Initialize metrics calculator.

        Args:
            equity_curve: DataFrame with 'date' and 'equity' columns
            trades: List of Trade objects
            risk_free_rate: Annual risk-free rate (default 5%)
            trading_days_per_year: Trading days per year (default 252)
        """
        self.equity_curve = equity_curve
        self.trades = trades or []
        self.risk_free_rate = risk_free_rate
        self.trading_days = trading_days_per_year

        # Calculate metrics
        self._calculate_metrics()

    def _calculate_metrics(self) -> None:
        """Calculate all metrics."""
        if self.equity_curve.empty:
            self._set_empty_metrics()
            return

        equity = self.equity_curve['equity'].values

        # Basic returns
        self.total_return = (equity[-1] - equity[0]) / equity[0] if equity[0] != 0 else 0

        # Daily returns
        daily_returns = pd.Series(equity).pct_change().dropna()

        # Annualized return
        n_days = len(equity)
        if n_days > 1:
            self.annualized_return = (1 + self.total_return) ** (self.trading_days / n_days) - 1
        else:
            self.annualized_return = 0

        # Volatility
        self.daily_volatility = daily_returns.std() if len(daily_returns) > 1 else 0
        self.annualized_volatility = self.daily_volatility * np.sqrt(self.trading_days)

        # Sharpe ratio
        if self.annualized_volatility > 0:
            excess_return = self.annualized_return - self.risk_free_rate
            self.sharpe_ratio = excess_return / self.annualized_volatility
        else:
            self.sharpe_ratio = 0

        # Sortino ratio (downside deviation)
        negative_returns = daily_returns[daily_returns < 0]
        if len(negative_returns) > 0:
            downside_std = negative_returns.std() * np.sqrt(self.trading_days)
            if downside_std > 0:
                self.sortino_ratio = (self.annualized_return - self.risk_free_rate) / downside_std
            else:
                self.sortino_ratio = 0
        else:
            self.sortino_ratio = float('inf') if self.annualized_return > 0 else 0

        # Drawdown calculations
        cumulative = pd.Series(equity)
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max) / running_max
        self.max_drawdown = abs(drawdown.min()) if len(drawdown) > 0 else 0

        # Calmar ratio (return / max drawdown)
        if self.max_drawdown > 0:
            self.calmar_ratio = self.annualized_return / self.max_drawdown
        else:
            self.calmar_ratio = float('inf') if self.annualized_return > 0 else 0

        # Trade metrics
        self._calculate_trade_metrics()

    def _set_empty_metrics(self) -> None:
        """Set all metrics to default empty values."""
        self.total_return = 0
        self.annualized_return = 0
        self.daily_volatility = 0
        self.annualized_volatility = 0
        self.sharpe_ratio = 0
        self.sortino_ratio = 0
        self.max_drawdown = 0
        self.calmar_ratio = 0
        self.win_rate = 0
        self.profit_factor = 0
        self.avg_win = 0
        self.avg_loss = 0
        self.largest_win = 0
        self.largest_loss = 0
        self.avg_trade_duration = 0

    def _calculate_trade_metrics(self) -> None:
        """Calculate trade-based metrics."""
        if not self.trades:
            self.win_rate = 0
            self.profit_factor = 0
            self.avg_win = 0
            self.avg_loss = 0
            self.largest_win = 0
            self.largest_loss = 0
            self.avg_trade_duration = 0
            return

        # Filter to closing trades with P&L
        closing_trades = [t for t in self.trades if hasattr(t, 'pnl') and t.pnl != 0]

        if not closing_trades:
            self._set_empty_metrics()
            return

        pnls = [t.pnl for t in closing_trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]

        # Win rate
        self.win_rate = len(wins) / len(pnls) if pnls else 0

        # Profit factor
        gross_profit = sum(wins) if wins else 0
        gross_loss = abs(sum(losses)) if losses else 0
        if gross_loss > 0:
            self.profit_factor = gross_profit / gross_loss
        else:
            self.profit_factor = float('inf') if gross_profit > 0 else 0

        # Average win/loss
        self.avg_win = np.mean(wins) if wins else 0
        self.avg_loss = np.mean(losses) if losses else 0

        # Largest win/loss
        self.largest_win = max(wins) if wins else 0
        self.largest_loss = min(losses) if losses else 0

        # Placeholder for duration (would need entry/exit matching)
        self.avg_trade_duration = 0

    def summary(self) -> dict:
        """Return summary dictionary of all metrics."""
        return {
            'total_return': round(self.total_return * 100, 2),
            'annualized_return': round(self.annualized_return * 100, 2),
            'annualized_volatility': round(self.annualized_volatility * 100, 2),
            'sharpe_ratio': round(self.sharpe_ratio, 3),
            'sortino_ratio': round(self.sortino_ratio, 3) if self.sortino_ratio != float('inf') else 'inf',
            'max_drawdown': round(self.max_drawdown * 100, 2),
            'calmar_ratio': round(self.calmar_ratio, 3) if self.calmar_ratio != float('inf') else 'inf',
            'win_rate': round(self.win_rate * 100, 1),
            'profit_factor': round(self.profit_factor, 2) if self.profit_factor != float('inf') else 'inf',
            'avg_win': round(self.avg_win, 2),
            'avg_loss': round(self.avg_loss, 2),
            'largest_win': round(self.largest_win, 2),
            'largest_loss': round(self.largest_loss, 2),
        }

    def __repr__(self) -> str:
        return (
            f"BacktestMetrics("
            f"return={self.total_return:.2%}, "
            f"sharpe={self.sharpe_ratio:.2f}, "
            f"max_dd={self.max_drawdown:.2%})"
        )


def calculate_rolling_sharpe(
    returns: pd.Series,
    window: int = 252,
    risk_free_rate: float = 0.05
) -> pd.Series:
    """
    Calculate rolling Sharpe ratio.

    Args:
        returns: Daily returns series
        window: Rolling window size (default 252 = 1 year)
        risk_free_rate: Annual risk-free rate

    Returns:
        Rolling Sharpe ratio series
    """
    daily_rf = risk_free_rate / 252
    excess_returns = returns - daily_rf

    rolling_mean = excess_returns.rolling(window=window).mean()
    rolling_std = excess_returns.rolling(window=window).std()

    rolling_sharpe = rolling_mean / rolling_std * np.sqrt(252)

    return rolling_sharpe


def calculate_var(
    returns: pd.Series,
    confidence: float = 0.95,
    method: str = 'historical'
) -> float:
    """
    Calculate Value at Risk.

    Args:
        returns: Daily returns series
        confidence: Confidence level (default 95%)
        method: 'historical' or 'parametric'

    Returns:
        VaR as positive number (expected loss)
    """
    if method == 'historical':
        var = returns.quantile(1 - confidence)
    else:
        # Parametric (assumes normal distribution)
        from scipy.stats import norm
        var = returns.mean() - norm.ppf(confidence) * returns.std()

    return abs(var)


def calculate_expected_shortfall(
    returns: pd.Series,
    confidence: float = 0.95
) -> float:
    """
    Calculate Expected Shortfall (CVaR).

    Average loss when VaR is breached.

    Args:
        returns: Daily returns series
        confidence: Confidence level

    Returns:
        Expected shortfall as positive number
    """
    var = -calculate_var(returns, confidence)
    es = returns[returns <= var].mean()
    return abs(es) if not np.isnan(es) else 0
