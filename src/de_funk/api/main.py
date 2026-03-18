"""
de_funk FastAPI application.

Startup sequence:
1. Load domain model registry (resolver)
2. Initialize DuckDB query executor
3. Mount routers: /api/health, /api/domains, /api/dimensions, /api/query

Run with:
    python -m scripts.serve.run_api
or:
    uvicorn de_funk.api.main:app --host 0.0.0.0 --port 8765
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from de_funk.api.bronze_resolver import BronzeResolver
from de_funk.api.executor import QueryEngine
from de_funk.api.handlers import build_registry
from de_funk.api.resolver import FieldResolver
from de_funk.api.routers import bronze, dimensions, domains, health, query
from de_funk.config.logging import get_logger, setup_logging
from de_funk.utils.repo import get_repo_root

setup_logging()
logger = get_logger(__name__)


def _load_storage_config(repo_root: Path) -> tuple[dict[str, Path], dict]:
    """
    Read configs/storage.json.

    Returns:
        overrides   — {domain → absolute_path} map for QueryExecutor
        api_cfg     — raw api: section (limits, etc.)
    """
    overrides: dict[str, Path] = {}
    api_cfg: dict = {}
    storage_cfg = repo_root / "configs" / "storage.json"
    if not storage_cfg.exists():
        return overrides, api_cfg

    try:
        cfg = json.loads(storage_cfg.read_text())
        api_cfg = cfg.get("api", {})

        roots = cfg.get("roots", {})
        default_silver = roots.get("silver", "storage/silver")
        base = Path(default_silver) if Path(default_silver).is_absolute() else repo_root / default_silver

        for key, raw_path in roots.items():
            if not key.endswith("_silver"):
                continue
            domain = key[: -len("_silver")]
            p = Path(raw_path) if Path(raw_path).is_absolute() else repo_root / raw_path
            overrides[domain] = p
            logger.debug(f"Storage override: {domain} → {p}")

        # domain_roots: explicit {domain_name: path} overrides for dotted domains
        # whose storage path doesn't match the default {silver}/{domain.replace('.','/')}
        for domain_name, raw_path in cfg.get("domain_roots", {}).items():
            p = Path(raw_path) if Path(raw_path).is_absolute() else base / raw_path
            overrides[domain_name] = p
            logger.debug(f"Domain root override: {domain_name} → {p}")

        overrides["_default"] = base
    except Exception as e:
        logger.warning(f"Could not parse storage.json: {e}")

    return overrides, api_cfg


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app(storage_root: Path | None = None, domains_root: Path | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    repo_root = get_repo_root()
    storage_overrides, api_cfg = _load_storage_config(repo_root)
    _storage_root = storage_root or storage_overrides.get("_default") or (repo_root / "storage" / "silver")
    _domains_root = domains_root or (repo_root / "domains")

    app = FastAPI(
        title="de_funk API",
        description="Query backend for the de_funk Obsidian plugin",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    # CORS — allow Obsidian app protocol + local subnets
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "app://obsidian.md",
            "capacitor://localhost",
            "http://localhost",
            "http://localhost:8765",
            "http://127.0.0.1:8765",
        ],
        allow_origin_regex=r"http://192\.168\.\d+\.\d+.*",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount routers
    app.include_router(health.router, prefix="/api")
    app.include_router(domains.router, prefix="/api")
    app.include_router(dimensions.router, prefix="/api")
    app.include_router(query.router, prefix="/api")
    app.include_router(bronze.router, prefix="/api")

    @app.on_event("startup")
    async def startup() -> None:
        logger.info(f"Starting de_funk API — default silver={_storage_root}")
        app.state.resolver = FieldResolver(
            domains_root=_domains_root,
            storage_root=_storage_root,
            domain_overrides=storage_overrides,
        )
        required_api_keys = ("duckdb_memory_limit", "max_sql_rows", "max_dimension_values", "max_response_mb")
        missing = [k for k in required_api_keys if k not in api_cfg]
        if missing:
            raise RuntimeError(
                f"Missing required keys in configs/storage.json [api]: {missing}. "
                "Add them before starting the API."
            )
        engine_kwargs = dict(
            storage_root=_storage_root,
            memory_limit=api_cfg["duckdb_memory_limit"],
            max_sql_rows=int(api_cfg["max_sql_rows"]),
            max_dimension_values=int(api_cfg["max_dimension_values"]),
            max_response_mb=float(api_cfg["max_response_mb"]),
        )
        # Handler registry for /api/query dispatch — creates one shared DuckDB connection
        app.state.registry = build_registry(**engine_kwargs)
        # Dimension endpoint reuses the same shared connection from the registry
        app.state.executor = app.state.registry.shared_engine

        # Bronze resolver — reads endpoint markdown, resolves provider.endpoint.field refs
        bronze_root_raw = storage_overrides.get("_bronze")
        if bronze_root_raw is None:
            # Read bronze root from storage.json roots section
            storage_cfg = repo_root / "configs" / "storage.json"
            try:
                cfg = json.loads(storage_cfg.read_text())
                raw = cfg.get("roots", {}).get("bronze", "storage/bronze")
                bronze_root_raw = Path(raw) if Path(raw).is_absolute() else repo_root / raw
            except Exception:
                bronze_root_raw = repo_root / "storage" / "bronze"
        app.state.bronze_resolver = BronzeResolver(
            data_sources_root=repo_root / "data_sources",
            bronze_root=Path(bronze_root_raw),
        )
        logger.info("de_funk API ready")

    return app


# Module-level app instance for uvicorn
app = create_app()
