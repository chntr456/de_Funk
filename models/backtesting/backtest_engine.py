"""
Backtest Engine - Core engine for walk-forward backtesting.

Features:
- Walk-forward validation with configurable train/test windows
- Portfolio simulation with position tracking
- Transaction costs and slippage modeling
- Performance metrics calculation
- Results persistence (easily clearable)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, TYPE_CHECKING
import json
import pandas as pd
import numpy as np

from config.logging import get_logger

if TYPE_CHECKING:
    from models.backtesting.strategies import Strategy

logger = get_logger(__name__)


class PositionSide(Enum):
    """Position side."""
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


@dataclass
class Position:
    """Represents a position in a security."""
    ticker: str
    side: PositionSide
    quantity: float
    entry_price: float
    entry_date: datetime
    current_price: float = 0.0
    unrealized_pnl: float = 0.0

    @property
    def market_value(self) -> float:
        """Current market value of position."""
        mult = 1 if self.side == PositionSide.LONG else -1
        return mult * self.quantity * self.current_price

    def update_price(self, price: float) -> None:
        """Update position with new price."""
        self.current_price = price
        if self.side == PositionSide.LONG:
            self.unrealized_pnl = (price - self.entry_price) * self.quantity
        else:
            self.unrealized_pnl = (self.entry_price - price) * self.quantity


@dataclass
class Trade:
    """Represents an executed trade."""
    ticker: str
    side: str  # 'buy' or 'sell'
    quantity: float
    price: float
    timestamp: datetime
    commission: float = 0.0
    slippage: float = 0.0
    pnl: float = 0.0  # Realized P&L (for closing trades)

    @property
    def total_cost(self) -> float:
        """Total cost including commission and slippage."""
        return self.quantity * self.price + self.commission + self.slippage


@dataclass
class BacktestConfig:
    """Configuration for a backtest run."""
    # Time windows
    train_window_days: int = 252  # 1 year of trading days
    test_window_days: int = 21    # 1 month
    step_days: int = 21           # Step forward by 1 month

    # Capital and sizing
    initial_capital: float = 100000.0
    position_size_pct: float = 0.1  # 10% per position
    max_positions: int = 10

    # Costs
    commission_per_trade: float = 0.0
    slippage_pct: float = 0.0  # As percentage of price

    # Risk management
    stop_loss_pct: Optional[float] = None  # e.g., 0.05 = 5% stop
    take_profit_pct: Optional[float] = None

    # Results storage
    results_dir: str = "storage/backtesting"
    save_results: bool = True


@dataclass
class BacktestResult:
    """Results from a backtest run."""
    config: BacktestConfig
    strategy_name: str
    start_date: datetime
    end_date: datetime
    # Performance
    total_return: float = 0.0
    annualized_return: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    # Trade statistics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    avg_trade_pnl: float = 0.0
    # Detailed data
    equity_curve: List[Dict[str, Any]] = field(default_factory=list)
    trades: List[Trade] = field(default_factory=list)
    positions_history: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "strategy_name": self.strategy_name,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "total_return": self.total_return,
            "annualized_return": self.annualized_return,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "win_rate": self.win_rate,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "avg_trade_pnl": self.avg_trade_pnl,
            "equity_curve": self.equity_curve,
            "trades": [
                {
                    "ticker": t.ticker,
                    "side": t.side,
                    "quantity": t.quantity,
                    "price": t.price,
                    "timestamp": t.timestamp.isoformat(),
                    "commission": t.commission,
                    "pnl": t.pnl,
                }
                for t in self.trades
            ],
        }

    def to_dataframe(self) -> pd.DataFrame:
        """Convert equity curve to DataFrame."""
        return pd.DataFrame(self.equity_curve)


class BacktestEngine:
    """
    Core backtesting engine with walk-forward validation.

    Usage:
        engine = BacktestEngine(config)
        engine.load_data(price_data)
        result = engine.run(strategy)

        # Results are persisted and can be cleared
        BacktestEngine.clear_results()
    """

    def __init__(self, config: BacktestConfig = None):
        """
        Initialize backtest engine.

        Args:
            config: Backtest configuration
        """
        self.config = config or BacktestConfig()
        self.data: Optional[pd.DataFrame] = None
        self.tickers: List[str] = []

        # Runtime state
        self.cash: float = 0.0
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.equity_curve: List[Dict[str, Any]] = []

    def load_data(
        self,
        data: pd.DataFrame,
        ticker_col: str = 'ticker',
        date_col: str = 'trade_date',
        price_col: str = 'close'
    ) -> None:
        """
        Load price data for backtesting.

        Args:
            data: DataFrame with price data
            ticker_col: Column name for ticker
            date_col: Column name for date
            price_col: Column name for price
        """
        # Standardize column names
        self.data = data.copy()

        if ticker_col != 'ticker' and ticker_col in self.data.columns:
            self.data = self.data.rename(columns={ticker_col: 'ticker'})
        if date_col != 'date' and date_col in self.data.columns:
            self.data = self.data.rename(columns={date_col: 'date'})
        if price_col != 'close' and price_col in self.data.columns:
            self.data = self.data.rename(columns={price_col: 'close'})

        # Ensure date is datetime
        self.data['date'] = pd.to_datetime(self.data['date'])
        self.data = self.data.sort_values(['ticker', 'date'])

        self.tickers = self.data['ticker'].unique().tolist()

        logger.info(
            f"Loaded data for {len(self.tickers)} tickers, "
            f"{len(self.data)} rows, "
            f"date range: {self.data['date'].min()} to {self.data['date'].max()}"
        )

    def _reset_state(self) -> None:
        """Reset engine state for new backtest."""
        self.cash = self.config.initial_capital
        self.positions = {}
        self.trades = []
        self.equity_curve = []

    def _get_current_equity(self) -> float:
        """Calculate current total equity (cash + positions)."""
        position_value = sum(p.market_value for p in self.positions.values())
        return self.cash + position_value

    def _update_positions(self, prices: Dict[str, float]) -> None:
        """Update position prices and check stop loss / take profit."""
        for ticker, position in list(self.positions.items()):
            if ticker in prices:
                position.update_price(prices[ticker])

                # Check stop loss
                if self.config.stop_loss_pct:
                    pnl_pct = position.unrealized_pnl / (position.entry_price * position.quantity)
                    if pnl_pct <= -self.config.stop_loss_pct:
                        logger.debug(f"Stop loss triggered for {ticker}")
                        self._close_position(ticker, prices[ticker], "stop_loss")

                # Check take profit
                if self.config.take_profit_pct:
                    pnl_pct = position.unrealized_pnl / (position.entry_price * position.quantity)
                    if pnl_pct >= self.config.take_profit_pct:
                        logger.debug(f"Take profit triggered for {ticker}")
                        self._close_position(ticker, prices[ticker], "take_profit")

    def _open_position(
        self,
        ticker: str,
        side: PositionSide,
        price: float,
        current_date: datetime
    ) -> Optional[Trade]:
        """Open a new position."""
        if len(self.positions) >= self.config.max_positions:
            return None

        if ticker in self.positions:
            return None  # Already have position

        # Calculate position size
        position_value = self._get_current_equity() * self.config.position_size_pct
        quantity = position_value / price

        # Calculate costs
        commission = self.config.commission_per_trade
        slippage = price * self.config.slippage_pct

        # Check if we have enough cash
        total_cost = quantity * price + commission + slippage
        if total_cost > self.cash:
            # Reduce size to fit available cash
            quantity = (self.cash - commission - slippage) / price
            if quantity <= 0:
                return None

        # Execute trade
        self.cash -= total_cost
        self.positions[ticker] = Position(
            ticker=ticker,
            side=side,
            quantity=quantity,
            entry_price=price,
            entry_date=current_date,
            current_price=price
        )

        trade = Trade(
            ticker=ticker,
            side='buy' if side == PositionSide.LONG else 'sell',
            quantity=quantity,
            price=price,
            timestamp=current_date,
            commission=commission,
            slippage=slippage
        )
        self.trades.append(trade)

        return trade

    def _close_position(
        self,
        ticker: str,
        price: float,
        reason: str = "signal"
    ) -> Optional[Trade]:
        """Close an existing position."""
        if ticker not in self.positions:
            return None

        position = self.positions[ticker]

        # Calculate P&L
        if position.side == PositionSide.LONG:
            pnl = (price - position.entry_price) * position.quantity
        else:
            pnl = (position.entry_price - price) * position.quantity

        # Calculate costs
        commission = self.config.commission_per_trade
        slippage = price * self.config.slippage_pct

        # Execute trade
        self.cash += position.quantity * price - commission - slippage
        del self.positions[ticker]

        trade = Trade(
            ticker=ticker,
            side='sell' if position.side == PositionSide.LONG else 'buy',
            quantity=position.quantity,
            price=price,
            timestamp=datetime.now(),  # Will be updated in run loop
            commission=commission,
            slippage=slippage,
            pnl=pnl - commission - slippage
        )
        self.trades.append(trade)

        return trade

    def run(
        self,
        strategy: 'Strategy',
        start_date: datetime = None,
        end_date: datetime = None
    ) -> BacktestResult:
        """
        Run backtest with walk-forward validation.

        Args:
            strategy: Trading strategy to test
            start_date: Backtest start date (optional)
            end_date: Backtest end date (optional)

        Returns:
            BacktestResult with performance metrics
        """
        if self.data is None:
            raise ValueError("No data loaded. Call load_data() first.")

        self._reset_state()

        # Determine date range
        if start_date is None:
            start_date = self.data['date'].min() + timedelta(days=self.config.train_window_days)
        if end_date is None:
            end_date = self.data['date'].max()

        logger.info(
            f"Running backtest: {strategy.__class__.__name__} "
            f"from {start_date} to {end_date}"
        )

        # Walk-forward loop
        current_date = start_date
        dates = self.data['date'].unique()
        dates = sorted([d for d in dates if d >= np.datetime64(start_date) and d <= np.datetime64(end_date)])

        for date in dates:
            current_date = pd.Timestamp(date).to_pydatetime()

            # Get data up to current date
            train_start = current_date - timedelta(days=self.config.train_window_days)
            train_data = self.data[
                (self.data['date'] >= train_start) &
                (self.data['date'] < current_date)
            ]

            # Get current prices
            current_prices = self.data[self.data['date'] == date].set_index('ticker')['close'].to_dict()

            # Update positions with current prices
            self._update_positions(current_prices)

            # Get strategy signals
            signals = strategy.generate_signals(
                train_data=train_data,
                current_prices=current_prices,
                positions=self.positions,
                date=current_date
            )

            # Execute signals
            for signal in signals:
                ticker = signal.get('ticker')
                action = signal.get('action')  # 'buy', 'sell', 'close'
                price = current_prices.get(ticker, 0)

                if price <= 0:
                    continue

                if action == 'buy' and ticker not in self.positions:
                    trade = self._open_position(ticker, PositionSide.LONG, price, current_date)
                elif action == 'sell' and ticker not in self.positions:
                    trade = self._open_position(ticker, PositionSide.SHORT, price, current_date)
                elif action == 'close' and ticker in self.positions:
                    trade = self._close_position(ticker, price, "signal")
                    if trade:
                        trade.timestamp = current_date

            # Record equity
            self.equity_curve.append({
                'date': current_date,
                'equity': self._get_current_equity(),
                'cash': self.cash,
                'positions_value': sum(p.market_value for p in self.positions.values()),
                'num_positions': len(self.positions),
            })

        # Calculate results
        result = self._calculate_results(strategy, start_date, end_date)

        # Save results if configured
        if self.config.save_results:
            self._save_results(result)

        return result

    def _calculate_results(
        self,
        strategy: 'Strategy',
        start_date: datetime,
        end_date: datetime
    ) -> BacktestResult:
        """Calculate performance metrics from backtest."""
        from models.backtesting.metrics import BacktestMetrics

        equity_df = pd.DataFrame(self.equity_curve)

        if equity_df.empty:
            return BacktestResult(
                config=self.config,
                strategy_name=strategy.__class__.__name__,
                start_date=start_date,
                end_date=end_date,
            )

        metrics = BacktestMetrics(equity_df, self.trades)

        # Trade statistics
        winning_trades = [t for t in self.trades if t.pnl > 0]
        losing_trades = [t for t in self.trades if t.pnl < 0]
        total_pnl = sum(t.pnl for t in self.trades)

        return BacktestResult(
            config=self.config,
            strategy_name=strategy.__class__.__name__,
            start_date=start_date,
            end_date=end_date,
            total_return=metrics.total_return,
            annualized_return=metrics.annualized_return,
            sharpe_ratio=metrics.sharpe_ratio,
            max_drawdown=metrics.max_drawdown,
            win_rate=len(winning_trades) / len(self.trades) if self.trades else 0,
            total_trades=len(self.trades),
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            avg_trade_pnl=total_pnl / len(self.trades) if self.trades else 0,
            equity_curve=self.equity_curve,
            trades=self.trades,
        )

    def _save_results(self, result: BacktestResult) -> None:
        """Save results to disk."""
        results_dir = Path(self.config.results_dir)
        results_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{result.strategy_name}_{timestamp}.json"

        filepath = results_dir / filename

        with open(filepath, 'w') as f:
            json.dump(result.to_dict(), f, indent=2, default=str)

        logger.info(f"Saved backtest results to {filepath}")

    @staticmethod
    def list_results(results_dir: str = "storage/backtesting") -> List[Dict]:
        """List all saved backtest results."""
        results_dir = Path(results_dir)
        if not results_dir.exists():
            return []

        results = []
        for filepath in results_dir.glob("*.json"):
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                results.append({
                    "file": filepath.name,
                    "strategy": data.get("strategy_name"),
                    "total_return": data.get("total_return"),
                    "sharpe_ratio": data.get("sharpe_ratio"),
                    "total_trades": data.get("total_trades"),
                    "start_date": data.get("start_date"),
                    "end_date": data.get("end_date"),
                })
            except Exception as e:
                logger.warning(f"Error reading {filepath}: {e}")

        return results

    @staticmethod
    def clear_results(results_dir: str = "storage/backtesting") -> int:
        """
        Clear all saved backtest results.

        Returns:
            Number of files cleared
        """
        results_dir = Path(results_dir)
        if not results_dir.exists():
            return 0

        count = 0
        for filepath in results_dir.glob("*.json"):
            try:
                filepath.unlink()
                count += 1
            except Exception as e:
                logger.warning(f"Error deleting {filepath}: {e}")

        logger.info(f"Cleared {count} backtest result files")
        return count
