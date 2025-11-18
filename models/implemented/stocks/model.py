"""
Stocks Model - Common stock equities.

Inherits from BaseModel with securities pattern.
Filters bronze data by asset_type='stocks'.

Version: 2.0 - Redesigned with inheritance architecture
"""

from models.base.model import BaseModel
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class StocksModel(BaseModel):
    """
    Common stock equities model.

    Key features:
    - Inherits base securities schema and measures
    - Filters unified bronze prices table by asset_type='stocks'
    - Links to Company model via company_id
    - Includes technical indicators (RSI, MACD, Bollinger Bands, etc.)
    - Supports complex Python measures (Sharpe, correlation, momentum, etc.)

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
        Get technical indicators.

        Args:
            ticker: Specific ticker (optional)
            start_date: Start date filter
            end_date: End date filter

        Returns:
            DataFrame with technical indicators
        """
        technicals_df = self.get_table('fact_stock_technicals')

        # Apply filters
        if self._backend == 'spark':
            if ticker:
                technicals_df = technicals_df.filter(technicals_df.ticker == ticker)
            if start_date:
                technicals_df = technicals_df.filter(technicals_df.trade_date >= start_date)
            if end_date:
                technicals_df = technicals_df.filter(technicals_df.trade_date <= end_date)
        else:  # duckdb/pandas
            if ticker:
                technicals_df = technicals_df[technicals_df['ticker'] == ticker]
            if start_date:
                technicals_df = technicals_df[technicals_df['trade_date'] >= start_date]
            if end_date:
                technicals_df = technicals_df[technicals_df['trade_date'] <= end_date]

        return technicals_df

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
