#!/usr/bin/env python
"""
Diagnose Spark Session Issues - Comprehensive debugging for Delta Lake 4.x session problems.

This script traces the full flow from ForecastBuilder → StocksModel → data access
to identify exactly where and why Spark sessions become unregistered.

Usage:
    python -m scripts.debug.diagnose_spark_session
"""
from __future__ import annotations

import sys
from pathlib import Path

# Setup repo imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.logging import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


def check_session_state(spark, label: str) -> dict:
    """Check and log current Spark session state."""
    result = {
        "label": label,
        "spark_object": str(spark),
        "spark_id": id(spark),
        "jvm_available": False,
        "active_session": None,
        "default_session": None,
        "error": None
    }

    try:
        jvm = spark._jvm
        result["jvm_available"] = True

        # Check active session
        active = jvm.org.apache.spark.sql.SparkSession.getActiveSession()
        result["active_session"] = "PRESENT" if active.isDefined() else "EMPTY"

        # Check default session
        default = jvm.org.apache.spark.sql.SparkSession.getDefaultSession()
        result["default_session"] = "PRESENT" if default.isDefined() else "EMPTY"

    except Exception as e:
        result["error"] = str(e)

    logger.info(f"SESSION STATE [{label}]:")
    logger.info(f"  Spark object: {result['spark_object'][:80]}")
    logger.info(f"  Object ID: {result['spark_id']}")
    logger.info(f"  JVM available: {result['jvm_available']}")
    logger.info(f"  Active session: {result['active_session']}")
    logger.info(f"  Default session: {result['default_session']}")
    if result["error"]:
        logger.error(f"  Error: {result['error']}")

    return result


def register_session(spark, label: str) -> bool:
    """Register Spark session and verify."""
    logger.info(f"REGISTERING SESSION [{label}]...")

    try:
        jvm = spark._jvm
        jss = spark._jsparkSession

        # Set active session
        jvm.org.apache.spark.sql.SparkSession.setActiveSession(jss)
        logger.info("  Called setActiveSession()")

        # Set default session
        jvm.org.apache.spark.sql.SparkSession.setDefaultSession(jss)
        logger.info("  Called setDefaultSession()")

        # Verify
        check_session_state(spark, f"{label}_AFTER_REGISTER")
        return True

    except Exception as e:
        logger.error(f"  FAILED to register: {e}")
        return False


def test_delta_read(spark, path: str, label: str) -> bool:
    """Test Delta read and log session state before/after."""
    logger.info(f"DELTA READ TEST [{label}]: {path}")

    # Check state before
    check_session_state(spark, f"{label}_BEFORE_READ")

    try:
        df = spark.read.format("delta").load(path)
        count = df.count()
        logger.info(f"  SUCCESS: Read {count} rows")
        return True
    except Exception as e:
        logger.error(f"  FAILED: {e}")

        # Check state after failure
        check_session_state(spark, f"{label}_AFTER_FAILURE")
        return False


def main():
    """Run comprehensive Spark session diagnostics."""
    import json

    logger.info("=" * 80)
    logger.info("SPARK SESSION DIAGNOSTIC TOOL")
    logger.info("=" * 80)

    # Load storage config
    repo_root = Path(__file__).parent.parent.parent
    storage_path = repo_root / "configs" / "storage.json"

    with open(storage_path) as f:
        storage_cfg = json.load(f)

    silver_root = Path(storage_cfg["roots"]["silver"])
    if not silver_root.is_absolute():
        silver_root = repo_root / silver_root

    logger.info(f"Repo root: {repo_root}")
    logger.info(f"Silver root: {silver_root}")

    # Step 1: Create Spark session
    logger.info("\n" + "=" * 80)
    logger.info("STEP 1: CREATE SPARK SESSION")
    logger.info("=" * 80)

    from orchestration.common.spark_session import get_spark
    spark = get_spark()

    check_session_state(spark, "INITIAL")

    # Step 2: Check if stocks Silver exists
    logger.info("\n" + "=" * 80)
    logger.info("STEP 2: CHECK STOCKS SILVER PATH")
    logger.info("=" * 80)

    stocks_silver = silver_root / "stocks"
    logger.info(f"Stocks Silver path: {stocks_silver}")
    logger.info(f"  Exists: {stocks_silver.exists()}")

    if stocks_silver.exists():
        dims_path = stocks_silver / "dims"
        facts_path = stocks_silver / "facts"
        logger.info(f"  dims/ exists: {dims_path.exists()}")
        logger.info(f"  facts/ exists: {facts_path.exists()}")

        if dims_path.exists():
            for table_dir in dims_path.iterdir():
                if table_dir.is_dir():
                    is_delta = (table_dir / "_delta_log").exists()
                    logger.info(f"    {table_dir.name}: Delta={is_delta}")

    # Step 3: Test basic Delta read
    logger.info("\n" + "=" * 80)
    logger.info("STEP 3: TEST BASIC DELTA READ")
    logger.info("=" * 80)

    # Find first Delta table
    test_table = None
    if stocks_silver.exists():
        for subdir in ["dims", "facts"]:
            subpath = stocks_silver / subdir
            if subpath.exists():
                for table_dir in subpath.iterdir():
                    if table_dir.is_dir() and (table_dir / "_delta_log").exists():
                        test_table = str(table_dir)
                        break
                if test_table:
                    break

    if test_table:
        test_delta_read(spark, test_table, "BASIC")
    else:
        logger.warning("No Delta tables found for testing")

    # Step 4: Test read after session registration
    logger.info("\n" + "=" * 80)
    logger.info("STEP 4: TEST AFTER SESSION REGISTRATION")
    logger.info("=" * 80)

    register_session(spark, "MANUAL")

    if test_table:
        test_delta_read(spark, test_table, "AFTER_REGISTER")

    # Step 5: Test through SparkConnection wrapper
    logger.info("\n" + "=" * 80)
    logger.info("STEP 5: TEST THROUGH SPARKCONNECTION WRAPPER")
    logger.info("=" * 80)

    from core.connection import SparkConnection
    conn = SparkConnection(spark)

    logger.info(f"SparkConnection created")
    logger.info(f"  conn.spark is spark: {conn.spark is spark}")
    logger.info(f"  conn.spark ID: {id(conn.spark)}")

    # Check session state through wrapper
    check_session_state(conn.spark, "THROUGH_WRAPPER")

    # Step 6: Test StocksModel creation flow
    logger.info("\n" + "=" * 80)
    logger.info("STEP 6: TEST STOCKSMODEL CREATION FLOW")
    logger.info("=" * 80)

    try:
        from core.connection import get_spark_connection
        from config.domain_loader import ModelConfigLoader
        from models.domains.securities.stocks.model import StocksModel

        # Create connection wrapper (same as ForecastBuilder does)
        connection = get_spark_connection(spark)
        logger.info(f"Created connection wrapper: {type(connection)}")
        logger.info(f"  connection.spark is spark: {connection.spark is spark}")

        # Load config
        domains_dir = repo_root / "domains"
        loader = ModelConfigLoader(domains_dir)
        stocks_config = loader.load_model_config("stocks")
        logger.info(f"Loaded stocks config")

        # Check session before creating model
        check_session_state(spark, "BEFORE_MODEL_CREATE")

        # Create model
        model = StocksModel(
            connection=connection,
            storage_cfg=storage_cfg,
            model_cfg=stocks_config,
            params={},
            repo_root=repo_root
        )
        logger.info(f"Created StocksModel")
        logger.info(f"  model.backend: {model.backend}")
        logger.info(f"  model.connection: {type(model.connection)}")

        # Check session after creating model
        check_session_state(spark, "AFTER_MODEL_CREATE")

        # Step 7: Test ensure_built flow
        logger.info("\n" + "=" * 80)
        logger.info("STEP 7: TEST ENSURE_BUILT FLOW")
        logger.info("=" * 80)

        # Manually trace the ensure_built flow
        logger.info("Calling _ensure_active_spark_session()...")
        model._ensure_active_spark_session()
        check_session_state(spark, "AFTER_ENSURE_ACTIVE")

        logger.info("Checking _load_from_silver()...")
        silver_root_path = model._get_silver_root()
        logger.info(f"  Silver root: {silver_root_path}")

        # Try to read a single table manually
        if test_table:
            logger.info(f"Manually reading: {test_table}")

            # Check state right before read
            check_session_state(spark, "RIGHT_BEFORE_READ")

            # Re-register right before
            register_session(spark, "RIGHT_BEFORE_READ")

            # Now try the read
            df = model._read_silver_table(test_table)
            if df is not None:
                logger.info(f"  SUCCESS: Got DataFrame")
            else:
                logger.error(f"  FAILED: Got None")

    except Exception as e:
        logger.error(f"StocksModel test failed: {e}", exc_info=True)

    # Step 8: Summary
    logger.info("\n" + "=" * 80)
    logger.info("DIAGNOSTIC SUMMARY")
    logger.info("=" * 80)

    logger.info("""
POSSIBLE ISSUES TO CHECK:
1. Is setActiveSession/setDefaultSession actually working?
   - Check if active session shows PRESENT after registration

2. Is the session getting cleared between operations?
   - Watch for EMPTY after registration

3. Is there a different thread being used?
   - Thread-local storage means session must be set per-thread

4. Is there a second SparkSession being created somewhere?
   - Check spark IDs throughout the flow

5. Is the connection wrapper causing issues?
   - Verify conn.spark is spark throughout
""")

    spark.stop()
    logger.info("Done.")


if __name__ == "__main__":
    main()
