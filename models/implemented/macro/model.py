"""
MacroModel - Macroeconomic indicators from BLS.

Inherits all graph building logic from BaseModel.
Provides convenient access to unemployment, CPI, employment, and wage data.

Version: 2.1 - Backend-agnostic via UniversalSession methods
"""

from typing import Optional, Any, Dict, List
from models.base.model import BaseModel
import logging

logger = logging.getLogger(__name__)

# Type alias for DataFrame (can be Spark or DuckDB)
DataFrame = Any


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

    Backend-agnostic: uses session methods for all DataFrame operations.
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

        if self.session:
            df = self.session.filter_by_range(df, 'date', min_val=date_from, max_val=date_to)
            return self.session.order_by(df, 'date')
        elif self.backend == 'spark':
            if date_from:
                df = df.filter(df.date >= date_from)
            if date_to:
                df = df.filter(df.date <= date_to)
            return df.orderBy('date')
        else:
            if date_from:
                df = df[df['date'] >= date_from]
            if date_to:
                df = df[df['date'] <= date_to]
            return df.sort_values('date') if hasattr(df, 'sort_values') else df

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

        if self.session:
            df = self.session.filter_by_range(df, 'date', min_val=date_from, max_val=date_to)
            return self.session.order_by(df, 'date')
        elif self.backend == 'spark':
            if date_from:
                df = df.filter(df.date >= date_from)
            if date_to:
                df = df.filter(df.date <= date_to)
            return df.orderBy('date')
        else:
            if date_from:
                df = df[df['date'] >= date_from]
            if date_to:
                df = df[df['date'] <= date_to]
            return df.sort_values('date') if hasattr(df, 'sort_values') else df

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

        if self.session:
            df = self.session.filter_by_range(df, 'date', min_val=date_from, max_val=date_to)
            return self.session.order_by(df, 'date')
        elif self.backend == 'spark':
            if date_from:
                df = df.filter(df.date >= date_from)
            if date_to:
                df = df.filter(df.date <= date_to)
            return df.orderBy('date')
        else:
            if date_from:
                df = df[df['date'] >= date_from]
            if date_to:
                df = df[df['date'] <= date_to]
            return df.sort_values('date') if hasattr(df, 'sort_values') else df

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

        if self.session:
            df = self.session.filter_by_range(df, 'date', min_val=date_from, max_val=date_to)
            return self.session.order_by(df, 'date')
        elif self.backend == 'spark':
            if date_from:
                df = df.filter(df.date >= date_from)
            if date_to:
                df = df.filter(df.date <= date_to)
            return df.orderBy('date')
        else:
            if date_from:
                df = df[df['date'] >= date_from]
            if date_to:
                df = df[df['date'] <= date_to]
            return df.sort_values('date') if hasattr(df, 'sort_values') else df

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
        # Get each indicator
        unemployment = self.get_unemployment(date_from, date_to)
        cpi = self.get_cpi(date_from, date_to)
        employment = self.get_employment(date_from, date_to)
        wages = self.get_wages(date_from, date_to)

        if self.session:
            # Convert to pandas for joining (works for both backends)
            import pandas as pd

            unemp_pdf = self.session.to_pandas(unemployment)
            cpi_pdf = self.session.to_pandas(cpi)
            emp_pdf = self.session.to_pandas(employment)
            wages_pdf = self.session.to_pandas(wages)

            # Select and rename columns
            unemp_pdf = unemp_pdf[['date', 'value']].rename(columns={'value': 'unemployment_rate'})
            cpi_pdf = cpi_pdf[['date', 'value']].rename(columns={'value': 'cpi_value'})
            emp_pdf = emp_pdf[['date', 'value']].rename(columns={'value': 'total_employment'})
            wages_pdf = wages_pdf[['date', 'value']].rename(columns={'value': 'avg_hourly_earnings'})

            # Join all on date
            result = unemp_pdf.merge(cpi_pdf, on='date', how='outer')
            result = result.merge(emp_pdf, on='date', how='outer')
            result = result.merge(wages_pdf, on='date', how='outer')
            result = result.sort_values('date')

            return result

        elif self.backend == 'spark':
            from pyspark.sql import functions as F

            unemployment = unemployment.select(
                F.col('date'),
                F.col('value').alias('unemployment_rate')
            )
            cpi = cpi.select(
                F.col('date'),
                F.col('value').alias('cpi_value')
            )
            employment = employment.select(
                F.col('date'),
                F.col('value').alias('total_employment')
            )
            wages = wages.select(
                F.col('date'),
                F.col('value').alias('avg_hourly_earnings')
            )

            result = (
                unemployment
                .join(cpi, on='date', how='full_outer')
                .join(employment, on='date', how='full_outer')
                .join(wages, on='date', how='full_outer')
                .orderBy('date')
            )
            return result
        else:
            # DuckDB/pandas fallback
            import pandas as pd

            if hasattr(unemployment, 'df'):
                unemp_pdf = unemployment.df()
                cpi_pdf = cpi.df()
                emp_pdf = employment.df()
                wages_pdf = wages.df()
            else:
                unemp_pdf = unemployment
                cpi_pdf = cpi
                emp_pdf = employment
                wages_pdf = wages

            unemp_pdf = unemp_pdf[['date', 'value']].rename(columns={'value': 'unemployment_rate'})
            cpi_pdf = cpi_pdf[['date', 'value']].rename(columns={'value': 'cpi_value'})
            emp_pdf = emp_pdf[['date', 'value']].rename(columns={'value': 'total_employment'})
            wages_pdf = wages_pdf[['date', 'value']].rename(columns={'value': 'avg_hourly_earnings'})

            result = unemp_pdf.merge(cpi_pdf, on='date', how='outer')
            result = result.merge(emp_pdf, on='date', how='outer')
            result = result.merge(wages_pdf, on='date', how='outer')
            return result.sort_values('date')

    def get_latest_values(self) -> Dict[str, Dict[str, Any]]:
        """
        Get the most recent value for each indicator.

        Returns:
            Dictionary with latest values
        """
        latest = {}

        if self.session:
            # Use session methods
            unemp = self.get_unemployment()
            unemp_pdf = self.session.to_pandas(unemp)
            if not unemp_pdf.empty:
                unemp_pdf = unemp_pdf.sort_values('date', ascending=False)
                row = unemp_pdf.iloc[0]
                latest['unemployment_rate'] = {
                    'value': row['value'],
                    'date': str(row['date'])
                }

            cpi = self.get_cpi()
            cpi_pdf = self.session.to_pandas(cpi)
            if not cpi_pdf.empty:
                cpi_pdf = cpi_pdf.sort_values('date', ascending=False)
                row = cpi_pdf.iloc[0]
                latest['cpi'] = {
                    'value': row['value'],
                    'date': str(row['date'])
                }

            emp = self.get_employment()
            emp_pdf = self.session.to_pandas(emp)
            if not emp_pdf.empty:
                emp_pdf = emp_pdf.sort_values('date', ascending=False)
                row = emp_pdf.iloc[0]
                latest['total_employment'] = {
                    'value': row['value'],
                    'date': str(row['date'])
                }

            wage = self.get_wages()
            wage_pdf = self.session.to_pandas(wage)
            if not wage_pdf.empty:
                wage_pdf = wage_pdf.sort_values('date', ascending=False)
                row = wage_pdf.iloc[0]
                latest['avg_hourly_earnings'] = {
                    'value': row['value'],
                    'date': str(row['date'])
                }

        elif self.backend == 'spark':
            from pyspark.sql import functions as F

            unemp = self.get_unemployment().orderBy(F.desc('date')).first()
            if unemp:
                latest['unemployment_rate'] = {
                    'value': unemp['value'],
                    'date': str(unemp['date'])
                }

            cpi = self.get_cpi().orderBy(F.desc('date')).first()
            if cpi:
                latest['cpi'] = {
                    'value': cpi['value'],
                    'date': str(cpi['date'])
                }

            emp = self.get_employment().orderBy(F.desc('date')).first()
            if emp:
                latest['total_employment'] = {
                    'value': emp['value'],
                    'date': str(emp['date'])
                }

            wage = self.get_wages().orderBy(F.desc('date')).first()
            if wage:
                latest['avg_hourly_earnings'] = {
                    'value': wage['value'],
                    'date': str(wage['date'])
                }
        else:
            # DuckDB/pandas fallback
            unemp = self.get_unemployment()
            if hasattr(unemp, 'df'):
                unemp = unemp.df()
            if not unemp.empty:
                unemp = unemp.sort_values('date', ascending=False)
                row = unemp.iloc[0]
                latest['unemployment_rate'] = {
                    'value': row['value'],
                    'date': str(row['date'])
                }

            cpi = self.get_cpi()
            if hasattr(cpi, 'df'):
                cpi = cpi.df()
            if not cpi.empty:
                cpi = cpi.sort_values('date', ascending=False)
                row = cpi.iloc[0]
                latest['cpi'] = {
                    'value': row['value'],
                    'date': str(row['date'])
                }

            emp = self.get_employment()
            if hasattr(emp, 'df'):
                emp = emp.df()
            if not emp.empty:
                emp = emp.sort_values('date', ascending=False)
                row = emp.iloc[0]
                latest['total_employment'] = {
                    'value': row['value'],
                    'date': str(row['date'])
                }

            wage = self.get_wages()
            if hasattr(wage, 'df'):
                wage = wage.df()
            if not wage.empty:
                wage = wage.sort_values('date', ascending=False)
                row = wage.iloc[0]
                latest['avg_hourly_earnings'] = {
                    'value': row['value'],
                    'date': str(row['date'])
                }

        return latest

    def get_bls_series_config(self) -> Dict[str, Any]:
        """
        Get BLS series configuration from YAML.

        Returns:
            Dictionary of BLS series configurations
        """
        return self.model_cfg.get('bls_series', {})
