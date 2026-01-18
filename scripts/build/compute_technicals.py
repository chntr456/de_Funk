#!/usr/bin/env python3
"""
CLI wrapper for computing technical indicators.

This is a thin CLI wrapper around the stocks domain technicals module.
The actual implementation lives in models/domains/securities/stocks/technicals.py.

Usage:
    python -m scripts.build.compute_technicals
    python -m scripts.build.compute_technicals --storage-path /shared/storage
    python -m scripts.build.compute_technicals --dry-run
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Setup imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from config.logging import setup_logging, get_logger

logger = get_logger(__name__)


def main():
    """CLI entry point for compute_technicals."""
    parser = argparse.ArgumentParser(
        description="Compute technical indicators using native Spark windowing"
    )
    parser.add_argument(
        "--storage-path",
        type=str,
        default="/shared/storage",
        help="Storage root path"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without executing"
    )
    args = parser.parse_args()

    setup_logging()

    # Import from the domain module
    from models.domains.securities.stocks.technicals import compute_technicals

    storage_path = Path(args.storage_path)

    print("=" * 70)
    print("Computing Technical Indicators (Native Spark)")
    print("=" * 70)
    print()
    print(f"Storage: {storage_path}")
    print()

    rows = compute_technicals(storage_path, dry_run=args.dry_run)

    if rows > 0:
        print()
        print("=" * 70)
        print(f"Complete: {rows:,} rows processed")
        print("=" * 70)


if __name__ == "__main__":
    main()
