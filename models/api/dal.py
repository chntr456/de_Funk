from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional, Literal
from pyspark.sql import DataFrame, SparkSession

Layer = Literal["bronze", "silver"]


@dataclass(frozen=True)
class StorageRouter:
    storage_cfg: Dict[str, Any]
    repo_root: Optional[Path] = None  # Optional repo root for absolute paths

    def resolve_path(self, layer: Layer, logical_name: str) -> str:
        """
        Resolve table path for any layer.

        Args:
            layer: "bronze" or "silver"
            logical_name: Table identifier (e.g., 'alpha_vantage.listing_status' or 'stocks/dims/dim_stock')

        Returns:
            Absolute or relative path to the table
        """
        root = self.storage_cfg["roots"][layer].rstrip("/")

        if layer == "bronze":
            # Bronze: check explicit table mapping first, then normalize dots→slashes
            tables = self.storage_cfg.get("tables", {})
            if logical_name in tables and isinstance(tables[logical_name], dict):
                rel = tables[logical_name]["rel"]
            else:
                rel = logical_name.replace(".", "/")
        else:
            # Silver: direct path
            rel = logical_name

        path = f"{root}/{rel}"

        if self.repo_root:
            return str(self.repo_root / path)
        return path

    # Legacy methods for backward compatibility
    def bronze_path(self, logical_table: str) -> str:
        return self.resolve_path("bronze", logical_table)

    def silver_path(self, logical_rel: str) -> str:
        return self.resolve_path("silver", logical_rel)


class Table:
    """
    Unified table reader for Bronze and Silver layers.

    Auto-detects Delta Lake vs Parquet format.
    Supports schema merging and in-memory DataFrame override.
    """

    def __init__(
        self,
        spark: SparkSession,
        router: StorageRouter,
        logical_name: str,
        layer: Layer = "silver"
    ):
        self.spark = spark
        self.router = router
        self.logical_name = logical_name
        self.layer = layer
        self._override_df: Optional[DataFrame] = None

    @property
    def path(self) -> str:
        return self.router.resolve_path(self.layer, self.logical_name)

    def _is_delta_table(self, path: str) -> bool:
        """Check if path contains a Delta table."""
        delta_log = Path(path) / "_delta_log"
        return delta_log.exists()

    def read(self, merge_schema: bool = True) -> DataFrame:
        """
        Read table (auto-detects Delta Lake or Parquet).

        Args:
            merge_schema: If True, merges schemas across partitions.
                         Useful for Bronze tables with schema evolution.

        Returns:
            DataFrame with table data
        """
        if self._override_df is not None:
            return self._override_df

        path = self.path

        if self._is_delta_table(path):
            return (
                self.spark.read
                .format("delta")
                .option("mergeSchema", str(merge_schema).lower())
                .load(path)
            )

        return (
            self.spark.read
            .option("mergeSchema", str(merge_schema).lower())
            .parquet(path)
        )

    def set_df(self, df: DataFrame):
        """Override with in-memory DataFrame (useful for testing)."""
        self._override_df = df


# Backward-compatible aliases
class BronzeTable(Table):
    """Reads Bronze layer tables. Alias for Table(layer='bronze')."""

    def __init__(self, spark: SparkSession, router: StorageRouter, logical_table: str):
        super().__init__(spark, router, logical_table, layer="bronze")


class SilverPath(Table):
    """Reads Silver layer tables. Alias for Table(layer='silver')."""

    def __init__(self, spark: SparkSession, router: StorageRouter, logical_rel: str):
        super().__init__(spark, router, logical_rel, layer="silver")
