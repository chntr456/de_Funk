from pathlib import Path

class BronzeSink:
    def __init__(self, storage_cfg):
        self.cfg = storage_cfg

    def _table_cfg(self, table):
        return self.cfg["tables"][table]

    def _path(self, table, partitions):
        base = Path(self.cfg["roots"]["bronze"]) / self._table_cfg(table)["rel"]
        for k, v in (partitions or {}).items():
            base = base / f"{k}={v}"
        return base

    def exists(self, table, partitions):
        return self._path(table, partitions).exists()

    def write_if_missing(self, table, partitions, df):
        path = self._path(table, partitions)
        if path.exists():
            return False
        path.mkdir(parents=True, exist_ok=True)
        df.write.mode("overwrite").parquet(str(path))
        return True

    def write(self, df, table, partitions=None):
        """
        Write DataFrame to bronze table with partitioning.

        Args:
            df: Spark DataFrame to write
            table: Table name (must exist in storage config)
            partitions: List of partition column names (e.g., ["snapshot_dt", "asset_type"])

        Returns:
            Path to written table
        """
        from datetime import date

        # Get base path for table
        table_cfg = self._table_cfg(table)
        base_path = Path(self.cfg["roots"]["bronze"]) / table_cfg["rel"]

        # Add snapshot_dt if not already in dataframe
        if partitions and "snapshot_dt" in partitions:
            from pyspark.sql.functions import lit
            if "snapshot_dt" not in df.columns:
                df = df.withColumn("snapshot_dt", lit(date.today().isoformat()))

        # Write with partitioning
        if partitions:
            df.write.mode("overwrite").partitionBy(*partitions).parquet(str(base_path))
        else:
            df.write.mode("overwrite").parquet(str(base_path))

        return str(base_path)
