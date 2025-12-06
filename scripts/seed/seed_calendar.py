#!/usr/bin/env python3
"""
Seed Calendar to Bronze Layer.

Generates calendar dimension data and writes to Bronze layer so the core model
can read it during Silver layer build.

Usage:
    python -m scripts.seed.seed_calendar

The calendar is generated data (not ingested from an API), but we seed it to
Bronze to maintain consistent architecture (Bronze -> Silver).
"""

import sys
from pathlib import Path

from utils.repo import setup_repo_imports

repo_root = setup_repo_imports()

from orchestration.common.spark_session import get_spark
from models.implemented.core.builders.calendar_builder import CalendarBuilder


def main():
    print("=" * 70)
    print("Seeding Calendar to Bronze Layer")
    print("=" * 70)
    print()

    # Initialize Spark
    print("1. Initializing Spark...")
    spark = get_spark("CalendarSeed")
    print()

    # Calendar configuration (matches core.yaml calendar_config)
    start_date = "2000-01-01"
    end_date = "2050-12-31"
    fiscal_year_start_month = 1

    print(f"2. Generating calendar data...")
    print(f"   Date range: {start_date} to {end_date}")
    print(f"   Fiscal year starts: Month {fiscal_year_start_month}")
    print()

    # Build calendar
    builder = CalendarBuilder(
        start_date=start_date,
        end_date=end_date,
        fiscal_year_start_month=fiscal_year_start_month
    )
    calendar_df = builder.build_spark_dataframe(spark)

    row_count = calendar_df.count()
    print(f"   Generated {row_count:,} calendar rows")
    print()

    # Write to Bronze layer
    bronze_path = repo_root / "storage" / "bronze" / "calendar_seed"
    print(f"3. Writing to Bronze layer...")
    print(f"   Path: {bronze_path}")
    print()

    calendar_df.write.format("delta").mode("overwrite").save(str(bronze_path))

    print(f"   Written successfully!")
    print()

    # Verify
    print("4. Verifying...")
    verify_df = spark.read.format("delta").load(str(bronze_path))
    verify_count = verify_df.count()
    print(f"   Verified: {verify_count:,} rows in Bronze")
    print()

    # Show sample
    print("5. Sample data:")
    verify_df.select("date", "year", "quarter", "month", "day_of_week_name", "is_weekday").show(5)

    print("=" * 70)
    print("Calendar seed complete!")
    print("=" * 70)
    print()
    print("You can now build the Silver layer:")
    print("  python -m scripts.build.build_silver_layer")
    print()

    spark.stop()


if __name__ == "__main__":
    main()
