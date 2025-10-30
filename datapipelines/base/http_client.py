import json, time, urllib.request, urllib.parse
from urllib.error import HTTPError, URLError
import math

class HttpClient:
    def __init__(self, base_urls, headers, rate_limit_per_sec, api_key_pool, safety_factor=0.9, max_retries=6):
        self.base_urls = base_urls
        self.headers = headers
        self.configured_rps = float(rate_limit_per_sec or 0.0834)
        self.api_key_pool = api_key_pool
        self.safety = float(safety_factor)
        self.max_retries = int(max_retries)
        self._last_ts = 0.0

    def _effective_min_interval(self):
        """
        Polygon hard limit ~5 req/min/key. If multiple keys, scale up conservatively.
        Use the configured rate_limit_per_sec as an upper bound, but cap by keys*5/min.
        """
        keys = max(1, self.api_key_pool.size())
        hard_rps = (keys * 5.0) / 60.0  # 5 per minute per key
        rps = min(self.configured_rps, hard_rps) * self.safety
        rps = max(rps, 1.0 / 120.0)  # never >1 req per 120s when misconfigured
        return 1.0 / rps

    def _throttle(self):
        min_interval = self._effective_min_interval()
        dt = time.time() - self._last_ts
        if dt < min_interval:
            time.sleep(min_interval - dt)
        self._last_ts = time.time()

    def _build_request(self, base_key, path, query, method):
        base = self.base_urls[base_key].rstrip("/")
        url = f"{base}{path}"
        if query:
            url += "?" + urllib.parse.urlencode(query, doseq=True)
        key = self.api_key_pool.next_key()
        hdrs = {k: v.replace("${API_KEY}", key or "") for k, v in self.headers.items()}
        return urllib.request.Request(url, headers=hdrs, method=method), url

    from urllib.error import HTTPError, URLError

    def request(self, base_key, path, query, method="GET"):
        backoff_base = 2.0
        for attempt in range(self.max_retries):
            self._throttle()
            req, url = self._build_request(base_key, path, query, method)
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except HTTPError as e:
                body = None
                try:
                    body = e.read().decode("utf-8")
                except Exception:
                    pass
                # 429 → backoff + retry (kept as-is)
                if e.code == 429:
                    retry_after = e.headers.get("Retry-After")
                    wait = float(retry_after) if retry_after and retry_after.isdigit() else min(120.0, (
                                backoff_base ** attempt)) + (0.1 * attempt)
                    time.sleep(wait);
                    continue
                # 5xx → retry
                if 500 <= e.code < 600:
                    time.sleep(min(60.0, (backoff_base ** attempt)));
                    continue
                # 4xx (like 400) → raise with details
                raise RuntimeError(f"HTTP {e.code} for {url} :: query={query} :: body={body}") from e
            except URLError:
                time.sleep(min(30.0, (backoff_base ** attempt)));
                continue
        raise RuntimeError(f"HTTP request failed after {self.max_retries} retries: {method} {path} {query}")
