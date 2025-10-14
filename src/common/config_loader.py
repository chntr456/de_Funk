from __future__ import annotations
import json

class ConfigLoader:
    def __init__(self, path: str):
        with open(path, "r", encoding="utf-8") as f:
            self.cfg = json.load(f)

    def injected(self) -> dict:
        cfg = json.loads(json.dumps(self.cfg))  # deep copy
        api_key = cfg.get("credentials", {}).get("api_key", "")
        if "headers" in cfg:
            cfg["headers"] = {
                k: (v.replace("${API_KEY}", api_key) if isinstance(v, str) else v)
                for k, v in cfg["headers"].items()
            }
        return cfg
