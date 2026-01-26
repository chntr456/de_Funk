"""
Securities Model - Master domain for all tradable instruments.

Provides the normalized foundation that all security-type models reference:
- dim_security: Master security dimension for ALL tradable instruments
- fact_security_prices: Unified OHLCV price data

Version: 3.0 - Normalized architecture
"""

from de_funk.models.base.model import BaseModel
from typing import Optional, Any, List
import logging

logger = logging.getLogger(__name__)


class SecuritiesModel(BaseModel):
    """
    Master securities model.

    Provides unified access to all tradable instruments regardless of type.
    Child models (stocks, etfs, options, futures) FK to dim_security.

    Tables:
    - dim_security: Master dimension with ticker, asset_type, exchange
    - fact_security_prices: Unified OHLCV for all securities
    """

    def get_security(self, ticker: str) -> Any:
        """
        Get security information by ticker.

        Args:
            ticker: Trading symbol (e.g., 'AAPL', 'SPY')

        Returns:
            DataFrame with security information
        """
        dim_security = self.get_table('dim_security')

        if self.session:
            return self.session.filter_by_value(dim_security, 'ticker', ticker)
        elif self.backend == 'spark':
            return dim_security.filter(dim_security.ticker == ticker)
        else:
            return dim_security[dim_security['ticker'] == ticker]

    def get_securities_by_type(self, asset_type: str) -> Any:
        """
        Get all securities of a given type.

        Args:
            asset_type: Security type ('stocks', 'etf', 'option', 'future')

        Returns:
            DataFrame with securities of that type
        """
        dim_security = self.get_table('dim_security')

        if self.session:
            return self.session.filter_by_value(dim_security, 'asset_type', asset_type)
        elif self.backend == 'spark':
            return dim_security.filter(dim_security.asset_type == asset_type)
        else:
            return dim_security[dim_security['asset_type'] == asset_type]

    def get_securities_by_exchange(self, exchange_code: str) -> Any:
        """
        Get all securities on a given exchange.

        Args:
            exchange_code: Exchange code (e.g., 'NYSE', 'NASDAQ')

        Returns:
            DataFrame with securities on that exchange
        """
        dim_security = self.get_table('dim_security')

        if self.session:
            return self.session.filter_by_value(dim_security, 'exchange_code', exchange_code)
        elif self.backend == 'spark':
            return dim_security.filter(dim_security.exchange_code == exchange_code)
        else:
            return dim_security[dim_security['exchange_code'] == exchange_code]

    def get_active_securities(self) -> Any:
        """
        Get all active (currently trading) securities.

        Returns:
            DataFrame with active securities
        """
        dim_security = self.get_table('dim_security')

        if self.session:
            return self.session.filter_by_value(dim_security, 'is_active', True)
        elif self.backend == 'spark':
            return dim_security.filter(dim_security.is_active == True)
        else:
            return dim_security[dim_security['is_active'] == True]

    def list_asset_types(self) -> List[str]:
        """
        Get list of all asset types.

        Returns:
            List of asset type names
        """
        dim_security = self.get_table('dim_security')

        if self.session:
            types = self.session.distinct_values(dim_security, 'asset_type')
            return [t for t in types if t is not None]
        elif self.backend == 'spark':
            types = dim_security.select('asset_type').distinct().collect()
            return [row.asset_type for row in types if row.asset_type]
        else:
            return dim_security['asset_type'].dropna().unique().tolist()

    def list_exchanges(self) -> List[str]:
        """
        Get list of all exchanges.

        Returns:
            List of exchange codes
        """
        dim_security = self.get_table('dim_security')

        if self.session:
            exchanges = self.session.distinct_values(dim_security, 'exchange_code')
            return [e for e in exchanges if e is not None]
        elif self.backend == 'spark':
            exchanges = dim_security.select('exchange_code').distinct().collect()
            return [row.exchange_code for row in exchanges if row.exchange_code]
        else:
            return dim_security['exchange_code'].dropna().unique().tolist()

    def get_prices(
        self,
        ticker: Optional[str] = None,
        asset_type: Optional[str] = None,
        start_date_id: Optional[int] = None,
        end_date_id: Optional[int] = None
    ) -> Any:
        """
        Get price data for securities.

        Args:
            ticker: Optional ticker filter
            asset_type: Optional asset type filter
            start_date_id: Optional start date (YYYYMMDD format)
            end_date_id: Optional end date (YYYYMMDD format)

        Returns:
            DataFrame with OHLCV price data
        """
        fact_prices = self.get_table('fact_security_prices')
        dim_security = self.get_table('dim_security')

        # Start with prices
        result = fact_prices

        # Filter by ticker if provided (requires join to dim_security)
        if ticker:
            if self.backend == 'spark':
                # Get security_id for ticker
                security_row = dim_security.filter(dim_security.ticker == ticker).first()
                if security_row:
                    result = result.filter(result.security_id == security_row.security_id)
                else:
                    # Return empty if ticker not found
                    return result.limit(0)
            else:
                security_id = dim_security[dim_security['ticker'] == ticker]['security_id'].iloc[0]
                result = result[result['security_id'] == security_id]

        # Filter by asset type
        if asset_type:
            if self.backend == 'spark':
                result = result.filter(result.asset_type == asset_type)
            else:
                result = result[result['asset_type'] == asset_type]

        # Filter by date range
        if start_date_id:
            if self.backend == 'spark':
                result = result.filter(result.date_id >= start_date_id)
            else:
                result = result[result['date_id'] >= start_date_id]

        if end_date_id:
            if self.backend == 'spark':
                result = result.filter(result.date_id <= end_date_id)
            else:
                result = result[result['date_id'] <= end_date_id]

        return result

    def get_security_count_by_type(self) -> dict:
        """
        Get count of securities by asset type.

        Returns:
            Dictionary mapping asset_type to count
        """
        dim_security = self.get_table('dim_security')

        if self.backend == 'spark':
            result = dim_security.groupBy('asset_type').count().collect()
            return {row.asset_type: row['count'] for row in result if row.asset_type}
        else:
            if hasattr(dim_security, 'df'):
                return dim_security.df()['asset_type'].value_counts().to_dict()
            return dim_security['asset_type'].value_counts().to_dict()

    def get_security_count_by_exchange(self) -> dict:
        """
        Get count of securities by exchange.

        Returns:
            Dictionary mapping exchange_code to count
        """
        dim_security = self.get_table('dim_security')

        if self.backend == 'spark':
            result = dim_security.groupBy('exchange_code').count().collect()
            return {row.exchange_code: row['count'] for row in result if row.exchange_code}
        else:
            if hasattr(dim_security, 'df'):
                return dim_security.df()['exchange_code'].value_counts().to_dict()
            return dim_security['exchange_code'].value_counts().to_dict()
