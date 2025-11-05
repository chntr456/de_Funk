"""
CityFinanceModel - Chicago municipal financial and economic data.

Inherits all graph building logic from BaseModel.
Provides convenient access to local unemployment, building permits, and business data.
"""

from typing import Optional
from pyspark.sql import DataFrame
from models.base.model import BaseModel


class CityFinanceModel(BaseModel):
    """
    City finance model - Chicago municipal data.

    Inherits all functionality from BaseModel:
    - Generic graph building from YAML config
    - Node loading from Bronze (Chicago data)
    - Edge validation
    - Path materialization
    - Table access methods

    The YAML config (configs/models/city_finance.yaml) drives everything.

    Data includes:
    - Unemployment by community area (monthly)
    - Building permits (event-based)
    - Business licenses (event-based)
    - Economic indicators (monthly)

    Cross-model dependency:
    - Depends on macro model for national vs local comparisons
    """

    def __init__(self, connection, storage_cfg: dict, model_cfg: dict, params: dict = None):
        """
        Initialize City Finance Model.

        Args:
            connection: Database connection (Spark or DuckDB)
            storage_cfg: Storage configuration
            model_cfg: Model configuration from YAML
            params: Runtime parameters
        """
        super().__init__(connection, storage_cfg, model_cfg, params)
        self._session: Optional['UniversalSession'] = None

    def set_session(self, session):
        """
        Inject session for cross-model access.

        City finance model can access macro model for comparisons.

        Args:
            session: UniversalSession instance
        """
        self._session = session

    # ============================================================
    # CITY FINANCE CONVENIENCE METHODS
    # ============================================================

    def get_local_unemployment(
        self,
        community_area: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> DataFrame:
        """
        Get local unemployment by community area.

        Args:
            community_area: Optional community area filter
            date_from: Start date (YYYY-MM-DD) optional
            date_to: End date (YYYY-MM-DD) optional

        Returns:
            DataFrame with local unemployment data
        """
        df = self.get_fact_df('fact_local_unemployment')

        if community_area:
            df = df.filter(df.geography == community_area)
        if date_from:
            df = df.filter(df.date >= date_from)
        if date_to:
            df = df.filter(df.date <= date_to)

        return df.orderBy('date', 'geography')

    def get_building_permits(
        self,
        community_area: Optional[str] = None,
        permit_type: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> DataFrame:
        """
        Get building permits data.

        Args:
            community_area: Optional community area filter
            permit_type: Optional permit type filter
            date_from: Start date (YYYY-MM-DD) optional
            date_to: End date (YYYY-MM-DD) optional

        Returns:
            DataFrame with building permits
        """
        df = self.get_fact_df('fact_building_permits')

        if community_area:
            df = df.filter(df.community_area == community_area)
        if permit_type:
            df = df.filter(df.permit_type == permit_type)
        if date_from:
            df = df.filter(df.issue_date >= date_from)
        if date_to:
            df = df.filter(df.issue_date <= date_to)

        return df.orderBy('issue_date')

    def get_permits_with_context(
        self,
        community_area: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> DataFrame:
        """
        Get building permits with full community area context.

        This uses a materialized path from the graph.

        Args:
            community_area: Optional community area filter
            date_from: Start date (YYYY-MM-DD) optional
            date_to: End date (YYYY-MM-DD) optional

        Returns:
            DataFrame with permits and community area details
        """
        df = self.get_table('permits_with_area')

        if community_area:
            df = df.filter(df.community_area == community_area)
        if date_from:
            df = df.filter(df.issue_date >= date_from)
        if date_to:
            df = df.filter(df.issue_date <= date_to)

        return df.orderBy('issue_date')

    def get_unemployment_with_context(
        self,
        community_area: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> DataFrame:
        """
        Get unemployment with full community area context.

        This uses a materialized path from the graph.

        Args:
            community_area: Optional community area filter
            date_from: Start date (YYYY-MM-DD) optional
            date_to: End date (YYYY-MM-DD) optional

        Returns:
            DataFrame with unemployment and community area details
        """
        df = self.get_table('unemployment_with_area')

        if community_area:
            df = df.filter(df.geography == community_area)
        if date_from:
            df = df.filter(df.date >= date_from)
        if date_to:
            df = df.filter(df.date <= date_to)

        return df.orderBy('date', 'geography')

    def get_community_areas(self) -> DataFrame:
        """
        Get all Chicago community areas.

        Returns:
            DataFrame with community area dimension data
        """
        return self.get_dimension_df('dim_community_area')

    def get_permit_types(self) -> DataFrame:
        """
        Get all permit types.

        Returns:
            DataFrame with permit type dimension data
        """
        return self.get_dimension_df('dim_permit_type')

    # ============================================================
    # CROSS-MODEL ANALYSIS
    # ============================================================

    def compare_to_national_unemployment(
        self,
        community_area: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> DataFrame:
        """
        Compare local unemployment to national rate.

        Requires macro model to be loaded in session.

        Args:
            community_area: Optional community area filter
            date_from: Start date (YYYY-MM-DD) optional
            date_to: End date (YYYY-MM-DD) optional

        Returns:
            DataFrame with local and national unemployment side by side

        Raises:
            RuntimeError: If session not set or macro model unavailable
        """
        if not self._session:
            raise RuntimeError(
                "CityFinanceModel requires session for cross-model access. "
                "Call set_session() first."
            )

        # Get local unemployment
        local = self.get_local_unemployment(community_area, date_from, date_to)

        # Get national unemployment from macro model
        macro_model = self._session.load_model('macro')
        national = macro_model.get_unemployment(date_from, date_to)

        # Join on date
        from pyspark.sql import functions as F

        result = local.alias('local').join(
            national.select(
                F.col('date'),
                F.col('value').alias('national_unemployment_rate')
            ).alias('national'),
            on='date',
            how='left'
        ).select(
            'local.date',
            'local.geography',
            F.col('local.unemployment_rate').alias('local_unemployment_rate'),
            'national_unemployment_rate',
            (F.col('local.unemployment_rate') - F.col('national_unemployment_rate')).alias('rate_diff')
        ).orderBy('date', 'geography')

        return result

    def get_permit_summary_by_area(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> DataFrame:
        """
        Get summary of permits by community area.

        Args:
            date_from: Start date (YYYY-MM-DD) optional
            date_to: End date (YYYY-MM-DD) optional

        Returns:
            DataFrame with permit counts and fees by area
        """
        from pyspark.sql import functions as F

        df = self.get_building_permits(date_from=date_from, date_to=date_to)

        summary = df.groupBy('community_area').agg(
            F.count('permit_number').alias('total_permits'),
            F.sum('total_fee').alias('total_fees'),
            F.avg('total_fee').alias('avg_fee'),
            F.countDistinct('permit_type').alias('permit_types_count')
        ).orderBy(F.desc('total_permits'))

        return summary

    def get_chicago_data_sources(self) -> dict:
        """
        Get Chicago data source configuration from YAML.

        Returns:
            Dictionary of data source configurations
        """
        return self.model_cfg.get('data_sources', {})
