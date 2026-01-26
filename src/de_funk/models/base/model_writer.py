"""
Model Writer for BaseModel.

Handles persistence of model tables to storage:
- write_tables: Write all dimensions and facts to Silver layer

This module is used by BaseModel via composition.

Storage format is Delta Lake for:
- ACID transactions
- Schema evolution
- Efficient upserts

Note: Time travel/versioning is DISABLED by default (auto_vacuum: true).
Set `storage.auto_vacuum: false` in domain markdown to enable versioning.
"""

from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

# Type alias for DataFrame (can be Spark or DuckDB)
DataFrame = Any

# Default storage format
DEFAULT_FORMAT = "delta"

# Default auto_vacuum setting - True means NO time travel (clean up old files immediately)
DEFAULT_AUTO_VACUUM = True


class ModelWriter:
    """
    Handles writing model tables to persistent storage.

    Uses Delta Lake format for ACID transactions.
    Auto-vacuum is enabled by default to disable time travel and save storage.

    To enable time travel/versioning, set in domain markdown:
        storage:
          auto_vacuum: false
    """

    def __init__(self, model):
        """
        Initialize model writer.

        Args:
            model: BaseModel instance
        """
        self.model = model
        self._quiet = False
        self._spark = None  # Lazy-loaded for vacuum operations

    def _print(self, msg: str):
        """Print message if not in quiet mode."""
        if not self._quiet:
            print(msg)

    @property
    def auto_vacuum(self) -> bool:
        """
        Check if auto_vacuum is enabled for this model.

        Reads from domain markdown: storage.auto_vacuum
        Default: True (vacuum after writes, no time travel)
        """
        return self.model.model_cfg.get("storage", {}).get("auto_vacuum", DEFAULT_AUTO_VACUUM)

    @property
    def model_name(self) -> str:
        return self.model.model_name

    @property
    def storage_cfg(self) -> Dict:
        return self.model.storage_cfg

    def _vacuum_table(self, path: str, format: str) -> bool:
        """
        Vacuum a Delta table to remove old files (disable time travel).

        Args:
            path: Path to the Delta table
            format: Storage format (only vacuums if 'delta')

        Returns:
            True if vacuum succeeded, False otherwise
        """
        if format != "delta" or not self.auto_vacuum:
            return False

        try:
            from delta import DeltaTable

            # Get or create Spark session
            if self._spark is None:
                from orchestration.common.spark_session import get_spark
                self._spark = get_spark("ModelWriter")

            # Disable retention check to allow vacuum(0)
            self._spark.conf.set(
                "spark.databricks.delta.retentionDurationCheck.enabled", "false"
            )

            dt = DeltaTable.forPath(self._spark, path)
            dt.vacuum(0)  # Remove ALL old files
            logger.debug(f"Vacuumed: {path}")
            return True

        except ImportError:
            logger.debug("Delta Lake not available, skipping vacuum")
            return False
        except Exception as e:
            logger.warning(f"Vacuum failed for {path}: {e}")
            return False

    def write_tables(
        self,
        output_root: Optional[str] = None,
        format: Optional[str] = None,
        mode: str = "overwrite",
        partition_by: Optional[Dict[str, List[str]]] = None,
        quiet: bool = False
    ):
        """
        Write all model tables to storage.

        This is the standard way to persist a model's Silver layer.
        Uses Delta Lake format by default.

        Args:
            output_root: Root path for output (defaults to storage_cfg silver root for this model)
            format: Output format (default: "delta" from storage_cfg or DEFAULT_FORMAT)
            mode: Write mode (overwrite, append, etc.)
            partition_by: Optional dict of table_name -> partition_columns
            quiet: Suppress verbose output (for clean progress display)

        Returns:
            Dictionary with write statistics

        Example:
            model = CompanyModel(...)
            stats = model.write_tables(
                output_root="storage/silver/company",
                partition_by={"fact_prices": ["trade_date"]}
            )
        """
        self._quiet = quiet
        # Get format from model's YAML config first, then global storage config, then default
        if format is None:
            # Priority: model.yaml storage.format > storage.json defaults.format > DEFAULT_FORMAT
            model_format = self.model.model_cfg.get("storage", {}).get("format")
            storage_default = self.storage_cfg.get("defaults", {}).get("format")
            format = model_format or storage_default or DEFAULT_FORMAT

            logger.debug(
                f"Format resolution: model_cfg={model_format}, "
                f"storage_default={storage_default}, resolved={format}"
            )
        # Ensure model is built
        self.model.ensure_built()

        # Determine output root
        if output_root is None:
            # Use storage config to find model's silver root
            model_silver_key = f"{self.model_name}_silver"
            if model_silver_key in self.storage_cfg.get('roots', {}):
                output_root = self.storage_cfg['roots'][model_silver_key]
            else:
                # Fallback to generic silver root
                output_root = f"{self.storage_cfg.get('roots', {}).get('silver', 'storage/silver')}/{self.model_name}"

        self._print(f"\n{'=' * 70}")
        self._print(f"Writing {self.model_name.upper()} Model to Silver Layer")
        self._print(f"{'=' * 70}")
        self._print(f"Output root: {output_root}")
        self._print(f"Format: {format}")
        self._print(f"Mode: {mode}")

        stats = {
            'dimensions': {},
            'facts': {},
            'total_rows': 0,
            'total_tables': 0
        }

        stats = self._write_tables(output_root, format, mode, partition_by, stats)

        self._print_summary(stats)
        return stats

    def _write_tables(
        self,
        output_root: str,
        format: str,
        mode: str,
        partition_by: Optional[Dict[str, List[str]]],
        stats: Dict
    ) -> Dict:
        """
        Write tables using Spark writer.

        Args:
            output_root: Root path for output
            format: Output format (delta)
            mode: Write mode (overwrite, append, etc.)
            partition_by: Optional partitioning config
            stats: Statistics dictionary to update

        Returns:
            Updated statistics
        """
        import time

        # Write dimensions
        self._print(f"\nWriting Dimensions:")
        for name, df in self.model._dims.items():
            path = f"{output_root}/dims/{name}"
            self._print(f"  Writing {name} to {path}...")
            start_time = time.time()

            row_count = df.count()
            writer = df.write.mode(mode).format(format)
            if format == "delta":
                writer = writer.option("overwriteSchema", "true")
            if partition_by and name in partition_by:
                writer = writer.partitionBy(partition_by[name])

            writer.save(path)

            # Auto-vacuum to remove old files (if enabled)
            if self.auto_vacuum and format == "delta":
                self._vacuum_table(path, format)

            elapsed = time.time() - start_time
            stats['dimensions'][name] = {
                'rows': row_count,
                'files': 1,
                'time': elapsed
            }
            stats['total_rows'] += row_count
            stats['total_tables'] += 1
            vacuum_status = " [vacuumed]" if self.auto_vacuum and format == "delta" else ""
            self._print(f"    ✓ {row_count:,} rows ({elapsed:.1f}s){vacuum_status}")

        # Write facts
        self._print(f"\nWriting Facts:")
        for name, df in self.model._facts.items():
            path = f"{output_root}/facts/{name}"
            self._print(f"  Writing {name} to {path}...")
            start_time = time.time()

            # Count rows first for progress tracking
            row_count = df.count()
            self._print(f"    Rows: {row_count:,}")

            # For large datasets, provide guidance on expected time
            if row_count > 1_000_000:
                est_minutes = row_count / 2_000_000  # ~2M rows/min estimate
                self._print(f"    Estimated time: {est_minutes:.1f} min (large dataset)")

            writer = df.write.mode(mode).format(format)
            if format == "delta":
                writer = writer.option("overwriteSchema", "true")
            if partition_by and name in partition_by:
                writer = writer.partitionBy(partition_by[name])
                self._print(f"    Partitioning by: {partition_by[name]}")

            self._print(f"    Writing... (this may take a moment for large datasets)")
            writer.save(path)

            # Auto-vacuum to remove old files (if enabled)
            if self.auto_vacuum and format == "delta":
                self._print(f"    Vacuuming old versions...")
                self._vacuum_table(path, format)

            elapsed = time.time() - start_time
            # Estimate file count for Delta
            num_files = max(1, row_count // 2_000_000 + 1)
            stats['facts'][name] = {
                'rows': row_count,
                'files': num_files,
                'time': elapsed
            }
            stats['total_rows'] += row_count
            stats['total_tables'] += 1
            vacuum_status = " [vacuumed]" if self.auto_vacuum and format == "delta" else ""
            self._print(f"    ✓ Complete ({elapsed:.1f}s){vacuum_status}")

        return stats

    def _print_summary(self, stats: Dict):
        """Print write summary."""
        self._print(f"\n{'=' * 70}")
        self._print(f"✓ Silver Layer Write Complete")
        self._print(f"{'=' * 70}")
        self._print(f"Total tables written: {stats['total_tables']}")
        self._print(f"Total rows written: {stats['total_rows']:,}")

        # Handle both old format (int) and new format (dict with rows/files/time)
        def sum_rows(table_stats):
            total = 0
            for v in table_stats.values():
                if isinstance(v, dict):
                    total += v.get('rows', 0)
                else:
                    total += v
            return total

        dim_rows = sum_rows(stats['dimensions'])
        fact_rows = sum_rows(stats['facts'])
        self._print(f"  - Dimensions: {len(stats['dimensions'])} tables, {dim_rows:,} rows")
        self._print(f"  - Facts: {len(stats['facts'])} tables, {fact_rows:,} rows")
