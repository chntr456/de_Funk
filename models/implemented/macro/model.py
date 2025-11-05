"""
MacroModel - Macroeconomic indicators from BLS.

Inherits all graph building logic from BaseModel.
Provides convenient access to unemployment, CPI, employment, and wage data.
"""

from typing import Optional
from pyspark.sql import DataFrame
from models.base.model import BaseModel


class MacroModel(BaseModel):
    """
    Macro economic model - BLS (Bureau of Labor Statistics) data.

    Inherits all functionality from BaseModel:
    - Generic graph building from YAML config
    - Node loading from Bronze (BLS data)
    - Edge validation
    - Table access methods

    The YAML config (configs/models/macro.yaml) drives everything.

    Data includes:
    - National unemployment rate (monthly)
    - Consumer Price Index (monthly)
    - Total nonfarm employment (monthly)
    - Average hourly earnings (monthly)
    """

    # ============================================================
    # MACRO-SPECIFIC CONVENIENCE METHODS
    # ============================================================

    def get_unemployment(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> DataFrame:
        """
        Get national unemployment rate data.

        Args:
            date_from: Start date (YYYY-MM-DD) optional
            date_to: End date (YYYY-MM-DD) optional

        Returns:
            DataFrame with unemployment data
        """
        df = self.get_fact_df('fact_unemployment')

        if date_from:
            df = df.filter(df.date >= date_from)
        if date_to:
            df = df.filter(df.date <= date_to)

        return df.orderBy('date')

    def get_cpi(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> DataFrame:
        """
        Get Consumer Price Index data.

        Args:
            date_from: Start date (YYYY-MM-DD) optional
            date_to: End date (YYYY-MM-DD) optional

        Returns:
            DataFrame with CPI data
        """
        df = self.get_fact_df('fact_cpi')

        if date_from:
            df = df.filter(df.date >= date_from)
        if date_to:
            df = df.filter(df.date <= date_to)

        return df.orderBy('date')

    def get_employment(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> DataFrame:
        """
        Get total nonfarm employment data.

        Args:
            date_from: Start date (YYYY-MM-DD) optional
            date_to: End date (YYYY-MM-DD) optional

        Returns:
            DataFrame with employment data
        """
        df = self.get_fact_df('fact_employment')

        if date_from:
            df = df.filter(df.date >= date_from)
        if date_to:
            df = df.filter(df.date <= date_to)

        return df.orderBy('date')

    def get_wages(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> DataFrame:
        """
        Get average hourly earnings data.

        Args:
            date_from: Start date (YYYY-MM-DD) optional
            date_to: End date (YYYY-MM-DD) optional

        Returns:
            DataFrame with wage data
        """
        df = self.get_fact_df('fact_wages')

        if date_from:
            df = df.filter(df.date >= date_from)
        if date_to:
            df = df.filter(df.date <= date_to)

        return df.orderBy('date')

    def get_all_indicators(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> DataFrame:
        """
        Get all economic indicators joined together.

        Returns a wide DataFrame with unemployment, CPI, employment, and wages
        all joined by date.

        Args:
            date_from: Start date (YYYY-MM-DD) optional
            date_to: End date (YYYY-MM-DD) optional

        Returns:
            DataFrame with all indicators
        """
        from pyspark.sql import functions as F

        # Get each indicator
        unemployment = self.get_unemployment(date_from, date_to).select(
            F.col('date'),
            F.col('value').alias('unemployment_rate')
        )

        cpi = self.get_cpi(date_from, date_to).select(
            F.col('date'),
            F.col('value').alias('cpi_value')
        )

        employment = self.get_employment(date_from, date_to).select(
            F.col('date'),
            F.col('value').alias('total_employment')
        )

        wages = self.get_wages(date_from, date_to).select(
            F.col('date'),
            F.col('value').alias('avg_hourly_earnings')
        )

        # Join all on date
        result = (
            unemployment
            .join(cpi, on='date', how='full_outer')
            .join(employment, on='date', how='full_outer')
            .join(wages, on='date', how='full_outer')
            .orderBy('date')
        )

        return result

    def get_latest_values(self) -> dict:
        """
        Get the most recent value for each indicator.

        Returns:
            Dictionary with latest values
        """
        from pyspark.sql import functions as F

        latest = {}

        # Get latest unemployment
        unemp = self.get_unemployment().orderBy(F.desc('date')).first()
        if unemp:
            latest['unemployment_rate'] = {
                'value': unemp['value'],
                'date': str(unemp['date'])
            }

        # Get latest CPI
        cpi = self.get_cpi().orderBy(F.desc('date')).first()
        if cpi:
            latest['cpi'] = {
                'value': cpi['value'],
                'date': str(cpi['date'])
            }

        # Get latest employment
        emp = self.get_employment().orderBy(F.desc('date')).first()
        if emp:
            latest['total_employment'] = {
                'value': emp['value'],
                'date': str(emp['date'])
            }

        # Get latest wages
        wage = self.get_wages().orderBy(F.desc('date')).first()
        if wage:
            latest['avg_hourly_earnings'] = {
                'value': wage['value'],
                'date': str(wage['date'])
            }

        return latest

    def get_bls_series_config(self) -> dict:
        """
        Get BLS series configuration from YAML.

        Returns:
            Dictionary of BLS series configurations
        """
        return self.model_cfg.get('bls_series', {})
