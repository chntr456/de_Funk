"""
TemporalModel - Time and calendar dimensions for time-series analysis.

This model contains time-based dimensions:
- dim_calendar: Universal calendar dimension with rich date attributes

All time-series models should depend on temporal for date-based queries.

Version: 2.1 - Backend-agnostic via UniversalSession methods
"""

from typing import Optional, Any, Dict
from models.base.model import BaseModel
import logging

logger = logging.getLogger(__name__)

# Type alias for DataFrame (can be Spark or DuckDB)
DataFrame = Any


class TemporalModel(BaseModel):
    """
    Temporal model - time and calendar dimensions.

    Inherits all functionality from BaseModel:
    - Generic graph building from YAML config
    - Node loading from Bronze
    - Table access methods

    This model is foundational because:
    - It has no dependencies (it's the time foundation)
    - Other models depend on it for date-based queries
    - It provides calendar and time reference data

    The YAML config (configs/models/temporal/) drives everything.

    Backend-agnostic: uses session methods for all DataFrame operations.
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

        if self.session:
            # Use session methods for filtering
            df = self.session.filter_by_range(df, 'date', min_val=date_from, max_val=date_to)
            if year:
                df = self.session.filter_by_value(df, 'year', year)
            if month:
                df = self.session.filter_by_value(df, 'month', month)
            return self.session.order_by(df, 'date')
        else:
            # Fallback for when session is not available
            if self.backend == 'spark':
                if date_from:
                    df = df.filter(df.date >= date_from)
                if date_to:
                    df = df.filter(df.date <= date_to)
                if year:
                    df = df.filter(df.year == year)
                if month:
                    df = df.filter(df.month == month)
                return df.orderBy('date')
            else:
                # DuckDB/pandas
                if date_from:
                    df = df[df['date'] >= date_from]
                if date_to:
                    df = df[df['date'] <= date_to]
                if year:
                    df = df[df['year'] == year]
                if month:
                    df = df[df['month'] == month]
                return df.sort_values('date') if hasattr(df, 'sort_values') else df

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

        if self.session:
            return self.session.filter_by_value(df, 'is_weekday', True)
        elif self.backend == 'spark':
            return df.filter(df.is_weekday == True)
        else:
            return df[df['is_weekday'] == True]

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

        if self.session:
            return self.session.filter_by_value(df, 'is_weekend', True)
        elif self.backend == 'spark':
            return df.filter(df.is_weekend == True)
        else:
            return df[df['is_weekend'] == True]

    def get_fiscal_year_dates(self, fiscal_year: int) -> DataFrame:
        """
        Get all dates for a specific fiscal year.

        Args:
            fiscal_year: Fiscal year number

        Returns:
            DataFrame with dates in fiscal year
        """
        df = self.get_dimension_df('dim_calendar')

        if self.session:
            df = self.session.filter_by_value(df, 'fiscal_year', fiscal_year)
            return self.session.order_by(df, 'date')
        elif self.backend == 'spark':
            return df.filter(df.fiscal_year == fiscal_year).orderBy('date')
        else:
            filtered = df[df['fiscal_year'] == fiscal_year]
            return filtered.sort_values('date') if hasattr(filtered, 'sort_values') else filtered

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

        if self.session:
            df = self.session.filter_by_value(df, 'year', year)
            df = self.session.filter_by_value(df, 'quarter', quarter)
            return self.session.order_by(df, 'date')
        elif self.backend == 'spark':
            return df.filter(
                (df.year == year) & (df.quarter == quarter)
            ).orderBy('date')
        else:
            filtered = df[(df['year'] == year) & (df['quarter'] == quarter)]
            return filtered.sort_values('date') if hasattr(filtered, 'sort_values') else filtered

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

        if self.session:
            df = self.session.filter_by_value(df, 'year', year)
            df = self.session.filter_by_value(df, 'month', month)
            return self.session.order_by(df, 'date')
        elif self.backend == 'spark':
            return df.filter(
                (df.year == year) & (df.month == month)
            ).orderBy('date')
        else:
            filtered = df[(df['year'] == year) & (df['month'] == month)]
            return filtered.sort_values('date') if hasattr(filtered, 'sort_values') else filtered

    def get_date_range_info(self, date_from: str, date_to: str) -> Dict[str, Any]:
        """
        Get summary information about a date range.

        Args:
            date_from: Start date (YYYY-MM-DD)
            date_to: End date (YYYY-MM-DD)

        Returns:
            Dictionary with date range statistics
        """
        df = self.get_calendar(date_from, date_to)

        if self.session:
            # Convert to pandas for aggregations (works for both backends)
            pdf = self.session.to_pandas(df)
            total_days = len(pdf)
            weekdays = len(pdf[pdf['is_weekday'] == True])
            weekends = len(pdf[pdf['is_weekend'] == True])
            num_years = pdf['year'].nunique()
            num_quarters = pdf['year_quarter'].nunique()
            num_months = pdf['year_month'].nunique()
        elif self.backend == 'spark':
            from pyspark.sql import functions as F

            total_days = df.count()
            weekdays = df.filter(df.is_weekday == True).count()
            weekends = df.filter(df.is_weekend == True).count()

            summary = df.agg(
                F.countDistinct('year').alias('num_years'),
                F.countDistinct('year_quarter').alias('num_quarters'),
                F.countDistinct('year_month').alias('num_months')
            ).first()

            num_years = summary['num_years']
            num_quarters = summary['num_quarters']
            num_months = summary['num_months']
        else:
            # DuckDB/pandas fallback
            if hasattr(df, 'df'):
                pdf = df.df()
            else:
                pdf = df
            total_days = len(pdf)
            weekdays = len(pdf[pdf['is_weekday'] == True])
            weekends = len(pdf[pdf['is_weekend'] == True])
            num_years = pdf['year'].nunique()
            num_quarters = pdf['year_quarter'].nunique()
            num_months = pdf['year_month'].nunique()

        return {
            'date_from': date_from,
            'date_to': date_to,
            'total_days': total_days,
            'weekdays': weekdays,
            'weekends': weekends,
            'num_years': num_years,
            'num_quarters': num_quarters,
            'num_months': num_months
        }

    def get_calendar_config(self) -> Dict[str, Any]:
        """
        Get calendar generation configuration from YAML.

        Returns:
            Dictionary with calendar configuration
        """
        return self.model_cfg.get('calendar_config', {})
