from __future__ import annotations
import time, json, random, urllib.parse, urllib.request
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from .key_pool import ApiKeyPool

def _render_headers(template: Dict[str, str], api_key: str) -> Dict[str, str]:
    out = {}
    for k, v in template.items():
        out[k] = v.replace("${API_KEY}", api_key) if isinstance(v, str) else v
    return out

class HttpClient:
    def __init__(
        self,
        base_urls: dict[str, str],
        headers: Optional[Dict[str, str]] = None,
        rate_limit_per_sec: float = 0.0834,
        api_key_pool: Optional[ApiKeyPool] = None,
        max_retries: int = 6,
        backoff_base: float = 0.75,
        backoff_factor: float = 2.0,
        backoff_jitter: float = 0.25
    ):
        self.base_urls = {k: v.rstrip("/") for k, v in base_urls.items()}
        self.header_template = headers or {}
        self.global_min_interval = 1.0 / max(rate_limit_per_sec, 0.0001)
        self._last_ts = 0.0
        self.pool = api_key_pool or ApiKeyPool(keys=[""], cooldown_seconds=60.0)
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.backoff_factor = backoff_factor
        self.backoff_jitter = backoff_jitter

    def request(self, base_key: str, path: str, query: Optional[Dict[str, Any]] = None,
                method: str = "GET", timeout: float = 60.0) -> dict:
        url = f"{self.base_urls[base_key]}/{path.lstrip('/')}"
        if query:
            q = "&".join(f"{urllib.parse.quote(str(k))}={urllib.parse.quote(str(v))}" for k, v in sorted(query.items()))
            url = f"{url}?{q}"

        attempt = 0
        while True:
            api_key, key_idx = self.pool.acquire()
            headers = _render_headers(self.header_template, api_key)

            self._respect_global_rate()
            req = urllib.request.Request(url, headers=headers, method=method)
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))

            except HTTPError as e:
                status = e.code
                if status == 429:
                    ra = self._parse_retry_after(e.headers.get("Retry-After")) or 120.0
                    self.pool.penalize(key_idx, ra)
                    sleep_for = self._next_backoff(attempt)
                elif status in (401, 403):
                    self.pool.penalize(key_idx, 600.0)
                    sleep_for = self._next_backoff(attempt)
                elif 500 <= status < 600:
                    sleep_for = self._next_backoff(attempt)
                else:
                    raise
                attempt += 1
                if attempt > self.max_retries: raise
                time.sleep(sleep_for)

            except (URLError, TimeoutError, ConnectionError):
                attempt += 1
                if attempt > self.max_retries: raise
                time.sleep(self._next_backoff(attempt))

    def _respect_global_rate(self):
        now = time.time()
        delta = now - self._last_ts
        if delta < self.global_min_interval:
            time.sleep(self.global_min_interval - delta)
        self._last_ts = time.time()

    def _next_backoff(self, attempt: int) -> float:
        base = self.backoff_base * (self.backoff_factor ** max(attempt - 1, 0))
        jitter = random.uniform(-self.backoff_jitter, self.backoff_jitter)
        return max(0.1, base + jitter)

    @staticmethod
    def _parse_retry_after(value: Optional[str]) -> Optional[float]:
        if not value: return None
        try: return max(0.0, float(value.strip()))
        except Exception: return None
