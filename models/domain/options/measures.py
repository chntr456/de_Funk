"""
Options Measures - Python measures for the options model.

Provides complex calculations referenced in configs/models/options/measures.yaml:
- Black-Scholes theoretical pricing
- Put/Call ratio calculation
- Implied volatility surface
- Greeks aggregation
"""
from __future__ import annotations

from typing import Dict, Any, Optional, List
import pandas as pd
import numpy as np

from config.logging import get_logger
from .black_scholes import BlackScholes, OptionType, OptionParams

logger = get_logger(__name__)


class OptionsMeasures:
    """
    Python measures for the Options model.

    Used by the model framework to calculate complex option metrics
    that can't be expressed in simple YAML aggregations.
    """

    def __init__(self, model):
        """
        Initialize options measures.

        Args:
            model: The OptionsModel instance
        """
        self.model = model
        self.bs = BlackScholes()

    def calculate_black_scholes(
        self,
        underlying_ticker: str = None,
        strike: float = None,
        expiration_date: str = None,
        option_type: str = "call",
        risk_free_rate: float = 0.05,
        dividend_yield: float = 0.0,
        **kwargs
    ) -> pd.DataFrame:
        """
        Calculate Black-Scholes theoretical prices for options.

        If specific parameters are provided, calculates for that option.
        Otherwise, calculates for all options in the data.

        Args:
            underlying_ticker: Filter by underlying ticker
            strike: Specific strike price (optional)
            expiration_date: Specific expiration (optional)
            option_type: 'call' or 'put'
            risk_free_rate: Risk-free rate (default 5%)
            dividend_yield: Dividend yield (default 0%)

        Returns:
            DataFrame with theoretical prices and Greeks
        """
        # Get options data
        try:
            options_df = self.model.get_table('fact_option_prices')
            if hasattr(options_df, 'toPandas'):
                options_df = options_df.toPandas()
        except Exception as e:
            logger.warning(f"Could not load options data: {e}")
            return pd.DataFrame()

        # Apply filters
        if underlying_ticker:
            options_df = options_df[options_df['underlying_ticker'] == underlying_ticker]
        if strike is not None:
            options_df = options_df[options_df['strike_price'] == strike]
        if expiration_date:
            options_df = options_df[options_df['expiration_date'] == expiration_date]
        if option_type:
            options_df = options_df[options_df['option_type'] == option_type.lower()]

        if options_df.empty:
            return pd.DataFrame()

        # Get current underlying price
        # Try to get from the model's stocks dependency
        underlying_prices = {}
        try:
            if hasattr(self.model, 'session') and self.model.session:
                stocks_model = self.model.session.load_model('stocks')
                if stocks_model:
                    prices_df = stocks_model.get_table('fact_stock_prices')
                    if hasattr(prices_df, 'toPandas'):
                        prices_df = prices_df.toPandas()
                    # Get latest price per ticker
                    latest = prices_df.sort_values('trade_date', ascending=False).groupby('ticker').first()
                    underlying_prices = latest['close'].to_dict()
        except Exception as e:
            logger.warning(f"Could not load underlying prices: {e}")

        # Calculate theoretical values
        results = []
        opt_type = OptionType.CALL if option_type.lower() == 'call' else OptionType.PUT

        for _, row in options_df.iterrows():
            ticker = row.get('underlying_ticker')
            spot = underlying_prices.get(ticker)

            if spot is None:
                # Use mark price as proxy for spot if no underlying data
                spot = row.get('mark_price', 100)

            strike_price = row.get('strike_price')
            days_to_exp = row.get('days_to_expiration', 30)

            if None in (spot, strike_price) or days_to_exp <= 0:
                continue

            T = days_to_exp / 365  # Convert to years

            # Use market IV if available, otherwise estimate
            sigma = row.get('implied_volatility', 0.3)
            if sigma is None or sigma <= 0:
                sigma = 0.3  # Default 30% vol

            try:
                result = self.bs.calculate(
                    S=spot,
                    K=strike_price,
                    T=T,
                    r=risk_free_rate,
                    sigma=sigma,
                    option_type=opt_type,
                    q=dividend_yield
                )

                results.append({
                    'contract_id': row.get('contract_id'),
                    'underlying_ticker': ticker,
                    'strike_price': strike_price,
                    'expiration_date': row.get('expiration_date'),
                    'option_type': option_type,
                    'spot_price': spot,
                    'days_to_expiration': days_to_exp,
                    'implied_volatility': sigma,
                    'theoretical_price': result.price,
                    'market_price': row.get('mark_price'),
                    'price_diff': result.price - row.get('mark_price', result.price),
                    'delta': result.delta,
                    'gamma': result.gamma,
                    'theta': result.theta,
                    'vega': result.vega,
                    'rho': result.rho,
                })
            except Exception as e:
                logger.debug(f"BS calculation failed for {row.get('contract_id')}: {e}")
                continue

        return pd.DataFrame(results)

    def calculate_put_call_ratio(
        self,
        underlying_ticker: str = None,
        by: str = "volume",  # 'volume' or 'open_interest'
        **kwargs
    ) -> pd.DataFrame:
        """
        Calculate put/call ratio by volume or open interest.

        Args:
            underlying_ticker: Filter by underlying ticker (optional)
            by: Calculate ratio by 'volume' or 'open_interest'

        Returns:
            DataFrame with put/call ratios
        """
        # Get options data
        try:
            options_df = self.model.get_table('fact_option_prices')
            if hasattr(options_df, 'toPandas'):
                options_df = options_df.toPandas()
        except Exception as e:
            logger.warning(f"Could not load options data: {e}")
            return pd.DataFrame()

        # Apply ticker filter
        if underlying_ticker:
            options_df = options_df[options_df['underlying_ticker'] == underlying_ticker]

        if options_df.empty:
            return pd.DataFrame()

        # Ensure we have the right column
        value_col = 'volume' if by == 'volume' else 'open_interest'
        if value_col not in options_df.columns:
            logger.warning(f"Column '{value_col}' not found in options data")
            return pd.DataFrame()

        # Group by ticker and date, calculate put/call ratio
        results = []

        group_cols = ['underlying_ticker', 'trade_date'] if 'trade_date' in options_df.columns else ['underlying_ticker']

        for name, group in options_df.groupby(group_cols):
            calls = group[group['option_type'] == 'call'][value_col].sum()
            puts = group[group['option_type'] == 'put'][value_col].sum()

            if calls > 0:
                pc_ratio = puts / calls
            else:
                pc_ratio = np.nan

            if isinstance(name, tuple):
                ticker, trade_date = name
            else:
                ticker = name
                trade_date = None

            results.append({
                'underlying_ticker': ticker,
                'trade_date': trade_date,
                'call_volume': calls,
                'put_volume': puts,
                'put_call_ratio': pc_ratio,
                'sentiment': 'bearish' if pc_ratio > 1 else 'bullish' if pc_ratio < 0.7 else 'neutral',
            })

        return pd.DataFrame(results)

    def calculate_iv_surface(
        self,
        underlying_ticker: str,
        **kwargs
    ) -> pd.DataFrame:
        """
        Calculate implied volatility surface (IV by strike and expiration).

        Args:
            underlying_ticker: Underlying ticker symbol

        Returns:
            DataFrame with IV surface data (strike, expiration, IV)
        """
        # Get options data with IV
        try:
            options_df = self.model.get_table('fact_option_greeks')
            if hasattr(options_df, 'toPandas'):
                options_df = options_df.toPandas()
        except Exception:
            try:
                options_df = self.model.get_table('fact_option_prices')
                if hasattr(options_df, 'toPandas'):
                    options_df = options_df.toPandas()
            except Exception as e:
                logger.warning(f"Could not load options data: {e}")
                return pd.DataFrame()

        # Filter by ticker
        options_df = options_df[options_df['underlying_ticker'] == underlying_ticker]

        if options_df.empty:
            return pd.DataFrame()

        # Get unique strikes and expirations
        if 'implied_volatility' not in options_df.columns:
            return pd.DataFrame()

        # Pivot to create surface
        surface_data = options_df.groupby(['strike_price', 'expiration_date']).agg({
            'implied_volatility': 'mean',
            'days_to_expiration': 'first'
        }).reset_index()

        # Add moneyness calculation if we have spot price
        spot = options_df.get('spot_price', pd.Series([100])).iloc[0]
        surface_data['moneyness'] = surface_data['strike_price'] / spot

        return surface_data

    def calculate_greeks_summary(
        self,
        underlying_ticker: str = None,
        **kwargs
    ) -> pd.DataFrame:
        """
        Calculate aggregated Greeks summary for a portfolio or ticker.

        Args:
            underlying_ticker: Filter by underlying ticker (optional)

        Returns:
            DataFrame with Greeks summary (total delta, gamma, etc.)
        """
        # Get options data with Greeks
        try:
            options_df = self.model.get_table('fact_option_greeks')
            if hasattr(options_df, 'toPandas'):
                options_df = options_df.toPandas()
        except Exception:
            try:
                # Try options prices which may have Greeks
                options_df = self.model.get_table('fact_option_prices')
                if hasattr(options_df, 'toPandas'):
                    options_df = options_df.toPandas()
            except Exception as e:
                logger.warning(f"Could not load options data: {e}")
                return pd.DataFrame()

        # Filter by ticker
        if underlying_ticker:
            options_df = options_df[options_df['underlying_ticker'] == underlying_ticker]

        if options_df.empty:
            return pd.DataFrame()

        # Aggregate Greeks
        greek_cols = ['delta', 'gamma', 'theta', 'vega', 'rho']
        available_greeks = [col for col in greek_cols if col in options_df.columns]

        if not available_greeks:
            return pd.DataFrame()

        # Group by underlying ticker
        summary = options_df.groupby('underlying_ticker').agg({
            **{col: ['sum', 'mean', 'std'] for col in available_greeks},
            'contract_id': 'count'
        })

        # Flatten column names
        summary.columns = ['_'.join(col).strip() for col in summary.columns.values]
        summary = summary.reset_index()
        summary = summary.rename(columns={'contract_id_count': 'num_contracts'})

        return summary
