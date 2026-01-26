"""
Company Model - Corporate legal entities.

Represents companies as legal entities (not tradable securities).
Primary key is SEC CIK (Central Index Key).

Version: 2.1 - Backend-agnostic via UniversalSession methods
"""

from de_funk.models.base.model import BaseModel
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

    Backend-agnostic: uses session methods for all DataFrame operations.
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

        if self.session:
            return self.session.filter_by_value(dim_company, 'cik', cik)
        elif self.backend == 'spark':
            return dim_company.filter(dim_company.cik == cik)
        else:
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

        if self.session:
            return self.session.filter_by_value(dim_company, 'ticker_primary', ticker)
        elif self.backend == 'spark':
            return dim_company.filter(dim_company.ticker_primary == ticker)
        else:
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

        if self.session:
            return self.session.filter_by_value(dim_company, 'sector', sector)
        elif self.backend == 'spark':
            return dim_company.filter(dim_company.sector == sector)
        else:
            return dim_company[dim_company['sector'] == sector]

    def get_active_companies(self) -> Any:
        """
        Get all active companies.

        Returns:
            DataFrame with active companies
        """
        dim_company = self.get_table('dim_company')

        if self.session:
            return self.session.filter_by_value(dim_company, 'is_active', True)
        elif self.backend == 'spark':
            return dim_company.filter(dim_company.is_active == True)
        else:
            return dim_company[dim_company['is_active'] == True]

    def list_sectors(self) -> List[str]:
        """
        Get list of all sectors.

        Returns:
            List of sector names
        """
        dim_company = self.get_table('dim_company')

        if self.session:
            sectors = self.session.distinct_values(dim_company, 'sector')
            return [s for s in sectors if s is not None]
        elif self.backend == 'spark':
            sectors = dim_company.select('sector').distinct().collect()
            return [row.sector for row in sectors if row.sector]
        else:
            return dim_company['sector'].dropna().unique().tolist()

    def get_company_count_by_sector(self) -> Dict[str, int]:
        """
        Get count of companies by sector.

        Returns:
            Dictionary mapping sector to count
        """
        dim_company = self.get_table('dim_company')

        # Note: aggregation is not yet abstracted in session, using backend-specific code
        if self.backend == 'spark':
            result = dim_company.groupBy('sector').count().collect()
            return {row.sector: row['count'] for row in result if row.sector}
        else:
            if hasattr(dim_company, 'df'):
                return dim_company.df()['sector'].value_counts().to_dict()
            return dim_company['sector'].value_counts().to_dict()

    def after_build(
        self,
        dims: Dict[str, Any],
        facts: Dict[str, Any]
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Post-process fact tables to add correct company_id from dim_company.

        Problem: Bronze financial statement tables only have ticker, not CIK.
        The company_id formula uses COALESCE(cik, ticker), so:
        - dim_company has company_id = HASH('COMPANY_' + cik)
        - fact tables have company_id = HASH('COMPANY_' + ticker)
        These don't match, causing 100% join failure.

        Solution: After dim_company is built, join fact tables by ticker
        to get the correct company_id from dim_company.
        """
        if 'dim_company' not in dims:
            logger.warning("dim_company not found in dims, skipping company_id enrichment")
            return dims, facts

        dim_company = dims['dim_company']

        # Extract company_id mapping: ticker → company_id
        if self.backend == 'spark':
            # Create lookup table with ticker and company_id
            company_id_map = dim_company.select('ticker', 'company_id')

            # Enrich each fact table
            for fact_name, fact_df in facts.items():
                if 'ticker' in fact_df.columns:
                    logger.info(f"Enriching {fact_name} with correct company_id from dim_company")

                    # Drop company_id if it exists (derived from ticker only, not CIK)
                    # We need the correct company_id from dim_company which uses CIK
                    if 'company_id' in fact_df.columns:
                        fact_df = fact_df.drop('company_id')
                        logger.debug(f"  Dropped incorrect company_id (ticker-only) from {fact_name}")

                    # Join with dim_company to get correct company_id (from CIK)
                    fact_df = fact_df.join(
                        company_id_map,
                        on='ticker',
                        how='left'
                    )

                    # Log stats
                    total = fact_df.count()
                    matched = fact_df.filter(fact_df.company_id.isNotNull()).count()
                    logger.info(f"  {fact_name}: {matched:,}/{total:,} rows matched ({matched/total*100:.1f}%)")

                    # Drop ticker - fact table should only have FKs (company_id, date_id)
                    fact_df = fact_df.drop('ticker')
                    logger.debug(f"  Dropped ticker from {fact_name}, keeping only FKs")

                    # Update facts dict
                    facts[fact_name] = fact_df

        else:
            # DuckDB backend
            logger.warning("DuckDB backend not yet implemented for company_id enrichment")
            # TODO: Implement DuckDB version if needed

        return dims, facts

    # Future methods when we add financial data:
    # def get_financials(self, cik: str, start_date=None, end_date=None):
    #     """Get financial statements for a company"""
    #     pass
    #
    # def get_filings(self, cik: str, filing_type=None):
    #     """Get SEC filings for a company"""
    #     pass
