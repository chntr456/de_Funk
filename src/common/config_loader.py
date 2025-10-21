from __future__ import annotations
import json
from pathlib import Path
from typing import Union

class ConfigLoader:
    def __init__(self, src: Union[str, Path, dict]):
        if isinstance(src, dict):
            self.cfg = src
        else:
            path = Path(src)
            with open(path, "r", encoding="utf-8") as f:
                self.cfg = json.load(f)

    def injected(self) -> dict:
        # leave ${API_KEY} placeholders intact; HttpClient renders at request time
        return self.cfg

