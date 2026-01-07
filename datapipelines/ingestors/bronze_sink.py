"""
Bronze Sink - Writes data to Bronze layer using Delta Lake format.

All Bronze data is stored as Delta Lake tables for:
- ACID transactions
- Time travel / version history
- Schema evolution
- Efficient upserts
- Automatic compaction (OPTIMIZE + VACUUM)
"""
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class BronzeSink:
    """
    Writes DataFrames to Bronze layer as Delta Lake tables.

    Delta Lake is the default storage format (v2.0+).
    """

    def __init__(self, storage_cfg: Dict[str, Any]):
        self.cfg = storage_cfg
        self._format = self.cfg.get("defaults", {}).get("format", "delta")

    def _table_cfg(self, table: str) -> Dict:
        return self.cfg["tables"][table]

    def _path(self, table: str, partitions: Optional[Dict] = None) -> Path:
        base = Path(self.cfg["roots"]["bronze"]) / self._table_cfg(table)["rel"]
        for k, v in (partitions or {}).items():
            base = base / f"{k}={v}"
        return base

    def _is_delta_table(self, path: Path) -> bool:
        """Check if path is a Delta Lake table."""
        return (path / "_delta_log").exists()

    def exists(self, table: str, partitions: Optional[Dict] = None) -> bool:
        path = self._path(table, partitions)
        if self._format == "delta":
            return self._is_delta_table(path)
        return path.exists()

    def write_if_missing(self, table: str, partitions: Optional[Dict], df) -> bool:
        path = self._path(table, partitions)
        if self.exists(table, partitions):
            return False
        path.mkdir(parents=True, exist_ok=True)
        self._write_delta(df, str(path), mode="overwrite")
        return True

    def append_immutable(
        self,
        df,
        table: str,
        key_columns: List[str],
        partitions: Optional[List[str]] = None,
        date_column: str = "trade_date"
    ) -> str:
        """
        Append immutable time-series data efficiently using INSERT-only semantics.

        RECOMMENDED for historical data that doesn't change (e.g., stock prices).
        Much faster than upsert() because it avoids expensive MERGE operations.

        Strategy:
        - First write: Create table with partitions
        - Subsequent writes: APPEND new data, skip existing date ranges
        - Uses Delta Lake's partition pruning for efficiency

        Args:
            df: Spark DataFrame to append
            table: Table name (must exist in storage config)
            key_columns: Columns that uniquely identify a row (for dedup within batch)
            partitions: List of partition column names (should include date-based partition)
            date_column: Column containing the date (for checking existing data)

        Returns:
            Path to table

        Example:
            # Daily price updates - only inserts new dates
            sink.append_immutable(
                df, "securities_prices_daily",
                key_columns=["ticker", "trade_date"],
                partitions=["asset_type", "year", "month"],
                date_column="trade_date"
            )
        """
        from datetime import date
        from delta.tables import DeltaTable
        from pyspark.sql.functions import lit, row_number, col, max as spark_max, min as spark_min
        from pyspark.sql.window import Window

        # Get base path for table
        table_cfg = self._table_cfg(table)
        base_path = Path(self.cfg["roots"]["bronze"]) / table_cfg["rel"]

        # Deduplicate source DataFrame by key columns
        if key_columns:
            window = Window.partitionBy(*key_columns).orderBy(lit(1))
            df = (df
                  .withColumn("_row_num", row_number().over(window))
                  .filter("_row_num = 1")
                  .drop("_row_num"))

        # Check if table exists
        is_existing = self._is_delta_table(base_path)

        if not is_existing:
            # First write - create the table
            base_path.parent.mkdir(parents=True, exist_ok=True)
            writer = df.write.format("delta").mode("overwrite")
            if partitions:
                writer = writer.partitionBy(*partitions)
            writer.save(str(base_path))
        else:
            # Table exists - filter out dates that already exist
            spark = df.sparkSession

            # Read existing schema and align new data to match types
            existing_df = spark.read.format("delta").load(str(base_path))
            existing_schema = {f.name: f.dataType for f in existing_df.schema.fields}

            # Get existing table's partition columns - must match when appending
            from delta.tables import DeltaTable
            dt = DeltaTable.forPath(spark, str(base_path))
            existing_partitions = dt.detail().select("partitionColumns").collect()[0][0]
            if existing_partitions != (partitions or []):
                logger.warning(
                    f"Partition mismatch: config has {partitions}, table has {existing_partitions}. "
                    f"Using existing table partitions to avoid Delta error."
                )
                partitions = existing_partitions if existing_partitions else None

            # Cast new df columns to match existing schema types to avoid merge conflicts
            for field in df.schema.fields:
                if field.name in existing_schema:
                    existing_type = existing_schema[field.name]
                    if field.dataType != existing_type:
                        logger.info(f"Casting {field.name} from {field.dataType} to {existing_type}")
                        df = df.withColumn(field.name, col(field.name).cast(existing_type))

            # Get date range of incoming data
            date_stats = df.agg(
                spark_min(col(date_column)).alias("min_date"),
                spark_max(col(date_column)).alias("max_date")
            ).collect()[0]

            if date_stats["min_date"] is None:
                # Empty DataFrame, nothing to append
                return str(base_path)

            # Read existing data for this date range to find what's new
            existing_for_dedup = (existing_df
                          .filter(
                              (col(date_column) >= date_stats["min_date"]) &
                              (col(date_column) <= date_stats["max_date"])
                          )
                          .select(*key_columns)
                          .distinct())

            # Anti-join to find only new records
            new_records = df.join(existing_for_dedup, on=key_columns, how="left_anti")

            new_count = new_records.count()
            if new_count == 0:
                # All data already exists
                return str(base_path)

            # Append only new records
            writer = (new_records.write
                     .format("delta")
                     .mode("append")
                     .option("mergeSchema", "true"))

            if partitions:
                writer = writer.partitionBy(*partitions)

            writer.save(str(base_path))

        return str(base_path)

    def upsert(
        self,
        df,
        table: str,
        key_columns: List[str],
        partitions: Optional[List[str]] = None,
        update_existing: bool = True
    ) -> str:
        """
        Upsert DataFrame into bronze table using Read-Merge-Overwrite strategy.

        This approach reads existing data, merges with new data, deduplicates,
        and overwrites the table. This prevents file accumulation that occurs
        with Delta MERGE operations.

        Strategy:
        - First write: Simple overwrite
        - Subsequent writes: Read existing → Union → Deduplicate → Overwrite
        - Result: Consistent file count (controlled by coalesce)

        Args:
            df: Spark DataFrame to upsert
            table: Table name (must exist in storage config)
            key_columns: Columns that uniquely identify a row
            partitions: List of partition column names for new tables
            update_existing: If True, new data overwrites existing for same key.
                            If False, existing data is preserved.

        Returns:
            Path to table
        """
        from datetime import date
        from pyspark.sql.functions import lit, row_number, col
        from pyspark.sql.window import Window

        # Get base path for table
        table_cfg = self._table_cfg(table)
        base_path = Path(self.cfg["roots"]["bronze"]) / table_cfg["rel"]

        spark = df.sparkSession

        # Check if table exists
        is_existing = self._is_delta_table(base_path)

        if not is_existing:
            # First write - create the table
            base_path.parent.mkdir(parents=True, exist_ok=True)

            # Deduplicate new data
            if key_columns:
                window = Window.partitionBy(*key_columns).orderBy(lit(1))
                df = (df
                      .withColumn("_row_num", row_number().over(window))
                      .filter("_row_num = 1")
                      .drop("_row_num"))

            # Coalesce to minimize file count
            df = df.coalesce(4)

            writer = df.write.format("delta").mode("overwrite")
            if partitions:
                writer = writer.partitionBy(*partitions)
            writer.save(str(base_path))
        else:
            # Read-Merge-Overwrite: Read existing, union with new, deduplicate, overwrite
            existing_df = spark.read.format("delta").load(str(base_path))

            # Get existing table's partition columns - must match when writing
            from delta.tables import DeltaTable
            dt = DeltaTable.forPath(spark, str(base_path))
            existing_partitions = dt.detail().select("partitionColumns").collect()[0][0]
            if existing_partitions != (partitions or []):
                logger.warning(
                    f"Partition mismatch in upsert: config has {partitions}, table has {existing_partitions}. "
                    f"Using existing table partitions."
                )
                partitions = existing_partitions if existing_partitions else None

            # Cast new df columns to match existing schema to avoid type conflicts
            # (e.g., shares_outstanding: string vs long)
            existing_schema = {f.name: f.dataType for f in existing_df.schema.fields}
            for field in df.schema.fields:
                if field.name in existing_schema:
                    existing_type = existing_schema[field.name]
                    if field.dataType != existing_type:
                        # Cast to existing type to maintain schema consistency
                        df = df.withColumn(field.name, col(field.name).cast(existing_type))

            # Add a source marker to handle update_existing logic
            existing_df = existing_df.withColumn("_source", lit(0))  # 0 = existing
            new_df = df.withColumn("_source", lit(1))  # 1 = new

            # Union all data
            combined = existing_df.unionByName(new_df, allowMissingColumns=True)

            # Deduplicate by key columns
            # If update_existing=True, prefer new data (source=1)
            # If update_existing=False, prefer existing data (source=0)
            if key_columns:
                order_col = col("_source").desc() if update_existing else col("_source").asc()
                window = Window.partitionBy(*key_columns).orderBy(order_col)
                combined = (combined
                           .withColumn("_row_num", row_number().over(window))
                           .filter("_row_num = 1")
                           .drop("_row_num", "_source"))
            else:
                combined = combined.drop("_source")

            # Coalesce to minimize file count
            combined = combined.coalesce(4)

            # Overwrite the entire table
            # Note: We cast new data columns to match existing schema types (above)
            # so we don't need overwriteSchema. mergeSchema handles new columns.
            # overwriteSchema is NOT compatible with dynamic partition overwrite mode.
            writer = combined.write.format("delta").mode("overwrite")
            if partitions:
                writer = writer.partitionBy(*partitions)
            writer = writer.option("mergeSchema", "true")
            writer.save(str(base_path))

            logger.info(f"Upsert complete for {table}: read-merge-overwrite strategy")

        # Clean up old files immediately
        self._cleanup_old_files(base_path)

        return str(base_path)

    def _cleanup_old_files(self, table_path: Path) -> None:
        """Delete old parquet files not in current Delta version."""
        try:
            from deltalake import DeltaTable
            dt = DeltaTable(str(table_path))
            current_files = set(dt.files())

            # Delete any parquet file not in current version
            for f in table_path.rglob('*.parquet'):
                if '_delta_log' in str(f):
                    continue
                rel_path = str(f.relative_to(table_path))
                if rel_path not in current_files:
                    f.unlink()
        except ImportError:
            pass  # No deltalake package, skip cleanup
        except Exception as e:
            logger.debug(f"Cleanup skipped: {e}")

    def smart_write(self, df, table: str) -> str:
        """
        Universal write method that picks strategy based on storage.json config.

        Reads write_strategy, key_columns, partitions, and date_column from config
        and calls the appropriate method (upsert or append_immutable).

        This is the RECOMMENDED method for all writes - it ensures the correct
        strategy is used based on data characteristics defined in config.

        Config fields in storage.json tables:
            write_strategy: "upsert" | "append"
                - "upsert": For reference data that changes (uses read-merge-overwrite)
                - "append": For immutable time-series (uses append_immutable, O(1) memory)
            key_columns: List of columns that uniquely identify a row
            partitions: List of partition columns
            date_column: Column containing date (required for append strategy)

        Args:
            df: Spark DataFrame to write
            table: Table name (must exist in storage config with write config)

        Returns:
            Path to written table

        Example:
            # Config in storage.json:
            # "securities_prices_daily": {
            #     "write_strategy": "append",
            #     "key_columns": ["ticker", "trade_date"],
            #     "date_column": "trade_date",
            #     "partitions": ["year"]
            # }

            sink.smart_write(prices_df, "securities_prices_daily")
        """
        table_cfg = self._table_cfg(table)

        # Get write configuration
        strategy = table_cfg.get("write_strategy", "upsert")  # Default to upsert for safety
        key_columns = table_cfg.get("key_columns", [])
        partitions = table_cfg.get("partitions", []) or None
        date_column = table_cfg.get("date_column")

        if strategy == "append":
            if not date_column:
                logger.warning(f"Table {table} has append strategy but no date_column - falling back to upsert")
                return self.upsert(df, table, key_columns=key_columns, partitions=partitions)

            return self.append_immutable(
                df,
                table,
                key_columns=key_columns,
                partitions=partitions,
                date_column=date_column
            )
        else:
            # Default: upsert
            return self.upsert(df, table, key_columns=key_columns, partitions=partitions)

    def write(self, df, table: str, partitions: Optional[List[str]] = None, mode: str = "overwrite") -> str:
        """
        Write DataFrame to bronze table as Delta Lake format.

        Args:
            df: Spark DataFrame to write
            table: Table name (must exist in storage config)
            partitions: List of partition column names (e.g., ["asset_type", "year"])
            mode: Write mode - "overwrite", "append", or "merge"
                  Use "append" when writing in batches to avoid overwriting previous data.

        Returns:
            Path to written table
        """
        from datetime import date

        # Validate mode
        valid_modes = ("overwrite", "append", "merge")
        if mode not in valid_modes:
            raise ValueError(f"Invalid write mode: {mode}. Must be one of {valid_modes}.")

        # Get base path for table
        table_cfg = self._table_cfg(table)
        base_path = Path(self.cfg["roots"]["bronze"]) / table_cfg["rel"]

        # Write as Delta Lake
        self._write_delta(df, str(base_path), mode=mode, partitions=partitions)

        return str(base_path)

    def _write_delta(
        self,
        df,
        path: str,
        mode: str = "overwrite",
        partitions: Optional[List[str]] = None
    ):
        """
        Write DataFrame as Delta Lake table.

        Args:
            df: Spark DataFrame
            path: Output path
            mode: Write mode (overwrite, append, merge)
            partitions: Partition columns
        """
        from pathlib import Path as PathLib

        writer = df.write.format("delta").mode(mode)

        if partitions:
            writer = writer.partitionBy(*partitions)

        # Check if table exists and handle schema evolution
        is_existing_delta = (PathLib(path) / "_delta_log").exists()

        # Enable schema evolution (mergeSchema) to allow adding new columns
        # Note: overwriteSchema is NOT compatible with partitionOverwriteMode=dynamic
        # so we only use mergeSchema which handles most schema evolution cases
        if is_existing_delta or mode == "append":
            writer = writer.option("mergeSchema", "true")

        writer.save(path)

