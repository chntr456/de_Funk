"""
Base class for domain-specific measure implementations.

Domain measures are complex calculations that can't be expressed in simple YAML.
They're referenced from the model's measures.yaml via python_measures.

Usage:
    1. Create a measures.py in your domain folder (e.g., models/domains/securities/stocks/measures.py)
    2. Inherit from DomainMeasures
    3. Implement measure methods that match YAML references

Example YAML (in measures.yaml):
    python_measures:
      sharpe_ratio:
        function: "stocks.measures.calculate_sharpe_ratio"
        params:
          risk_free_rate: 0.045
          window_days: 252

Example implementation:
    class StocksMeasures(DomainMeasures):
        def calculate_sharpe_ratio(self, ticker=None, risk_free_rate=0.045, window_days=252, **kwargs):
            prices_df = self.get_table('fact_stock_prices', ticker=ticker)
            # ... calculation logic ...
            return result_df
"""

from abc import ABC
from typing import Dict, Any, Optional, List, Union
import logging

import pandas as pd

logger = logging.getLogger(__name__)


class DomainMeasures(ABC):
    """
    Base class for domain-specific measure implementations.

    Provides common utilities for:
    - Accessing model data
    - Converting DataFrames (backend-agnostic)
    - Applying filters
    - Logging

    Subclasses implement measure calculation methods that are referenced
    from the model's YAML configuration.
    """

    def __init__(self, model):
        """
        Initialize with model instance.

        Args:
            model: Domain model instance (e.g., StocksModel)
                   Provides access to tables, session, and configuration
        """
        self.model = model
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    # ============================================================
    # DATA ACCESS HELPERS
    # ============================================================

    def get_table(
        self,
        table_name: str,
        ticker: Optional[str] = None,
        filters: Optional[List[Dict]] = None,
        as_pandas: bool = True
    ) -> pd.DataFrame:
        """
        Get a table from the model with optional filtering.

        Args:
            table_name: Name of the table (e.g., 'fact_stock_prices', 'dim_stock')
            ticker: Optional ticker filter (convenience for single-ticker queries)
            filters: Optional list of filter dicts
            as_pandas: Convert to pandas DataFrame (default: True)

        Returns:
            DataFrame (pandas if as_pandas=True, else native backend format)
        """
        df = self.model.get_table(table_name)

        if as_pandas:
            df = self._to_pandas(df)

        # Apply ticker filter if specified
        if ticker and 'ticker' in df.columns:
            df = df[df['ticker'] == ticker]

        # Apply additional filters
        if filters and self.model.session:
            df = self.model.session.apply_filters(df, filters)

        return df

    def _to_pandas(self, df) -> pd.DataFrame:
        """
        Convert DataFrame to pandas (backend-agnostic).

        Handles:
        - Spark DataFrames
        - DuckDB result sets
        - Already-pandas DataFrames

        Args:
            df: DataFrame in any supported format

        Returns:
            pandas DataFrame
        """
        if df is None:
            return pd.DataFrame()

        # Use session conversion if available
        if self.model.session:
            return self.model.session.to_pandas(df)

        # Fallback for Spark
        if hasattr(df, 'toPandas'):
            return df.toPandas()

        # Fallback for DuckDB
        if hasattr(df, 'df'):
            return df.df()

        # Already pandas
        if isinstance(df, pd.DataFrame):
            return df

        # Last resort: try to construct
        return pd.DataFrame(df)

    # ============================================================
    # CALCULATION UTILITIES
    # ============================================================

    def rolling_apply(
        self,
        df: pd.DataFrame,
        column: str,
        func,
        window: int,
        min_periods: Optional[int] = None,
        group_by: Optional[str] = None
    ) -> pd.Series:
        """
        Apply a rolling function to a column, optionally grouped.

        Args:
            df: Input DataFrame
            column: Column to apply function to
            func: Function to apply (receives window as array)
            window: Window size
            min_periods: Minimum periods required (default: window)
            group_by: Optional grouping column (e.g., 'ticker')

        Returns:
            Series with rolling calculation results
        """
        if min_periods is None:
            min_periods = window

        if group_by:
            return df.groupby(group_by)[column].rolling(
                window=window, min_periods=min_periods
            ).apply(func, raw=True).reset_index(drop=True)
        else:
            return df[column].rolling(
                window=window, min_periods=min_periods
            ).apply(func, raw=True)

    def normalize_to_range(
        self,
        series: pd.Series,
        min_val: float = 0.0,
        max_val: float = 1.0
    ) -> pd.Series:
        """
        Normalize a series to a specified range.

        Args:
            series: Input series
            min_val: Target minimum (default: 0)
            max_val: Target maximum (default: 1)

        Returns:
            Normalized series
        """
        s_min = series.min()
        s_max = series.max()

        if s_max == s_min:
            return pd.Series([0.5] * len(series), index=series.index)

        return min_val + (series - s_min) / (s_max - s_min) * (max_val - min_val)

    def calculate_returns(
        self,
        df: pd.DataFrame,
        price_column: str = 'close',
        group_by: str = 'ticker',
        log_returns: bool = False
    ) -> pd.Series:
        """
        Calculate returns from price data.

        Args:
            df: DataFrame with price data
            price_column: Column with prices (default: 'close')
            group_by: Column to group by (default: 'ticker')
            log_returns: Use log returns instead of simple returns

        Returns:
            Series of returns
        """
        if log_returns:
            import numpy as np
            return df.groupby(group_by)[price_column].transform(
                lambda x: np.log(x / x.shift(1))
            )
        else:
            return df.groupby(group_by)[price_column].pct_change()

    # ============================================================
    # LOGGING UTILITIES
    # ============================================================

    def log_start(self, measure_name: str, **params):
        """Log measure calculation start with parameters."""
        param_str = ", ".join(f"{k}={v}" for k, v in params.items())
        self._logger.info(f"Calculating {measure_name}({param_str})")

    def log_result(self, measure_name: str, result_df: pd.DataFrame):
        """Log measure calculation result."""
        self._logger.info(
            f"{measure_name}: {len(result_df):,} rows, "
            f"columns: {list(result_df.columns)}"
        )


# ============================================================
# TEMPLATE FOR NEW DOMAIN MEASURES
# ============================================================

class _DomainMeasuresTemplate(DomainMeasures):
    """
    Template for creating domain-specific measures.

    Copy this class to your domain folder and customize:
        models/domains/{category}/{model}/measures.py

    Reference in your measures.yaml:
        python_measures:
          my_measure:
            function: "{model}.measures.calculate_my_measure"
            params:
              param1: value1
    """

    def calculate_example_measure(
        self,
        ticker: Optional[str] = None,
        filters: Optional[List[Dict]] = None,
        param1: float = 1.0,
        **kwargs
    ) -> pd.DataFrame:
        """
        Example measure calculation.

        Args:
            ticker: Optional ticker filter
            filters: Optional additional filters
            param1: Example parameter from YAML
            **kwargs: Additional runtime parameters

        Returns:
            DataFrame with measure results
        """
        self.log_start("example_measure", ticker=ticker, param1=param1)

        # 1. Get data from model
        df = self.get_table('fact_prices', ticker=ticker, filters=filters)

        # 2. Perform calculation
        df['result'] = df['close'] * param1

        # 3. Select output columns
        result = df[['ticker', 'trade_date', 'result']]

        self.log_result("example_measure", result)
        return result
