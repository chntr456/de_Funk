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
        writer = df.write.format("delta").mode(mode)

        if partitions:
            writer = writer.partitionBy(*partitions)

        # Enable schema evolution for append mode
        if mode == "append":
            writer = writer.option("mergeSchema", "true")

        writer.save(path)
