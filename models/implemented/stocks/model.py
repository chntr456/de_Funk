"""
Stocks Model - Common stock equities.

Inherits from BaseModel with securities pattern.
Filters bronze data by asset_type='stocks'.

Version: 2.0 - Redesigned with inheritance architecture
"""

from models.base.model import BaseModel
from typing import Optional, Dict, Any, List, Tuple
import logging

logger = logging.getLogger(__name__)

# Type alias for DataFrame (can be Spark or DuckDB)
DataFrame = Any


class StocksModel(BaseModel):
    """
    Common stock equities model.

    Key features:
    - Inherits base securities schema and measures
    - Uses JOIN-based filtering: prices filtered to tickers in dim_stock
    - Links to Company model via company_id
    - Includes technical indicators (RSI, MACD, Bollinger Bands, etc.)
    - Supports complex Python measures (Sharpe, correlation, momentum, etc.)

    Architecture Note:
        Bronze prices table may have NULL asset_type. Instead of filtering by
        asset_type='stocks', we filter fact_stock_prices to only include tickers
        that exist in dim_stock (which IS filtered by asset_type='stocks' from
        the securities_reference table). This JOIN-based approach is more robust.

    Usage:
        from models.implemented.stocks.model import StocksModel
        stocks = StocksModel(connection, storage_cfg, model_cfg)
        stocks.build()

        # Get price data
        prices = stocks.get_prices('AAPL')

        # Calculate measures
        sharpe = stocks.calculate_measure('sharpe_ratio', ticker='AAPL')
    """

    def get_asset_type_filter(self) -> str:
        """
        Return asset type to filter from unified bronze table.

        This is used by the graph building logic to filter
        bronze.securities_prices_daily and bronze.securities_reference.

        Returns:
            'stocks' - filters for common stock equities
        """
        return 'stocks'

    def after_build(
        self,
        dims: Dict[str, DataFrame],
        facts: Dict[str, DataFrame]
    ) -> Tuple[Dict[str, DataFrame], Dict[str, DataFrame]]:
        """
        Post-build hook: Filter fact_stock_prices to only tickers in dim_stock
        and denormalize key dimension columns (sector, exchange_code).

        This implements JOIN-based filtering for the prices table. Since Bronze
        prices may have NULL asset_type, we can't filter directly. Instead, we:
        1. Build dim_stock (filtered by asset_type='stocks' from securities_reference)
        2. Build fact_stock_prices (all prices, no asset_type filter)
        3. Join fact_stock_prices with dim_stock to:
           - Filter to only tickers that exist in dim_stock
           - Denormalize sector and exchange_code for interactive analytics

        This ensures we only have prices for actual stock tickers and enables
        dimension-based filtering/grouping in notebooks without auto-join.
        """
        # Check if we have both tables
        if 'dim_stock' not in dims or 'fact_stock_prices' not in facts:
            logger.warning("Missing dim_stock or fact_stock_prices, skipping JOIN filter")
            return dims, facts

        dim_stock = dims['dim_stock']
        fact_prices = facts['fact_stock_prices']

        # Columns to denormalize from dim_stock
        denorm_columns = ['sector', 'exchange_code']

        # Get stock tickers from dim_stock
        if self._backend == 'spark':
            from pyspark.sql.functions import col

            # Select only needed columns from dim_stock for the join
            dim_for_join = dim_stock.select('ticker', *denorm_columns).distinct()

            # Count before filtering
            before_count = fact_prices.count()

            # Inner join to filter AND denormalize
            filtered_prices = fact_prices.join(
                dim_for_join,
                on='ticker',
                how='inner'  # Filter to matching tickers AND bring in dim columns
            )

            after_count = filtered_prices.count()
            logger.info(
                f"  JOIN filter + denormalize: {before_count:,} → {after_count:,} prices "
                f"(filtered to {dim_for_join.count()} stock tickers, added {denorm_columns})"
            )

            facts['fact_stock_prices'] = filtered_prices

        else:
            # DuckDB/pandas: Use merge
            import pandas as pd

            # Convert to pandas if needed
            if hasattr(dim_stock, 'df'):
                dim_stock_pdf = dim_stock.df()
            elif isinstance(dim_stock, pd.DataFrame):
                dim_stock_pdf = dim_stock
            else:
                dim_stock_pdf = dim_stock

            if hasattr(fact_prices, 'df'):
                fact_prices_pdf = fact_prices.df()
            elif isinstance(fact_prices, pd.DataFrame):
                fact_prices_pdf = fact_prices
            else:
                fact_prices_pdf = fact_prices

            # Select only needed columns for join
            dim_for_join = dim_stock_pdf[['ticker'] + denorm_columns].drop_duplicates()

            before_count = len(fact_prices_pdf)

            # Inner merge to filter AND denormalize
            filtered_prices_pdf = fact_prices_pdf.merge(
                dim_for_join,
                on='ticker',
                how='inner'
            )

            after_count = len(filtered_prices_pdf)
            logger.info(
                f"  JOIN filter + denormalize: {before_count:,} → {after_count:,} prices "
                f"(filtered to {len(dim_for_join)} stock tickers, added {denorm_columns})"
            )

            # Convert back to DuckDB relation if needed
            if hasattr(self.connection, 'conn'):
                facts['fact_stock_prices'] = self.connection.conn.from_df(filtered_prices_pdf)
            else:
                facts['fact_stock_prices'] = filtered_prices_pdf

        return dims, facts

    def get_prices(self, ticker: Optional[str] = None,
                   start_date: Optional[str] = None,
                   end_date: Optional[str] = None) -> Any:
        """
        Get stock price data.

        Args:
            ticker: Specific ticker (optional)
            start_date: Start date filter (YYYY-MM-DD)
            end_date: End date filter (YYYY-MM-DD)

        Returns:
            DataFrame with price data
        """
        prices_df = self.get_table('fact_stock_prices')

        # Apply filters
        if self._backend == 'spark':
            if ticker:
                prices_df = prices_df.filter(prices_df.ticker == ticker)
            if start_date:
                prices_df = prices_df.filter(prices_df.trade_date >= start_date)
            if end_date:
                prices_df = prices_df.filter(prices_df.trade_date <= end_date)
        else:  # duckdb/pandas
            if ticker:
                prices_df = prices_df[prices_df['ticker'] == ticker]
            if start_date:
                prices_df = prices_df[prices_df['trade_date'] >= start_date]
            if end_date:
                prices_df = prices_df[prices_df['trade_date'] <= end_date]

        return prices_df

    def get_technicals(self, ticker: Optional[str] = None,
                       start_date: Optional[str] = None,
                       end_date: Optional[str] = None) -> Any:
        """
        Get technical indicators (from fact_stock_prices which now includes all technicals).

        Args:
            ticker: Specific ticker (optional)
            start_date: Start date filter
            end_date: End date filter

        Returns:
            DataFrame with price data including technical indicators
        """
        # Technical indicators are now consolidated into fact_stock_prices
        return self.get_prices(ticker=ticker, start_date=start_date, end_date=end_date)

    def get_stock_info(self, ticker: Optional[str] = None) -> Any:
        """
        Get stock dimension data.

        Args:
            ticker: Specific ticker (optional)

        Returns:
            DataFrame with stock information
        """
        dim_stock = self.get_table('dim_stock')

        if ticker:
            if self._backend == 'spark':
                return dim_stock.filter(dim_stock.ticker == ticker)
            else:
                return dim_stock[dim_stock['ticker'] == ticker]

        return dim_stock

    def get_stock_with_company(self, ticker: str) -> Any:
        """
        Get stock information with company data.

        Uses cross-model join to company.dim_company.

        Args:
            ticker: Stock ticker symbol

        Returns:
            DataFrame with stock and company information merged
        """
        dim_stock = self.get_stock_info(ticker)

        # Cross-model join to company
        if self.session:
            company_model = self.session.get_model_instance('company')
            company_dim = company_model.get_table('dim_company')

            if self._backend == 'spark':
                return dim_stock.join(
                    company_dim,
                    dim_stock.company_id == company_dim.company_id,
                    'left'
                )
            else:  # pandas
                return dim_stock.merge(company_dim, on='company_id', how='left')

        return dim_stock

    def get_stocks_by_sector(self, sector: str) -> Any:
        """
        Get all stocks in a given sector.

        Args:
            sector: GICS sector name

        Returns:
            DataFrame with stocks in sector
        """
        dim_stock = self.get_table('dim_stock')

        if self._backend == 'spark':
            return dim_stock.filter(dim_stock.sector == sector)
        else:
            return dim_stock[dim_stock['sector'] == sector]

    def list_tickers(self, active_only: bool = True) -> List[str]:
        """
        Get list of all stock tickers.

        Args:
            active_only: Only return active stocks

        Returns:
            List of ticker symbols
        """
        dim_stock = self.get_table('dim_stock')

        if active_only:
            if self._backend == 'spark':
                dim_stock = dim_stock.filter(dim_stock.is_active == True)
            else:
                dim_stock = dim_stock[dim_stock['is_active'] == True]

        if self._backend == 'spark':
            return [row.ticker for row in dim_stock.select('ticker').distinct().collect()]
        else:
            return dim_stock['ticker'].unique().tolist()

    def list_sectors(self) -> List[str]:
        """
        Get list of all sectors.

        Returns:
            List of sector names
        """
        dim_stock = self.get_table('dim_stock')

        if self._backend == 'spark':
            sectors = dim_stock.select('sector').distinct().collect()
            return [row.sector for row in sectors if row.sector]
        else:
            return dim_stock['sector'].dropna().unique().tolist()

    def get_top_by_market_cap(self, limit: int = 10) -> Any:
        """
        Get top stocks by market capitalization.

        Args:
            limit: Number of top stocks to return

        Returns:
            DataFrame with top stocks
        """
        dim_stock = self.get_table('dim_stock')

        if self._backend == 'spark':
            return dim_stock.orderBy(dim_stock.market_cap.desc()).limit(limit)
        else:
            return dim_stock.nlargest(limit, 'market_cap')

    # Complex measures are accessed via calculate_measure()
    # Example:
    #   sharpe = model.calculate_measure('sharpe_ratio', ticker='AAPL')
    #   corr = model.calculate_measure('correlation_matrix', tickers=['AAPL', 'MSFT'])
