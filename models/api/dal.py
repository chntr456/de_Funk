from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional
from pyspark.sql import DataFrame, SparkSession

@dataclass(frozen=True)
class StorageRouter:
    storage_cfg: Dict[str, Any]
    repo_root: Optional[Path] = None  # Optional repo root for absolute paths

    def bronze_path(self, logical_table: str) -> str:
        """
        Resolve bronze table path.

        First checks storage.json tables dict for explicit mapping.
        If not found, constructs path from normalized table name (dots → slashes).

        Examples:
            - 'calendar_seed' → looks up in tables → 'storage/bronze/seeds/calendar'
            - 'alpha_vantage.listing_status' → constructs → 'storage/bronze/alpha_vantage/listing_status'
        """
        root = self.storage_cfg["roots"]["bronze"].rstrip("/")

        # First try explicit table mapping in storage.json
        tables = self.storage_cfg.get("tables", {})
        if logical_table in tables and isinstance(tables[logical_table], dict):
            rel = tables[logical_table]["rel"]
        else:
            # Construct path from normalized table name (dots → slashes)
            # e.g., 'alpha_vantage.listing_status' → 'alpha_vantage/listing_status'
            rel = logical_table.replace(".", "/")

        path = f"{root}/{rel}"

        # Convert to absolute path if repo_root provided
        if self.repo_root:
            return str(self.repo_root / path)
        return path

    def silver_path(self, logical_rel: str) -> str:
        root = self.storage_cfg["roots"]["silver"].rstrip("/")
        path = f"{root}/{logical_rel}"

        # Convert to absolute path if repo_root provided
        if self.repo_root:
            return str(self.repo_root / path)
        return path

class BronzeTable:
    """
    Reads Bronze layer tables (default: Delta Lake format).
    """

    def __init__(self, spark: SparkSession, router: StorageRouter, logical_table: str):
        self.spark = spark
        self.router = router
        self.logical_table = logical_table

    @property
    def path(self) -> str:
        return self.router.bronze_path(self.logical_table)

    def _is_delta_table(self, path: str) -> bool:
        """Check if path contains a Delta table."""
        delta_log = Path(path) / "_delta_log"
        return delta_log.exists()

    def read(self, merge_schema: bool = True) -> DataFrame:
        """
        Read bronze table (auto-detects Delta Lake or Parquet).

        Args:
            merge_schema: If True, merges schemas across partitions to handle schema evolution.
                         This prevents 'CANNOT_DETERMINE_TYPE' errors when different partitions
                         have slightly different schemas.

        Returns:
            DataFrame with data from all partitions
        """
        path = self.path

        # Auto-detect Delta Lake tables
        if self._is_delta_table(path):
            return (
                self.spark.read
                .format("delta")
                .option("mergeSchema", str(merge_schema).lower())
                .load(path)
            )

        # Fallback to Parquet for legacy tables
        return (
            self.spark.read
            .option("mergeSchema", str(merge_schema).lower())
            .parquet(path)
        )

class SilverPath:
    """
    Represents a materialized silver 'path' (fact/view) built by the model builder.

    Reads from Delta Lake format by default, with fallback to Parquet for legacy tables.
    If you keep tables in-memory, you can inject a DataFrame via `override_df`.
    """

    def __init__(self, spark: SparkSession, router: StorageRouter, logical_rel: str):
        self.spark = spark
        self.router = router
        self.logical_rel = logical_rel
        self._override_df: Optional[DataFrame] = None

    @property
    def path(self) -> str:
        return self.router.silver_path(self.logical_rel)

    def _is_delta_table(self, path: str) -> bool:
        """Check if path contains a Delta table."""
        delta_log = Path(path) / "_delta_log"
        return delta_log.exists()

    def read(self) -> DataFrame:
        """Read silver table (auto-detects Delta Lake or Parquet)."""
        if self._override_df is not None:
            return self._override_df

        path = self.path

        # Auto-detect Delta Lake tables
        if self._is_delta_table(path):
            return self.spark.read.format("delta").load(path)

        # Fallback to Parquet for legacy tables
        return self.spark.read.parquet(path)

    def set_df(self, df: DataFrame):
        self._override_df = df
