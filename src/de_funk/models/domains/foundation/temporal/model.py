"""
TemporalModel - Time and calendar dimensions for time-series analysis.

This model contains time-based dimensions:
- dim_calendar: Universal calendar dimension with rich date attributes

All time-series models should depend on temporal for date-based queries.

Version: 2.2 - Self-generating calendar (no bronze dependency)
"""

from typing import Optional, Any, Dict
from de_funk.models.base.model import BaseModel
from datetime import date, timedelta
import logging

logger = logging.getLogger(__name__)

# Type alias for DataFrame (can be Spark or DuckDB)
DataFrame = Any


class TemporalModel(BaseModel):
    """
    Temporal model - time and calendar dimensions.

    This is a SELF-GENERATING model - it creates dim_calendar directly
    without requiring bronze layer data. The calendar is computed from
    a date range with all temporal attributes derived.

    This model is foundational because:
    - It has no dependencies (it's the time foundation)
    - Other models depend on it for date-based queries
    - It provides calendar and time reference data

    Downstream models join to dim_calendar for temporal normalization.

    Backend-agnostic: uses session methods for all DataFrame operations.
    """

    # Default date range for calendar generation
    DEFAULT_START_DATE = "2000-01-01"
    DEFAULT_END_DATE = "2050-12-31"

    def custom_node_loading(self, node_id: str, node_config: Dict) -> Optional[DataFrame]:
        """
        Generate calendar dimension directly without bronze dependency.

        This override makes temporal self-sufficient - it doesn't need
        bronze.calendar_seed because we generate all dates programmatically.

        Args:
            node_id: Node identifier (e.g., 'dim_calendar')
            node_config: Node configuration from graph

        Returns:
            DataFrame with generated calendar data, or None to use default loading
        """
        if node_id == "dim_calendar":
            logger.info("Generating dim_calendar directly (no bronze dependency)")
            return self._generate_calendar()

        # For any other nodes, use default loading
        return None

    def _generate_calendar(self) -> DataFrame:
        """
        Generate complete calendar dimension with all temporal attributes.

        Returns:
            DataFrame with calendar dimension (2000-01-01 to 2050-12-31)
        """
        # Get date range from config or use defaults
        calendar_config = self.model_cfg.get('calendar_config', {})
        start_date = calendar_config.get('start_date', self.DEFAULT_START_DATE)
        end_date = calendar_config.get('end_date', self.DEFAULT_END_DATE)
        fiscal_year_start_month = calendar_config.get('fiscal_year_start_month', 1)

        logger.info(f"Generating calendar: {start_date} to {end_date}")

        if self.backend == 'spark':
            return self._generate_calendar_spark(start_date, end_date, fiscal_year_start_month)
        else:
            return self._generate_calendar_duckdb(start_date, end_date, fiscal_year_start_month)

    def _generate_calendar_spark(self, start_date: str, end_date: str, fiscal_year_start_month: int) -> DataFrame:
        """Generate calendar using Spark SQL."""
        from pyspark.sql import functions as F
        from pyspark.sql.types import DateType

        # Get spark session from connection
        spark = getattr(self.connection, 'spark', self.connection)

        # Generate date sequence using Spark SQL
        df = spark.sql(f"""
            SELECT explode(sequence(
                to_date('{start_date}'),
                to_date('{end_date}'),
                interval 1 day
            )) as date
        """)

        # Add all calendar attributes
        df = df.select(
            # Primary key - integer YYYYMMDD format (required for cross-model joins)
            F.date_format("date", "yyyyMMdd").cast("int").alias("date_id"),
            F.col("date"),
            F.year("date").alias("year"),
            F.quarter("date").alias("quarter"),
            F.month("date").alias("month"),
            F.date_format("date", "MMMM").alias("month_name"),
            F.date_format("date", "MMM").alias("month_abbr"),
            F.weekofyear("date").alias("week_of_year"),
            F.dayofmonth("date").alias("day_of_month"),
            F.dayofweek("date").alias("day_of_week"),  # 1=Sun, 7=Sat in Spark
            F.date_format("date", "EEEE").alias("day_of_week_name"),
            F.date_format("date", "EEE").alias("day_of_week_abbr"),
            F.dayofyear("date").alias("day_of_year"),
            # Weekend: Spark dayofweek returns 1=Sunday, 7=Saturday
            (F.dayofweek("date").isin([1, 7])).alias("is_weekend"),
            (~F.dayofweek("date").isin([1, 7])).alias("is_weekday"),
            # Month boundaries
            (F.dayofmonth("date") == 1).alias("is_month_start"),
            (F.date_add(F.last_day("date"), 0) == F.col("date")).alias("is_month_end"),
            # Quarter boundaries
            ((F.month("date").isin([1, 4, 7, 10])) & (F.dayofmonth("date") == 1)).alias("is_quarter_start"),
            ((F.month("date").isin([3, 6, 9, 12])) & (F.date_add(F.last_day("date"), 0) == F.col("date"))).alias("is_quarter_end"),
            # Year boundaries
            ((F.month("date") == 1) & (F.dayofmonth("date") == 1)).alias("is_year_start"),
            ((F.month("date") == 12) & (F.dayofmonth("date") == 31)).alias("is_year_end"),
            # Fiscal year (assuming fiscal year starts in fiscal_year_start_month)
            F.when(F.month("date") >= fiscal_year_start_month, F.year("date"))
             .otherwise(F.year("date") - 1).alias("fiscal_year"),
            # Fiscal quarter
            F.when(F.month("date") >= fiscal_year_start_month,
                   F.ceil((F.month("date") - fiscal_year_start_month + 1) / 3))
             .otherwise(F.ceil((F.month("date") + 12 - fiscal_year_start_month + 1) / 3)).cast("int").alias("fiscal_quarter"),
            # Fiscal month
            F.when(F.month("date") >= fiscal_year_start_month,
                   F.month("date") - fiscal_year_start_month + 1)
             .otherwise(F.month("date") + 12 - fiscal_year_start_month + 1).alias("fiscal_month"),
            # Days in month
            F.dayofmonth(F.last_day("date")).alias("days_in_month"),
            # Composite keys
            F.date_format("date", "yyyy-MM").alias("year_month"),
            F.concat(F.year("date"), F.lit("-Q"), F.quarter("date")).alias("year_quarter"),
            F.date_format("date", "yyyy-MM-dd").alias("date_str"),
        )

        row_count = df.count()
        logger.info(f"Generated {row_count:,} calendar rows")
        return df

    def _generate_calendar_duckdb(self, start_date: str, end_date: str, fiscal_year_start_month: int) -> DataFrame:
        """Generate calendar using DuckDB/pandas."""
        import pandas as pd

        # Generate date range
        dates = pd.date_range(start=start_date, end=end_date, freq='D')

        # Build calendar dataframe
        df = pd.DataFrame({'date': dates})
        # Primary key - integer YYYYMMDD format (required for cross-model joins)
        df['date_id'] = df['date'].dt.strftime('%Y%m%d').astype(int)
        df['year'] = df['date'].dt.year
        df['quarter'] = df['date'].dt.quarter
        df['month'] = df['date'].dt.month
        df['month_name'] = df['date'].dt.month_name()
        df['month_abbr'] = df['date'].dt.strftime('%b')
        df['week_of_year'] = df['date'].dt.isocalendar().week
        df['day_of_month'] = df['date'].dt.day
        df['day_of_week'] = df['date'].dt.dayofweek + 1  # 1=Mon, 7=Sun
        df['day_of_week_name'] = df['date'].dt.day_name()
        df['day_of_week_abbr'] = df['date'].dt.strftime('%a')
        df['day_of_year'] = df['date'].dt.dayofyear
        df['is_weekend'] = df['date'].dt.dayofweek >= 5
        df['is_weekday'] = df['date'].dt.dayofweek < 5
        df['is_month_start'] = df['date'].dt.is_month_start
        df['is_month_end'] = df['date'].dt.is_month_end
        df['is_quarter_start'] = df['date'].dt.is_quarter_start
        df['is_quarter_end'] = df['date'].dt.is_quarter_end
        df['is_year_start'] = df['date'].dt.is_year_start
        df['is_year_end'] = df['date'].dt.is_year_end

        # Fiscal year calculations
        df['fiscal_year'] = df.apply(
            lambda r: r['year'] if r['month'] >= fiscal_year_start_month else r['year'] - 1,
            axis=1
        )
        df['fiscal_quarter'] = df.apply(
            lambda r: ((r['month'] - fiscal_year_start_month) % 12) // 3 + 1,
            axis=1
        )
        df['fiscal_month'] = df.apply(
            lambda r: (r['month'] - fiscal_year_start_month) % 12 + 1,
            axis=1
        )

        df['days_in_month'] = df['date'].dt.days_in_month
        df['year_month'] = df['date'].dt.strftime('%Y-%m')
        df['year_quarter'] = df['year'].astype(str) + '-Q' + df['quarter'].astype(str)
        df['date_str'] = df['date'].dt.strftime('%Y-%m-%d')

        logger.info(f"Generated {len(df):,} calendar rows")

        # Convert to DuckDB relation if connection supports it
        if hasattr(self.connection, 'conn'):
            return self.connection.conn.from_df(df)
        return df

    # ============================================================
    # CORE MODEL CONVENIENCE METHODS
    # ============================================================

