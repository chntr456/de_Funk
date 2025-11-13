"""
CompanyModel - Domain model for company financial data.

⚠️  DEPRECATED: This model has been split into EquityModel and CorporateModel
    for better separation of concerns.

    - For price/volume/trading data: Use EquityModel
    - For corporate fundamentals/SEC filings: Use CorporateModel

    See docs/EQUITY_CORPORATE_MIGRATION_GUIDE.md for migration instructions.

    This model remains for backward compatibility but will be removed in a future release.

Inherits all graph building logic from BaseModel.
Only adds company-specific convenience methods.
"""

import warnings
from typing import Optional
from pyspark.sql import DataFrame
from models.base.model import BaseModel


class CompanyModel(BaseModel):
    """
    Company domain model.

    ⚠️  DEPRECATED: This model is deprecated and will be removed in a future release.

    **Migration Path:**
    ```python
    # OLD
    from models.implemented.company.model import CompanyModel
    company = CompanyModel(...)

    # NEW
    from models.implemented.equity.model import EquityModel
    equity = EquityModel(...)  # Same API!
    ```

    **Reason for Deprecation:**
    The "company" model conflated two distinct concepts:
    - Equity: Tradable securities (ticker, prices, volume)
    - Corporate: Legal entities (company, fundamentals, SEC filings)

    These have been split into EquityModel and CorporateModel for better
    separation of concerns.

    See docs/EQUITY_CORPORATE_MIGRATION_GUIDE.md for full migration guide.

    Inherits all functionality from BaseModel:
    - Generic graph building from YAML config
    - Node loading from Bronze
    - Edge validation
    - Path materialization
    - Table access methods
    - Measure calculations

    The YAML config (configs/models/company.yaml) drives everything.

    This class adds company-specific convenience methods.
    """

    def __init__(self, *args, **kwargs):
        """
        Initialize CompanyModel with deprecation warning.
        """
        # Emit deprecation warning
        warnings.warn(
            "CompanyModel is deprecated and will be removed in a future release. "
            "Use EquityModel for price/trading data or CorporateModel for fundamentals. "
            "See docs/EQUITY_CORPORATE_MIGRATION_GUIDE.md for migration instructions.",
            DeprecationWarning,
            stacklevel=2
        )
        super().__init__(*args, **kwargs)

    # All core functionality is inherited from BaseModel!
    # The YAML config defines:
    # - Nodes: dim_company, dim_exchange, fact_prices, fact_news
    # - Edges: relationships between tables
    # - Paths: prices_with_company, news_with_company
    # - Measures: market_cap, avg_close_price, total_volume, etc.

    # ============================================================
    # COMPANY-SPECIFIC MEASURE CALCULATIONS
    # ============================================================

    def calculate_measure_by_ticker(self, measure_name: str, limit: Optional[int] = None):
        """
        Calculate a measure aggregated by ticker (NEW: uses unified framework).

        This is a convenience wrapper around BaseModel.calculate_measure()
        specifically for the 'ticker' entity column.

        Now supports ALL measure types (simple, computed, weighted) with both backends!

        Args:
            measure_name: Name of measure from config (e.g., 'market_cap', 'volume_weighted_index')
            limit: Optional limit for top-N results

        Returns:
            QueryResult with data and metadata

        Example:
            # Simple measure
            result = company_model.calculate_measure_by_ticker('market_cap', limit=10)
            df = result.data  # Access DataFrame

            # Weighted measure (no ticker grouping needed)
            result = company_model.calculate_measure_by_ticker('volume_weighted_index')
        """
        return self.calculate_measure(
            measure_name=measure_name,
            entity_column='ticker',
            limit=limit
        )

    def get_top_tickers_by_measure(self, measure_name: str, limit: int = 10) -> list:
        """
        Get list of top ticker symbols by a measure (NEW: uses unified framework).

        Convenience method that returns just the ticker list.

        Args:
            measure_name: Name of measure from config
            limit: Number of top tickers to return

        Returns:
            List of ticker symbols, ordered by measure value descending

        Example:
            # Get top 10 companies by market cap
            tickers = company_model.get_top_tickers_by_measure('market_cap', limit=10)
            # Returns: ['AAPL', 'MSFT', 'GOOGL', ...]
        """
        result = self.calculate_measure_by_ticker(measure_name, limit=limit)

        # Handle both Pandas and Spark DataFrames
        if self.backend == 'duckdb':
            return result.data['ticker'].tolist()
        else:  # spark
            return [row['ticker'] for row in result.data.collect()]

    # ============================================================
    # COMPANY-SPECIFIC CONVENIENCE METHODS
    # ============================================================

    def get_prices(self, ticker: Optional[str] = None) -> DataFrame:
        """
        Convenience method for getting price data.

        Args:
            ticker: Optional ticker filter

        Returns:
            DataFrame with price data
        """
        df = self.get_fact_df('fact_prices')
        if ticker:
            df = df.filter(df.ticker == ticker)
        return df

    def get_news(self, ticker: Optional[str] = None) -> DataFrame:
        """
        Convenience method for getting news data.

        Args:
            ticker: Optional ticker filter

        Returns:
            DataFrame with news data
        """
        df = self.get_table('news_with_company')
        if ticker:
            df = df.filter(df.ticker == ticker)
        return df

    def get_company_info(self, ticker: Optional[str] = None) -> DataFrame:
        """
        Convenience method for getting company dimension data.

        Args:
            ticker: Optional ticker filter

        Returns:
            DataFrame with company info
        """
        df = self.get_dimension_df('dim_company')
        if ticker:
            df = df.filter(df.ticker == ticker)
        return df

    def get_exchanges(self) -> DataFrame:
        """
        Convenience method for getting exchange dimension data.

        Returns:
            DataFrame with exchange info
        """
        return self.get_dimension_df('dim_exchange')

    def get_prices_with_context(self, ticker: Optional[str] = None) -> DataFrame:
        """
        Get prices with full company and exchange context.

        This is a materialized path from the graph.

        Args:
            ticker: Optional ticker filter

        Returns:
            DataFrame with prices, company, and exchange info
        """
        df = self.get_table('prices_with_company')
        if ticker:
            df = df.filter(df.ticker == ticker)
        return df
