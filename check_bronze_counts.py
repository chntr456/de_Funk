#!/usr/bin/env python3
"""Check row counts in bronze tables"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from orchestration.common.spark_session import get_spark
from models.api.session import ModelSession
from core.context import RepoContext

# Initialize
ctx = RepoContext.from_repo_root()
ms = ModelSession(ctx.spark, ctx.repo, ctx.storage)

# Check bronze tables
print("Bronze Table Row Counts:")
print("=" * 50)

tables = ["ref_all_tickers", "ref_ticker", "prices_daily", "exchanges"]

for table in tables:
    try:
        df = ms.bronze(table).read()
        count = df.count()
        print(f"{table:20} {count:,} rows")
    except Exception as e:
        print(f"{table:20} ERROR: {e}")

print("=" * 50)

# Show sample of ref_ticker
print("\nSample from ref_ticker:")
try:
    df = ms.bronze("ref_ticker").read()
    df.show(10, truncate=False)
except Exception as e:
    print(f"ERROR: {e}")
