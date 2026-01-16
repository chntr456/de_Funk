"""
Stocks Model - Common stock equities.

Inherits from BaseModel with securities pattern.
Filters bronze data by asset_type='stocks'.

Version: 2.1 - Backend-agnostic via UniversalSession methods
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
    - Backend-agnostic: uses session methods for all DataFrame operations

    Architecture Note:
        Bronze prices table may have NULL asset_type. Instead of filtering by
        asset_type='stocks', we filter fact_stock_prices to only include tickers
        that exist in dim_stock (which IS filtered by asset_type='stocks' from
        the securities_reference table). This JOIN-based approach is more robust.

    Usage:
        from models.domains.securities.stocks import StocksModel
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
        Post-build hook: Filter fact_stock_prices to only securities in dim_stock.

        This implements JOIN-based filtering for the prices table. Since Bronze
        prices may have NULL asset_type, we can't filter directly. Instead, we:
        1. Build dim_stock (filtered by asset_type='stocks' from securities_reference)
        2. Build fact_stock_prices (all prices, no asset_type filter)
        3. Filter fact_stock_prices to only security_ids that exist in dim_stock

        This ensures we only have prices for actual stock securities.

        Note: Dimension columns (sector, exchange_code) are accessed via auto-join
        at query time using the model graph edges, not denormalized here.

        Note: Facts use security_id (FK) not ticker. Ticker is dropped after deriving FKs.
        """
        # Check if we have both tables
        if 'dim_stock' not in dims or 'fact_stock_prices' not in facts:
            logger.warning("Missing dim_stock or fact_stock_prices, skipping JOIN filter")
            return dims, facts

        dim_stock = dims['dim_stock']
        fact_prices = facts['fact_stock_prices']

        # Use session methods if available, otherwise fall back to direct approach
        if self.session:
            # Count before filtering
            before_count = self.session.row_count(fact_prices)

            # Semi-join on security_id (FK pattern - facts don't have ticker)
            filtered_prices = self.session.semi_join(fact_prices, dim_stock, on='security_id')

            after_count = self.session.row_count(filtered_prices)
            security_count = len(self.session.distinct_values(dim_stock, 'security_id'))

            logger.info(
                f"  JOIN filter: {before_count:,} → {after_count:,} prices "
                f"(filtered to {security_count} stock securities)"
            )

            facts['fact_stock_prices'] = filtered_prices
        else:
            # Fallback for when session is not available (e.g., during initial build)
            # Use backend property from BaseModel
            if self.backend == 'spark':
                # Semi-join on security_id (not ticker - ticker is dropped from facts)
                stock_security_ids = dim_stock.select('security_id').distinct()
                before_count = fact_prices.count()
                filtered_prices = fact_prices.join(stock_security_ids, on='security_id', how='left_semi')
                after_count = filtered_prices.count()
                logger.info(
                    f"  JOIN filter: {before_count:,} → {after_count:,} prices "
                    f"(filtered to {stock_security_ids.count()} stock securities)"
                )
                facts['fact_stock_prices'] = filtered_prices
            else:
                import pandas as pd
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

                # Filter by security_id (not ticker - ticker is dropped from facts)
                stock_security_ids = set(dim_stock_pdf['security_id'].unique())
                before_count = len(fact_prices_pdf)
                filtered_prices_pdf = fact_prices_pdf[fact_prices_pdf['security_id'].isin(stock_security_ids)]
                after_count = len(filtered_prices_pdf)

                logger.info(
                    f"  JOIN filter: {before_count:,} → {after_count:,} prices "
                    f"(filtered to {len(stock_security_ids)} stock securities)"
                )

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

        # Use session methods if available
        if self.session:
            if ticker:
                prices_df = self.session.filter_by_value(prices_df, 'ticker', ticker)
            prices_df = self.session.filter_by_range(
                prices_df, 'trade_date', min_val=start_date, max_val=end_date
            )
        else:
            # Fallback for when session is not available
            if self.backend == 'spark':
                if ticker:
                    prices_df = prices_df.filter(prices_df.ticker == ticker)
                if start_date:
                    prices_df = prices_df.filter(prices_df.trade_date >= start_date)
                if end_date:
                    prices_df = prices_df.filter(prices_df.trade_date <= end_date)
            else:
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
            if self.session:
                return self.session.filter_by_value(dim_stock, 'ticker', ticker)
            elif self.backend == 'spark':
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
            return self.session.join(dim_stock, company_dim, on=['company_id'], how='left')

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

        if self.session:
            return self.session.filter_by_value(dim_stock, 'sector', sector)
        elif self.backend == 'spark':
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
            if self.session:
                dim_stock = self.session.filter_by_value(dim_stock, 'is_active', True)
            elif self.backend == 'spark':
                dim_stock = dim_stock.filter(dim_stock.is_active == True)
            else:
                dim_stock = dim_stock[dim_stock['is_active'] == True]

        if self.session:
            return self.session.distinct_values(dim_stock, 'ticker')
        elif self.backend == 'spark':
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

        if self.session:
            sectors = self.session.distinct_values(dim_stock, 'sector')
            return [s for s in sectors if s is not None]
        elif self.backend == 'spark':
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

        if self.session:
            return self.session.top_n_by(dim_stock, limit, 'market_cap', ascending=False)
        elif self.backend == 'spark':
            return dim_stock.orderBy(dim_stock.market_cap.desc()).limit(limit)
        else:
            return dim_stock.nlargest(limit, 'market_cap')

    # Complex measures are accessed via calculate_measure()
    # Example:
    #   sharpe = model.calculate_measure('sharpe_ratio', ticker='AAPL')
    #   corr = model.calculate_measure('correlation_matrix', tickers=['AAPL', 'MSFT'])
