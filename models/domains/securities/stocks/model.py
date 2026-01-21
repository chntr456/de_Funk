"""
Stocks Model - Common stock equities.

Normalized architecture (v3.0):
- dim_stock FKs to securities.dim_security (master dimension)
- Prices are in securities.fact_security_prices (unified OHLCV)
- Stock-specific tables: fact_stock_technicals, fact_dividends, fact_splits

Version: 3.0 - Normalized securities architecture
"""

from models.base.model import BaseModel
from typing import Optional, Dict, Any, List, Tuple
import logging

logger = logging.getLogger(__name__)

# Type alias for DataFrame (can be Spark or DuckDB)
DataFrame = Any


class StocksModel(BaseModel):
    """
    Common stock equities model (Normalized Architecture v3.0).

    Architecture:
    - dim_stock: Stock-specific attributes, FKs to securities.dim_security and corporate.dim_company
    - Prices: Located in securities.fact_security_prices (unified for all asset types)
    - Technicals: fact_stock_technicals (computed from prices, stock-specific indicators)
    - Corporate actions: fact_dividends, fact_splits (time-series facts)

    Key features:
    - Links to master securities via security_id FK
    - Links to Company model via company_id FK
    - Stock-level attributes: shares_outstanding, market_cap, sector, industry
    - Technical indicators computed from unified price data
    - Backend-agnostic: uses session methods for all DataFrame operations

    Usage:
        from models.domains.securities.stocks import StocksModel
        stocks = StocksModel(connection, storage_cfg, model_cfg)
        stocks.build()

        # Get price data (from securities model)
        prices = stocks.get_prices('AAPL')

        # Calculate measures
        sharpe = stocks.calculate_measure('sharpe_ratio', ticker='AAPL')
    """

    def get_asset_type_filter(self) -> str:
        """
        Return asset type to filter from unified bronze table.

        This is used by the graph building logic to filter
        bronze.securities_reference for dim_stock.

        Returns:
            'stocks' - filters for common stock equities
        """
        return 'stocks'

    # NOTE: Prices are now in securities.fact_security_prices (normalized architecture)
    # No after_build filtering needed - prices are filtered at query time by joining
    # through securities.dim_security via security_id FK.

    def get_prices(self, ticker: Optional[str] = None,
                   start_date: Optional[str] = None,
                   end_date: Optional[str] = None) -> Any:
        """
        Get stock price data from securities.fact_security_prices.

        In the normalized architecture, prices are stored in the securities model.
        This method queries the securities model for prices filtered to stock securities.

        Args:
            ticker: Specific ticker (optional)
            start_date: Start date filter (YYYY-MM-DD)
            end_date: End date filter (YYYY-MM-DD)

        Returns:
            DataFrame with price data (joined with dim_stock for stock-only prices)
        """
        # Get dim_stock for filtering to stock securities only
        dim_stock = self.get_table('dim_stock')

        # Try to get prices from securities model via session
        if self.session:
            try:
                securities_model = self.session.get_model_instance('securities')
                prices_df = securities_model.get_prices(
                    ticker=ticker,
                    asset_type='stocks',
                    start_date_id=int(start_date.replace('-', '')) if start_date else None,
                    end_date_id=int(end_date.replace('-', '')) if end_date else None
                )
                return prices_df
            except Exception as e:
                logger.warning(f"Could not get prices from securities model: {e}")

        # Fallback: Query securities.fact_security_prices directly if available
        # This handles cases where session doesn't have the securities model loaded
        try:
            from pathlib import Path

            # Get storage root from model config or default
            storage_root = Path(self.storage_cfg.get('root', 'storage/silver'))

            if self.backend == 'spark':
                from pyspark.sql import functions as F

                # Load prices from securities silver layer
                securities_prices_path = storage_root.parent / 'securities' / 'fact_security_prices'
                if securities_prices_path.exists():
                    prices_df = self.connection.read.format('delta').load(str(securities_prices_path))

                    # Join with dim_stock to filter to stock securities
                    stock_security_ids = dim_stock.select('security_id').distinct()
                    prices_df = prices_df.join(stock_security_ids, on='security_id', how='inner')

                    if ticker:
                        # Need to join back to dim_stock to filter by ticker
                        dim_with_ticker = dim_stock.select('security_id', 'ticker')
                        prices_df = prices_df.join(dim_with_ticker, on='security_id', how='inner')
                        prices_df = prices_df.filter(F.col('ticker') == ticker)

                    if start_date:
                        start_id = int(start_date.replace('-', ''))
                        prices_df = prices_df.filter(F.col('date_id') >= start_id)
                    if end_date:
                        end_id = int(end_date.replace('-', ''))
                        prices_df = prices_df.filter(F.col('date_id') <= end_id)

                    return prices_df

            logger.warning("Securities prices not available, returning empty result")
            return dim_stock.limit(0)  # Return empty DataFrame with compatible schema

        except Exception as e:
            logger.error(f"Failed to get prices: {e}")
            raise

    def get_technicals(self, ticker: Optional[str] = None,
                       start_date: Optional[str] = None,
                       end_date: Optional[str] = None) -> Any:
        """
        Get technical indicators from fact_stock_technicals.

        In normalized architecture, technicals are computed post-build from
        securities.fact_security_prices and stored in stocks.fact_stock_technicals.

        Args:
            ticker: Specific ticker (optional)
            start_date: Start date filter
            end_date: End date filter

        Returns:
            DataFrame with technical indicators (RSI, MACD, Bollinger, etc.)
        """
        try:
            technicals_df = self.get_table('fact_stock_technicals')

            if self.session:
                if ticker:
                    # Join to dim_stock to filter by ticker
                    dim_stock = self.get_table('dim_stock')
                    stock_row = self.session.filter_by_value(dim_stock, 'ticker', ticker)
                    if stock_row is not None:
                        security_ids = self.session.distinct_values(stock_row, 'security_id')
                        if security_ids:
                            technicals_df = self.session.filter_by_value(technicals_df, 'security_id', security_ids[0])

                technicals_df = self.session.filter_by_range(
                    technicals_df, 'date_id',
                    min_val=int(start_date.replace('-', '')) if start_date else None,
                    max_val=int(end_date.replace('-', '')) if end_date else None
                )

            return technicals_df

        except Exception as e:
            logger.warning(f"Technicals table not available: {e}")
            # Return prices as fallback (without computed technicals)
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

        Uses market_cap column from dim_stock if available (v3.0 architecture stores
        market_cap in dim_stock as a stock-level attribute).

        Args:
            limit: Number of top stocks to return

        Returns:
            DataFrame with top stocks ordered by market cap
        """
        dim_stock = self.get_table('dim_stock')

        # In v3.0 architecture, market_cap is a stock-level attribute in dim_stock
        if self.session:
            return self.session.top_n_by(dim_stock, limit, 'market_cap', ascending=False)
        elif self.backend == 'spark':
            return dim_stock.orderBy(dim_stock.market_cap.desc_nulls_last()).limit(limit)
        else:
            if 'market_cap' in dim_stock.columns:
                return dim_stock.nlargest(limit, 'market_cap')
            else:
                # Fallback to alphabetical if market_cap not available
                return dim_stock.head(limit)

    # Complex measures are accessed via calculate_measure()
    # Example:
    #   sharpe = model.calculate_measure('sharpe_ratio', ticker='AAPL')
    #   corr = model.calculate_measure('correlation_matrix', tickers=['AAPL', 'MSFT'])
