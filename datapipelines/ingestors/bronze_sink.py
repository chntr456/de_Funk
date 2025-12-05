"""
Bronze Sink - Writes data to Bronze layer using Delta Lake format.

All Bronze data is stored as Delta Lake tables for:
- ACID transactions
- Time travel / version history
- Schema evolution
- Efficient upserts
"""
from pathlib import Path
from typing import Dict, List, Optional, Any


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

        This is the preferred method for incremental ingestion:
        - Updates existing rows where key columns match (if update_existing=True)
        - Inserts new rows where key columns don't match
        - Preserves data from previous runs

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
