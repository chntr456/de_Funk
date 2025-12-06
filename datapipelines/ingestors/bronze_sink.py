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

            # Get date range of incoming data
            date_stats = df.agg(
                spark_min(col(date_column)).alias("min_date"),
                spark_max(col(date_column)).alias("max_date")
            ).collect()[0]

            if date_stats["min_date"] is None:
                # Empty DataFrame, nothing to append
                return str(base_path)

            # Read existing data for this date range to find what's new
            existing_df = (spark.read.format("delta")
                          .load(str(base_path))
                          .filter(
                              (col(date_column) >= date_stats["min_date"]) &
                              (col(date_column) <= date_stats["max_date"])
                          )
                          .select(*key_columns)
                          .distinct())

            # Anti-join to find only new records
            new_records = df.join(existing_df, on=key_columns, how="left_anti")

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
        Upsert (merge) DataFrame into bronze table using Delta Lake MERGE.

        NOTE: For immutable time-series data (prices), prefer append_immutable() instead.
        Use upsert() for:
        - Reference data that can change (company info, metadata)
        - Backfilling historical data for specific tickers
        - Data corrections

        Args:
            df: Spark DataFrame to upsert
            table: Table name (must exist in storage config)
            key_columns: Columns that uniquely identify a row (e.g., ["ticker"] or ["ticker", "trade_date"])
            partitions: List of partition column names for new tables
            update_existing: If True, update existing rows. If False, only insert new rows.
                            Use False for bulk listing data that shouldn't overwrite detailed OVERVIEW data.

        Returns:
            Path to table
        """
        from datetime import date
        from delta.tables import DeltaTable
        from pyspark.sql.functions import lit, row_number
        from pyspark.sql.window import Window

        # Get base path for table
        table_cfg = self._table_cfg(table)
        base_path = Path(self.cfg["roots"]["bronze"]) / table_cfg["rel"]

        # Add snapshot_dt if specified in partitions but not in dataframe
        if partitions and "snapshot_dt" in partitions:
            if "snapshot_dt" not in df.columns:
                df = df.withColumn("snapshot_dt", lit(date.today().isoformat()))

        # CRITICAL: Deduplicate source DataFrame by key columns before merge
        # This prevents "multiple source rows matching target row" errors
        # (e.g., GOOGL and GOOG both have the same CIK)
        if key_columns:
            # Use row_number to keep only first occurrence per key
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
            # Table exists - perform MERGE
            spark = df.sparkSession
            delta_table = DeltaTable.forPath(spark, str(base_path))

            # Build merge condition from key columns
            merge_condition = " AND ".join([f"target.{col} = source.{col}" for col in key_columns])

            # Perform merge based on update_existing flag
            if update_existing:
                # Full upsert: update existing + insert new
                (delta_table.alias("target")
                    .merge(df.alias("source"), merge_condition)
                    .whenMatchedUpdateAll()
                    .whenNotMatchedInsertAll()
                    .execute())
            else:
                # Insert-only: only add new rows, preserve existing data
                (delta_table.alias("target")
                    .merge(df.alias("source"), merge_condition)
                    .whenNotMatchedInsertAll()
                    .execute())

        return str(base_path)

    def write(self, df, table: str, partitions: Optional[List[str]] = None, mode: str = "overwrite") -> str:
        """
        Write DataFrame to bronze table as Delta Lake format.

        Args:
            df: Spark DataFrame to write
            table: Table name (must exist in storage config)
            partitions: List of partition column names (e.g., ["snapshot_dt", "asset_type"])
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

        # Add snapshot_dt if not already in dataframe
        if partitions and "snapshot_dt" in partitions:
            from pyspark.sql.functions import lit
            if "snapshot_dt" not in df.columns:
                df = df.withColumn("snapshot_dt", lit(date.today().isoformat()))

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

    def compact(
        self,
        table: str,
        vacuum: bool = True,
        target_file_size_mb: int = 128,
        retention_hours: int = 168
    ) -> dict:
        """
        Compact a Delta table using OPTIMIZE and optionally VACUUM.

        This reduces the number of small files by merging them into larger ones,
        improving read performance. Should be called after batch writes.

        Args:
            table: Table name (must exist in storage config)
            vacuum: If True, also remove old files (default: True)
            target_file_size_mb: Target size for compacted files (default: 128 MB)
            retention_hours: Hours to retain old files before vacuum (default: 168 = 7 days)

        Returns:
            Dictionary with compaction results:
            {
                'status': 'success' | 'skipped' | 'error',
                'files_before': int,
                'files_after': int,
                'files_removed': int,
                'error': str (if status == 'error')
            }
        """
        try:
            from deltalake import DeltaTable
        except ImportError:
            logger.warning("deltalake package not installed - skipping compaction")
            return {'status': 'skipped', 'reason': 'deltalake not installed'}

        # Get table path
        table_cfg = self._table_cfg(table)
        base_path = Path(self.cfg["roots"]["bronze"]) / table_cfg["rel"]

        if not self._is_delta_table(base_path):
            return {'status': 'skipped', 'reason': 'not a delta table'}

        try:
            dt = DeltaTable(str(base_path))

            # Count files before
            parquet_files_before = list(base_path.rglob('*.parquet'))
            files_before = len([f for f in parquet_files_before if '_delta_log' not in str(f)])

            # Skip if already well compacted (< 5 files or avg size > 50 MB)
            if files_before > 0:
                total_size = sum(f.stat().st_size for f in parquet_files_before if f.exists() and '_delta_log' not in str(f))
                avg_size_mb = total_size / files_before / (1024 * 1024)
                if files_before <= 4 and avg_size_mb >= 50:
                    logger.debug(f"Table {table} already well compacted ({files_before} files, {avg_size_mb:.1f} MB avg)")
                    return {'status': 'skipped', 'reason': 'already compacted', 'files': files_before}

            # Run OPTIMIZE (compact small files)
            logger.info(f"Compacting {table}: {files_before} files...")
            dt.optimize.compact()

            # Run VACUUM if requested (remove old files)
            if vacuum:
                logger.debug(f"Vacuuming {table} (retention: {retention_hours}h)...")
                dt.vacuum(
                    retention_hours=retention_hours,
                    enforce_retention_duration=True,
                    dry_run=False
                )

            # Count files after
            parquet_files_after = list(base_path.rglob('*.parquet'))
            files_after = len([f for f in parquet_files_after if '_delta_log' not in str(f)])

            logger.info(f"Compacted {table}: {files_before} → {files_after} files")

            return {
                'status': 'success',
                'files_before': files_before,
                'files_after': files_after,
                'files_removed': files_before - files_after
            }

        except Exception as e:
            logger.error(f"Compaction failed for {table}: {e}")
            return {'status': 'error', 'error': str(e)}

    def compact_all(self, vacuum: bool = True) -> dict:
        """
        Compact all Delta tables in the bronze layer.

        Args:
            vacuum: If True, also vacuum old files

        Returns:
            Dictionary with results for each table
        """
        bronze_root = Path(self.cfg["roots"]["bronze"])
        results = {}

        for table_name in self.cfg.get("tables", {}):
            table_cfg = self.cfg["tables"][table_name]
            table_path = bronze_root / table_cfg["rel"]

            if self._is_delta_table(table_path):
                results[table_name] = self.compact(table_name, vacuum=vacuum)

        return results
