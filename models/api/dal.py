from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, TYPE_CHECKING

# Conditional PySpark import for environments without Spark
try:
    from pyspark.sql import DataFrame, SparkSession
    PYSPARK_AVAILABLE = True
except ImportError:
    PYSPARK_AVAILABLE = False
    DataFrame = Any  # type: ignore
    SparkSession = Any  # type: ignore


@dataclass(frozen=True)
class StorageRouter:
    """
    Resolves table paths from config-style references.

    Supports:
        - Config refs: "bronze.alpha_vantage.listing_status" → parses layer + path
        - Direct paths: "stocks/dims/dim_stock" with explicit layer
        - Absolute paths: "/shared/storage/..." passed through
    """
    storage_cfg: Dict[str, Any]
    repo_root: Optional[Path] = None

    def parse_table_ref(self, table_ref: str) -> Tuple[str, str]:
        """
        Parse a table reference into (layer, path).

        Args:
            table_ref: Config-style reference like "bronze.alpha_vantage.listing_status"
                      or "silver.stocks/dims/dim_stock"

        Returns:
            Tuple of (layer, relative_path)

        Examples:
            "bronze.alpha_vantage.listing_status" → ("bronze", "alpha_vantage/listing_status")
            "silver.stocks/dims/dim_stock" → ("silver", "stocks/dims/dim_stock")
        """
        if table_ref.startswith("bronze."):
            return "bronze", table_ref[7:].replace(".", "/")
        elif table_ref.startswith("silver."):
            return "silver", table_ref[7:]
        else:
            # Default to silver if no prefix (backward compat)
            return "silver", table_ref

    def resolve(self, table_ref: str) -> str:
        """
        Resolve a table reference to a filesystem path.

        Args:
            table_ref: Config-style reference like "bronze.alpha_vantage.listing_status"

        Returns:
            Absolute or relative filesystem path
        """
        # Absolute paths pass through
        if table_ref.startswith("/"):
            return table_ref

        layer, rel_path = self.parse_table_ref(table_ref)
        root = self.storage_cfg["roots"][layer].rstrip("/")

        # For bronze, check explicit table mapping in storage.json
        if layer == "bronze":
            tables = self.storage_cfg.get("tables", {})
            # rel_path might be like "alpha_vantage/listing_status"
            # Check if there's a mapping for it
            table_key = rel_path.replace("/", ".")
            if table_key in tables and isinstance(tables[table_key], dict):
                rel_path = tables[table_key]["rel"]

        path = f"{root}/{rel_path}"

        if self.repo_root:
            return str(self.repo_root / path)
        return path

    # Legacy methods for backward compatibility
    def bronze_path(self, logical_table: str) -> str:
        return self.resolve(f"bronze.{logical_table}")

    def silver_path(self, logical_rel: str) -> str:
        return self.resolve(f"silver.{logical_rel}")


class Table:
    """
    Unified table reader.

    Takes a config-style table reference like "bronze.alpha_vantage.listing_status"
    or "silver.stocks/dims/dim_stock" and resolves it to a filesystem path.

    Auto-detects Delta Lake vs Parquet format.
    Supports schema merging and in-memory DataFrame override.

    Usage:
        # From graph config "from:" field
        table = Table(spark, router, "bronze.alpha_vantage.listing_status")
        df = table.read()

        # Or with direct path
        table = Table(spark, router, "silver.stocks/dims/dim_stock")
        df = table.read()
    """

    def __init__(
        self,
        spark: SparkSession,
        router: StorageRouter,
        table_ref: str,
    ):
        self.spark = spark
        self.router = router
        self.table_ref = table_ref
        self._override_df: Optional[DataFrame] = None

    @property
    def path(self) -> str:
        return self.router.resolve(self.table_ref)

    def _is_delta_table(self, path: str) -> bool:
        """Check if path contains a Delta table."""
        delta_log = Path(path) / "_delta_log"
        return delta_log.exists()

    def _ensure_active_session(self) -> None:
        """
        Ensure Spark session is active for Delta Lake 4.x.

        Delta Lake calls SparkSession.active() internally which requires
        the session in thread-local storage. Must be called right before
        any Delta read operation.

        Sets both active session (thread-local) and default session (global).
        """
        try:
            jvm = self.spark._jvm
            jss = self.spark._jsparkSession
            # Set as active (thread-local)
            jvm.org.apache.spark.sql.SparkSession.setActiveSession(jss)
            # Also set as default (global fallback)
            jvm.org.apache.spark.sql.SparkSession.setDefaultSession(jss)
        except Exception:
            pass  # Best effort - some environments may not support this

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
            # CRITICAL: Ensure session is active right before Delta read
            self._ensure_active_session()
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
