from __future__ import annotations
from dataclasses import dataclass
from typing import Any
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

class PolygonRegistry:
    def __init__(self, cfg_path: str):
        cfg = ConfigLoader(cfg_path).injected()
        self.headers = cfg["headers"]
        self.base_urls = cfg["base_urls"]
        self.rate_limit = cfg.get("rate_limit_per_sec", 4.0)
        self.endpoints: dict[str, Endpoint] = {}
        for name, e in cfg["endpoints"].items():
            self.endpoints[name] = Endpoint(
                name=name,
                base=e["base"],
                method=e.get("method","GET"),
                path_template=e["path_template"],
                required_params=e.get("required_params", []),
                default_query=e.get("default_query", {}),
                response_key=e.get("response_key","results"),
                default_path_params=e.get("default_path_params", {})
            )

    def render(self, ep_name: str, **params) -> tuple[Endpoint, str, dict]:
        ep = self.endpoints[ep_name]
        merged = {**ep.default_path_params, **params}
        missing = [k for k in ep.required_params if k not in merged]
        if missing:
            raise ValueError(f"{ep_name}: missing {missing}")
        path = ep.path_template.format(**merged)
        query = {k: (str(v).format(**merged) if isinstance(v,str) else v) for k,v in ep.default_query.items()}
        query.update(params.get("query") or {})
        return ep, path, query
