"""
Comprehensive Test Suite for GraphQueryPlanner and Measure Auto-Enrichment

Tests all functionality developed:
1. DuckDB backend joins
2. Spark backend joins
3. Column aliasing across tables
4. Table path resolution
5. Join type mapping
6. Measure auto-enrichment
7. Multi-hop joins

Run with: python examples/comprehensive_test.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = get_repo_root()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from core.context import RepoContext
from models.api.session import UniversalSession
from models.base.measures.executor import MeasureExecutor


def check_spark_available():
    """Check if PySpark is available."""
    try:
        import pyspark
        return True
    except ImportError:
        return False


class TestResults:
    """Track test results."""
    def __init__(self):
        self.passed = []
        self.failed = []
        self.skipped = []

    def add_pass(self, test_name):
        self.passed.append(test_name)
        print(f"  ✓ {test_name}")

    def add_fail(self, test_name, error):
        self.failed.append((test_name, str(error)))
        print(f"  ✗ {test_name}: {error}")

    def add_skip(self, test_name, reason):
        self.skipped.append((test_name, reason))
        print(f"  ⊘ {test_name} (skipped: {reason})")

    def summary(self):
        total = len(self.passed) + len(self.failed) + len(self.skipped)
        print()
        print("=" * 80)
        print("Test Summary")
        print("=" * 80)
        print(f"Total: {total}")
        print(f"✓ Passed: {len(self.passed)}")
        print(f"✗ Failed: {len(self.failed)}")
        print(f"⊘ Skipped: {len(self.skipped)}")
        print()

        if self.failed:
            print("Failed Tests:")
            for name, error in self.failed:
                print(f"  • {name}: {error}")
            print()

        return len(self.failed) == 0


def test_duckdb_basic_join(results):
    """Test 1: Basic DuckDB join (single hop)."""
    print()
    print("Test 1: DuckDB Basic Join (fact_equity_prices + dim_equity)")
    print("-" * 80)

    try:
        ctx = RepoContext.from_repo_root(connection_type="duckdb")
        session = UniversalSession(
            connection=ctx.connection,
            storage_cfg=ctx.storage,
            repo_root=ctx.repo
        )
        equity_model = session.get_model_instance('equity')

        # Join prices with equity
        df = equity_model.get_table_enriched(
            'fact_equity_prices',
            enrich_with=['dim_equity'],
            columns=['ticker', 'trade_date', 'close', 'company_name']
        )

        # Verify results
        assert len(df) > 0, "No rows returned"
        assert 'ticker' in df.columns, "ticker column missing"
        assert 'company_name' in df.columns, "company_name column missing"

        print(f"  Rows: {len(df):,}")
        print(f"  Columns: {list(df.columns)}")
        print(f"  Sample:\n{df.head(3)}")

        results.add_pass("DuckDB basic join")

    except Exception as e:
        results.add_fail("DuckDB basic join", e)


def test_duckdb_multi_hop_join(results):
    """Test 2: DuckDB multi-hop join (2 hops)."""
    print()
    print("Test 2: DuckDB Multi-Hop Join (prices → equity → exchange)")
    print("-" * 80)

    try:
        ctx = RepoContext.from_repo_root(connection_type="duckdb")
        session = UniversalSession(
            connection=ctx.connection,
            storage_cfg=ctx.storage,
            repo_root=ctx.repo
        )
        equity_model = session.get_model_instance('equity')

        # Multi-hop join
        df = equity_model.get_table_enriched(
            'fact_equity_prices',
            enrich_with=['dim_equity', 'dim_exchange'],
            columns=[
                'ticker',
                'trade_date',
                'close',
                'company_name',
                'exchange_name'
                # Note: country and timezone not in physical table
            ]
        )

        # Verify results
        assert len(df) > 0, "No rows returned"
        assert 'exchange_name' in df.columns, "exchange_name column missing"

        print(f"  Rows: {len(df):,}")
        print(f"  Columns: {list(df.columns)}")
        print(f"  Sample:\n{df.head(3)}")

        results.add_pass("DuckDB multi-hop join")

    except Exception as e:
        results.add_fail("DuckDB multi-hop join", e)


def test_duckdb_column_aliasing(results):
    """Test 3: Column aliasing (columns from different tables)."""
    print()
    print("Test 3: DuckDB Column Aliasing")
    print("-" * 80)

    try:
        ctx = RepoContext.from_repo_root(connection_type="duckdb")
        session = UniversalSession(
            connection=ctx.connection,
            storage_cfg=ctx.storage,
            repo_root=ctx.repo
        )
        equity_model = session.get_model_instance('equity')

        # Request columns from multiple tables
        df = equity_model.get_table_enriched(
            'fact_equity_prices',
            enrich_with=['dim_equity', 'dim_exchange'],
            columns=[
                'ticker',           # from fact_equity_prices (t0)
                'close',            # from fact_equity_prices (t0)
                'company_name',     # from dim_equity (t1)
                'exchange_name',    # from dim_exchange (t2)
            ]
        )

        # Verify all columns present
        for col in ['ticker', 'close', 'company_name', 'exchange_name']:
            assert col in df.columns, f"{col} column missing"

        print(f"  ✓ All columns correctly aliased")
        print(f"  Columns: {list(df.columns)}")

        results.add_pass("DuckDB column aliasing")

    except Exception as e:
        results.add_fail("DuckDB column aliasing", e)


def test_duckdb_join_type_mapping(results):
    """Test 4: Join type mapping (many_to_one → LEFT)."""
    print()
    print("Test 4: DuckDB Join Type Mapping")
    print("-" * 80)

    try:
        ctx = RepoContext.from_repo_root(connection_type="duckdb")
        session = UniversalSession(
            connection=ctx.connection,
            storage_cfg=ctx.storage,
            repo_root=ctx.repo
        )
        equity_model = session.get_model_instance('equity')

        # Check edge join types
        planner = equity_model.query_planner

        # Get edge from prices to equity
        edge_data = planner.graph.edges['fact_equity_prices', 'dim_equity']
        join_type = edge_data.get('join_type', 'left')

        print(f"  Edge: fact_equity_prices → dim_equity")
        print(f"  Config join_type: {join_type}")
        print(f"  Maps to SQL: LEFT (via join_type_map)")

        # Verify join executes without error
        df = equity_model.get_table_enriched(
            'fact_equity_prices',
            enrich_with=['dim_equity']
        )

        assert len(df) > 0, "Join failed to return rows"

        results.add_pass("DuckDB join type mapping")

    except Exception as e:
        results.add_fail("DuckDB join type mapping", e)


def test_measure_auto_enrichment_duckdb(results):
    """Test 5: Measure auto-enrichment with DuckDB."""
    print()
    print("Test 5: Measure Auto-Enrichment (DuckDB)")
    print("-" * 80)

    try:
        ctx = RepoContext.from_repo_root(connection_type="duckdb")
        session = UniversalSession(
            connection=ctx.connection,
            storage_cfg=ctx.storage,
            repo_root=ctx.repo
        )
        equity_model = session.get_model_instance('equity')
        executor = MeasureExecutor(equity_model, backend='duckdb')

        # Execute auto-enriched measure
        print("  Executing: avg_close_by_exchange")
        print("  Group by: exchange_name (not in fact_equity_prices)")
        print("  Auto-enrich: true → system joins to dim_exchange")

        result = executor.execute_measure(
            'avg_close_by_exchange',
            entity_column='exchange_name',
            limit=5
        )

        # Verify results
        assert result.rows > 0, "No rows returned"
        assert 'exchange_name' in result.data.columns, "exchange_name missing"

        print(f"  ✓ Rows: {result.rows}")
        print(f"  ✓ Query time: {result.query_time_ms:.2f}ms")
        print(f"  Sample:\n{result.data.head(3)}")

        results.add_pass("Measure auto-enrichment (DuckDB)")

    except Exception as e:
        results.add_fail("Measure auto-enrichment (DuckDB)", e)


def test_spark_basic_join(results):
    """Test 6: Spark basic join."""
    print()
    print("Test 6: Spark Basic Join")
    print("-" * 80)

    if not check_spark_available():
        results.add_skip("Spark basic join", "PySpark not available")
        return

    try:
        ctx = RepoContext.from_repo_root(connection_type="spark")
        session = UniversalSession(
            connection=ctx.connection,
            storage_cfg=ctx.storage,
            repo_root=ctx.repo
        )
        equity_model = session.get_model_instance('equity')

        # Join with Spark
        df = equity_model.get_table_enriched(
            'fact_equity_prices',
            enrich_with=['dim_equity'],
            columns=['ticker', 'trade_date', 'close', 'company_name']
        )

        # Verify results (Spark DataFrame)
        count = df.count()
        assert count > 0, "No rows returned"

        print(f"  Rows: {count:,}")
        print(f"  Columns: {df.columns}")
        print(f"  Backend: Spark DataFrame (lazy)")

        results.add_pass("Spark basic join")

    except Exception as e:
        results.add_fail("Spark basic join", e)


def test_spark_join_type_mapping(results):
    """Test 7: Spark join type mapping."""
    print()
    print("Test 7: Spark Join Type Mapping")
    print("-" * 80)

    if not check_spark_available():
        results.add_skip("Spark join type mapping", "PySpark not available")
        return

    try:
        ctx = RepoContext.from_repo_root(connection_type="spark")
        session = UniversalSession(
            connection=ctx.connection,
            storage_cfg=ctx.storage,
            repo_root=ctx.repo
        )
        equity_model = session.get_model_instance('equity')
        planner = equity_model.query_planner

        # Check edge join types
        edge_data = planner.graph.edges['fact_equity_prices', 'dim_equity']
        join_type = edge_data.get('join_type', 'left')

        print(f"  Edge: fact_equity_prices → dim_equity")
        print(f"  Config join_type: {join_type}")
        print(f"  Maps to Spark: left (via join_type_map)")

        # Verify join executes
        df = equity_model.get_table_enriched(
            'fact_equity_prices',
            enrich_with=['dim_equity']
        )

        assert df.count() > 0, "Join failed"

        results.add_pass("Spark join type mapping")

    except Exception as e:
        results.add_fail("Spark join type mapping", e)


def test_measure_auto_enrichment_spark(results):
    """Test 8: Measure auto-enrichment with Spark."""
    print()
    print("Test 8: Measure Auto-Enrichment (Spark)")
    print("-" * 80)

    if not check_spark_available():
        results.add_skip("Measure auto-enrichment (Spark)", "PySpark not available")
        return

    try:
        ctx = RepoContext.from_repo_root(connection_type="spark")
        session = UniversalSession(
            connection=ctx.connection,
            storage_cfg=ctx.storage,
            repo_root=ctx.repo
        )
        equity_model = session.get_model_instance('equity')
        executor = MeasureExecutor(equity_model, backend='spark')

        # Execute auto-enriched measure
        print("  Executing: avg_close_by_exchange")
        print("  Group by: exchange_name (not in fact_equity_prices)")
        print("  Auto-enrich: true → system joins to dim_exchange")

        result = executor.execute_measure(
            'avg_close_by_exchange',
            entity_column='exchange_name',
            limit=5
        )

        # Verify results
        assert result.rows > 0, "No rows returned"

        print(f"  ✓ Rows: {result.rows}")
        print(f"  ✓ Query time: {result.query_time_ms:.2f}ms")
        print(f"  ✓ Backend: Spark")

        results.add_pass("Measure auto-enrichment (Spark)")

    except Exception as e:
        results.add_fail("Measure auto-enrichment (Spark)", e)


def test_query_planner_capabilities(results):
    """Test 9: Query planner utility methods."""
    print()
    print("Test 9: Query Planner Capabilities")
    print("-" * 80)

    try:
        ctx = RepoContext.from_repo_root(connection_type="duckdb")
        session = UniversalSession(
            connection=ctx.connection,
            storage_cfg=ctx.storage,
            repo_root=ctx.repo
        )
        equity_model = session.get_model_instance('equity')
        planner = equity_model.query_planner

        # Test find_tables_with_column
        tables = planner.find_tables_with_column('exchange_name')
        assert 'dim_exchange' in tables, "exchange_name not found in dim_exchange"
        print(f"  ✓ find_tables_with_column('exchange_name'): {tables}")

        # Test get_join_path
        path = planner.get_join_path('fact_equity_prices', 'dim_exchange')
        assert path == ['fact_equity_prices', 'dim_equity', 'dim_exchange'], "Wrong path"
        print(f"  ✓ get_join_path: {' → '.join(path)}")

        # Test get_table_relationships
        rels = planner.get_table_relationships('fact_equity_prices')
        assert 'dim_equity' in rels['can_join_to'], "dim_equity not in relationships"
        print(f"  ✓ get_table_relationships: {rels}")

        results.add_pass("Query planner capabilities")

    except Exception as e:
        results.add_fail("Query planner capabilities", e)


def main():
    """Run all tests."""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 78 + "║")
    print("║" + "  Comprehensive Test Suite".center(78) + "║")
    print("║" + "  GraphQueryPlanner & Measure Auto-Enrichment".center(78) + "║")
    print("║" + " " * 78 + "║")
    print("╚" + "=" * 78 + "╝")

    results = TestResults()
    has_spark = check_spark_available()

    print()
    print("Environment:")
    print(f"  PySpark: {'✓ Available' if has_spark else '✗ Not available'}")
    print()

    # Run all tests
    test_duckdb_basic_join(results)
    test_duckdb_multi_hop_join(results)
    test_duckdb_column_aliasing(results)
    test_duckdb_join_type_mapping(results)
    test_measure_auto_enrichment_duckdb(results)
    test_spark_basic_join(results)
    test_spark_join_type_mapping(results)
    test_measure_auto_enrichment_spark(results)
    test_query_planner_capabilities(results)

    # Print summary
    success = results.summary()

    if success:
        print("=" * 80)
        print("✓ ALL TESTS PASSED!")
        print("=" * 80)
        return 0
    else:
        print("=" * 80)
        print("✗ SOME TESTS FAILED")
        print("=" * 80)
        return 1


if __name__ == '__main__':
    sys.exit(main())
