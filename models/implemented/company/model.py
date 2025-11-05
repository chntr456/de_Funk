"""
CompanyModel - Domain model for company financial data.

Inherits all graph building logic from BaseModel.
Only adds company-specific convenience methods.
"""

from typing import Optional
from pyspark.sql import DataFrame
from models.base.model import BaseModel


class CompanyModel(BaseModel):
    """
    Company domain model.

    Inherits all functionality from BaseModel:
    - Generic graph building from YAML config
    - Node loading from Bronze
    - Edge validation
    - Path materialization
    - Table access methods

    The YAML config (configs/models/company.yaml) drives everything.

    This class only adds company-specific convenience methods.
    """

    # All core functionality is inherited from BaseModel!
    # The YAML config defines:
    # - Nodes: dim_company, dim_exchange, fact_prices, fact_news
    # - Edges: relationships between tables
    # - Paths: prices_with_company, news_with_company

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
