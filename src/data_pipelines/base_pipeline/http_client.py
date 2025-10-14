from __future__ import annotations
import time, json, urllib.parse, urllib.request
from typing import Any, Dict, Optional

class HttpClient:
    def __init__(self, base_urls: dict[str,str], headers: Optional[Dict[str,str]] = None, rate_limit_per_sec: float = 4.0):
        self.base_urls = {k:v.rstrip("/") for k,v in base_urls.items()}
        self.headers = headers or {}
        self.min_interval = 1.0 / max(rate_limit_per_sec, 0.0001)
        self._last_ts = 0.0

    def request(self, base_key: str, path: str, query: Optional[Dict[str,Any]] = None, method: str = "GET") -> dict:
        self._respect_rate_limit()
        url = f"{self.base_urls[base_key]}/{path.lstrip('/')}"
        if query:
            q = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k,v in query.items())
            url = f"{url}?{q}"
        req = urllib.request.Request(url, headers=self.headers, method=method)
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _respect_rate_limit(self):
        now = time.time()
        if (delta := now - self._last_ts) < self.min_interval:
            time.sleep(self.min_interval - delta)
        self._last_ts = time.time()
