"""
CompanyModel - Domain model for company financial data.

Inherits all graph building logic from BaseModel.
Only adds company-specific convenience methods.
"""

from typing import Optional, Dict
from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window
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
    # CUSTOM NODE LOADING
    # ============================================================

    def custom_node_loading(self, node_id: str, node_config: Dict) -> Optional[DataFrame]:
        """
        Custom loading for dim_company to add market cap calculation.

        Args:
            node_id: Node identifier
            node_config: Node configuration from YAML

        Returns:
            DataFrame with custom loading, or None for default loading
        """
        if node_id == 'dim_company':
            return self._load_dim_company_with_market_cap(node_config)
        return None

    def _load_dim_company_with_market_cap(self, node_config: Dict) -> DataFrame:
        """
        Load dim_company with market cap proxy calculation.

        Market cap proxy = recent average of (close * volume)
        Uses last 30 days of trading data.

        Args:
            node_config: Node configuration from YAML

        Returns:
            DataFrame with ticker, company_name, exchange_code, company_id, market_cap_proxy
        """
        from pyspark.sql import functions as F

        # Load ref_ticker (company reference data)
        ref_ticker = self._load_bronze_table('ref_ticker')

        # Apply standard select transformations from config
        select_cols = node_config.get('select', {})
        dim_company = ref_ticker.select(
            F.col(select_cols.get('ticker', 'ticker')).alias('ticker'),
            F.col(select_cols.get('company_name', 'name')).alias('company_name'),
            F.col(select_cols.get('exchange_code', 'exchange_code')).alias('exchange_code')
        )

        # Apply derive transformations
        derive_cols = node_config.get('derive', {})
        for col_name, expr in derive_cols.items():
            if expr == "sha1(ticker)":
                dim_company = dim_company.withColumn(col_name, F.sha1(F.col('ticker')))
            else:
                dim_company = dim_company.withColumn(col_name, F.expr(expr))

        # Calculate market cap proxy from recent prices
        try:
            prices = self._load_bronze_table('prices_daily')

            # Calculate market cap proxy: close * volume
            # Use average over last 30 days for stability
            market_cap_calc = (
                prices
                .withColumn('market_cap', F.col('close') * F.col('volume'))
                .groupBy('ticker')
                .agg(
                    F.avg('market_cap').alias('market_cap_proxy'),
                    F.max('trade_date').alias('latest_trade_date')
                )
            )

            # Left join to preserve all companies even if no recent prices
            dim_company = dim_company.join(
                market_cap_calc,
                on='ticker',
                how='left'
            )

            # Fill null market caps with 0 (companies without price data)
            dim_company = dim_company.fillna({'market_cap_proxy': 0.0})

        except Exception as e:
            # If prices not available, add market_cap_proxy as null
            print(f"    Warning: Could not calculate market cap proxy: {e}")
            dim_company = dim_company.withColumn('market_cap_proxy', F.lit(None).cast('double'))

        return dim_company

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
