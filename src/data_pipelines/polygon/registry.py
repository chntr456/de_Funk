from __future__ import annotations
from typing import Tuple, Union
from pathlib import Path
from src.data_pipelines.base_pipeline.registry import BaseRegistry, Endpoint

class PolygonRegistry(BaseRegistry):
    """
    Polygon-specific registry.
    - Keeps base behavior
    - Optionally enforces Polygon-wide query defaults (adjust here if desired)
    - No symbol/ticker renaming; everything remains ticker-centric
    """
    def __init__(self, cfg_source: Union[str, Path, dict]):
        super().__init__(cfg_source)

    def render(self, ep_name: str, **params) -> Tuple[Endpoint, str, dict]:
        ep, path, query = super().render(ep_name, **params)

        # Example of provider-wide defaults (opt-in):
        # if "adjusted" not in query:
        #     query["adjusted"] = "true"
        # if "limit" not in query:
        #     query["limit"] = 5000

        return ep, path, query
