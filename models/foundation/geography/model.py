"""
GeographyModel - US location reference dimensions.

This model contains location-based dimensions:
- dim_state: US states with FIPS codes and census regions
- dim_county: US counties with FIPS codes
- dim_city: US cities and incorporated places
- dim_zip: US ZIP codes with coordinates

All location-based models can depend on geography for geographic joins.

Version: 2.0 - Backend-agnostic via UniversalSession methods
"""

from typing import Optional, Any, Dict, List
from models.base.model import BaseModel
import logging

logger = logging.getLogger(__name__)

# Type alias for DataFrame (can be Spark or DuckDB)
DataFrame = Any


class GeographyModel(BaseModel):
    """
    Geography model - US location reference dimensions.

    Inherits all functionality from BaseModel:
    - Generic graph building from YAML config
    - Node loading from Bronze
    - Table access methods

    This model is foundational because:
    - It has no dependencies (it's the geographic foundation)
    - Other models depend on it for location-based queries
    - It provides state, county, city, and ZIP reference data

    The YAML config (configs/models/geography/) drives everything.

    Backend-agnostic: uses session methods for all DataFrame operations.
    """

    # ============================================================
    # CORE MODEL CONVENIENCE METHODS
    # ============================================================

    def get_states(
        self,
        region: Optional[str] = None,
        division: Optional[str] = None,
        states_only: bool = True
    ) -> DataFrame:
        """
        Get US states dimension data.

        Args:
            region: Filter by census region (Northeast, South, Midwest, West)
            division: Filter by census division
            states_only: If True, exclude territories (default True)

        Returns:
            DataFrame with state dimension data
        """
        df = self.get_dimension_df('dim_state')

        if self.session:
            if states_only:
                df = self.session.filter_by_value(df, 'is_state', True)
            if region:
                df = self.session.filter_by_value(df, 'region', region)
            if division:
                df = self.session.filter_by_value(df, 'division', division)
            return self.session.order_by(df, 'state_name')
        else:
            # Fallback for when session is not available
            if self.backend == 'spark':
                if states_only:
                    df = df.filter(df.is_state == True)
                if region:
                    df = df.filter(df.region == region)
                if division:
                    df = df.filter(df.division == division)
                return df.orderBy('state_name')
            else:
                # DuckDB/pandas
                if states_only:
                    df = df[df['is_state'] == True]
                if region:
                    df = df[df['region'] == region]
                if division:
                    df = df[df['division'] == division]
                return df.sort_values('state_name') if hasattr(df, 'sort_values') else df

    def get_counties(
        self,
        state_fips: Optional[str] = None,
        state_code: Optional[str] = None
    ) -> DataFrame:
        """
        Get US counties dimension data.

        Args:
            state_fips: Filter by 2-digit state FIPS code
            state_code: Filter by 2-letter state code (converted to FIPS internally)

        Returns:
            DataFrame with county dimension data
        """
        df = self.get_dimension_df('dim_county')

        # Convert state_code to state_fips if provided
        if state_code and not state_fips:
            state_fips = self._get_state_fips(state_code)

        if self.session:
            if state_fips:
                df = self.session.filter_by_value(df, 'state_fips', state_fips)
            return self.session.order_by(df, 'county_name')
        elif self.backend == 'spark':
            if state_fips:
                df = df.filter(df.state_fips == state_fips)
            return df.orderBy('county_name')
        else:
            if state_fips:
                df = df[df['state_fips'] == state_fips]
            return df.sort_values('county_name') if hasattr(df, 'sort_values') else df

    def get_cities(
        self,
        state_fips: Optional[str] = None,
        county_fips: Optional[str] = None,
        capitals_only: bool = False
    ) -> DataFrame:
        """
        Get US cities dimension data.

        Args:
            state_fips: Filter by 2-digit state FIPS code
            county_fips: Filter by 5-digit county FIPS code
            capitals_only: If True, only return state capitals

        Returns:
            DataFrame with city dimension data
        """
        df = self.get_dimension_df('dim_city')

        if self.session:
            if state_fips:
                df = self.session.filter_by_value(df, 'state_fips', state_fips)
            if county_fips:
                df = self.session.filter_by_value(df, 'county_fips', county_fips)
            if capitals_only:
                df = self.session.filter_by_value(df, 'is_capital', True)
            return self.session.order_by(df, 'city_name')
        elif self.backend == 'spark':
            if state_fips:
                df = df.filter(df.state_fips == state_fips)
            if county_fips:
                df = df.filter(df.county_fips == county_fips)
            if capitals_only:
                df = df.filter(df.is_capital == True)
            return df.orderBy('city_name')
        else:
            if state_fips:
                df = df[df['state_fips'] == state_fips]
            if county_fips:
                df = df[df['county_fips'] == county_fips]
            if capitals_only:
                df = df[df['is_capital'] == True]
            return df.sort_values('city_name') if hasattr(df, 'sort_values') else df

    def get_zip_codes(
        self,
        state_code: Optional[str] = None,
        county_fips: Optional[str] = None,
        zip_type: Optional[str] = None
    ) -> DataFrame:
        """
        Get US ZIP codes dimension data.

        Args:
            state_code: Filter by 2-letter state code
            county_fips: Filter by 5-digit county FIPS code
            zip_type: Filter by ZIP type ('Standard', 'PO Box', 'Unique')

        Returns:
            DataFrame with ZIP code dimension data
        """
        df = self.get_dimension_df('dim_zip')

        if self.session:
            if state_code:
                df = self.session.filter_by_value(df, 'state_code', state_code)
            if county_fips:
                df = self.session.filter_by_value(df, 'county_fips', county_fips)
            if zip_type:
                df = self.session.filter_by_value(df, 'zip_type', zip_type)
            return self.session.order_by(df, 'zip_code')
        elif self.backend == 'spark':
            if state_code:
                df = df.filter(df.state_code == state_code)
            if county_fips:
                df = df.filter(df.county_fips == county_fips)
            if zip_type:
                df = df.filter(df.zip_type == zip_type)
            return df.orderBy('zip_code')
        else:
            if state_code:
                df = df[df['state_code'] == state_code]
            if county_fips:
                df = df[df['county_fips'] == county_fips]
            if zip_type:
                df = df[df['zip_type'] == zip_type]
            return df.sort_values('zip_code') if hasattr(df, 'sort_values') else df

    def _get_state_fips(self, state_code: str) -> Optional[str]:
        """
        Convert 2-letter state code to 2-digit FIPS code.

        Args:
            state_code: 2-letter state code (e.g., 'IL')

        Returns:
            2-digit FIPS code (e.g., '17') or None if not found
        """
        try:
            df = self.get_dimension_df('dim_state')
            if self.session:
                filtered = self.session.filter_by_value(df, 'state_code', state_code.upper())
                result = self.session.to_pandas(filtered)
            elif self.backend == 'spark':
                result = df.filter(df.state_code == state_code.upper()).toPandas()
            else:
                result = df[df['state_code'] == state_code.upper()]

            if len(result) > 0:
                return result.iloc[0]['state_fips']
        except Exception as e:
            logger.warning(f"Could not convert state code '{state_code}' to FIPS: {e}")
        return None

    def get_state_info(self, state_code: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific state.

        Args:
            state_code: 2-letter state code (e.g., 'IL')

        Returns:
            Dictionary with state information
        """
        df = self.get_states(states_only=False)

        if self.session:
            filtered = self.session.filter_by_value(df, 'state_code', state_code.upper())
            result = self.session.to_pandas(filtered)
        elif self.backend == 'spark':
            result = df.filter(df.state_code == state_code.upper()).toPandas()
        else:
            result = df[df['state_code'] == state_code.upper()]

        if len(result) == 0:
            return {}

        row = result.iloc[0]
        return {
            'state_fips': row['state_fips'],
            'state_code': row['state_code'],
            'state_name': row['state_name'],
            'region': row['region'],
            'division': row['division'],
            'is_state': row['is_state'],
            'population': row['population'],
            'land_area_sq_mi': row['land_area_sq_mi']
        }

    def get_geography_summary(self) -> Dict[str, Any]:
        """
        Get summary statistics about the geography data.

        Returns:
            Dictionary with geography statistics
        """
        summary = {}

        try:
            states_df = self.get_dimension_df('dim_state')
            counties_df = self.get_dimension_df('dim_county')

            if self.session:
                states_pdf = self.session.to_pandas(states_df)
                counties_pdf = self.session.to_pandas(counties_df)
            elif self.backend == 'spark':
                states_pdf = states_df.toPandas()
                counties_pdf = counties_df.toPandas()
            else:
                states_pdf = states_df if hasattr(states_df, 'iloc') else states_df.df()
                counties_pdf = counties_df if hasattr(counties_df, 'iloc') else counties_df.df()

            summary['total_states'] = len(states_pdf[states_pdf['is_state'] == True])
            summary['total_territories'] = len(states_pdf[states_pdf['is_state'] == False])
            summary['total_counties'] = len(counties_pdf)
            summary['regions'] = states_pdf['region'].nunique()
            summary['divisions'] = states_pdf['division'].nunique()

            # Try to get ZIP and city counts if available
            try:
                zips_df = self.get_dimension_df('dim_zip')
                if self.session:
                    zips_pdf = self.session.to_pandas(zips_df)
                elif self.backend == 'spark':
                    zips_pdf = zips_df.toPandas()
                else:
                    zips_pdf = zips_df if hasattr(zips_df, 'iloc') else zips_df.df()
                summary['total_zip_codes'] = len(zips_pdf)
            except Exception:
                summary['total_zip_codes'] = 0

            try:
                cities_df = self.get_dimension_df('dim_city')
                if self.session:
                    cities_pdf = self.session.to_pandas(cities_df)
                elif self.backend == 'spark':
                    cities_pdf = cities_df.toPandas()
                else:
                    cities_pdf = cities_df if hasattr(cities_df, 'iloc') else cities_df.df()
                summary['total_cities'] = len(cities_pdf)
            except Exception:
                summary['total_cities'] = 0

        except Exception as e:
            logger.warning(f"Error getting geography summary: {e}")
            summary['error'] = str(e)

        return summary
