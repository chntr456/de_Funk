"""
Calendar Builder - Generates calendar dimension table.

Creates a comprehensive date dimension table with:
- All dates from start_date to end_date
- Rich date attributes (day of week, month, quarter, etc.)
- Fiscal year calculations
- Weekend/weekday flags
- Period boundaries (month start/end, etc.)
"""

from datetime import datetime, timedelta
from typing import Dict, List
import calendar


class CalendarBuilder:
    """
    Builds a calendar dimension table with rich date attributes.

    Usage:
        builder = CalendarBuilder(
            start_date='2000-01-01',
            end_date='2050-12-31',
            fiscal_year_start_month=1
        )
        calendar_data = builder.build()
    """

    def __init__(
        self,
        start_date: str = '2000-01-01',
        end_date: str = '2050-12-31',
        fiscal_year_start_month: int = 1,
        weekend_days: List[int] = None
    ):
        """
        Initialize calendar builder.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            fiscal_year_start_month: Month fiscal year starts (1-12)
            weekend_days: List of weekend days (1=Monday, 7=Sunday)
        """
        self.start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        self.end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        self.fiscal_year_start_month = fiscal_year_start_month
        self.weekend_days = weekend_days or [6, 7]  # Saturday, Sunday

    def build(self) -> List[Dict]:
        """
        Build calendar dimension data.

        Returns:
            List of dictionaries, one per date
        """
        calendar_data = []
        current_date = self.start_date

        while current_date <= self.end_date:
            calendar_data.append(self._build_date_record(current_date))
            current_date += timedelta(days=1)

        return calendar_data

    def _build_date_record(self, date) -> Dict:
        """
        Build a single date record with all attributes.

        Args:
            date: Date object

        Returns:
            Dictionary with all date attributes
        """
        # Basic date components
        year = date.year
        month = date.month
        day = date.day

        # ISO calendar
        iso_year, iso_week, iso_day = date.isocalendar()

        # Month info
        month_name = date.strftime('%B')  # January
        month_abbr = date.strftime('%b')  # Jan
        days_in_month = calendar.monthrange(year, month)[1]

        # Day of week info
        day_of_week = iso_day  # 1=Monday, 7=Sunday
        day_of_week_name = date.strftime('%A')  # Monday
        day_of_week_abbr = date.strftime('%a')  # Mon

        # Day of year
        day_of_year = date.timetuple().tm_yday

        # Quarter
        quarter = (month - 1) // 3 + 1

        # Weekend/weekday
        is_weekend = day_of_week in self.weekend_days
        is_weekday = not is_weekend

        # Period boundaries
        is_month_start = day == 1
        is_month_end = day == days_in_month
        is_quarter_start = is_month_start and month in [1, 4, 7, 10]
        is_quarter_end = is_month_end and month in [3, 6, 9, 12]
        is_year_start = month == 1 and day == 1
        is_year_end = month == 12 and day == 31

        # Fiscal year
        fiscal_year, fiscal_quarter, fiscal_month = self._calculate_fiscal_period(
            date,
            self.fiscal_year_start_month
        )

        # Formatted strings
        year_month = f"{year:04d}-{month:02d}"
        year_quarter = f"{year:04d}-Q{quarter}"
        date_str = date.strftime('%Y-%m-%d')

        # Primary key - integer YYYYMMDD format (required for cross-model joins)
        date_id = int(date.strftime('%Y%m%d'))

        return {
            'date_id': date_id,
            'date': date,
            'year': year,
            'quarter': quarter,
            'month': month,
            'month_name': month_name,
            'month_abbr': month_abbr,
            'week_of_year': iso_week,
            'day_of_month': day,
            'day_of_week': day_of_week,
            'day_of_week_name': day_of_week_name,
            'day_of_week_abbr': day_of_week_abbr,
            'day_of_year': day_of_year,
            'is_weekend': is_weekend,
            'is_weekday': is_weekday,
            'is_month_start': is_month_start,
            'is_month_end': is_month_end,
            'is_quarter_start': is_quarter_start,
            'is_quarter_end': is_quarter_end,
            'is_year_start': is_year_start,
            'is_year_end': is_year_end,
            'fiscal_year': fiscal_year,
            'fiscal_quarter': fiscal_quarter,
            'fiscal_month': fiscal_month,
            'days_in_month': days_in_month,
            'year_month': year_month,
            'year_quarter': year_quarter,
            'date_str': date_str
        }

    def _calculate_fiscal_period(self, date, fiscal_start_month: int) -> tuple:
        """
        Calculate fiscal year, quarter, and month.

        Args:
            date: Date object
            fiscal_start_month: Month fiscal year starts (1-12)

        Returns:
            Tuple of (fiscal_year, fiscal_quarter, fiscal_month)
        """
        year = date.year
        month = date.month

        # Calculate fiscal year
        if month >= fiscal_start_month:
            fiscal_year = year
            fiscal_month = month - fiscal_start_month + 1
        else:
            fiscal_year = year - 1
            fiscal_month = month + (12 - fiscal_start_month) + 1

        # Calculate fiscal quarter (1-4)
        fiscal_quarter = (fiscal_month - 1) // 3 + 1

        return fiscal_year, fiscal_quarter, fiscal_month

    def build_spark_dataframe(self, spark):
        """
        Build calendar as Spark DataFrame.

        Args:
            spark: SparkSession

        Returns:
            Spark DataFrame with calendar data
        """
        from pyspark.sql.types import (
            StructType, StructField, DateType, IntegerType,
            StringType, BooleanType
        )

        # Define schema
        schema = StructType([
            StructField('date_id', IntegerType(), False),  # PK - YYYYMMDD format
            StructField('date', DateType(), False),
            StructField('year', IntegerType(), False),
            StructField('quarter', IntegerType(), False),
            StructField('month', IntegerType(), False),
            StructField('month_name', StringType(), False),
            StructField('month_abbr', StringType(), False),
            StructField('week_of_year', IntegerType(), False),
            StructField('day_of_month', IntegerType(), False),
            StructField('day_of_week', IntegerType(), False),
            StructField('day_of_week_name', StringType(), False),
            StructField('day_of_week_abbr', StringType(), False),
            StructField('day_of_year', IntegerType(), False),
            StructField('is_weekend', BooleanType(), False),
            StructField('is_weekday', BooleanType(), False),
            StructField('is_month_start', BooleanType(), False),
            StructField('is_month_end', BooleanType(), False),
            StructField('is_quarter_start', BooleanType(), False),
            StructField('is_quarter_end', BooleanType(), False),
            StructField('is_year_start', BooleanType(), False),
            StructField('is_year_end', BooleanType(), False),
            StructField('fiscal_year', IntegerType(), False),
            StructField('fiscal_quarter', IntegerType(), False),
            StructField('fiscal_month', IntegerType(), False),
            StructField('days_in_month', IntegerType(), False),
            StructField('year_month', StringType(), False),
            StructField('year_quarter', StringType(), False),
            StructField('date_str', StringType(), False)
        ])

        # Build data
        calendar_data = self.build()

        # Create DataFrame
        df = spark.createDataFrame(calendar_data, schema)

        return df


def build_calendar_table(
    spark,
    output_path: str,
    start_date: str = '2000-01-01',
    end_date: str = '2050-12-31',
    fiscal_year_start_month: int = 1
):
    """
    Build and write calendar dimension table.

    Args:
        spark: SparkSession
        output_path: Path to write calendar table
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        fiscal_year_start_month: Month fiscal year starts (1-12)
    """
    builder = CalendarBuilder(
        start_date=start_date,
        end_date=end_date,
        fiscal_year_start_month=fiscal_year_start_month
    )

    df = builder.build_spark_dataframe(spark)

    # Write to Delta Lake (default format)
    df.write.format("delta").mode('overwrite').save(output_path)

    print(f"✓ Calendar dimension created: {df.count()} dates")
    print(f"✓ Date range: {start_date} to {end_date}")
    print(f"✓ Written to: {output_path}")

    return df
