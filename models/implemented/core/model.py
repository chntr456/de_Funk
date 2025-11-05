"""
CoreModel - Shared dimensions and reference data used across all models.

This model contains common dimensions that all other models reference:
- dim_calendar: Universal calendar dimension with rich date attributes

All other models should depend on this core model for shared dimensions.
"""

from typing import Optional
from pyspark.sql import DataFrame
from models.base.model import BaseModel


class CoreModel(BaseModel):
    """
    Core model - shared dimensions and reference data.

    Inherits all functionality from BaseModel:
    - Generic graph building from YAML config
    - Node loading from Bronze
    - Table access methods

    This model is special because:
    - It has no dependencies (it's the foundation)
    - Other models depend on it for shared dimensions
    - It provides reference data like calendar

    The YAML config (configs/models/core.yaml) drives everything.
    """

    # ============================================================
    # CORE MODEL CONVENIENCE METHODS
    # ============================================================

    def get_calendar(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        year: Optional[int] = None,
        month: Optional[int] = None
    ) -> DataFrame:
        """
        Get calendar dimension data.

        Args:
            date_from: Start date (YYYY-MM-DD) optional
            date_to: End date (YYYY-MM-DD) optional
            year: Filter by year optional
            month: Filter by month (1-12) optional

        Returns:
            DataFrame with calendar dimension data
        """
        df = self.get_dimension_df('dim_calendar')

        if date_from:
            df = df.filter(df.date >= date_from)
        if date_to:
            df = df.filter(df.date <= date_to)
        if year:
            df = df.filter(df.year == year)
        if month:
            df = df.filter(df.month == month)

        return df.orderBy('date')

    def get_weekdays(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> DataFrame:
        """
        Get only weekdays (Monday-Friday).

        Args:
            date_from: Start date (YYYY-MM-DD) optional
            date_to: End date (YYYY-MM-DD) optional

        Returns:
            DataFrame with weekday dates
        """
        df = self.get_calendar(date_from, date_to)
        return df.filter(df.is_weekday == True)

    def get_weekends(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> DataFrame:
        """
        Get only weekends (Saturday-Sunday).

        Args:
            date_from: Start date (YYYY-MM-DD) optional
            date_to: End date (YYYY-MM-DD) optional

        Returns:
            DataFrame with weekend dates
        """
        df = self.get_calendar(date_from, date_to)
        return df.filter(df.is_weekend == True)

    def get_fiscal_year_dates(self, fiscal_year: int) -> DataFrame:
        """
        Get all dates for a specific fiscal year.

        Args:
            fiscal_year: Fiscal year number

        Returns:
            DataFrame with dates in fiscal year
        """
        df = self.get_dimension_df('dim_calendar')
        return df.filter(df.fiscal_year == fiscal_year).orderBy('date')

    def get_quarter_dates(self, year: int, quarter: int) -> DataFrame:
        """
        Get all dates for a specific calendar quarter.

        Args:
            year: Calendar year
            quarter: Quarter number (1-4)

        Returns:
            DataFrame with dates in quarter
        """
        df = self.get_dimension_df('dim_calendar')
        return df.filter(
            (df.year == year) & (df.quarter == quarter)
        ).orderBy('date')

    def get_month_dates(self, year: int, month: int) -> DataFrame:
        """
        Get all dates for a specific month.

        Args:
            year: Calendar year
            month: Month number (1-12)

        Returns:
            DataFrame with dates in month
        """
        df = self.get_dimension_df('dim_calendar')
        return df.filter(
            (df.year == year) & (df.month == month)
        ).orderBy('date')

    def get_date_range_info(self, date_from: str, date_to: str) -> dict:
        """
        Get summary information about a date range.

        Args:
            date_from: Start date (YYYY-MM-DD)
            date_to: End date (YYYY-MM-DD)

        Returns:
            Dictionary with date range statistics
        """
        from pyspark.sql import functions as F

        df = self.get_calendar(date_from, date_to)

        total_days = df.count()
        weekdays = df.filter(df.is_weekday == True).count()
        weekends = df.filter(df.is_weekend == True).count()

        # Get unique years, quarters, months
        summary = df.agg(
            F.countDistinct('year').alias('num_years'),
            F.countDistinct('year_quarter').alias('num_quarters'),
            F.countDistinct('year_month').alias('num_months')
        ).first()

        return {
            'date_from': date_from,
            'date_to': date_to,
            'total_days': total_days,
            'weekdays': weekdays,
            'weekends': weekends,
            'num_years': summary['num_years'],
            'num_quarters': summary['num_quarters'],
            'num_months': summary['num_months']
        }

    def get_calendar_config(self) -> dict:
        """
        Get calendar generation configuration from YAML.

        Returns:
            Dictionary with calendar configuration
        """
        return self.model_cfg.get('calendar_config', {})
