"""
Optimized Parquet Loader for DuckDB Analytics.

This loader produces large, sorted, consolidated files ideal for DuckDB queries,
replacing the old approach which created 100+ tiny files.

Key optimizations:
- Coalesce to 1-5 files (vs 200 default partitions)
- Sort by query columns (enables zone maps)
- No nested partitioning (flat structure)
- Snappy compression
"""

from __future__ import annotations
from pathlib import Path
from typing import Any, List, Optional
import json
import datetime as dt


class ParquetLoader:
    """
    Optimized Parquet writer for analytical queries.

    Designed for DuckDB performance:
    - Minimizes file count (1-5 files per table)
    - Sorts by query columns for predicate pushdown
    - Simple flat directory structure
    - No unnecessary partitioning
    """

    def __init__(self, root="storage"):
        """
        Initialize loader.

        Args:
            root: Storage root directory (full path to model's silver directory)
        """
        self.root = Path(root)
        (self.root / "_meta" / "manifests").mkdir(parents=True, exist_ok=True)

    def _manifest(self, name: str, out_path: Path, rows: int):
        """Write manifest file with metadata."""
        ts = dt.datetime.utcnow().strftime("%Y-%m-%dT%H%MZ")
        mf = {
            "dataset": name,
            "path": str(out_path),
            "rows": rows,
            "written_at": ts
        }
        manifest_file = self.root / "_meta" / "manifests" / f"{ts}__{name.replace('/', '_')}.json"
        manifest_file.write_text(json.dumps(mf, indent=2))

    def _write(
        self,
        rel_path: str,
        df: Any,
        sort_by: Optional[List[str]] = None,
        num_files: int = 1,
        row_count: Optional[int] = None
    ):
        """
        Write DataFrame to Parquet with DuckDB optimizations.

        Args:
            rel_path: Relative path (e.g., "dims/dim_equity" or "facts/fact_equity_prices")
            df: Spark DataFrame
            sort_by: Columns to sort by for query performance (enables zone maps)
            num_files: Number of files to write (default: 1 for <1GB data)
            row_count: Pre-computed row count (avoids counting after transformations)
        """
        out = self.root / rel_path
        out.parent.mkdir(parents=True, exist_ok=True)

        # Cache row count if not provided (do this BEFORE expensive operations)
        if row_count is None:
            print(f"  Counting rows...")
            row_count = df.count()

        # Sort by query columns for zone maps and predicate pushdown
        if sort_by:
            print(f"  Sorting by: {', '.join(sort_by)}")
            df = df.sortWithinPartitions(*sort_by)

        # Coalesce to minimize file count
        # For datasets <10M rows, use single file
        # For larger datasets, use 2-5 files
        print(f"  Coalescing to {num_files} file(s)")
        df = df.coalesce(num_files)

        # Write with snappy compression
        (df.write
         .mode("overwrite")
         .option("compression", "snappy")
         .parquet(str(out)))

        # Write manifest
        self._manifest(rel_path, out, row_count)

        print(f"  ✓ Written to: {out}")

    def write_dim(self, rel_path: str, df: Any, row_count: Optional[int] = None):
        """
        Write dimension table.

        Dimensions are always single files (typically <1 MB).

        Args:
            rel_path: Relative path from model root (e.g., "dims/dim_equity")
            df: Spark DataFrame
            row_count: Optional pre-computed row count
        """
        self._write(rel_path, df, num_files=1, row_count=row_count)

    def write_fact(self, rel_path: str, df: Any, sort_by: List[str], row_count: Optional[int] = None):
        """
        Write fact table sorted by query columns.

        Facts are consolidated and sorted for optimal query performance.

        Args:
            rel_path: Relative path from model root (e.g., "facts/fact_equity_prices")
            df: Spark DataFrame
            sort_by: Columns to sort by (e.g., ["trade_date", "ticker"])
            row_count: Optional pre-computed row count (recommended for large datasets)
        """
        # Count rows if not provided (do this BEFORE transformations)
        if row_count is None:
            print(f"  Counting rows...")
            row_count = df.count()

        # Determine optimal file count based on size
        # For typical datasets (<10M rows), use single file
        # For very large datasets (>10M rows), use 2-5 files
        if row_count < 10_000_000:
            num_files = 1
        elif row_count < 50_000_000:
            num_files = 2
        else:
            num_files = 5

        self._write(rel_path, df, sort_by=sort_by, num_files=num_files, row_count=row_count)
