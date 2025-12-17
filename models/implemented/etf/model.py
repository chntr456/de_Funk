"""
ETFModel - Domain model for ETF data.

Inherits all graph building logic from BaseModel.
Adds ETF-specific convenience methods.

Version: 2.1 - Backend-agnostic via UniversalSession methods
"""

from typing import Optional, Any, List
from models.base.model import BaseModel
import logging

logger = logging.getLogger(__name__)

# Type alias for DataFrame (can be Spark or DuckDB)
DataFrame = Any

# Bootstrap ETF-specific domain features when this model is loaded
# This ensures ETF weighting strategies are available
from models.implemented.etf.domains import weighting


class ETFModel(BaseModel):
    """
    ETF domain model.

    Demonstrates advanced features:
    - Holdings-based weighted measures
    - Cross-model references (ETF -> company stocks)
    - Temporal dimension (holdings change over time)

    Inherits all functionality from BaseModel:
    - Generic graph building from YAML config
    - Unified measure execution framework
    - Cross-model edge support
    - Path materialization

    The YAML config (configs/models/etf.yaml) drives everything.

    Backend-agnostic: uses session methods for all DataFrame operations.
    """

    # ============================================================
    # ETF-SPECIFIC MEASURE CALCULATIONS
    # ============================================================

    def calculate_measure_by_etf(self, measure_name: str, limit: Optional[int] = None):
        """
        Calculate a measure aggregated by ETF ticker.

        Convenience wrapper around BaseModel.calculate_measure()
        specifically for the 'etf_ticker' entity column.

        Args:
            measure_name: Name of measure from config
            limit: Optional limit for top-N results

        Returns:
            QueryResult with data and metadata

        Example:
            # Simple measure
            result = etf_model.calculate_measure_by_etf('avg_expense_ratio', limit=10)

            # Holdings-based weighted return
            result = etf_model.calculate_measure_by_etf('holdings_weighted_return')
        """
        return self.calculate_measure(
            measure_name=measure_name,
            entity_column='etf_ticker',
            limit=limit
        )

    def get_top_etfs_by_measure(self, measure_name: str, limit: int = 10) -> List[str]:
        """
        Get list of top ETF ticker symbols by a measure.

        Args:
            measure_name: Name of measure from config
            limit: Number of top ETFs to return

        Returns:
            List of ETF ticker symbols, ordered by measure value descending

        Example:
            # Get ETFs with highest expense ratios
            etfs = etf_model.get_top_etfs_by_measure('avg_expense_ratio', limit=10)
        """
        result = self.calculate_measure_by_etf(measure_name, limit=limit)

        if self.session:
            # Use session to convert to list
            pdf = self.session.to_pandas(result.data)
            return pdf['etf_ticker'].tolist()
        elif self.backend == 'spark':
            return [row['etf_ticker'] for row in result.data.collect()]
        else:
            # DuckDB/pandas
            if hasattr(result.data, 'df'):
                return result.data.df()['etf_ticker'].tolist()
            return result.data['etf_ticker'].tolist()

    # ============================================================
    # ETF-SPECIFIC CONVENIENCE METHODS
    # ============================================================

    def get_etf_prices(self, etf_ticker: Optional[str] = None) -> DataFrame:
        """
        Get ETF price data.

        Args:
            etf_ticker: Optional ETF ticker filter

        Returns:
            DataFrame with ETF price data
        """
        df = self.get_table('fact_etf_prices')

        if etf_ticker:
            if self.session:
                return self.session.filter_by_value(df, 'etf_ticker', etf_ticker)
            elif self.backend == 'spark':
                return df.filter(df.etf_ticker == etf_ticker)
            else:
                return df[df['etf_ticker'] == etf_ticker]

        return df

    def get_etf_info(self, etf_ticker: Optional[str] = None) -> DataFrame:
        """
        Get ETF information.

        Args:
            etf_ticker: Optional ETF ticker filter

        Returns:
            DataFrame with ETF info
        """
        df = self.get_dimension_df('dim_etf')

        if etf_ticker:
            if self.session:
                return self.session.filter_by_value(df, 'etf_ticker', etf_ticker)
            elif self.backend == 'spark':
                return df.filter(df.etf_ticker == etf_ticker)
            else:
                return df[df['etf_ticker'] == etf_ticker]

        return df

    def get_etf_holdings(
        self,
        etf_ticker: Optional[str] = None,
        as_of_date: Optional[str] = None
    ) -> DataFrame:
        """
        Get ETF holdings data.

        Args:
            etf_ticker: Optional ETF ticker filter
            as_of_date: Optional date filter (YYYY-MM-DD)

        Returns:
            DataFrame with holdings data

        Example:
            # Get SPY holdings as of 2024-01-01
            holdings = etf_model.get_etf_holdings('SPY', '2024-01-01')
        """
        df = self.get_dimension_df('dim_etf_holdings')

        if self.session:
            if etf_ticker:
                df = self.session.filter_by_value(df, 'etf_ticker', etf_ticker)
            if as_of_date:
                df = self.session.filter_by_value(df, 'as_of_date', as_of_date)
        elif self.backend == 'spark':
            if etf_ticker:
                df = df.filter(df.etf_ticker == etf_ticker)
            if as_of_date:
                df = df.filter(df.as_of_date == as_of_date)
        else:
            # DuckDB/pandas
            if etf_ticker:
                df = df[df['etf_ticker'] == etf_ticker]
            if as_of_date:
                df = df[df['as_of_date'] == as_of_date]

        return df

    def get_etf_with_context(self, etf_ticker: Optional[str] = None) -> DataFrame:
        """
        Get ETF prices with full fund information.

        Uses materialized path from graph.

        Args:
            etf_ticker: Optional ETF ticker filter

        Returns:
            DataFrame with prices and fund info
        """
        df = self.get_table('etf_prices_with_info')

        if etf_ticker:
            if self.session:
                return self.session.filter_by_value(df, 'etf_ticker', etf_ticker)
            elif self.backend == 'spark':
                return df.filter(df.etf_ticker == etf_ticker)
            else:
                return df[df['etf_ticker'] == etf_ticker]

        return df

    def list_etf_tickers(self, active_only: bool = True) -> List[str]:
        """
        Get list of all ETF tickers.

        Args:
            active_only: Only return active ETFs

        Returns:
            List of ETF ticker symbols
        """
        df = self.get_dimension_df('dim_etf')

        if active_only and 'is_active' in self._get_columns(df):
            if self.session:
                df = self.session.filter_by_value(df, 'is_active', True)
            elif self.backend == 'spark':
                df = df.filter(df.is_active == True)
            else:
                df = df[df['is_active'] == True]

        if self.session:
            return self.session.distinct_values(df, 'etf_ticker')
        elif self.backend == 'spark':
            return [row.etf_ticker for row in df.select('etf_ticker').distinct().collect()]
        else:
            if hasattr(df, 'df'):
                return df.df()['etf_ticker'].unique().tolist()
            return df['etf_ticker'].unique().tolist()

    def _get_columns(self, df) -> List[str]:
        """Get column names from DataFrame (helper for both backends)."""
        if self.backend == 'spark':
            return df.columns
        elif hasattr(df, 'columns'):
            return list(df.columns)
        else:
            return []
