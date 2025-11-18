"""
Company Model - Corporate legal entities.

Represents companies as legal entities (not tradable securities).
Primary key is SEC CIK (Central Index Key).

Version: 2.0 - Redesigned model architecture
"""

from models.base.model import BaseModel
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class CompanyModel(BaseModel):
    """
    Corporate entity model.

    Represents legal business entities with CIK as primary key.
    Companies can have multiple tickers (e.g., Alphabet: GOOGL, GOOG).

    This model focuses on corporate entities, fundamentals, and SEC filings.
    For tradable securities and prices, use StocksModel.
    """

    def get_company_by_cik(self, cik: str) -> Any:
        """
        Get company information by SEC CIK number.

        Args:
            cik: SEC Central Index Key (10 digits, zero-padded)

        Returns:
            DataFrame with company information
        """
        dim_company = self.get_table('dim_company')

        if self._backend == 'spark':
            return dim_company.filter(dim_company.cik == cik)
        else:  # duckdb/pandas
            return dim_company[dim_company['cik'] == cik]

    def get_company_by_ticker(self, ticker: str) -> Any:
        """
        Get company information by primary ticker symbol.

        Args:
            ticker: Trading symbol (e.g., 'AAPL')

        Returns:
            DataFrame with company information
        """
        dim_company = self.get_table('dim_company')

        if self._backend == 'spark':
            return dim_company.filter(dim_company.ticker_primary == ticker)
        else:  # duckdb/pandas
            return dim_company[dim_company['ticker_primary'] == ticker]

    def get_companies_by_sector(self, sector: str) -> Any:
        """
        Get all companies in a given sector.

        Args:
            sector: GICS sector name

        Returns:
            DataFrame with companies in sector
        """
        dim_company = self.get_table('dim_company')

        if self._backend == 'spark':
            return dim_company.filter(dim_company.sector == sector)
        else:  # duckdb/pandas
            return dim_company[dim_company['sector'] == sector]

    def get_active_companies(self) -> Any:
        """
        Get all active companies.

        Returns:
            DataFrame with active companies
        """
        dim_company = self.get_table('dim_company')

        if self._backend == 'spark':
            return dim_company.filter(dim_company.is_active == True)
        else:  # duckdb/pandas
            return dim_company[dim_company['is_active'] == True]

    def list_sectors(self) -> List[str]:
        """
        Get list of all sectors.

        Returns:
            List of sector names
        """
        dim_company = self.get_table('dim_company')

        if self._backend == 'spark':
            sectors = dim_company.select('sector').distinct().collect()
            return [row.sector for row in sectors if row.sector]
        else:  # duckdb/pandas
            return dim_company['sector'].dropna().unique().tolist()

    def get_company_count_by_sector(self) -> Dict[str, int]:
        """
        Get count of companies by sector.

        Returns:
            Dictionary mapping sector to count
        """
        dim_company = self.get_table('dim_company')

        if self._backend == 'spark':
            result = dim_company.groupBy('sector').count().collect()
            return {row.sector: row['count'] for row in result if row.sector}
        else:  # duckdb/pandas
            return dim_company['sector'].value_counts().to_dict()

    # Future methods when we add financial data:
    # def get_financials(self, cik: str, start_date=None, end_date=None):
    #     """Get financial statements for a company"""
    #     pass
    #
    # def get_filings(self, cik: str, filing_type=None):
    #     """Get SEC filings for a company"""
    #     pass
