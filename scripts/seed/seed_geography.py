#!/usr/bin/env python3
"""
Seed Geography to Bronze Layer.

Generates US geography dimension data (states, counties, cities, ZIP codes)
and writes to Bronze layer so the geography model can read it during Silver build.

Usage:
    python -m scripts.seed.seed_geography

The geography data is reference data (not ingested from an API), but we seed it to
Bronze to maintain consistent architecture (Bronze -> Silver).

Phase 1: States only (50 states + DC + territories)
Phase 2 (future): Counties from Census Bureau
Phase 3 (future): Cities from Census Bureau
Phase 4 (future): ZIP codes from HUD/USPS
"""
from __future__ import annotations

import sys
from pathlib import Path

from utils.repo import setup_repo_imports

repo_root = setup_repo_imports()

from orchestration.common.spark_session import get_spark
from models.foundation.geography.builders.state_builder import StateBuilder


def main():
    print("=" * 70)
    print("Seeding Geography to Bronze Layer")
    print("=" * 70)
    print()

    # Initialize Spark
    print("1. Initializing Spark...")
    spark = get_spark("GeographySeed")
    print()

    # ================================================================
    # STATES
    # ================================================================
    print("2. Generating state data...")
    print("   - 50 US states + DC")
    print("   - US territories (PR, GU, VI, AS, MP)")
    print()

    state_builder = StateBuilder(include_territories=True)
    state_df = state_builder.build_spark_dataframe(spark)

    state_count = state_df.count()
    print(f"   Generated {state_count} state/territory records")
    print()

    # Write states to Bronze layer
    bronze_states_path = repo_root / "storage" / "bronze" / "geography_states"
    print(f"3. Writing states to Bronze layer...")
    print(f"   Path: {bronze_states_path}")
    print()

    state_df.write.format("delta").mode("overwrite").save(str(bronze_states_path))

    print(f"   Written successfully!")
    print()

    # Verify
    print("4. Verifying...")
    verify_df = spark.read.format("delta").load(str(bronze_states_path))
    verify_count = verify_df.count()
    print(f"   Verified: {verify_count} state records in Bronze")
    print()

    # Show sample
    print("5. Sample data:")
    verify_df.select(
        "state_fips", "state_code", "state_name", "region", "division", "is_state"
    ).show(10)

    # Show by region
    print("6. States by region:")
    verify_df.groupBy("region").count().orderBy("region").show()

    print("=" * 70)
    print("Geography seed complete!")
    print("=" * 70)
    print()
    print("Seeded:")
    print(f"  - {state_count} US states and territories")
    print()
    print("You can now build the Silver layer:")
    print("  python -m scripts.build.build_silver_layer")
    print()
    print("Or build just the geography model:")
    print("  python -m scripts.orchestrate --models geography --build-only")
    print()

    spark.stop()


if __name__ == "__main__":
    main()
