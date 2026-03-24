#!/usr/bin/env python3
"""
Build Silver layer models via DeFunk.

Uses DeFunk.from_config() → BuildSession for all builds.
Discovers models from domains/models/, resolves dependencies,
and builds Silver tables from Bronze via Spark.

Usage:
    python -m scripts.build.build_models
    python -m scripts.build.build_models --models temporal securities.stocks
    python -m scripts.build.build_models --dry-run
"""
from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

import sys
import argparse
from pathlib import Path
from datetime import datetime, date, timedelta

_script_dir = Path(__file__).resolve().parent
_repo_root = _script_dir.parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from de_funk.utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

from de_funk.config.logging import setup_logging, get_logger
logger = get_logger(__name__)


def main():
    setup_logging()

    parser = argparse.ArgumentParser(
        description="Build Silver layer models",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python -m scripts.build.build_models
    python -m scripts.build.build_models --models temporal securities.stocks
    python -m scripts.build.build_models --models municipal.public_safety --skip-deps
    python -m scripts.build.build_models --dry-run
        """
    )
    parser.add_argument('--models', nargs='+', help='Models to build (default: all)')
    parser.add_argument('--dry-run', action='store_true', help='Show plan without building')
    parser.add_argument('--date-from', type=str, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--date-to', type=str, help='End date (YYYY-MM-DD)')
    parser.add_argument('--max-tickers', type=int, help='Max tickers to process')
    parser.add_argument('--storage-root', type=str, help='Custom storage root')
    parser.add_argument('--skip-deps', action='store_true', help='Skip dependency builds')
    parser.add_argument('--connection', type=str, default='spark', help='Backend (spark or duckdb)')
    args = parser.parse_args()

    try:
        from de_funk.app import DeFunk

        # Create DeFunk app
        app = DeFunk.from_config(str(_repo_root / "configs"), connection_type=args.connection)
        logger.info(f"DeFunk: {len(app.models)} models, backend={app.engine.backend}")

        # Create build session with CLI overrides
        session_kwargs = {
            "date_from": args.date_from or (date.today() - timedelta(days=365)).strftime("%Y-%m-%d"),
            "date_to": args.date_to or date.today().strftime("%Y-%m-%d"),
            "repo_root": str(_repo_root),
        }
        if args.max_tickers:
            session_kwargs["max_tickers"] = args.max_tickers

        # Override storage root if specified
        if args.storage_root:
            storage = app.config.storage if hasattr(app.config, 'storage') else {}
            if isinstance(storage, dict):
                storage = dict(storage)
                storage['roots'] = dict(storage.get('roots', {}))
                storage['roots']['silver'] = args.storage_root
                app.config.storage = storage

        session = app.build_session(**session_kwargs)

        # Determine what to build
        if args.models:
            models_to_build = args.models
        else:
            models_to_build = list(app.models.keys())

        # Get build order
        if args.skip_deps:
            build_order = models_to_build
        else:
            build_order = session._topological_sort()
            # Filter to requested models + their deps
            if args.models:
                needed = set(args.models)
                for m in args.models:
                    deps = session.get_dependencies(m)
                    needed.update(deps)
                build_order = [m for m in build_order if m in needed]

        print(f"\n{'='*70}")
        print(f"  Building Silver Layer — {len(build_order)} models")
        print(f"  Order: {' → '.join(build_order)}")
        print(f"{'='*70}\n")

        if args.dry_run:
            for m in build_order:
                deps = session.get_dependencies(m)
                print(f"  {m}" + (f" (depends: {', '.join(deps)})" if deps else ""))
            print(f"\n[DRY RUN] No builds executed.")
            return

        # Build each model
        results = {}
        t0 = datetime.now()

        for model_name in build_order:
            result = session.build(model_name)
            results[model_name] = result
            if result.success:
                print(f"  ✓ {result}")
            else:
                print(f"  ✗ {result}")

        # Summary
        elapsed = (datetime.now() - t0).total_seconds()
        ok = sum(1 for r in results.values() if r.success)
        fail = len(results) - ok

        print(f"\n{'-'*70}")
        print(f"  Complete: {ok}/{len(results)} models ({elapsed:.1f}s)")
        if fail:
            print(f"  Failed: {fail}")
        print(f"{'-'*70}\n")

    except Exception as e:
        logger.error(f"Build failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
