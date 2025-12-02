"""
OptionsModel - Domain model for options contracts.

Extends BaseModel to provide:
- Options pricing and Greeks from Bronze layer
- Integration with Black-Scholes calculations
- Python measures for complex option analytics
"""
from __future__ import annotations

from typing import Dict, Any, Optional
import pandas as pd

from config.logging import get_logger
from models.base.model import BaseModel

logger = get_logger(__name__)


class OptionsModel(BaseModel):
    """
    Options domain model.

    Loads options data from Bronze layer and provides:
    - Option prices (OHLC, bid/ask, volume)
    - Greeks (delta, gamma, theta, vega, rho)
    - Implied volatility
    - Integration with stocks model for underlying prices

    YAML Config: configs/models/options/
    - model.yaml: Model metadata and dependencies
    - schema.yaml: Table definitions (extends base securities)
    - graph.yaml: Node and edge definitions
    - measures.yaml: Simple and Python measures
    """

    def __init__(
        self,
        connection,
        storage_cfg: Dict,
        model_cfg: Dict = None,
        params: Dict = None
    ):
        """
        Initialize Options Model.

        Args:
            connection: Database connection
            storage_cfg: Storage configuration
            model_cfg: Model configuration (loaded from YAML if not provided)
            params: Runtime parameters
        """
        super().__init__(connection, storage_cfg, model_cfg, params)
        self._measures_instance = None

    def get_python_measures(self):
        """
        Get the Python measures instance.

        Lazy-loads OptionsMeasures on first access.

        Returns:
            OptionsMeasures instance
        """
        if self._measures_instance is None:
            from models.implemented.options.measures import OptionsMeasures
            self._measures_instance = OptionsMeasures(self)
        return self._measures_instance

    def calculate_measure(
        self,
        measure_name: str,
        **kwargs
    ) -> Any:
        """
        Calculate a measure by name.

        Supports both YAML-defined simple measures and Python measures.

        Args:
            measure_name: Name of measure to calculate
            **kwargs: Parameters for measure calculation

        Returns:
            Calculated measure value
        """
        # Check if it's a Python measure
        python_measures = self.model_cfg.get('python_measures', {})

        if measure_name in python_measures:
            measure_config = python_measures[measure_name]
            function_name = measure_config.get('function', '').split('.')[-1]

            # Get method from measures instance
            measures = self.get_python_measures()
            if hasattr(measures, function_name):
                method = getattr(measures, function_name)
                # Merge config params with kwargs (kwargs override)
                params = {**measure_config.get('params', {}), **kwargs}
                return method(**params)

        # Fall back to parent implementation for YAML measures
        return super().calculate_measure(measure_name, **kwargs)

    def get_option_chain(
        self,
        underlying_ticker: str,
        expiration_date: str = None,
        option_type: str = None
    ) -> pd.DataFrame:
        """
        Get options chain for an underlying ticker.

        Args:
            underlying_ticker: Stock ticker symbol
            expiration_date: Filter by expiration (optional)
            option_type: 'call' or 'put' (optional)

        Returns:
            DataFrame with options chain data
        """
        try:
            df = self.get_table('fact_option_prices')

            # Convert to pandas if needed
            if hasattr(df, 'toPandas'):
                df = df.toPandas()

            # Apply filters
            if 'underlying_ticker' in df.columns:
                df = df[df['underlying_ticker'] == underlying_ticker]

            if expiration_date and 'expiration_date' in df.columns:
                df = df[df['expiration_date'] == expiration_date]

            if option_type and 'option_type' in df.columns:
                df = df[df['option_type'] == option_type.lower()]

            return df

        except Exception as e:
            logger.warning(f"Error getting option chain for {underlying_ticker}: {e}")
            return pd.DataFrame()

    def get_greeks(
        self,
        underlying_ticker: str = None,
        contract_id: str = None
    ) -> pd.DataFrame:
        """
        Get Greeks data for options.

        Args:
            underlying_ticker: Filter by underlying (optional)
            contract_id: Filter by specific contract (optional)

        Returns:
            DataFrame with Greeks (delta, gamma, theta, vega, rho)
        """
        try:
            df = self.get_table('fact_option_greeks')

            # Convert to pandas if needed
            if hasattr(df, 'toPandas'):
                df = df.toPandas()

            # Apply filters
            if underlying_ticker and 'underlying_ticker' in df.columns:
                df = df[df['underlying_ticker'] == underlying_ticker]

            if contract_id and 'contract_id' in df.columns:
                df = df[df['contract_id'] == contract_id]

            return df

        except Exception as e:
            logger.warning(f"Error getting Greeks: {e}")
            return pd.DataFrame()

    def get_implied_volatility(
        self,
        underlying_ticker: str,
        strike: float = None,
        expiration_date: str = None
    ) -> pd.DataFrame:
        """
        Get implied volatility data.

        Args:
            underlying_ticker: Stock ticker symbol
            strike: Filter by strike price (optional)
            expiration_date: Filter by expiration (optional)

        Returns:
            DataFrame with IV data
        """
        df = self.get_greeks(underlying_ticker=underlying_ticker)

        if df.empty:
            return df

        if strike is not None and 'strike_price' in df.columns:
            df = df[df['strike_price'] == strike]

        if expiration_date and 'expiration_date' in df.columns:
            df = df[df['expiration_date'] == expiration_date]

        # Select relevant columns
        iv_cols = ['contract_id', 'underlying_ticker', 'strike_price',
                   'expiration_date', 'option_type', 'implied_volatility',
                   'trade_date', 'days_to_expiration']
        available_cols = [c for c in iv_cols if c in df.columns]

        return df[available_cols]

    def price_option(
        self,
        spot: float,
        strike: float,
        days_to_expiration: int,
        volatility: float,
        option_type: str = "call",
        risk_free_rate: float = 0.05,
        dividend_yield: float = 0.0
    ) -> Dict[str, float]:
        """
        Price an option using Black-Scholes.

        Args:
            spot: Current underlying price
            strike: Strike price
            days_to_expiration: Days until expiration
            volatility: Implied volatility (decimal, e.g., 0.3 for 30%)
            option_type: 'call' or 'put'
            risk_free_rate: Risk-free rate (decimal)
            dividend_yield: Dividend yield (decimal)

        Returns:
            Dict with price and Greeks
        """
        from models.implemented.options.black_scholes import BlackScholes, OptionType

        bs = BlackScholes()
        opt_type = OptionType.CALL if option_type.lower() == 'call' else OptionType.PUT

        T = days_to_expiration / 365

        result = bs.calculate(
            S=spot,
            K=strike,
            T=T,
            r=risk_free_rate,
            sigma=volatility,
            option_type=opt_type,
            q=dividend_yield
        )

        return {
            'price': result.price,
            'delta': result.delta,
            'gamma': result.gamma,
            'theta': result.theta,
            'vega': result.vega,
            'rho': result.rho,
        }

    def calculate_iv(
        self,
        market_price: float,
        spot: float,
        strike: float,
        days_to_expiration: int,
        option_type: str = "call",
        risk_free_rate: float = 0.05,
        dividend_yield: float = 0.0
    ) -> Optional[float]:
        """
        Calculate implied volatility from market price.

        Args:
            market_price: Observed market price
            spot: Current underlying price
            strike: Strike price
            days_to_expiration: Days until expiration
            option_type: 'call' or 'put'
            risk_free_rate: Risk-free rate
            dividend_yield: Dividend yield

        Returns:
            Implied volatility (decimal), or None if calculation fails
        """
        from models.implemented.options.black_scholes import BlackScholes, OptionType

        bs = BlackScholes()
        opt_type = OptionType.CALL if option_type.lower() == 'call' else OptionType.PUT

        T = days_to_expiration / 365

        return bs.implied_volatility(
            market_price=market_price,
            S=spot,
            K=strike,
            T=T,
            r=risk_free_rate,
            option_type=opt_type,
            q=dividend_yield
        )
