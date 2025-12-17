"""Company API for company model"""

from typing import Optional
from pyspark.sql import DataFrame, functions as F
from models.base.service import BaseAPI


class CompanyAPI(BaseAPI):
    """
    API for accessing company reference data.

    Provides:
    - Company dimension data
    - Active ticker universe
    - Exchange information
    """

    def __init__(self, session):
        """
        Initialize Company API.

        Args:
            session: ModelSession or UniversalSession
        """
        super().__init__(session, model_name='company')

    def dim_company_df(self) -> DataFrame:
        """
        Get company dimension data.

        Returns:
            DataFrame with company info (ticker, name, exchange, etc.)
        """
        return self._get_table('dim_company')

    def active_universe(self, limit: Optional[int] = None) -> DataFrame:
        """
        Get active ticker universe.

        Pulls active tickers from Bronze snapshot.

        Args:
            limit: Optional limit on number of tickers

        Returns:
            DataFrame with ticker column
        """
        df = self.session.bronze("ref_all_tickers").read()
        df = (
            df.where(F.col("active") == True)
            .select("ticker")
            .distinct()
            .orderBy("ticker")
        )

        if limit:
            df = df.limit(int(limit))

        return df

    def get_exchanges(self) -> DataFrame:
        """
        Get exchange dimension data.

        Returns:
            DataFrame with exchange info
        """
        return self._get_table('dim_exchange')
