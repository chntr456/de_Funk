"""
CorporateModel - Domain model for corporate entity data.

This model represents legal business entities (companies) with fundamentals,
SEC filings, and financial statement data.

Key distinction from EquityModel:
- CorporateModel: Legal entities (company, CIK, SEC filings, fundamentals)
- EquityModel: Trading instruments (ticker, prices, volume, technicals)

Relationship: One corporate entity can have many equities
Example: Alphabet Inc. → GOOG + GOOGL

Inherits all graph building logic from BaseModel.
Adds corporate-specific convenience methods.
"""

from typing import Optional, List, Dict, Any
from models.base.model import BaseModel

# Bootstrap corporate-specific domain features when this model is loaded
# This ensures fundamentals calculations are available for corporate measures
import models.domains.corporate.fundamentals


class CorporateModel(BaseModel):
    """
    Corporate domain model for legal business entities.

    Inherits all functionality from BaseModel:
    - Generic graph building from YAML config
    - Node loading from Bronze
    - Edge validation
    - Path materialization
    - Table access methods
    - Unified measure execution framework

    The YAML config (configs/models/corporate.yaml) drives everything.

    This class adds corporate-specific convenience methods.
    """

    # All core functionality is inherited from BaseModel!
    # The YAML config defines:
    # - Nodes: dim_corporate, fact_sec_filings, fact_financials, fact_financial_ratios
    # - Edges: company relationships, cross-model link to equity
    # - Measures: fundamental ratios, financial aggregates

    # ============================================================
    # CORPORATE-SPECIFIC MEASURE CALCULATIONS
    # ============================================================

    def calculate_measure_by_company(
        self,
        measure_name: str,
        companies: Optional[List[str]] = None,
        limit: Optional[int] = None,
        **kwargs
    ):
        """
        Calculate a measure aggregated by company_id.

        This is a convenience wrapper around BaseModel.calculate_measure()
        specifically for the 'company_id' entity column.

        Args:
            measure_name: Name of measure from config (e.g., 'avg_revenue', 'avg_pe_ratio')
            companies: Optional list of company_ids to filter
            limit: Optional limit for top-N results
            **kwargs: Additional filters (e.g., report_date={'start': '2024-01-01'})

        Returns:
            QueryResult with data and metadata

        Example:
            # Simple measure - average revenue by company
            result = corporate_model.calculate_measure_by_company('avg_revenue', limit=10)
            df = result.data  # DataFrame with company_id, avg_revenue columns

            # With filters
            result = corporate_model.calculate_measure_by_company(
                'avg_pe_ratio',
                companies=['COMPANY_AAPL', 'COMPANY_MSFT'],
                report_date={'start': '2023-01-01', 'end': '2023-12-31'}
            )
        """
        # Build filters
        filters = kwargs.copy()
        if companies:
            filters['company_id'] = companies

        return self.calculate_measure(
            measure_name=measure_name,
            entity_column='company_id',
            filters=filters,
            limit=limit
        )

    def get_top_companies_by_measure(
        self,
        measure_name: str,
        limit: int = 10,
        **kwargs
    ) -> List[str]:
        """
        Get list of top companies by a measure.

        Convenience method that returns just the company_id list.

        Args:
            measure_name: Name of measure from config
            limit: Number of top companies to return
            **kwargs: Additional filters

        Returns:
            List of company_ids, ordered by measure value descending

        Example:
            # Get top 10 companies by revenue
            companies = corporate_model.get_top_companies_by_measure('avg_revenue', limit=10)
            # Returns: ['COMPANY_AAPL', 'COMPANY_MSFT', ...]

            # Get top 10 by ROE
            companies = corporate_model.get_top_companies_by_measure('avg_roe', limit=10)
        """
        result = self.calculate_measure_by_company(measure_name, limit=limit, **kwargs)

        # Handle both Pandas and Spark DataFrames
        if self.backend == 'duckdb':
            return result.data['company_id'].tolist()
        else:  # spark
            return [row['company_id'] for row in result.data.collect()]

    # ============================================================
    # CORPORATE-SPECIFIC CONVENIENCE METHODS
    # ============================================================

    def get_company_info(
        self,
        company_ids: Optional[List[str]] = None,
        tickers: Optional[List[str]] = None,
        limit: Optional[int] = None
    ):
        """
        Get corporate entity information.

        Args:
            company_ids: Optional list of company_ids to filter
            tickers: Optional list of primary tickers to filter
            limit: Optional row limit

        Returns:
            DataFrame with company info

        Example:
            # Get info for specific companies
            df = corporate_model.get_company_info(
                company_ids=['COMPANY_AAPL', 'COMPANY_MSFT']
            )

            # Get info by ticker
            df = corporate_model.get_company_info(
                tickers=['AAPL', 'MSFT']
            )
        """
        # Build filters
        filters = {}
        if company_ids:
            filters['company_id'] = company_ids
        if tickers:
            filters['ticker_primary'] = tickers

        return self.query_table('dim_corporate', filters=filters, limit=limit)

    def get_sec_filings(
        self,
        company_ids: Optional[List[str]] = None,
        filing_types: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = None
    ):
        """
        Get SEC filing metadata (future enhancement).

        Args:
            company_ids: Optional list of company_ids to filter
            filing_types: Optional list of filing types (e.g., ['10-K', '10-Q'])
            start_date: Optional start date for filing_date
            end_date: Optional end date for filing_date
            limit: Optional row limit

        Returns:
            DataFrame with filing metadata

        Example:
            # Get all 10-K filings for AAPL
            df = corporate_model.get_sec_filings(
                company_ids=['COMPANY_AAPL'],
                filing_types=['10-K'],
                start_date='2020-01-01'
            )

        Note:
            This requires SEC EDGAR data ingestion to be implemented.
            Currently returns empty result.
        """
        # Build filters
        filters = {}
        if company_ids:
            filters['company_id'] = company_ids
        if filing_types:
            filters['filing_type'] = filing_types
        if start_date or end_date:
            date_filter = {}
            if start_date:
                date_filter['start'] = start_date
            if end_date:
                date_filter['end'] = end_date
            filters['filing_date'] = date_filter

        return self.query_table('fact_sec_filings', filters=filters, limit=limit)

    def get_financials(
        self,
        company_ids: Optional[List[str]] = None,
        statement_type: Optional[str] = None,
        report_period: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = None
    ):
        """
        Get financial statement data (future enhancement).

        Args:
            company_ids: Optional list of company_ids to filter
            statement_type: Optional statement type ('income', 'balance_sheet', 'cash_flow')
            report_period: Optional report period ('Q1', 'Q2', 'Q3', 'Q4', 'FY')
            start_date: Optional start date for report_date
            end_date: Optional end date for report_date
            limit: Optional row limit

        Returns:
            DataFrame with financial statement data

        Example:
            # Get annual income statements for AAPL
            df = corporate_model.get_financials(
                company_ids=['COMPANY_AAPL'],
                statement_type='income',
                report_period='FY',
                start_date='2020-01-01'
            )
            print(df[['company_id', 'report_date', 'revenue', 'net_income']])

        Note:
            This requires SEC EDGAR or financial data provider integration.
            Currently returns empty result.
        """
        # Build filters
        filters = {}
        if company_ids:
            filters['company_id'] = company_ids
        if statement_type:
            filters['statement_type'] = statement_type
        if report_period:
            filters['report_period'] = report_period
        if start_date or end_date:
            date_filter = {}
            if start_date:
                date_filter['start'] = start_date
            if end_date:
                date_filter['end'] = end_date
            filters['report_date'] = date_filter

        return self.query_table('fact_financials', filters=filters, limit=limit)

    def get_financial_ratios(
        self,
        company_ids: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = None
    ):
        """
        Get calculated financial ratios (future enhancement).

        Args:
            company_ids: Optional list of company_ids to filter
            start_date: Optional start date for report_date
            end_date: Optional end date for report_date
            limit: Optional row limit

        Returns:
            DataFrame with financial ratios

        Example:
            # Get ratios for AAPL
            df = corporate_model.get_financial_ratios(
                company_ids=['COMPANY_AAPL'],
                start_date='2020-01-01'
            )
            print(df[['company_id', 'report_date', 'pe_ratio', 'roe', 'debt_to_equity']])

        Note:
            This requires financial data integration.
            Currently returns empty result.
        """
        # Build filters
        filters = {}
        if company_ids:
            filters['company_id'] = company_ids
        if start_date or end_date:
            date_filter = {}
            if start_date:
                date_filter['start'] = start_date
            if end_date:
                date_filter['end'] = end_date
            filters['report_date'] = date_filter

        return self.query_table('fact_financial_ratios', filters=filters, limit=limit)

    def screen_by_fundamentals(
        self,
        pe_max: Optional[float] = None,
        roe_min: Optional[float] = None,
        debt_to_equity_max: Optional[float] = None,
        revenue_growth_min: Optional[float] = None,
        **kwargs
    ) -> List[str]:
        """
        Screen companies by fundamental criteria (future enhancement).

        Returns list of company_ids that meet the criteria.

        Args:
            pe_max: Maximum P/E ratio (e.g., 15 for undervalued)
            roe_min: Minimum ROE (e.g., 15 for profitable)
            debt_to_equity_max: Maximum D/E ratio (e.g., 0.5 for low leverage)
            revenue_growth_min: Minimum revenue growth YoY (e.g., 0.10 for 10%)
            **kwargs: Additional filters (date range, etc.)

        Returns:
            List of company_ids

        Example:
            # Find undervalued, profitable, low-debt companies
            companies = corporate_model.screen_by_fundamentals(
                pe_max=15,
                roe_min=15,
                debt_to_equity_max=0.5,
                report_date={'start': '2023-01-01'}
            )

        Note:
            This requires financial data integration.
            Currently returns empty list.
        """
        # Get ratio data
        df = self.get_financial_ratios(**kwargs)

        # Convert to pandas for filtering (if Spark)
        if self.backend == 'spark':
            df = df.toPandas()

        # Apply filters
        if pe_max is not None:
            df = df[df['pe_ratio'] <= pe_max]
        if roe_min is not None:
            df = df[df['roe'] >= roe_min]
        if debt_to_equity_max is not None:
            df = df[df['debt_to_equity'] <= debt_to_equity_max]
        if revenue_growth_min is not None:
            df = df[df['revenue_growth_yoy'] >= revenue_growth_min]

        # Return unique company_ids
        return df['company_id'].unique().tolist()
