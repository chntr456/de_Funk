"""
EquityModel - Domain model for equity trading data.

This model represents tradable securities (equities) with ticker symbols.
It contains price/volume data, technical indicators, and trading-related measures.

Key distinction from CompanyModel:
- EquityModel: Trading instruments (ticker, prices, volume, technicals)
- CorporateModel: Legal entities (company, CIK, SEC filings, fundamentals)

Relationship: Many equities can belong to one corporate entity
Example: GOOG and GOOGL both belong to Alphabet Inc.

Inherits all graph building logic from BaseModel.
Only adds equity-specific convenience methods.
"""

from typing import Optional, List, Dict, Any
from models.base.model import BaseModel

# Bootstrap equity-specific domain features when this model is loaded
# This ensures measure types and domain strategies are available for equity calculations
import models.domains.equities.weighting
import models.domains.equities.technical
import models.domains.equities.risk


class EquityModel(BaseModel):
    """
    Equity domain model for tradable securities.

    Inherits all functionality from BaseModel:
    - Generic graph building from YAML config
    - Node loading from Bronze
    - Edge validation
    - Path materialization
    - Table access methods
    - Unified measure execution framework

    The YAML config (configs/models/equity.yaml) drives everything.

    This class adds equity-specific convenience methods.
    """

    # All core functionality is inherited from BaseModel!
    # The YAML config defines:
    # - Nodes: dim_equity, dim_exchange, fact_equity_prices, fact_equity_technicals
    # - Edges: ticker relationships, cross-model link to corporate
    # - Paths: equity_prices_with_company
    # - Measures: price aggregates, weighted indices, technical indicators

    # ============================================================
    # EQUITY-SPECIFIC MEASURE CALCULATIONS
    # ============================================================

    def calculate_measure_by_ticker(
        self,
        measure_name: str,
        tickers: Optional[List[str]] = None,
        limit: Optional[int] = None,
        **kwargs
    ):
        """
        Calculate a measure aggregated by ticker.

        This is a convenience wrapper around BaseModel.calculate_measure()
        specifically for the 'ticker' entity column.

        Supports ALL measure types (simple, computed, weighted) with both backends!

        Args:
            measure_name: Name of measure from config (e.g., 'avg_close_price', 'volume_weighted_index')
            tickers: Optional list of tickers to filter (e.g., ['AAPL', 'MSFT'])
            limit: Optional limit for top-N results
            **kwargs: Additional filters (e.g., trade_date={'start': '2024-01-01'})

        Returns:
            QueryResult with data and metadata

        Example:
            # Simple measure - average close price by ticker
            result = equity_model.calculate_measure_by_ticker('avg_close_price', limit=10)
            df = result.data  # DataFrame with ticker, avg_close_price columns

            # Weighted measure - volume weighted index (no ticker grouping)
            result = equity_model.calculate_measure_by_ticker('volume_weighted_index')

            # With filters
            result = equity_model.calculate_measure_by_ticker(
                'avg_close_price',
                tickers=['AAPL', 'MSFT', 'GOOGL'],
                trade_date={'start': '2024-01-01', 'end': '2024-01-31'}
            )
        """
        # Build filters
        filters = kwargs.copy()
        if tickers:
            filters['ticker'] = tickers

        return self.calculate_measure(
            measure_name=measure_name,
            entity_column='ticker',
            filters=filters,
            limit=limit
        )

    def get_top_tickers_by_measure(
        self,
        measure_name: str,
        limit: int = 10,
        **kwargs
    ) -> List[str]:
        """
        Get list of top ticker symbols by a measure.

        Convenience method that returns just the ticker list.

        Args:
            measure_name: Name of measure from config
            limit: Number of top tickers to return
            **kwargs: Additional filters

        Returns:
            List of ticker symbols, ordered by measure value descending

        Example:
            # Get top 10 companies by average market cap
            tickers = equity_model.get_top_tickers_by_measure('avg_market_cap', limit=10)
            # Returns: ['AAPL', 'MSFT', 'GOOGL', ...]

            # Get top 10 by trading volume in January
            tickers = equity_model.get_top_tickers_by_measure(
                'total_volume',
                limit=10,
                trade_date={'start': '2024-01-01', 'end': '2024-01-31'}
            )
        """
        result = self.calculate_measure_by_ticker(measure_name, limit=limit, **kwargs)

        # Handle both Pandas and Spark DataFrames
        if self.backend == 'duckdb':
            return result.data['ticker'].tolist()
        else:  # spark
            return [row['ticker'] for row in result.data.collect()]

    # ============================================================
    # EQUITY-SPECIFIC CONVENIENCE METHODS
    # ============================================================

    def get_equity_prices(
        self,
        tickers: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = None
    ):
        """
        Get equity price data with optional filters.

        Args:
            tickers: Optional list of tickers to filter
            start_date: Optional start date (YYYY-MM-DD)
            end_date: Optional end date (YYYY-MM-DD)
            limit: Optional row limit

        Returns:
            DataFrame with price data

        Example:
            # Get all prices for AAPL in January
            df = equity_model.get_equity_prices(
                tickers=['AAPL'],
                start_date='2024-01-01',
                end_date='2024-01-31'
            )
        """
        # Build filters
        filters = {}
        if tickers:
            filters['ticker'] = tickers
        if start_date or end_date:
            date_filter = {}
            if start_date:
                date_filter['start'] = start_date
            if end_date:
                date_filter['end'] = end_date
            filters['trade_date'] = date_filter

        # Use BaseModel's generic query method
        return self.query_table('fact_equity_prices', filters=filters, limit=limit)

    def get_equity_technicals(
        self,
        tickers: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = None
    ):
        """
        Get technical indicator data with optional filters.

        Args:
            tickers: Optional list of tickers to filter
            start_date: Optional start date (YYYY-MM-DD)
            end_date: Optional end date (YYYY-MM-DD)
            limit: Optional row limit

        Returns:
            DataFrame with technical indicators

        Example:
            # Get RSI and volatility for AAPL
            df = equity_model.get_equity_technicals(
                tickers=['AAPL'],
                start_date='2024-01-01',
                end_date='2024-01-31'
            )
            print(df[['ticker', 'trade_date', 'rsi_14', 'volatility_20d']])
        """
        # Build filters
        filters = {}
        if tickers:
            filters['ticker'] = tickers
        if start_date or end_date:
            date_filter = {}
            if start_date:
                date_filter['start'] = start_date
            if end_date:
                date_filter['end'] = end_date
            filters['trade_date'] = date_filter

        return self.query_table('fact_equity_technicals', filters=filters, limit=limit)

    def get_prices_with_company(
        self,
        tickers: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = None
    ):
        """
        Get prices joined with equity and exchange info (canonical analytics path).

        This uses the materialized 'equity_prices_with_company' path.

        Args:
            tickers: Optional list of tickers to filter
            start_date: Optional start date (YYYY-MM-DD)
            end_date: Optional end date (YYYY-MM-DD)
            limit: Optional row limit

        Returns:
            DataFrame with prices + company_name + exchange_name

        Example:
            # Get enriched price data
            df = equity_model.get_prices_with_company(
                tickers=['AAPL', 'MSFT'],
                start_date='2024-01-01',
                end_date='2024-01-05'
            )
            print(df[['ticker', 'trade_date', 'company_name', 'close']])
        """
        # Build filters
        filters = {}
        if tickers:
            filters['ticker'] = tickers
        if start_date or end_date:
            date_filter = {}
            if start_date:
                date_filter['start'] = start_date
            if end_date:
                date_filter['end'] = end_date
            filters['trade_date'] = date_filter

        return self.query_table('equity_prices_with_company', filters=filters, limit=limit)

    def screen_by_technicals(
        self,
        rsi_max: Optional[float] = None,
        rsi_min: Optional[float] = None,
        volatility_max: Optional[float] = None,
        beta_max: Optional[float] = None,
        **kwargs
    ) -> List[str]:
        """
        Screen equities by technical indicators.

        Returns list of tickers that meet the criteria.

        Args:
            rsi_max: Maximum RSI (e.g., 30 for oversold)
            rsi_min: Minimum RSI (e.g., 70 for overbought)
            volatility_max: Maximum volatility
            beta_max: Maximum beta
            **kwargs: Additional filters (date range, etc.)

        Returns:
            List of ticker symbols

        Example:
            # Find oversold stocks (RSI < 30) with low volatility
            tickers = equity_model.screen_by_technicals(
                rsi_max=30,
                volatility_max=0.02,
                trade_date={'start': '2024-01-01'}
            )
        """
        # Get technical data
        df = self.get_equity_technicals(**kwargs)

        # Convert to pandas for filtering (if Spark)
        if self.backend == 'spark':
            df = df.toPandas()

        # Apply filters
        if rsi_max is not None:
            df = df[df['rsi_14'] <= rsi_max]
        if rsi_min is not None:
            df = df[df['rsi_14'] >= rsi_min]
        if volatility_max is not None:
            df = df[df['volatility_20d'] <= volatility_max]
        if beta_max is not None:
            df = df[df['beta'] <= beta_max]

        # Return unique tickers
        return df['ticker'].unique().tolist()

    # ============================================================
    # LEGACY COMPATIBILITY (for migration from CompanyModel)
    # ============================================================

    def get_table(self, table_name: str, **kwargs):
        """
        Get a table by name (legacy compatibility).

        Maps old company table names to new equity table names.

        Args:
            table_name: Name of table (supports both old and new names)

        Returns:
            DataFrame
        """
        # Map old company table names to new equity names
        table_mapping = {
            'fact_prices': 'fact_equity_prices',
            'fact_news': 'fact_equity_news',
            'prices_with_company': 'equity_prices_with_company',
            'news_with_company': 'equity_news_with_company',
            'dim_company': 'dim_equity',
        }

        # Use mapped name if exists
        actual_table_name = table_mapping.get(table_name, table_name)

        return super().get_table(actual_table_name, **kwargs)
