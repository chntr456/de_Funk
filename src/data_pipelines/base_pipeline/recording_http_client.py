from __future__ import annotations
import json, hashlib, os
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlencode
from .http_client import HttpClient

def _stable_query_string(query: Optional[Dict[str, Any]]) -> str:
    if not query: return ""
    return urlencode([(k, str(query[k])) for k in sorted(query.keys())])

def _make_key(base_key: str, path: str, query: Optional[Dict[str, Any]]) -> str:
    return hashlib.sha1(f"{base_key}::{path}::{_stable_query_string(query)}".encode("utf-8")).hexdigest()

class RecordingHttpClient(HttpClient):
    def __init__(self, base_urls: dict[str, str], headers: Optional[Dict[str, str]] = None,
                 rate_limit_per_sec: float = 0.0834, cassette_dir: str | os.PathLike = "tests/fixtures/polygon_cassettes",
                 mode: str = "replay_or_record", **kwargs):
        super().__init__(base_urls, headers, rate_limit_per_sec, **kwargs)
        self.cassette_dir = Path(cassette_dir); self.cassette_dir.mkdir(parents=True, exist_ok=True)
        self.mode = mode

    def request(self, base_key: str, path: str, query: Optional[Dict[str, Any]] = None,
                method: str = "GET", timeout: float = 60.0) -> dict:
        key = _make_key(base_key, path, query)
        fpath = self.cassette_dir / f"{key}.json"
        if self.mode in ("replay","replay_or_record") and fpath.exists():
            return json.loads(fpath.read_text(encoding="utf-8"))
        if self.mode == "replay":
            raise FileNotFoundError(f"Cassette not found: {fpath}")
        payload = super().request(base_key, path, query, method, timeout)
        tmp = fpath.with_suffix(".json.tmp"); tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8"); os.replace(tmp, fpath)
        return payload
