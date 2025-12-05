"""
Model Writer for BaseModel.

Handles persistence of model tables to storage:
- write_tables: Write all dimensions and facts to Silver layer

This module is used by BaseModel via composition.

Default storage format is Delta Lake (v2.0+) for:
- ACID transactions
- Time travel / version history
- Schema evolution
- Efficient upserts
"""

from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

# Type alias for DataFrame (can be Spark or DuckDB)
DataFrame = Any

# Default storage format
DEFAULT_FORMAT = "delta"


class ModelWriter:
    """
    Handles writing model tables to persistent storage.

    Supports:
    - Delta Lake format (default - ACID transactions, time travel)
    - Parquet format (legacy fallback)
    - Partitioning and sorting
    """

    def __init__(self, model):
        """
        Initialize model writer.

        Args:
            model: BaseModel instance
        """
        self.model = model
        self._quiet = False

    def _print(self, msg: str):
        """Print message if not in quiet mode."""
        if not self._quiet:
            print(msg)

    @property
    def model_name(self) -> str:
        return self.model.model_name

    @property
    def storage_cfg(self) -> Dict:
        return self.model.storage_cfg

    def write_tables(
        self,
        output_root: Optional[str] = None,
        format: Optional[str] = None,
        mode: str = "overwrite",
        use_optimized_writer: bool = False,
        partition_by: Optional[Dict[str, List[str]]] = None,
        quiet: bool = False
    ):
        """
        Write all model tables to storage.

        This is the standard way to persist a model's Silver layer.
        Default format is Delta Lake (v2.0+).

        Args:
            output_root: Root path for output (defaults to storage_cfg silver root for this model)
            format: Output format (default: "delta" from storage_cfg or DEFAULT_FORMAT)
            mode: Write mode (overwrite, append, etc.)
            use_optimized_writer: Use ParquetLoader for parquet format (legacy)
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
        # Get format from storage config or use default
        if format is None:
            format = self.storage_cfg.get("defaults", {}).get("format", DEFAULT_FORMAT)
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
        self._print(f"Optimized writer: {use_optimized_writer}")

        stats = {
            'dimensions': {},
            'facts': {},
            'total_rows': 0,
            'total_tables': 0
        }

        # Use optimized ParquetLoader if requested and format is parquet
        if use_optimized_writer and format == "parquet":
            stats = self._write_with_parquet_loader(output_root, partition_by, stats)
        else:
            stats = self._write_with_spark_writer(output_root, format, mode, partition_by, stats)

        self._print_summary(stats)
        return stats

    def _write_with_parquet_loader(
        self,
        output_root: str,
        partition_by: Optional[Dict[str, List[str]]],
        stats: Dict
    ) -> Dict:
        """
        Write tables using optimized ParquetLoader.

        Args:
            output_root: Root path for output
            partition_by: Optional partitioning config
            stats: Statistics dictionary to update

        Returns:
            Updated statistics
        """
        from models.base.parquet_loader import ParquetLoader
        import time
        loader = ParquetLoader(root=output_root, quiet=self._quiet)

        # Write dimensions
        self._print(f"\nWriting Dimensions:")
        for name, df in self.model._dims.items():
            self._print(f"  Writing {name}...")
            start_time = time.time()
            row_count = df.count()

            # ParquetLoader expects relative path from output_root
            rel_path = f"dims/{name}"
            loader.write_dim(rel_path, df, row_count=row_count)

            elapsed = time.time() - start_time
            stats['dimensions'][name] = {
                'rows': row_count,
                'files': 1,
                'time': elapsed
            }
            stats['total_rows'] += row_count
            stats['total_tables'] += 1
            self._print(f"    ✓ {row_count:,} rows ({elapsed:.1f}s)")

        # Write facts
        self._print(f"\nWriting Facts:")
        for name, df in self.model._facts.items():
            self._print(f"  Writing {name}...")
            start_time = time.time()
            # Count rows BEFORE optimizations (more memory-efficient)
            row_count = df.count()
            self._print(f"    Rows: {row_count:,}")

            # Determine sort columns for optimal query performance
            sort_by = partition_by.get(name, []) if partition_by else []
            if not sort_by:
                # Default: use common date/time columns if present
                sort_by = self._infer_sort_columns(df.columns)

            rel_path = f"facts/{name}"
            # Pass pre-computed row_count to avoid re-counting after sort/coalesce
            loader.write_fact(rel_path, df, sort_by=sort_by, row_count=row_count)

            elapsed = time.time() - start_time
            # Calculate file count (same logic as ParquetLoader)
            ROWS_PER_FILE = 2_000_000
            if row_count < ROWS_PER_FILE:
                num_files = 1
            else:
                num_files = min(20, max(2, (row_count + ROWS_PER_FILE - 1) // ROWS_PER_FILE))

            stats['facts'][name] = {
                'rows': row_count,
                'files': num_files,
                'time': elapsed
            }
            stats['total_rows'] += row_count
            stats['total_tables'] += 1

        return stats

    def _write_with_spark_writer(
        self,
        output_root: str,
        format: str,
        mode: str,
        partition_by: Optional[Dict[str, List[str]]],
        stats: Dict
    ) -> Dict:
        """
        Write tables using standard Spark writer.

        Args:
            output_root: Root path for output
            format: Output format (parquet, delta, etc.)
            mode: Write mode (overwrite, append, etc.)
            partition_by: Optional partitioning config
            stats: Statistics dictionary to update

        Returns:
            Updated statistics
        """
        import time
        self._print("\nUsing standard Spark writer...")

        # Write dimensions
        self._print(f"\nWriting Dimensions:")
        for name, df in self.model._dims.items():
            path = f"{output_root}/dims/{name}"
            self._print(f"  Writing {name} to {path}...")
            start_time = time.time()

            row_count = df.count()
            writer = df.write.mode(mode).format(format)
            if partition_by and name in partition_by:
                writer = writer.partitionBy(partition_by[name])

            writer.save(path)
            elapsed = time.time() - start_time
            stats['dimensions'][name] = {
                'rows': row_count,
                'files': 1,
                'time': elapsed
            }
            stats['total_rows'] += row_count
            stats['total_tables'] += 1
            self._print(f"    ✓ {row_count:,} rows ({elapsed:.1f}s)")

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
            if partition_by and name in partition_by:
                writer = writer.partitionBy(partition_by[name])
                self._print(f"    Partitioning by: {partition_by[name]}")

            self._print(f"    Writing... (this may take a moment for large datasets)")
            writer.save(path)

            elapsed = time.time() - start_time
            # Estimate file count for Delta/Parquet
            num_files = max(1, row_count // 2_000_000 + 1)
            stats['facts'][name] = {
                'rows': row_count,
                'files': num_files,
                'time': elapsed
            }
            stats['total_rows'] += row_count
            stats['total_tables'] += 1
            self._print(f"    ✓ Complete ({elapsed:.1f}s)")

        return stats

    def _infer_sort_columns(self, columns: List[str]) -> List[str]:
        """
        Infer sort columns based on common date/time column patterns.

        Args:
            columns: List of column names

        Returns:
            List of sort column names
        """
        sort_by = []
        for date_col in ['trade_date', 'date', 'publish_date', 'timestamp']:
            if date_col in columns:
                sort_by = [date_col]
                if 'ticker' in columns:
                    sort_by.append('ticker')
                elif 'symbol' in columns:
                    sort_by.append('symbol')
                break
        return sort_by

    def _print_summary(self, stats: Dict):
        """Print write summary."""
        self._print(f"\n{'=' * 70}")
        self._print(f"✓ Silver Layer Write Complete")
        self._print(f"{'=' * 70}")
        self._print(f"Total tables written: {stats['total_tables']}")
        self._print(f"Total rows written: {stats['total_rows']:,}")
        self._print(f"  - Dimensions: {len(stats['dimensions'])} tables, {sum(stats['dimensions'].values()):,} rows")
        self._print(f"  - Facts: {len(stats['facts'])} tables, {sum(stats['facts'].values()):,} rows")
