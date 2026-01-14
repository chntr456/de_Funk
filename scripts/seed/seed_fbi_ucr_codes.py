#!/usr/bin/env python3
"""
Seed FBI UCR Codes to Bronze Layer.

Generates FBI Uniform Crime Reporting code reference table and writes to Bronze layer.
This is static reference data (codes are stable and defined by FBI).

Usage:
    python -m scripts.seed.seed_fbi_ucr_codes
    python -m scripts.seed.seed_fbi_ucr_codes --storage-path /shared/storage

The FBI UCR codes are a national standard for crime classification.
- Part I (Index) crimes: Tracked nationally for crime statistics
- Part II crimes: All other offenses

Reference: https://ucr.fbi.gov/
"""

import sys
import argparse
from pathlib import Path

from utils.repo import setup_repo_imports

repo_root = setup_repo_imports()

from orchestration.common.spark_session import get_spark
from pyspark.sql.types import StructType, StructField, StringType, BooleanType


# FBI UCR Code Data
# Source: FBI Uniform Crime Reporting Program
FBI_UCR_CODES = [
    # Part I - Violent Crimes
    {"fbi_code": "01A", "name": "Homicide - 1st & 2nd Degree Murder", "part": "I", "is_index": True, "is_violent": True, "category": "VIOLENT", "subcategory": "HOMICIDE"},
    {"fbi_code": "01B", "name": "Homicide - Involuntary Manslaughter", "part": "I", "is_index": True, "is_violent": True, "category": "VIOLENT", "subcategory": "HOMICIDE"},
    {"fbi_code": "02", "name": "Criminal Sexual Assault", "part": "I", "is_index": True, "is_violent": True, "category": "VIOLENT", "subcategory": "SEXUAL_ASSAULT"},
    {"fbi_code": "03", "name": "Robbery", "part": "I", "is_index": True, "is_violent": True, "category": "VIOLENT", "subcategory": "ROBBERY"},
    {"fbi_code": "04A", "name": "Aggravated Assault", "part": "I", "is_index": True, "is_violent": True, "category": "VIOLENT", "subcategory": "ASSAULT"},
    {"fbi_code": "04B", "name": "Aggravated Battery", "part": "I", "is_index": True, "is_violent": True, "category": "VIOLENT", "subcategory": "ASSAULT"},
    {"fbi_code": "08A", "name": "Simple Assault", "part": "II", "is_index": False, "is_violent": True, "category": "VIOLENT", "subcategory": "ASSAULT"},
    {"fbi_code": "08B", "name": "Simple Battery", "part": "II", "is_index": False, "is_violent": True, "category": "VIOLENT", "subcategory": "ASSAULT"},

    # Part I - Property Crimes
    {"fbi_code": "05", "name": "Burglary", "part": "I", "is_index": True, "is_violent": False, "category": "PROPERTY", "subcategory": "BURGLARY"},
    {"fbi_code": "06", "name": "Larceny-Theft", "part": "I", "is_index": True, "is_violent": False, "category": "PROPERTY", "subcategory": "THEFT"},
    {"fbi_code": "07", "name": "Motor Vehicle Theft", "part": "I", "is_index": True, "is_violent": False, "category": "PROPERTY", "subcategory": "VEHICLE_THEFT"},
    {"fbi_code": "09", "name": "Arson", "part": "I", "is_index": True, "is_violent": False, "category": "PROPERTY", "subcategory": "ARSON"},

    # Part II - Financial
    {"fbi_code": "10", "name": "Forgery & Counterfeiting", "part": "II", "is_index": False, "is_violent": False, "category": "FINANCIAL", "subcategory": "FORGERY"},
    {"fbi_code": "11", "name": "Fraud", "part": "II", "is_index": False, "is_violent": False, "category": "FINANCIAL", "subcategory": "FRAUD"},
    {"fbi_code": "12", "name": "Embezzlement", "part": "II", "is_index": False, "is_violent": False, "category": "FINANCIAL", "subcategory": "EMBEZZLEMENT"},

    # Part II - Property
    {"fbi_code": "13", "name": "Stolen Property", "part": "II", "is_index": False, "is_violent": False, "category": "PROPERTY", "subcategory": "STOLEN_PROPERTY"},
    {"fbi_code": "14", "name": "Vandalism", "part": "II", "is_index": False, "is_violent": False, "category": "PROPERTY", "subcategory": "VANDALISM"},

    # Part II - Public Order
    {"fbi_code": "15", "name": "Weapons Violation", "part": "II", "is_index": False, "is_violent": False, "category": "PUBLIC_ORDER", "subcategory": "WEAPONS"},
    {"fbi_code": "16", "name": "Prostitution", "part": "II", "is_index": False, "is_violent": False, "category": "PUBLIC_ORDER", "subcategory": "PROSTITUTION"},
    {"fbi_code": "17", "name": "Sex Offense", "part": "II", "is_index": False, "is_violent": False, "category": "PUBLIC_ORDER", "subcategory": "SEX_OFFENSE"},
    {"fbi_code": "18", "name": "Drug Abuse", "part": "II", "is_index": False, "is_violent": False, "category": "DRUG", "subcategory": "NARCOTICS"},
    {"fbi_code": "19", "name": "Gambling", "part": "II", "is_index": False, "is_violent": False, "category": "PUBLIC_ORDER", "subcategory": "GAMBLING"},
    {"fbi_code": "20", "name": "Offenses Against Family", "part": "II", "is_index": False, "is_violent": False, "category": "PUBLIC_ORDER", "subcategory": "FAMILY"},
    {"fbi_code": "22", "name": "Liquor Laws", "part": "II", "is_index": False, "is_violent": False, "category": "PUBLIC_ORDER", "subcategory": "LIQUOR"},
    {"fbi_code": "24", "name": "Disorderly Conduct", "part": "II", "is_index": False, "is_violent": False, "category": "PUBLIC_ORDER", "subcategory": "DISORDERLY"},
    {"fbi_code": "26", "name": "Other Offense", "part": "II", "is_index": False, "is_violent": False, "category": "OTHER", "subcategory": "OTHER"},
]


def get_schema():
    """Get Spark schema for FBI UCR codes."""
    return StructType([
        StructField("fbi_code", StringType(), False),
        StructField("name", StringType(), True),
        StructField("part", StringType(), True),
        StructField("is_index", BooleanType(), True),
        StructField("is_violent", BooleanType(), True),
        StructField("category", StringType(), True),
        StructField("subcategory", StringType(), True),
    ])


def seed_fbi_ucr_codes(storage_path: Path = None, spark=None) -> int:
    """
    Seed FBI UCR codes to Bronze layer.

    Args:
        storage_path: Optional storage root (default: repo_root/storage)
        spark: Optional SparkSession (will create one if not provided)

    Returns:
        Number of rows written
    """
    # Determine storage path
    if storage_path is None:
        storage_path = repo_root / "storage"
    storage_path = Path(storage_path)

    bronze_path = storage_path / "bronze" / "fbi_ucr_codes"

    # Check if already exists
    if bronze_path.exists() and (bronze_path / "_delta_log").exists():
        owns_spark = spark is None
        if owns_spark:
            spark = get_spark("FBICodesSeedCheck")
        try:
            existing_df = spark.read.format("delta").load(str(bronze_path))
            existing_count = existing_df.count()
            if existing_count > 0:
                print(f"FBI UCR codes already seeded: {existing_count} codes at {bronze_path}")
                return existing_count
        except Exception:
            pass
        finally:
            if owns_spark:
                spark.stop()

    print("=" * 70)
    print("Seeding FBI UCR Codes to Bronze Layer")
    print("=" * 70)
    print()

    # Initialize Spark if not provided
    owns_spark = spark is None
    if owns_spark:
        print("1. Initializing Spark...")
        spark = get_spark("FBICodesSeed")
        print()
    else:
        print("1. Using existing Spark session...")
        print()

    print(f"2. Creating FBI UCR codes dataframe...")
    print(f"   Total codes: {len(FBI_UCR_CODES)}")
    print()

    # Create DataFrame
    schema = get_schema()
    codes_df = spark.createDataFrame(FBI_UCR_CODES, schema)

    # Show breakdown
    print("   Breakdown:")
    codes_df.groupBy("part", "category").count().orderBy("part", "category").show(truncate=False)

    # Write to Bronze layer
    print(f"3. Writing to Bronze layer...")
    print(f"   Path: {bronze_path}")
    print()

    codes_df.write.format("delta").mode("overwrite").save(str(bronze_path))

    print(f"   Written successfully!")
    print()

    # Verify
    print("4. Verifying...")
    verify_df = spark.read.format("delta").load(str(bronze_path))
    verify_count = verify_df.count()
    print(f"   Verified: {verify_count} codes in Bronze")
    print()

    # Show all codes
    print("5. FBI UCR Codes:")
    verify_df.select("fbi_code", "name", "part", "is_index", "category").show(30, truncate=False)

    print("=" * 70)
    print("FBI UCR codes seed complete!")
    print("=" * 70)
    print()

    if owns_spark:
        spark.stop()

    return verify_count


def main():
    parser = argparse.ArgumentParser(description="Seed FBI UCR codes to Bronze layer")
    parser.add_argument(
        "--storage-path",
        type=str,
        default=None,
        help="Storage root path (default: repo_root/storage)"
    )
    args = parser.parse_args()

    storage_path = Path(args.storage_path) if args.storage_path else None
    seed_fbi_ucr_codes(storage_path)


if __name__ == "__main__":
    main()
