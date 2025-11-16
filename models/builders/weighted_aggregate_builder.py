"""
Weighted Aggregate Builder for Silver Layer.

Builds materialized views/tables for weighted aggregate measures defined in model configuration.
These pre-calculated aggregates provide fast, consistent weighted indices across multiple stocks.
"""

from typing import Dict, Any, Optional, List
from pathlib import Path
import yaml


class WeightedAggregateBuilder:
    """
    Builds weighted aggregate tables/views in Silver layer using DuckDB.

    Weighted aggregates are multi-stock indices that combine values across stocks
    using various weighting schemes (equal, volume, market cap, etc.).
    """

    def __init__(self, connection, model_config: Dict[str, Any], storage_path: Path):
        """
        Initialize builder.

        Args:
            connection: DuckDB connection
            model_config: Parsed model configuration (from YAML)
            storage_path: Path to silver layer storage
        """
        self.connection = connection
        self.model_config = model_config
        self.storage_path = storage_path
        self.measures = model_config.get('measures', {})

    def build_all_weighted_aggregates(self, materialize: bool = False):
        """
        Build all weighted aggregate measures defined in model.

        Args:
            materialize: If True, create tables. If False, create views (default).
        """
        weighted_measures = self._get_weighted_aggregate_measures()

        if not weighted_measures:
            print("  No weighted aggregate measures found in model")
            return

        print(f"  Building {len(weighted_measures)} weighted aggregate measure(s)...")

        for measure_id in weighted_measures:
            try:
                self.build_weighted_aggregate(measure_id, materialize=materialize)
                print(f"  ✓ {measure_id}")
            except Exception as e:
                print(f"  ✗ {measure_id}: {str(e)}")

    def build_weighted_aggregate(
        self,
        measure_id: str,
        materialize: bool = False
    ):
        """
        Build a single weighted aggregate measure.

        Args:
            measure_id: ID of the weighted aggregate measure
            materialize: If True, create table. If False, create view.
        """
        measure = self.measures.get(measure_id)
        if not measure:
            raise ValueError(f"Measure '{measure_id}' not found in model config")

        if measure.get('type') not in ('weighted', 'weighted_aggregate'):
            raise ValueError(
                f"Measure '{measure_id}' is not a weighted type "
                f"(got type: {measure.get('type')})"
            )

        # Generate SQL for weighted aggregate
        sql = self._generate_weighted_aggregate_sql(measure_id, measure)

        # Create view or table
        if materialize:
            table_path = self.storage_path / "aggregates" / f"{measure_id}.parquet"
            table_path.parent.mkdir(parents=True, exist_ok=True)

            # Create table and write to parquet
            self.connection.execute(f"""
                COPY ({sql}) TO '{table_path}' (FORMAT PARQUET)
            """)

            # Create view that reads from parquet
            self.connection.execute(f"""
                CREATE OR REPLACE VIEW {measure_id} AS
                SELECT * FROM read_parquet('{table_path}')
            """)
        else:
            # Create view only (calculated on-demand)
            self.connection.execute(f"""
                CREATE OR REPLACE VIEW {measure_id} AS
                {sql}
            """)

    def _get_weighted_aggregate_measures(self) -> List[str]:
        """Get list of weighted aggregate measure IDs from model config."""
        return [
            measure_id
            for measure_id, measure in self.measures.items()
            if measure.get('type') in ('weighted', 'weighted_aggregate')  # Support both types
        ]

    def _generate_weighted_aggregate_sql(self, measure_id: str, measure: Dict[str, Any]) -> str:
        """
        Generate DuckDB SQL for weighted aggregate calculation.

        Args:
            measure_id: Measure ID
            measure: Measure configuration

        Returns:
            SQL query string
        """
        method = measure.get('weighting_method', 'equal')
        source = measure.get('source', 'fact_prices.close')
        group_by = measure.get('group_by', ['trade_date'])

        # Parse source (e.g., "fact_equity_prices.close" -> table="fact_equity_prices", column="close")
        if '.' in source:
            source_table, value_column = source.rsplit('.', 1)
        else:
            raise ValueError(f"Source must be in format 'table.column', got: {source}")

        # Build table reference - use actual table path for Parquet files
        # DuckDB can query Parquet files directly
        table_ref = self._get_table_reference(source_table)

        # Build group by clause
        group_cols = ', '.join(group_by)

        # Generate SQL based on weighting method
        if method == 'equal':
            return self._sql_equal_weighted(table_ref, value_column, group_cols)

        elif method == 'volume':
            return self._sql_volume_weighted(table_ref, value_column, group_cols)

        elif method == 'market_cap':
            return self._sql_market_cap_weighted(table_ref, value_column, group_cols)

        elif method == 'price':
            return self._sql_price_weighted(table_ref, value_column, group_cols)

        elif method == 'volume_deviation':
            return self._sql_volume_deviation_weighted(table_ref, value_column, group_cols)

        elif method == 'volatility':
            return self._sql_volatility_weighted(table_ref, value_column, group_cols)

        else:
            raise ValueError(f"Unknown weighting method: {method}")

    def _get_table_reference(self, table_name: str) -> str:
        """
        Get DuckDB table reference for a table name.

        Checks if table is already registered in DuckDB, otherwise constructs
        a read_parquet() reference to the Silver layer files.

        Args:
            table_name: Table name (e.g., 'fact_equity_prices')

        Returns:
            SQL table reference (e.g., 'fact_equity_prices' or 'read_parquet(...)')
        """
        # Try to use table if it's already registered
        try:
            result = self.connection.execute(f"SELECT 1 FROM {table_name} LIMIT 1")
            # Table exists, use it directly
            return table_name
        except:
            # Table not registered, use Parquet file path
            # Construct path based on table naming convention
            if table_name.startswith('fact_'):
                subdir = 'facts'
            elif table_name.startswith('dim_'):
                subdir = 'dimensions'
            else:
                subdir = 'tables'

            # Use glob pattern to read all partitions
            parquet_path = f"{self.storage_path}/{subdir}/{table_name}/**/*.parquet"
            return f"read_parquet('{parquet_path}', union_by_name=true)"

    def _sql_equal_weighted(self, table: str, value_col: str, group_cols: str) -> str:
        """Generate SQL for equal weighting (simple average). Normalization applied at query time."""
        return f"""
        SELECT
            {group_cols},
            AVG({value_col}) as weighted_value,
            COUNT(*) as stock_count
        FROM {table}
        WHERE {value_col} IS NOT NULL
        GROUP BY {group_cols}
        ORDER BY {group_cols}
        """

    def _sql_volume_weighted(self, table: str, value_col: str, group_cols: str) -> str:
        """Generate SQL for volume weighting. Normalization applied at query time."""
        return f"""
        SELECT
            {group_cols},
            SUM({value_col} * volume) / NULLIF(SUM(volume), 0) as weighted_value,
            COUNT(*) as stock_count,
            SUM(volume) as total_volume
        FROM {table}
        WHERE {value_col} IS NOT NULL
          AND volume IS NOT NULL
          AND volume > 0
        GROUP BY {group_cols}
        ORDER BY {group_cols}
        """

    def _sql_market_cap_weighted(self, table: str, value_col: str, group_cols: str) -> str:
        """Generate SQL for market cap weighting (price * volume as proxy). Normalization applied at query time."""
        return f"""
        SELECT
            {group_cols},
            SUM({value_col} * close * volume) / NULLIF(SUM(close * volume), 0) as weighted_value,
            COUNT(*) as stock_count,
            SUM(close * volume) as total_market_cap
        FROM {table}
        WHERE {value_col} IS NOT NULL
          AND close IS NOT NULL
          AND volume IS NOT NULL
          AND close > 0
          AND volume > 0
        GROUP BY {group_cols}
        ORDER BY {group_cols}
        """

    def _sql_price_weighted(self, table: str, value_col: str, group_cols: str) -> str:
        """Generate SQL for price weighting. Normalization applied at query time."""
        return f"""
        SELECT
            {group_cols},
            SUM({value_col} * close) / NULLIF(SUM(close), 0) as weighted_value,
            COUNT(*) as stock_count,
            SUM(close) as total_price
        FROM {table}
        WHERE {value_col} IS NOT NULL
          AND close IS NOT NULL
          AND close > 0
        GROUP BY {group_cols}
        ORDER BY {group_cols}
        """

    def _sql_volume_deviation_weighted(self, table: str, value_col: str, group_cols: str) -> str:
        """Generate SQL for volume deviation weighting (unusual activity). Normalization applied at query time."""
        return f"""
        WITH avg_volumes AS (
            SELECT
                ticker,
                AVG(volume) as avg_volume
            FROM {table}
            WHERE volume IS NOT NULL
            GROUP BY ticker
        )
        SELECT
            f.{group_cols},
            SUM(f.{value_col} * ABS(f.volume - av.avg_volume) * f.close) /
                NULLIF(SUM(ABS(f.volume - av.avg_volume) * f.close), 0) as weighted_value,
            COUNT(*) as stock_count,
            AVG(av.avg_volume) as avg_volume
        FROM {table} f
        JOIN avg_volumes av ON f.ticker = av.ticker
        WHERE f.{value_col} IS NOT NULL
          AND f.volume IS NOT NULL
          AND f.close IS NOT NULL
          AND f.close > 0
        GROUP BY f.{group_cols}
        ORDER BY f.{group_cols}
        """

    def _sql_volatility_weighted(self, table: str, value_col: str, group_cols: str) -> str:
        """Generate SQL for inverse volatility weighting (risk-adjusted). Normalization applied at query time."""
        return f"""
        WITH daily_ranges AS (
            SELECT
                {group_cols},
                ticker,
                {value_col},
                (high - low) as daily_range
            FROM {table}
            WHERE high IS NOT NULL
              AND low IS NOT NULL
              AND high >= low
              AND {value_col} IS NOT NULL
        )
        SELECT
            {group_cols},
            SUM({value_col} / NULLIF(daily_range, 0)) /
                NULLIF(SUM(1.0 / NULLIF(daily_range, 0)), 0) as weighted_value,
            COUNT(*) as stock_count,
            AVG(daily_range) as avg_volatility
        FROM daily_ranges
        WHERE daily_range > 0.001  -- Avoid division by zero
        GROUP BY {group_cols}
        ORDER BY {group_cols}
        """

    def drop_weighted_aggregates(self):
        """Drop all weighted aggregate views/tables."""
        weighted_measures = self._get_weighted_aggregate_measures()

        for measure_id in weighted_measures:
            try:
                self.connection.execute(f"DROP VIEW IF EXISTS {measure_id}")
                print(f"  ✓ Dropped {measure_id}")
            except Exception as e:
                print(f"  ✗ Error dropping {measure_id}: {str(e)}")


def load_model_config(model_path: Path) -> Dict[str, Any]:
    """Load model configuration from YAML file."""
    with open(model_path, 'r') as f:
        return yaml.safe_load(f)
