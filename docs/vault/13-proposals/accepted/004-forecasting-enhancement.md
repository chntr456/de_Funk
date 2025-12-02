# Proposal: Forecasting Enhancement & Black-Scholes Integration

**Status**: Accepted
**Author**: Claude
**Date**: 2025-11-29
**Updated**: 2025-12-02
**Implemented**: 2025-12-02
**Priority**: High

---

## Summary

This proposal addresses critical issues in the current forecasting system, adds strategy backtesting infrastructure, and implements Black-Scholes option pricing. The forecasting system has several blocking bugs preventing execution, placeholder implementations, and missing features that need to be fixed.

---

## Motivation

### Current State: Critical Issues

The forecasting system analysis revealed **12 significant issues**:

| Issue | Severity | Status |
|-------|----------|--------|
| `from __future__` placement syntax error | BLOCKING | Prevents script execution |
| Missing `get_repo_root` definition | BLOCKING | NameError at runtime |
| RandomForest returns all zeros | BROKEN | Placeholder implementation |
| Metrics calculation returns all zeros | BROKEN | Placeholder implementation |
| Missing Prophet library | CRITICAL | Optional dependency not installed |
| Missing pmdarima (auto_arima) | CRITICAL | Optional dependency not installed |
| Unconditional PySpark import | CRITICAL | Breaks DuckDB-only usage |
| Deprecated model dependencies (equity/corporate) | BROKEN | v2.0 migration incomplete |
| Options model missing measures.py | INCOMPLETE | No Greeks calculations |
| No backtesting infrastructure | MISSING | Can't validate forecasts |
| No Black-Scholes implementation | MISSING | Can't price options |
| v1.x config (not modular) | TECHNICAL DEBT | Not aligned with v2.0 |

### Affected Files

```
scripts/forecast/
├── run_forecasts.py              ← SyntaxError line 18, NameError line 110
└── run_forecasts_large_cap.py    ← SyntaxError line 33, NameError line 190

models/
├── base/forecast_model.py        ← Placeholder zeros in RF and metrics
└── implemented/
    ├── forecast/
    │   └── company_forecast_model.py  ← Hard PySpark dependency
    └── options/
        └── measures.py           ← MISSING (referenced in config)

configs/models/
├── forecast.yaml                 ← References deprecated equity/corporate
└── options/measures.yaml         ← References non-existent Python measures
```

---

## Detailed Design

### Part 1: Bug Fixes (Immediate)

#### Fix 1: Syntax Error in Forecast Scripts

**Problem**: `from __future__ import annotations` must be first import.

**Files**:
- `scripts/forecast/run_forecasts.py:18`
- `scripts/forecast/run_forecasts_large_cap.py:33`

**Fix**:
```python
# BEFORE (broken)
import sys
from pathlib import Path

from __future__ import annotations  # ← SyntaxError!

# AFTER (correct)
from __future__ import annotations  # ← Must be first!

import sys
from pathlib import Path
```

#### Fix 2: Missing get_repo_root Import

**Problem**: Script uses `get_repo_root()` without importing it.

**Fix**:
```python
# BEFORE
from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()
# ... later ...
config_root = get_repo_root() / "configs"  # ← NameError!

# AFTER
from utils.repo import setup_repo_imports, get_repo_root
repo_root = setup_repo_imports()
# ... later ...
config_root = get_repo_root() / "configs"  # ✓ Works
```

#### Fix 3: Update Deprecated Model Dependencies

**Problem**: `forecast.yaml` references deprecated models.

**File**: `configs/models/forecast.yaml`

```yaml
# BEFORE
depends_on:
  - core
  - equity      # ← DEPRECATED
  - corporate   # ← DEPRECATED

# AFTER
depends_on:
  - core
  - stocks      # v2.0 replacement for equity
  - company     # v2.0 replacement for corporate
```

#### Fix 4: Optional PySpark Import

**Problem**: Unconditional PySpark import breaks DuckDB-only usage.

**File**: `models/implemented/forecast/company_forecast_model.py`

```python
# BEFORE
from pyspark.sql import DataFrame, Row  # ← Fails without Spark!

# AFTER
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyspark.sql import DataFrame, Row

try:
    from pyspark.sql import DataFrame as SparkDataFrame, Row
    HAS_SPARK = True
except ImportError:
    HAS_SPARK = False
    SparkDataFrame = None
    Row = None
```

### Part 2: Implement Missing Functionality

#### RandomForest Forecasting (Currently Placeholder)

**File**: `models/base/forecast_model.py`

```python
def _generate_rf_forecast(
    self,
    model: object,
    metadata: Dict,
    forecast_horizon: int
) -> pd.DataFrame:
    """
    Generate multi-step RandomForest forecast using iterative prediction.

    Uses lag features to generate recursive forecasts.
    """
    from sklearn.ensemble import RandomForestRegressor

    # Get historical data
    history = metadata.get('training_data', pd.DataFrame())
    if history.empty:
        raise ValueError("No training data for RF forecast")

    # Extract features
    target_col = metadata.get('target_column', 'close')
    date_col = metadata.get('date_column', 'date')

    # Build lag features
    lags = metadata.get('lag_features', [1, 2, 3, 5, 10, 20])
    df = history.copy()
    for lag in lags:
        df[f'lag_{lag}'] = df[target_col].shift(lag)
    df = df.dropna()

    feature_cols = [f'lag_{lag}' for lag in lags]
    X = df[feature_cols].values
    y = df[target_col].values

    # Iterative forecasting
    last_values = list(df[target_col].tail(max(lags)).values)
    predictions = []

    for step in range(forecast_horizon):
        # Build feature vector from recent values
        features = [last_values[-(lag)] if lag <= len(last_values) else 0
                   for lag in lags]

        # Predict
        pred = model.predict([features])[0]
        predictions.append(pred)

        # Update history
        last_values.append(pred)

    # Build forecast DataFrame
    last_date = df[date_col].max()
    forecast_dates = pd.date_range(
        start=last_date + pd.Timedelta(days=1),
        periods=forecast_horizon,
        freq='D'
    )

    # Calculate confidence intervals (using OOB error if available)
    std_error = getattr(model, 'oob_score_', 0.1) * np.std(y)

    return pd.DataFrame({
        'forecast_date': forecast_dates,
        'predicted_value': predictions,
        'lower_bound': [p - 1.96 * std_error for p in predictions],
        'upper_bound': [p + 1.96 * std_error for p in predictions],
        'model_type': 'RandomForest',
        'confidence_level': 0.95,
    })
```

#### Metrics Calculation (Currently Placeholder)

```python
def calculate_metrics(
    self,
    model: object,
    metadata: Dict,
    holdout_data: Optional[pd.DataFrame] = None
) -> Dict:
    """
    Calculate forecast accuracy metrics on holdout data.

    Metrics:
    - MAE: Mean Absolute Error
    - RMSE: Root Mean Square Error
    - MAPE: Mean Absolute Percentage Error
    - R2: Coefficient of Determination
    - Directional Accuracy: % of correct direction predictions
    """
    import numpy as np
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

    if holdout_data is None or holdout_data.empty:
        # Use cross-validation on training data
        holdout_data = metadata.get('validation_data', pd.DataFrame())

    if holdout_data.empty:
        return self._empty_metrics(metadata)

    target_col = metadata.get('target_column', 'close')
    y_true = holdout_data[target_col].values

    # Generate predictions for holdout period
    y_pred = self._predict_holdout(model, holdout_data, metadata)

    # Calculate metrics
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))

    # MAPE (handle zeros)
    non_zero_mask = y_true != 0
    if non_zero_mask.any():
        mape = np.mean(np.abs((y_true[non_zero_mask] - y_pred[non_zero_mask])
                              / y_true[non_zero_mask])) * 100
    else:
        mape = np.nan

    r2 = r2_score(y_true, y_pred)

    # Directional accuracy
    actual_direction = np.diff(y_true) > 0
    pred_direction = np.diff(y_pred) > 0
    directional_accuracy = np.mean(actual_direction == pred_direction) * 100

    return {
        'mae': float(mae),
        'rmse': float(rmse),
        'mape': float(mape),
        'r2_score': float(r2),
        'directional_accuracy': float(directional_accuracy),
        'num_predictions': len(y_true),
        'avg_error_pct': float(mape),
        'holdout_start': str(holdout_data[metadata.get('date_column', 'date')].min()),
        'holdout_end': str(holdout_data[metadata.get('date_column', 'date')].max()),
    }
```

### Part 3: Backtesting Infrastructure

**New Module**: `models/backtesting/`

```
models/backtesting/
├── __init__.py
├── backtest_engine.py      # Core backtesting logic
├── strategies.py           # Trading strategy definitions
├── metrics.py              # Performance metrics
└── results.py              # Results storage and analysis
```

**File**: `models/backtesting/backtest_engine.py`

```python
"""
Backtest Engine for Strategy Validation.

Supports:
- Walk-forward validation
- Rolling window backtests
- Multiple strategy comparison
- Transaction cost modeling
- Drawdown analysis
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable, Any
from datetime import date, datetime
import pandas as pd
import numpy as np
from abc import ABC, abstractmethod

@dataclass
class BacktestConfig:
    """Configuration for a backtest run."""
    start_date: date
    end_date: date
    initial_capital: float = 100_000.0
    transaction_cost_pct: float = 0.001  # 10 bps
    slippage_pct: float = 0.0005         # 5 bps
    rebalance_frequency: str = 'daily'   # daily, weekly, monthly
    benchmark: str = 'SPY'               # Benchmark for comparison

@dataclass
class Position:
    """Represents a position in the portfolio."""
    ticker: str
    shares: float
    entry_price: float
    entry_date: date
    current_price: float = 0.0

    @property
    def market_value(self) -> float:
        return self.shares * self.current_price

    @property
    def unrealized_pnl(self) -> float:
        return self.shares * (self.current_price - self.entry_price)

@dataclass
class Trade:
    """Represents a completed trade."""
    ticker: str
    side: str           # 'BUY' or 'SELL'
    shares: float
    price: float
    date: date
    commission: float
    slippage: float

@dataclass
class BacktestResult:
    """Results from a backtest run."""
    strategy_name: str
    config: BacktestConfig
    trades: List[Trade]
    daily_returns: pd.Series
    equity_curve: pd.Series
    positions_history: pd.DataFrame

    # Computed metrics
    total_return: float = 0.0
    annualized_return: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    calmar_ratio: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_trade_return: float = 0.0
    num_trades: int = 0


class Strategy(ABC):
    """Abstract base class for trading strategies."""

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def generate_signals(
        self,
        data: pd.DataFrame,
        current_positions: Dict[str, Position]
    ) -> Dict[str, float]:
        """
        Generate trading signals.

        Returns:
            Dict mapping ticker to target weight (0.0 to 1.0)
        """
        pass


class MomentumStrategy(Strategy):
    """Simple momentum strategy based on lookback returns."""

    def __init__(self, lookback_days: int = 20, top_n: int = 5):
        self.lookback_days = lookback_days
        self.top_n = top_n

    @property
    def name(self) -> str:
        return f"Momentum_{self.lookback_days}d_Top{self.top_n}"

    def generate_signals(
        self,
        data: pd.DataFrame,
        current_positions: Dict[str, Position]
    ) -> Dict[str, float]:
        """Select top N momentum stocks."""
        # Calculate returns
        returns = data.groupby('ticker')['close'].pct_change(self.lookback_days)
        latest_returns = returns.groupby(data['ticker']).last()

        # Select top N
        top_tickers = latest_returns.nlargest(self.top_n).index.tolist()

        # Equal weight
        weight = 1.0 / self.top_n
        return {ticker: weight for ticker in top_tickers}


class ForecastStrategy(Strategy):
    """Strategy based on model forecasts."""

    def __init__(self, model, threshold: float = 0.02):
        self.model = model
        self.threshold = threshold  # Minimum predicted return to buy

    @property
    def name(self) -> str:
        return f"Forecast_{self.model.name}"

    def generate_signals(
        self,
        data: pd.DataFrame,
        current_positions: Dict[str, Position]
    ) -> Dict[str, float]:
        """Generate signals from model forecasts."""
        signals = {}

        for ticker in data['ticker'].unique():
            ticker_data = data[data['ticker'] == ticker]
            forecast = self.model.predict(ticker_data, horizon=5)

            expected_return = (forecast['predicted_value'].iloc[-1] /
                             ticker_data['close'].iloc[-1]) - 1

            if expected_return > self.threshold:
                signals[ticker] = expected_return  # Use return as weight

        # Normalize weights
        total = sum(signals.values()) or 1
        return {k: v/total for k, v in signals.items()}


class BacktestEngine:
    """Execute backtests with configurable strategies."""

    def __init__(self, config: BacktestConfig):
        self.config = config
        self.cash = config.initial_capital
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.equity_history: List[Dict] = []

    def run(
        self,
        strategy: Strategy,
        data: pd.DataFrame
    ) -> BacktestResult:
        """
        Run backtest with given strategy.

        Args:
            strategy: Trading strategy to backtest
            data: Historical price data with columns:
                  [ticker, date, open, high, low, close, volume]
        """
        # Filter to date range
        data = data[
            (data['date'] >= self.config.start_date) &
            (data['date'] <= self.config.end_date)
        ].sort_values('date')

        # Get unique dates
        dates = data['date'].unique()

        for current_date in dates:
            day_data = data[data['date'] == current_date]

            # Update position prices
            self._update_positions(day_data)

            # Generate signals
            signals = strategy.generate_signals(day_data, self.positions)

            # Rebalance portfolio
            self._rebalance(signals, day_data, current_date)

            # Record equity
            self._record_equity(current_date)

        # Calculate results
        return self._calculate_results(strategy.name, data)

    def _update_positions(self, day_data: pd.DataFrame):
        """Update position prices with current market data."""
        for ticker, position in self.positions.items():
            ticker_data = day_data[day_data['ticker'] == ticker]
            if not ticker_data.empty:
                position.current_price = ticker_data['close'].iloc[0]

    def _rebalance(
        self,
        target_weights: Dict[str, float],
        day_data: pd.DataFrame,
        current_date: date
    ):
        """Rebalance portfolio to target weights."""
        total_equity = self.cash + sum(
            p.market_value for p in self.positions.values()
        )

        # Close positions not in target
        for ticker in list(self.positions.keys()):
            if ticker not in target_weights:
                self._close_position(ticker, day_data, current_date)

        # Adjust positions to target weights
        for ticker, target_weight in target_weights.items():
            target_value = total_equity * target_weight
            ticker_data = day_data[day_data['ticker'] == ticker]

            if ticker_data.empty:
                continue

            price = ticker_data['close'].iloc[0]
            current_value = self.positions.get(ticker, Position(ticker, 0, 0, current_date)).market_value

            diff_value = target_value - current_value
            shares_to_trade = diff_value / price

            if abs(shares_to_trade) > 0.01:  # Minimum trade size
                self._execute_trade(ticker, shares_to_trade, price, current_date)

    def _execute_trade(
        self,
        ticker: str,
        shares: float,
        price: float,
        current_date: date
    ):
        """Execute a trade with transaction costs."""
        side = 'BUY' if shares > 0 else 'SELL'
        abs_shares = abs(shares)

        # Apply slippage
        slippage = price * self.config.slippage_pct * (1 if side == 'BUY' else -1)
        execution_price = price + slippage

        # Calculate commission
        commission = abs_shares * execution_price * self.config.transaction_cost_pct

        # Update position
        if ticker in self.positions:
            pos = self.positions[ticker]
            if side == 'BUY':
                # Average up
                total_cost = pos.shares * pos.entry_price + abs_shares * execution_price
                pos.shares += abs_shares
                pos.entry_price = total_cost / pos.shares
            else:
                pos.shares -= abs_shares
                if pos.shares <= 0:
                    del self.positions[ticker]
        else:
            self.positions[ticker] = Position(
                ticker=ticker,
                shares=abs_shares,
                entry_price=execution_price,
                entry_date=current_date,
                current_price=price
            )

        # Update cash
        trade_value = abs_shares * execution_price
        self.cash -= trade_value if side == 'BUY' else -trade_value
        self.cash -= commission

        # Record trade
        self.trades.append(Trade(
            ticker=ticker,
            side=side,
            shares=abs_shares,
            price=execution_price,
            date=current_date,
            commission=commission,
            slippage=abs(slippage * abs_shares)
        ))

    def _close_position(self, ticker: str, day_data: pd.DataFrame, current_date: date):
        """Close an entire position."""
        if ticker not in self.positions:
            return

        position = self.positions[ticker]
        ticker_data = day_data[day_data['ticker'] == ticker]

        if not ticker_data.empty:
            price = ticker_data['close'].iloc[0]
            self._execute_trade(ticker, -position.shares, price, current_date)

    def _record_equity(self, current_date: date):
        """Record daily equity value."""
        positions_value = sum(p.market_value for p in self.positions.values())
        total_equity = self.cash + positions_value

        self.equity_history.append({
            'date': current_date,
            'cash': self.cash,
            'positions_value': positions_value,
            'total_equity': total_equity,
            'num_positions': len(self.positions),
        })

    def _calculate_results(self, strategy_name: str, data: pd.DataFrame) -> BacktestResult:
        """Calculate backtest metrics."""
        equity_df = pd.DataFrame(self.equity_history)
        equity_curve = equity_df.set_index('date')['total_equity']

        # Daily returns
        daily_returns = equity_curve.pct_change().dropna()

        # Annualized metrics
        trading_days = 252
        total_return = (equity_curve.iloc[-1] / equity_curve.iloc[0]) - 1
        annualized_return = (1 + total_return) ** (trading_days / len(equity_curve)) - 1

        # Sharpe ratio (assuming 4.5% risk-free rate)
        risk_free_daily = 0.045 / trading_days
        excess_returns = daily_returns - risk_free_daily
        sharpe = np.sqrt(trading_days) * excess_returns.mean() / excess_returns.std()

        # Sortino ratio (downside deviation)
        downside_returns = excess_returns[excess_returns < 0]
        downside_std = downside_returns.std()
        sortino = np.sqrt(trading_days) * excess_returns.mean() / downside_std if downside_std > 0 else 0

        # Max drawdown
        running_max = equity_curve.expanding().max()
        drawdown = (equity_curve - running_max) / running_max
        max_drawdown = drawdown.min()

        # Calmar ratio
        calmar = annualized_return / abs(max_drawdown) if max_drawdown != 0 else 0

        # Trade statistics
        trade_returns = []
        for trade in self.trades:
            if trade.side == 'SELL':
                # Find matching buy
                # Simplified: just track if trade was profitable
                pass

        winning_trades = [t for t in self.trades if t.side == 'SELL']  # Simplified
        win_rate = len(winning_trades) / len(self.trades) if self.trades else 0

        return BacktestResult(
            strategy_name=strategy_name,
            config=self.config,
            trades=self.trades,
            daily_returns=daily_returns,
            equity_curve=equity_curve,
            positions_history=equity_df,
            total_return=total_return,
            annualized_return=annualized_return,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            max_drawdown=max_drawdown,
            calmar_ratio=calmar,
            win_rate=win_rate,
            num_trades=len(self.trades),
        )
```

### Part 4: Black-Scholes Options Pricing

**New File**: `models/implemented/options/measures.py`

```python
"""
Options Measures - Black-Scholes pricing and Greeks calculations.

Implements:
- European option pricing
- Greeks (delta, gamma, theta, vega, rho)
- Implied volatility calculation
- Option strategy payoffs
"""

import numpy as np
from scipy.stats import norm
from scipy.optimize import brentq
from typing import Dict, Tuple, Optional
from dataclasses import dataclass

@dataclass
class OptionParams:
    """Parameters for option pricing."""
    spot: float           # Current stock price
    strike: float         # Strike price
    time_to_expiry: float # Time to expiry in years
    risk_free_rate: float # Annual risk-free rate
    volatility: float     # Annual volatility (sigma)
    dividend_yield: float = 0.0  # Continuous dividend yield


class BlackScholes:
    """Black-Scholes option pricing model."""

    @staticmethod
    def d1(params: OptionParams) -> float:
        """Calculate d1 in Black-Scholes formula."""
        S, K, T, r, sigma, q = (
            params.spot, params.strike, params.time_to_expiry,
            params.risk_free_rate, params.volatility, params.dividend_yield
        )

        if T <= 0 or sigma <= 0:
            return 0.0

        return (np.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))

    @staticmethod
    def d2(params: OptionParams) -> float:
        """Calculate d2 in Black-Scholes formula."""
        return BlackScholes.d1(params) - params.volatility * np.sqrt(params.time_to_expiry)

    @classmethod
    def call_price(cls, params: OptionParams) -> float:
        """Calculate European call option price."""
        S, K, T, r, q = (
            params.spot, params.strike, params.time_to_expiry,
            params.risk_free_rate, params.dividend_yield
        )

        if T <= 0:
            return max(S - K, 0)

        d1 = cls.d1(params)
        d2 = cls.d2(params)

        call = (S * np.exp(-q * T) * norm.cdf(d1) -
                K * np.exp(-r * T) * norm.cdf(d2))
        return call

    @classmethod
    def put_price(cls, params: OptionParams) -> float:
        """Calculate European put option price."""
        S, K, T, r, q = (
            params.spot, params.strike, params.time_to_expiry,
            params.risk_free_rate, params.dividend_yield
        )

        if T <= 0:
            return max(K - S, 0)

        d1 = cls.d1(params)
        d2 = cls.d2(params)

        put = (K * np.exp(-r * T) * norm.cdf(-d2) -
               S * np.exp(-q * T) * norm.cdf(-d1))
        return put

    @classmethod
    def delta(cls, params: OptionParams, option_type: str = 'call') -> float:
        """
        Calculate option delta (sensitivity to spot price).

        Delta ranges:
        - Call: 0 to 1
        - Put: -1 to 0
        """
        d1 = cls.d1(params)
        q = params.dividend_yield
        T = params.time_to_expiry

        if option_type.lower() == 'call':
            return np.exp(-q * T) * norm.cdf(d1)
        else:
            return np.exp(-q * T) * (norm.cdf(d1) - 1)

    @classmethod
    def gamma(cls, params: OptionParams) -> float:
        """
        Calculate option gamma (sensitivity of delta to spot price).

        Gamma is same for calls and puts.
        """
        S, T, sigma, q = (
            params.spot, params.time_to_expiry,
            params.volatility, params.dividend_yield
        )

        if T <= 0 or sigma <= 0:
            return 0.0

        d1 = cls.d1(params)
        return np.exp(-q * T) * norm.pdf(d1) / (S * sigma * np.sqrt(T))

    @classmethod
    def theta(cls, params: OptionParams, option_type: str = 'call') -> float:
        """
        Calculate option theta (time decay).

        Returns daily theta (divide annual by 365).
        """
        S, K, T, r, sigma, q = (
            params.spot, params.strike, params.time_to_expiry,
            params.risk_free_rate, params.volatility, params.dividend_yield
        )

        if T <= 0:
            return 0.0

        d1 = cls.d1(params)
        d2 = cls.d2(params)

        # Common term
        term1 = -(S * sigma * np.exp(-q * T) * norm.pdf(d1)) / (2 * np.sqrt(T))

        if option_type.lower() == 'call':
            theta = (term1
                    + q * S * np.exp(-q * T) * norm.cdf(d1)
                    - r * K * np.exp(-r * T) * norm.cdf(d2))
        else:
            theta = (term1
                    - q * S * np.exp(-q * T) * norm.cdf(-d1)
                    + r * K * np.exp(-r * T) * norm.cdf(-d2))

        return theta / 365  # Daily theta

    @classmethod
    def vega(cls, params: OptionParams) -> float:
        """
        Calculate option vega (sensitivity to volatility).

        Returns vega per 1% change in volatility.
        Vega is same for calls and puts.
        """
        S, T, q = params.spot, params.time_to_expiry, params.dividend_yield

        if T <= 0:
            return 0.0

        d1 = cls.d1(params)
        vega = S * np.exp(-q * T) * norm.pdf(d1) * np.sqrt(T)
        return vega / 100  # Per 1% vol change

    @classmethod
    def rho(cls, params: OptionParams, option_type: str = 'call') -> float:
        """
        Calculate option rho (sensitivity to interest rate).

        Returns rho per 1% change in rates.
        """
        K, T, r = params.strike, params.time_to_expiry, params.risk_free_rate

        if T <= 0:
            return 0.0

        d2 = cls.d2(params)

        if option_type.lower() == 'call':
            rho = K * T * np.exp(-r * T) * norm.cdf(d2)
        else:
            rho = -K * T * np.exp(-r * T) * norm.cdf(-d2)

        return rho / 100  # Per 1% rate change

    @classmethod
    def greeks(cls, params: OptionParams, option_type: str = 'call') -> Dict[str, float]:
        """Calculate all Greeks at once."""
        return {
            'delta': cls.delta(params, option_type),
            'gamma': cls.gamma(params),
            'theta': cls.theta(params, option_type),
            'vega': cls.vega(params),
            'rho': cls.rho(params, option_type),
        }

    @classmethod
    def implied_volatility(
        cls,
        market_price: float,
        params: OptionParams,
        option_type: str = 'call',
        precision: float = 1e-6
    ) -> float:
        """
        Calculate implied volatility from market price.

        Uses Brent's method for root finding.
        """
        def objective(sigma):
            params_copy = OptionParams(
                spot=params.spot,
                strike=params.strike,
                time_to_expiry=params.time_to_expiry,
                risk_free_rate=params.risk_free_rate,
                volatility=sigma,
                dividend_yield=params.dividend_yield
            )
            if option_type.lower() == 'call':
                return cls.call_price(params_copy) - market_price
            else:
                return cls.put_price(params_copy) - market_price

        try:
            # Search between 1% and 500% volatility
            iv = brentq(objective, 0.01, 5.0, xtol=precision)
            return iv
        except ValueError:
            return np.nan  # No valid IV found


class OptionsMeasures:
    """
    Python measures for options model.

    Integrates with YAML measures configuration.
    """

    def __init__(self, model):
        self.model = model
        self.bs = BlackScholes()

    def calculate_option_price(
        self,
        ticker: str = None,
        strike: float = None,
        expiry_date: str = None,
        option_type: str = 'call',
        **kwargs
    ) -> float:
        """Calculate theoretical option price using Black-Scholes."""
        # Get current stock price
        stock_data = self.model.get_underlying_price(ticker)
        spot = stock_data['close'].iloc[-1]

        # Calculate time to expiry
        from datetime import datetime
        expiry = datetime.strptime(expiry_date, '%Y-%m-%d')
        today = datetime.now()
        T = (expiry - today).days / 365.0

        # Get volatility (from historical or implied)
        vol = self._get_volatility(ticker, kwargs.get('vol_lookback_days', 30))

        # Risk-free rate (default or from config)
        r = kwargs.get('risk_free_rate', 0.045)

        params = OptionParams(
            spot=spot,
            strike=strike,
            time_to_expiry=T,
            risk_free_rate=r,
            volatility=vol
        )

        if option_type.lower() == 'call':
            return self.bs.call_price(params)
        else:
            return self.bs.put_price(params)

    def calculate_greeks(
        self,
        ticker: str = None,
        strike: float = None,
        expiry_date: str = None,
        option_type: str = 'call',
        **kwargs
    ) -> Dict[str, float]:
        """Calculate all Greeks for an option."""
        stock_data = self.model.get_underlying_price(ticker)
        spot = stock_data['close'].iloc[-1]

        from datetime import datetime
        expiry = datetime.strptime(expiry_date, '%Y-%m-%d')
        today = datetime.now()
        T = (expiry - today).days / 365.0

        vol = self._get_volatility(ticker, kwargs.get('vol_lookback_days', 30))
        r = kwargs.get('risk_free_rate', 0.045)

        params = OptionParams(
            spot=spot,
            strike=strike,
            time_to_expiry=T,
            risk_free_rate=r,
            volatility=vol
        )

        return self.bs.greeks(params, option_type)

    def calculate_implied_volatility(
        self,
        market_price: float,
        ticker: str = None,
        strike: float = None,
        expiry_date: str = None,
        option_type: str = 'call',
        **kwargs
    ) -> float:
        """Calculate implied volatility from market price."""
        stock_data = self.model.get_underlying_price(ticker)
        spot = stock_data['close'].iloc[-1]

        from datetime import datetime
        expiry = datetime.strptime(expiry_date, '%Y-%m-%d')
        today = datetime.now()
        T = (expiry - today).days / 365.0

        r = kwargs.get('risk_free_rate', 0.045)

        params = OptionParams(
            spot=spot,
            strike=strike,
            time_to_expiry=T,
            risk_free_rate=r,
            volatility=0.2  # Initial guess (will be solved)
        )

        return self.bs.implied_volatility(market_price, params, option_type)

    def _get_volatility(self, ticker: str, lookback_days: int = 30) -> float:
        """Calculate historical volatility."""
        stock_data = self.model.get_underlying_price(ticker)
        returns = stock_data['close'].pct_change().dropna()

        # Annualized volatility
        daily_vol = returns.tail(lookback_days).std()
        annual_vol = daily_vol * np.sqrt(252)

        return annual_vol
```

---

## Implementation Plan

### Phase 1: Bug Fixes (Day 1-2)
1. Fix `from __future__` placement in forecast scripts
2. Add missing `get_repo_root` import
3. Update deprecated model references in `forecast.yaml`
4. Add optional PySpark imports

### Phase 2: Core Functionality (Week 1)
1. Implement proper RandomForest forecasting
2. Implement metrics calculation
3. Add optional Prophet/pmdarima handling
4. Test forecast pipeline end-to-end

### Phase 3: Black-Scholes (Week 2)
1. Create `options/measures.py`
2. Implement pricing and Greeks
3. Add implied volatility solver
4. Integrate with options model

### Phase 4: Backtesting (Week 3-4)
1. Create backtesting module structure
2. Implement BacktestEngine
3. Add built-in strategies
4. Create results storage and visualization

### Phase 5: Integration (Week 5)
1. Add backtesting to notebooks
2. Create strategy comparison dashboard
3. Document API and examples
4. Performance testing

---

## Open Questions

1. Should we support American option pricing (binomial tree)?
2. How to handle missing volatility data for new stocks?
3. Should backtests store results in Bronze/Silver layers?
4. What third-party data sources for options chains?

---

## References

- Black-Scholes Original Paper: https://www.jstor.org/stable/1831029
- Current forecast implementation: `/models/base/forecast_model.py`
- Options model skeleton: `/configs/models/options/`
