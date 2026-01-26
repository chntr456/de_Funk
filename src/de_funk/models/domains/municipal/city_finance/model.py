"""
CityFinanceModel - Chicago municipal financial and economic data.

Inherits all graph building logic from BaseModel.
Provides convenient access to local unemployment, building permits, and business data.

Version: 2.1 - Backend-agnostic via UniversalSession methods
"""

from typing import Optional, Any, Dict, List
from de_funk.models.base.model import BaseModel
import logging

logger = logging.getLogger(__name__)

# Type alias for DataFrame (can be Spark or DuckDB)
DataFrame = Any


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

    Backend-agnostic: uses session methods for all DataFrame operations.
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

        if self.session:
            if community_area:
                df = self.session.filter_by_value(df, 'geography', community_area)
            df = self.session.filter_by_range(df, 'date', min_val=date_from, max_val=date_to)
            return self.session.order_by(df, ['date', 'geography'])
        elif self.backend == 'spark':
            if community_area:
                df = df.filter(df.geography == community_area)
            if date_from:
                df = df.filter(df.date >= date_from)
            if date_to:
                df = df.filter(df.date <= date_to)
            return df.orderBy('date', 'geography')
        else:
            # DuckDB/pandas
            if community_area:
                df = df[df['geography'] == community_area]
            if date_from:
                df = df[df['date'] >= date_from]
            if date_to:
                df = df[df['date'] <= date_to]
            if hasattr(df, 'sort_values'):
                return df.sort_values(['date', 'geography'])
            return df

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

        if self.session:
            if community_area:
                df = self.session.filter_by_value(df, 'community_area', community_area)
            if permit_type:
                df = self.session.filter_by_value(df, 'permit_type', permit_type)
            df = self.session.filter_by_range(df, 'issue_date', min_val=date_from, max_val=date_to)
            return self.session.order_by(df, 'issue_date')
        elif self.backend == 'spark':
            if community_area:
                df = df.filter(df.community_area == community_area)
            if permit_type:
                df = df.filter(df.permit_type == permit_type)
            if date_from:
                df = df.filter(df.issue_date >= date_from)
            if date_to:
                df = df.filter(df.issue_date <= date_to)
            return df.orderBy('issue_date')
        else:
            # DuckDB/pandas
            if community_area:
                df = df[df['community_area'] == community_area]
            if permit_type:
                df = df[df['permit_type'] == permit_type]
            if date_from:
                df = df[df['issue_date'] >= date_from]
            if date_to:
                df = df[df['issue_date'] <= date_to]
            if hasattr(df, 'sort_values'):
                return df.sort_values('issue_date')
            return df

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

        if self.session:
            if community_area:
                df = self.session.filter_by_value(df, 'community_area', community_area)
            df = self.session.filter_by_range(df, 'issue_date', min_val=date_from, max_val=date_to)
            return self.session.order_by(df, 'issue_date')
        elif self.backend == 'spark':
            if community_area:
                df = df.filter(df.community_area == community_area)
            if date_from:
                df = df.filter(df.issue_date >= date_from)
            if date_to:
                df = df.filter(df.issue_date <= date_to)
            return df.orderBy('issue_date')
        else:
            # DuckDB/pandas
            if community_area:
                df = df[df['community_area'] == community_area]
            if date_from:
                df = df[df['issue_date'] >= date_from]
            if date_to:
                df = df[df['issue_date'] <= date_to]
            if hasattr(df, 'sort_values'):
                return df.sort_values('issue_date')
            return df

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

        if self.session:
            if community_area:
                df = self.session.filter_by_value(df, 'geography', community_area)
            df = self.session.filter_by_range(df, 'date', min_val=date_from, max_val=date_to)
            return self.session.order_by(df, ['date', 'geography'])
        elif self.backend == 'spark':
            if community_area:
                df = df.filter(df.geography == community_area)
            if date_from:
                df = df.filter(df.date >= date_from)
            if date_to:
                df = df.filter(df.date <= date_to)
            return df.orderBy('date', 'geography')
        else:
            # DuckDB/pandas
            if community_area:
                df = df[df['geography'] == community_area]
            if date_from:
                df = df[df['date'] >= date_from]
            if date_to:
                df = df[df['date'] <= date_to]
            if hasattr(df, 'sort_values'):
                return df.sort_values(['date', 'geography'])
            return df

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
        if not self.session:
            raise RuntimeError(
                "CityFinanceModel requires session for cross-model access. "
                "Call set_session() first."
            )

        # Get local unemployment
        local = self.get_local_unemployment(community_area, date_from, date_to)

        # Get national unemployment from macro model
        macro_model = self.session.load_model('macro')
        national = macro_model.get_unemployment(date_from, date_to)

        # Convert both to pandas for joining (works for both backends)
        import pandas as pd

        local_pdf = self.session.to_pandas(local)
        national_pdf = self.session.to_pandas(national)

        # Prepare national data
        national_pdf = national_pdf[['date', 'value']].rename(
            columns={'value': 'national_unemployment_rate'}
        )

        # Join on date
        result = local_pdf.merge(national_pdf, on='date', how='left')

        # Calculate rate difference
        if 'unemployment_rate' in result.columns and 'national_unemployment_rate' in result.columns:
            result['rate_diff'] = result['unemployment_rate'] - result['national_unemployment_rate']

        # Sort and select columns
        result = result.sort_values(['date', 'geography'])

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
        df = self.get_building_permits(date_from=date_from, date_to=date_to)

        if self.session:
            # Convert to pandas for aggregation
            pdf = self.session.to_pandas(df)
            summary = pdf.groupby('community_area').agg(
                total_permits=('permit_number', 'count'),
                total_fees=('total_fee', 'sum'),
                avg_fee=('total_fee', 'mean'),
                permit_types_count=('permit_type', 'nunique')
            ).reset_index().sort_values('total_permits', ascending=False)
            return summary

        elif self.backend == 'spark':
            from pyspark.sql import functions as F

            summary = df.groupBy('community_area').agg(
                F.count('permit_number').alias('total_permits'),
                F.sum('total_fee').alias('total_fees'),
                F.avg('total_fee').alias('avg_fee'),
                F.countDistinct('permit_type').alias('permit_types_count')
            ).orderBy(F.desc('total_permits'))
            return summary
        else:
            # DuckDB/pandas fallback
            if hasattr(df, 'df'):
                pdf = df.df()
            else:
                pdf = df
            summary = pdf.groupby('community_area').agg(
                total_permits=('permit_number', 'count'),
                total_fees=('total_fee', 'sum'),
                avg_fee=('total_fee', 'mean'),
                permit_types_count=('permit_type', 'nunique')
            ).reset_index().sort_values('total_permits', ascending=False)
            return summary

    def list_community_areas(self) -> List[str]:
        """
        Get list of all community area names.

        Returns:
            List of community area names
        """
        df = self.get_community_areas()

        if self.session:
            return self.session.distinct_values(df, 'community_area')
        elif self.backend == 'spark':
            return [row.community_area for row in df.select('community_area').distinct().collect()]
        else:
            if hasattr(df, 'df'):
                return df.df()['community_area'].unique().tolist()
            return df['community_area'].unique().tolist()

    def get_chicago_data_sources(self) -> Dict[str, Any]:
        """
        Get Chicago data source configuration from YAML.

        Returns:
            Dictionary of data source configurations
        """
        return self.model_cfg.get('data_sources', {})
