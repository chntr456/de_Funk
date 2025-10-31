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

        if measure.get('type') != 'weighted_aggregate':
            raise ValueError(f"Measure '{measure_id}' is not a weighted_aggregate type")

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
            if measure.get('type') == 'weighted_aggregate'
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

        # Parse source (e.g., "fact_prices.close" -> table="fact_prices", column="close")
        if '.' in source:
            source_table, value_column = source.rsplit('.', 1)
        else:
            raise ValueError(f"Source must be in format 'table.column', got: {source}")

        # Build group by clause
        group_cols = ', '.join(group_by)

        # Generate SQL based on weighting method
        if method == 'equal':
            return self._sql_equal_weighted(source_table, value_column, group_cols)

        elif method == 'volume':
            return self._sql_volume_weighted(source_table, value_column, group_cols)

        elif method == 'market_cap':
            return self._sql_market_cap_weighted(source_table, value_column, group_cols)

        elif method == 'price':
            return self._sql_price_weighted(source_table, value_column, group_cols)

        elif method == 'volume_deviation':
            return self._sql_volume_deviation_weighted(source_table, value_column, group_cols)

        elif method == 'volatility':
            return self._sql_volatility_weighted(source_table, value_column, group_cols)

        else:
            raise ValueError(f"Unknown weighting method: {method}")

    def _sql_equal_weighted(self, table: str, value_col: str, group_cols: str) -> str:
        """Generate SQL for equal weighting (simple average), normalized to base 100."""
        return f"""
        WITH daily_values AS (
            SELECT
                {group_cols},
                AVG({value_col}) as raw_value,
                COUNT(*) as stock_count
            FROM {table}
            WHERE {value_col} IS NOT NULL
            GROUP BY {group_cols}
        ),
        base_value AS (
            SELECT MIN({group_cols}) as base_date, raw_value as base_raw_value
            FROM daily_values
            LIMIT 1
        )
        SELECT
            dv.{group_cols},
            (dv.raw_value / bv.base_raw_value) * 100 as weighted_value,
            dv.stock_count
        FROM daily_values dv
        CROSS JOIN base_value bv
        ORDER BY dv.{group_cols}
        """

    def _sql_volume_weighted(self, table: str, value_col: str, group_cols: str) -> str:
        """Generate SQL for volume weighting, normalized to base 100."""
        return f"""
        WITH daily_values AS (
            SELECT
                {group_cols},
                SUM({value_col} * volume) / NULLIF(SUM(volume), 0) as raw_value,
                COUNT(*) as stock_count,
                SUM(volume) as total_volume
            FROM {table}
            WHERE {value_col} IS NOT NULL
              AND volume IS NOT NULL
              AND volume > 0
            GROUP BY {group_cols}
        ),
        base_value AS (
            SELECT MIN({group_cols}) as base_date, raw_value as base_raw_value
            FROM daily_values
            LIMIT 1
        )
        SELECT
            dv.{group_cols},
            (dv.raw_value / bv.base_raw_value) * 100 as weighted_value,
            dv.stock_count,
            dv.total_volume
        FROM daily_values dv
        CROSS JOIN base_value bv
        ORDER BY dv.{group_cols}
        """

    def _sql_market_cap_weighted(self, table: str, value_col: str, group_cols: str) -> str:
        """Generate SQL for market cap weighting (price * volume as proxy), normalized to base 100."""
        return f"""
        WITH daily_values AS (
            SELECT
                {group_cols},
                SUM({value_col} * close * volume) / NULLIF(SUM(close * volume), 0) as raw_value,
                COUNT(*) as stock_count,
                SUM(close * volume) as total_market_cap
            FROM {table}
            WHERE {value_col} IS NOT NULL
              AND close IS NOT NULL
              AND volume IS NOT NULL
              AND close > 0
              AND volume > 0
            GROUP BY {group_cols}
        ),
        base_value AS (
            SELECT MIN({group_cols}) as base_date, raw_value as base_raw_value
            FROM daily_values
            LIMIT 1
        )
        SELECT
            dv.{group_cols},
            (dv.raw_value / bv.base_raw_value) * 100 as weighted_value,
            dv.stock_count,
            dv.total_market_cap
        FROM daily_values dv
        CROSS JOIN base_value bv
        ORDER BY dv.{group_cols}
        """

    def _sql_price_weighted(self, table: str, value_col: str, group_cols: str) -> str:
        """Generate SQL for price weighting, normalized to base 100."""
        return f"""
        WITH daily_values AS (
            SELECT
                {group_cols},
                SUM({value_col} * close) / NULLIF(SUM(close), 0) as raw_value,
                COUNT(*) as stock_count,
                SUM(close) as total_price
            FROM {table}
            WHERE {value_col} IS NOT NULL
              AND close IS NOT NULL
              AND close > 0
            GROUP BY {group_cols}
        ),
        base_value AS (
            SELECT MIN({group_cols}) as base_date, raw_value as base_raw_value
            FROM daily_values
            LIMIT 1
        )
        SELECT
            dv.{group_cols},
            (dv.raw_value / bv.base_raw_value) * 100 as weighted_value,
            dv.stock_count,
            dv.total_price
        FROM daily_values dv
        CROSS JOIN base_value bv
        ORDER BY dv.{group_cols}
        """

    def _sql_volume_deviation_weighted(self, table: str, value_col: str, group_cols: str) -> str:
        """Generate SQL for volume deviation weighting (unusual activity), normalized to base 100."""
        return f"""
        WITH avg_volumes AS (
            SELECT
                {group_cols},
                AVG(volume) as avg_volume
            FROM {table}
            WHERE volume IS NOT NULL
            GROUP BY {group_cols}
        ),
        daily_values AS (
            SELECT
                f.{group_cols},
                SUM(f.{value_col} * ABS(f.volume - av.avg_volume) * f.close) /
                    NULLIF(SUM(ABS(f.volume - av.avg_volume) * f.close), 0) as raw_value,
                COUNT(*) as stock_count,
                av.avg_volume
            FROM {table} f
            JOIN avg_volumes av USING ({group_cols})
            WHERE f.{value_col} IS NOT NULL
              AND f.volume IS NOT NULL
              AND f.close IS NOT NULL
              AND f.close > 0
            GROUP BY f.{group_cols}, av.avg_volume
        ),
        base_value AS (
            SELECT MIN({group_cols}) as base_date, raw_value as base_raw_value
            FROM daily_values
            LIMIT 1
        )
        SELECT
            dv.{group_cols},
            (dv.raw_value / bv.base_raw_value) * 100 as weighted_value,
            dv.stock_count,
            dv.avg_volume
        FROM daily_values dv
        CROSS JOIN base_value bv
        ORDER BY dv.{group_cols}
        """

    def _sql_volatility_weighted(self, table: str, value_col: str, group_cols: str) -> str:
        """Generate SQL for inverse volatility weighting (risk-adjusted), normalized to base 100."""
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
        ),
        daily_values AS (
            SELECT
                {group_cols},
                SUM({value_col} / NULLIF(daily_range, 0)) /
                    NULLIF(SUM(1.0 / NULLIF(daily_range, 0)), 0) as raw_value,
                COUNT(*) as stock_count,
                AVG(daily_range) as avg_volatility
            FROM daily_ranges
            WHERE daily_range > 0.001  -- Avoid division by zero
            GROUP BY {group_cols}
        ),
        base_value AS (
            SELECT MIN({group_cols}) as base_date, raw_value as base_raw_value
            FROM daily_values
            LIMIT 1
        )
        SELECT
            dv.{group_cols},
            (dv.raw_value / bv.base_raw_value) * 100 as weighted_value,
            dv.stock_count,
            dv.avg_volatility
        FROM daily_values dv
        CROSS JOIN base_value bv
        ORDER BY dv.{group_cols}
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
