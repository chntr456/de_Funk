from __future__ import annotations
import shutil
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.context import RepoContext
from orchestration.orchestrator import Orchestrator

DATE_FROM = "2024-01-01"
DATE_TO   = "2024-01-05"

def clear_storage(storage_cfg: dict) -> dict:
    """Delete bronze/silver roots from the storage config, then recreate them."""
    roots = storage_cfg.get("roots", {})
    for layer, path_str in roots.items():
        p = Path(path_str)
        if p.exists():
            print(f"⚠️  Clearing {layer.upper()} layer: {p}")
            shutil.rmtree(p)
        p.mkdir(parents=True, exist_ok=True)
    return storage_cfg

#def main():
# Build a context (repo paths, configs, spark) and pass it to the orchestrator
ctx = RepoContext.from_repo_root()
# Optional: start clean each run
# ctx.storage = clear_storage(ctx.storage)

o = Orchestrator(ctx)                 # <-- pass the ctx here
final_df = o.run_company_pipeline(
    date_from=DATE_FROM,
    date_to=DATE_TO,
)

# show a sample from the canonical path
final_df.show(10, truncate=False)

final_df.show