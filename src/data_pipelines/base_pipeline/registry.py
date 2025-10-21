from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Tuple, Union
from pathlib import Path
from src.common.config_loader import ConfigLoader

@dataclass
class Endpoint:
    name: str
    base: str
    method: str
    path_template: str
    required_params: list[str]
    default_query: dict[str, Any]
    response_key: str
    default_path_params: dict[str, Any]

class BaseRegistry:
    """
    Provider-agnostic endpoint registry.
    - Loads endpoints from JSON/YAML config
    - Renders (path, query) with simple string formatting
    - NO provider-specific quirks, NO symbol/ticker shims
    """
    def __init__(self, cfg_source: Union[str, Path, dict]):
        cfg = ConfigLoader(cfg_source).injected()
        self.headers: Dict[str, str]   = cfg.get("headers", {})
        self.base_urls: Dict[str, str] = {k: v.rstrip("/") for k, v in (cfg.get("base_urls", {}) or {}).items()}
        self.rate_limit: float         = cfg.get("rate_limit_per_sec", 0.0834)

        self.endpoints: Dict[str, Endpoint] = {
            name: Endpoint(
                name=name,
                base=e["base"],
                method=e.get("method", "GET"),
                path_template=e["path_template"],
                required_params=e.get("required_params", []),
                default_query=e.get("default_query", {}),
                response_key=e.get("response_key", "results"),
                default_path_params=e.get("default_path_params", {})
            )
            for name, e in (cfg.get("endpoints", {}) or {}).items()
        }

    def render(self, ep_name: str, **params) -> Tuple[Endpoint, str, dict]:
        if ep_name not in self.endpoints:
            raise KeyError(f"Endpoint not found: {ep_name}")
        ep = self.endpoints[ep_name]

        # 1) merge defaults + user params
        merged = {**ep.default_path_params, **params}

        # 2) validate required params
        missing = [k for k in ep.required_params if k not in merged]
        if missing:
            raise ValueError(f"{ep_name}: missing required params {missing}")

        # 3) render path
        path = ep.path_template.format(**merged)

        # 4) build query (defaults, then user overrides via 'query' dict)
        query = {}
        for k, v in (ep.default_query or {}).items():
            query[k] = v.format(**merged) if isinstance(v, str) else v
        user_q = params.get("query") or {}
        query.update(user_q)

        return ep, path, query
