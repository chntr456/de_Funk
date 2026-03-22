"""
Session abstractions — scoped contexts for each pipeline path.

Sessions are short-lived (per task/request). They hold the configs
needed for their specific path and delegate operations to the Engine.

    BuildSession: reads Bronze+Silver, writes Silver
    QuerySession: reads Silver, writes nothing
    IngestSession: reads APIs, writes Raw+Bronze
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

from de_funk.config.logging import get_logger

logger = get_logger(__name__)


class Session(ABC):
    """Abstract base for all sessions."""

    def __init__(self, engine, storage_config=None, **kwargs):
        self.engine = engine
        self._storage_config = storage_config or {}

    def raw_path(self, provider: str, endpoint: str) -> str:
        """Resolve raw storage path."""
        roots = self._storage_config.get("roots", {}) if isinstance(self._storage_config, dict) else {}
        raw_root = roots.get("raw", "storage/raw")
        return f"{raw_root}/{provider}/{endpoint}"

    def bronze_path(self, provider: str, endpoint: str) -> str:
        """Resolve bronze storage path."""
        roots = self._storage_config.get("roots", {}) if isinstance(self._storage_config, dict) else {}
        bronze_root = roots.get("bronze", "storage/bronze")
        return f"{bronze_root}/{provider}/{endpoint}"

    def silver_path(self, domain: str, model: str = "") -> str:
        """Resolve silver storage path."""
        roots = self._storage_config.get("roots", {}) if isinstance(self._storage_config, dict) else {}
        silver_root = roots.get("silver", "storage/silver")
        if model:
            return f"{silver_root}/{domain}/{model}"
        return f"{silver_root}/{domain}"

    @abstractmethod
    def close(self):
        """Clean up session resources."""
        pass


class BuildSession(Session):
    """Session for building Silver tables from Bronze + Silver dependencies."""

    def __init__(self, engine, models: dict, graph=None, storage_config=None, **kwargs):
        super().__init__(engine, storage_config)
        self.models = models
        self.graph = graph
        self._kwargs = kwargs

    def get_model(self, model_name: str) -> dict:
        """Get a domain model config by name."""
        if model_name not in self.models:
            raise KeyError(f"Model '{model_name}' not found. Available: {list(self.models.keys())}")
        return self.models[model_name]

    def get_dependencies(self, model_name: str) -> list[str]:
        """Get dependency list for a model."""
        model = self.get_model(model_name)
        return model.get("depends_on", []) if isinstance(model, dict) else getattr(model, 'depends_on', [])

    def build(self, model_name: str) -> dict:
        """Build a single model. Returns BuildResult-like dict."""
        logger.info(f"BuildSession.build({model_name})")
        # This will be wired to BaseModelBuilder in Phase 2
        return {"model_name": model_name, "success": True}

    def build_all(self) -> list[dict]:
        """Build all models in dependency order."""
        results = []
        for model_name in self.models:
            results.append(self.build(model_name))
        return results

    def close(self):
        pass


class QuerySession(Session):
    """Session for querying Silver tables (read-only)."""

    def __init__(self, engine, models: dict, resolver=None, storage_config=None, **kwargs):
        super().__init__(engine, storage_config)
        self.models = models
        self.resolver = resolver

    def resolve(self, ref_str: str):
        """Resolve a domain.field reference to a ResolvedField."""
        if self.resolver is None:
            raise RuntimeError("QuerySession has no resolver — was it created with one?")
        return self.resolver.resolve(ref_str)

    def find_join_path(self, src: str, dst: str) -> list:
        """Find join path between two tables."""
        if self.resolver is None:
            return []
        return self.resolver.find_join_path(src, dst)

    def close(self):
        pass


class IngestSession(Session):
    """Session for ingesting data from external APIs."""

    def __init__(self, engine, providers: dict, endpoints: dict, run_config=None, storage_config=None, **kwargs):
        super().__init__(engine, storage_config)
        self.providers = providers
        self.endpoints = endpoints
        self.run_config = run_config or {}

    def get_provider(self, provider_id: str) -> dict:
        """Get provider config by ID."""
        if provider_id not in self.providers:
            raise KeyError(f"Provider '{provider_id}' not found. Available: {list(self.providers.keys())}")
        return self.providers[provider_id]

    def get_endpoint(self, provider_id: str, endpoint_id: str) -> dict:
        """Get endpoint config by provider + endpoint ID."""
        key = f"{provider_id}.{endpoint_id}"
        if key not in self.endpoints:
            raise KeyError(f"Endpoint '{key}' not found.")
        return self.endpoints[key]

    def close(self):
        pass
