"""
Complex measures for stocks model.

These functions are referenced from stocks/measures.yaml via python_measures.
Each function receives the model instance and can access all model data.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)


class StocksMeasures:
    """
    Complex measure calculations for stocks.
    Each method is referenced from stocks/measures.yaml.
    """

    def __init__(self, model):
        """
        Initialize with model instance.

        Args:
            model: StocksModel instance (provides access to data and session)
        """
        self.model = model

    def calculate_sharpe_ratio(
        self,
        ticker: Optional[str] = None,
        filters: Optional[List[Dict]] = None,
        risk_free_rate: float = 0.045,
        window_days: int = 252,
        **kwargs
    ) -> pd.DataFrame:
        """
        Calculate Sharpe ratio for stocks.

        Referenced in YAML as:
          function: "stocks.measures.calculate_sharpe_ratio"

        Args:
            ticker: Specific ticker (optional, calculates for all if None)
            filters: Additional filters to apply
            risk_free_rate: Annual risk-free rate (e.g., 0.045 = 4.5%)
            window_days: Rolling window for calculation

        Returns:
            DataFrame with columns: [ticker, trade_date, sharpe_ratio]
        """
        logger.info(f"Calculating Sharpe ratio (window={window_days}, rf={risk_free_rate})")

        # Get price data
        prices_df = self.model.get_table('fact_stock_prices')

        # Convert to pandas if Spark
        if self.model._backend == 'spark':
            prices_df = prices_df.toPandas()

        # Apply filters
        if ticker:
            prices_df = prices_df[prices_df['ticker'] == ticker]
        if filters:
            # Apply filters using model's filter engine
            prices_df = self.model.session.apply_filters(prices_df, filters)

        # Sort by ticker and date
        prices_df = prices_df.sort_values(['ticker', 'trade_date'])

        # Calculate returns
        prices_df['return'] = prices_df.groupby('ticker')['close'].pct_change()

        # Calculate rolling Sharpe ratio
        daily_rf = (1 + risk_free_rate) ** (1/252) - 1

        def sharpe_for_window(returns):
            """Calculate Sharpe ratio for a window of returns"""
            if len(returns) < 2 or returns.std() == 0:
                return 0
            excess_return = returns.mean() - daily_rf
            return (excess_return / returns.std()) * np.sqrt(252)

        # Calculate rolling Sharpe
        sharpe_values = []
        for ticker_val in prices_df['ticker'].unique():
            ticker_data = prices_df[prices_df['ticker'] == ticker_val].copy()
            ticker_data['sharpe_ratio'] = ticker_data['return'].rolling(
                window=window_days, min_periods=window_days
            ).apply(sharpe_for_window, raw=False)
            sharpe_values.append(ticker_data[['ticker', 'trade_date', 'sharpe_ratio']])

        result_df = pd.concat(sharpe_values, ignore_index=True)
        return result_df.dropna()

    def calculate_correlation_matrix(
        self,
        tickers: Optional[List[str]] = None,
        filters: Optional[List[Dict]] = None,
        window_days: int = 60,
        min_periods: int = 30,
        **kwargs
    ) -> pd.DataFrame:
        """
        Calculate rolling correlation matrix between stocks.

        Args:
            tickers: List of tickers (optional, uses all if None)
            filters: Additional filters
            window_days: Rolling window size
            min_periods: Minimum periods required

        Returns:
            DataFrame with columns: [ticker_1, ticker_2, correlation, as_of_date]
        """
        logger.info(f"Calculating correlation matrix (window={window_days})")

        prices_df = self.model.get_table('fact_stock_prices')

        # Convert to pandas if Spark
        if self.model._backend == 'spark':
            prices_df = prices_df.toPandas()

        # Apply filters
        if tickers:
            prices_df = prices_df[prices_df['ticker'].isin(tickers)]
        if filters:
            prices_df = self.model.session.apply_filters(prices_df, filters)

        # Pivot to wide format (tickers as columns)
        prices_wide = prices_df.pivot(
            index='trade_date',
            columns='ticker',
            values='close'
        )

        # Calculate returns
        returns = prices_wide.pct_change()

        # Calculate rolling correlation
        correlations = []
        dates = returns.index[window_days:]

        for date in dates:
            window_data = returns.loc[:date].tail(window_days)

            if len(window_data) >= min_periods:
                corr_matrix = window_data.corr()

                # Convert to long format (only upper triangle to avoid duplicates)
                for i, ticker_1 in enumerate(corr_matrix.columns):
                    for ticker_2 in corr_matrix.columns[i+1:]:
                        correlations.append({
                            'ticker_1': ticker_1,
                            'ticker_2': ticker_2,
                            'correlation': corr_matrix.loc[ticker_1, ticker_2],
                            'as_of_date': date
                        })

        return pd.DataFrame(correlations)

    def calculate_momentum_score(
        self,
        ticker: Optional[str] = None,
        filters: Optional[List[Dict]] = None,
        weights: Optional[Dict[str, float]] = None,
        **kwargs
    ) -> pd.DataFrame:
        """
        Calculate composite momentum score from multiple factors.

        Args:
            ticker: Specific ticker
            filters: Additional filters
            weights: Dict of factor weights (e.g., {'rsi': 0.3, 'macd': 0.3, ...})

        Returns:
            DataFrame with columns: [ticker, trade_date, momentum_score, ...]
        """
        if weights is None:
            weights = {'rsi': 0.3, 'macd': 0.3, 'price_trend': 0.4}

        logger.info(f"Calculating momentum score with weights: {weights}")

        # Get technical data (includes RSI, MACD, etc.)
        technicals_df = self.model.get_table('fact_stock_technicals')

        # Convert to pandas if Spark
        if self.model._backend == 'spark':
            technicals_df = technicals_df.toPandas()

        # Apply filters
        if ticker:
            technicals_df = technicals_df[technicals_df['ticker'] == ticker]
        if filters:
            technicals_df = self.model.session.apply_filters(technicals_df, filters)

        # Normalize factors to 0-1 scale
        df = technicals_df.copy()

        # RSI is already 0-100, normalize to 0-1
        df['rsi_norm'] = df['rsi_14'] / 100

        # MACD: Normalize by price (to make comparable across stocks)
        # Then scale to 0-1 using min-max
        if 'macd' in df.columns:
            df['macd_pct'] = df['macd'] / df['close']
            df['macd_norm'] = (df['macd_pct'] - df['macd_pct'].min()) / (
                df['macd_pct'].max() - df['macd_pct'].min() + 1e-10
            )
        else:
            df['macd_norm'] = 0.5  # Neutral if not available

        # Price trend: % above/below 50-day SMA
        if 'sma_50' in df.columns:
            df['price_trend'] = (df['close'] - df['sma_50']) / df['sma_50']
            # Clip to [-1, 1] and scale to [0, 1]
            df['price_trend'] = df['price_trend'].clip(-1, 1)
            df['price_trend_norm'] = (df['price_trend'] + 1) / 2
        else:
            df['price_trend_norm'] = 0.5  # Neutral

        # Calculate weighted score
        df['momentum_score'] = (
            df['rsi_norm'].fillna(0.5) * weights.get('rsi', 0) +
            df['macd_norm'].fillna(0.5) * weights.get('macd', 0) +
            df['price_trend_norm'].fillna(0.5) * weights.get('price_trend', 0)
        )

        # Clip to [0, 1] range
        df['momentum_score'] = df['momentum_score'].clip(0, 1)

        return df[['ticker', 'trade_date', 'momentum_score',
                   'rsi_norm', 'macd_norm', 'price_trend_norm']]

    def calculate_sector_rotation(
        self,
        filters: Optional[List[Dict]] = None,
        lookback_days: int = 20,
        threshold: float = 0.1,
        **kwargs
    ) -> pd.DataFrame:
        """
        Calculate sector rotation signals.

        Args:
            filters: Additional filters
            lookback_days: Lookback period for momentum
            threshold: Threshold for signal generation (10% = 0.1)

        Returns:
            DataFrame with columns: [sector, trade_date, signal, momentum]
        """
        logger.info(f"Calculating sector rotation (lookback={lookback_days})")

        # Get stock dimension (for sector) and prices
        dim_stock = self.model.get_table('dim_stock')
        prices_df = self.model.get_table('fact_stock_prices')

        # Convert to pandas if Spark
        if self.model._backend == 'spark':
            dim_stock = dim_stock.toPandas()
            prices_df = prices_df.toPandas()

        # Merge to get sector for each ticker
        df = prices_df.merge(dim_stock[['ticker', 'sector']], on='ticker', how='inner')

        # Apply filters
        if filters:
            df = self.model.session.apply_filters(df, filters)

        # Remove rows without sector
        df = df[df['sector'].notna()]

        # Sort by sector, ticker, date
        df = df.sort_values(['sector', 'ticker', 'trade_date'])

        # Calculate returns for each stock
        df['return'] = df.groupby(['sector', 'ticker'])['close'].pct_change()

        # Aggregate to sector level (equal-weighted within sector)
        sector_returns = df.groupby(['sector', 'trade_date'])['return'].mean().reset_index()

        # Calculate rolling momentum for each sector
        sector_returns = sector_returns.sort_values(['sector', 'trade_date'])
        sector_returns['momentum'] = sector_returns.groupby('sector')['return'].rolling(
            window=lookback_days, min_periods=lookback_days
        ).mean().reset_index(drop=True)

        # Generate signals based on momentum
        sector_returns['signal'] = 'HOLD'
        sector_returns.loc[sector_returns['momentum'] > threshold, 'signal'] = 'BUY'
        sector_returns.loc[sector_returns['momentum'] < -threshold, 'signal'] = 'SELL'

        return sector_returns[['sector', 'trade_date', 'signal', 'momentum']].dropna()

    def calculate_rolling_beta(
        self,
        ticker: Optional[str] = None,
        filters: Optional[List[Dict]] = None,
        market_ticker: str = 'SPY',
        window_days: int = 252,
        **kwargs
    ) -> pd.DataFrame:
        """
        Calculate rolling beta vs. market index.

        Args:
            ticker: Specific ticker
            filters: Additional filters
            market_ticker: Market index ticker (default: SPY)
            window_days: Rolling window size

        Returns:
            DataFrame with columns: [ticker, trade_date, beta]
        """
        logger.info(f"Calculating rolling beta vs. {market_ticker} (window={window_days})")

        prices_df = self.model.get_table('fact_stock_prices')

        # Convert to pandas if Spark
        if self.model._backend == 'spark':
            prices_df = prices_df.toPandas()

        # Apply filters
        if ticker:
            prices_df = prices_df[prices_df['ticker'] == ticker]
        if filters:
            prices_df = self.model.session.apply_filters(prices_df, filters)

        # Get market returns
        market_prices = prices_df[prices_df['ticker'] == market_ticker].copy()
        market_prices = market_prices.sort_values('trade_date')
        market_prices['market_return'] = market_prices['close'].pct_change()

        # Get stock returns
        stock_tickers = prices_df[prices_df['ticker'] != market_ticker]['ticker'].unique()

        beta_results = []
        for stock_ticker in stock_tickers:
            stock_prices = prices_df[prices_df['ticker'] == stock_ticker].copy()
            stock_prices = stock_prices.sort_values('trade_date')
            stock_prices['stock_return'] = stock_prices['close'].pct_change()

            # Merge with market returns
            merged = stock_prices[['trade_date', 'stock_return']].merge(
                market_prices[['trade_date', 'market_return']],
                on='trade_date',
                how='inner'
            )

            # Calculate rolling beta
            def calc_beta(window_data):
                """Calculate beta for a window"""
                if len(window_data) < 30:
                    return np.nan
                cov = np.cov(window_data['stock_return'], window_data['market_return'])[0, 1]
                var = np.var(window_data['market_return'])
                return cov / var if var > 0 else np.nan

            merged = merged.sort_values('trade_date')
            merged['beta'] = merged.rolling(window=window_days, min_periods=30).apply(
                lambda w: calc_beta(merged.iloc[w.index]), raw=False
            )

            merged['ticker'] = stock_ticker
            beta_results.append(merged[['ticker', 'trade_date', 'beta']])

        if beta_results:
            return pd.concat(beta_results, ignore_index=True).dropna()
        else:
            return pd.DataFrame(columns=['ticker', 'trade_date', 'beta'])

    def calculate_drawdown(
        self,
        ticker: Optional[str] = None,
        filters: Optional[List[Dict]] = None,
        window_days: int = 252,
        **kwargs
    ) -> pd.DataFrame:
        """
        Calculate maximum drawdown from peak.

        Args:
            ticker: Specific ticker
            filters: Additional filters
            window_days: Rolling window for peak calculation

        Returns:
            DataFrame with columns: [ticker, trade_date, drawdown, peak_price]
        """
        logger.info(f"Calculating drawdown (window={window_days})")

        prices_df = self.model.get_table('fact_stock_prices')

        # Convert to pandas if Spark
        if self.model._backend == 'spark':
            prices_df = prices_df.toPandas()

        # Apply filters
        if ticker:
            prices_df = prices_df[prices_df['ticker'] == ticker]
        if filters:
            prices_df = self.model.session.apply_filters(prices_df, filters)

        # Sort by ticker and date
        prices_df = prices_df.sort_values(['ticker', 'trade_date'])

        # Calculate rolling peak and drawdown for each ticker
        drawdown_results = []
        for ticker_val in prices_df['ticker'].unique():
            ticker_data = prices_df[prices_df['ticker'] == ticker_val].copy()

            # Calculate rolling peak
            ticker_data['peak_price'] = ticker_data['close'].rolling(
                window=window_days, min_periods=1
            ).max()

            # Calculate drawdown as % from peak
            ticker_data['drawdown'] = (ticker_data['close'] - ticker_data['peak_price']) / ticker_data['peak_price'] * 100

            drawdown_results.append(ticker_data[['ticker', 'trade_date', 'drawdown', 'peak_price']])

        return pd.concat(drawdown_results, ignore_index=True)
