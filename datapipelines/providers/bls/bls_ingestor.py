import json
from datapipelines.providers.bls.bls_registry import BLSRegistry
from datapipelines.base.http_client import HttpClient
from datapipelines.base.key_pool import ApiKeyPool
from datapipelines.ingestors.bronze_sink import BronzeSink
from datapipelines.ingestors.base_ingestor import Ingestor

class BLSIngestor(Ingestor):
    """
    Base ingestor for Bureau of Labor Statistics (BLS) API.

    BLS API uses POST requests with JSON body containing series IDs and date ranges.
    No pagination needed as all data for the period is returned in a single response.
    """

    def __init__(self, bls_cfg, storage_cfg, spark):
        super().__init__(storage_cfg=storage_cfg)
        self.registry = BLSRegistry(bls_cfg)
        self.api_key = (bls_cfg.get("credentials") or {}).get("api_keys", [None])[0]
        self.http = HttpClient(
            self.registry.base_urls,
            self.registry.headers,
            self.registry.rate_limit,
            ApiKeyPool((bls_cfg.get("credentials") or {}).get("api_keys") or [], 90)
        )
        self.sink = BronzeSink(storage_cfg)
        self.spark = spark

    def _fetch_calls(self, calls, response_key="Results.series", max_pages=None, enable_pagination=False):
        """
        Fetch data from BLS API.

        BLS API doesn't use traditional pagination - it returns all data for the requested
        time period in a single response. The API uses POST requests with JSON body.

        Args:
            calls: Iterator of call specs
            response_key: Key path in response containing data (e.g., "Results.series")
            max_pages: Not used for BLS (included for interface compatibility)
            enable_pagination: Not used for BLS (included for interface compatibility)

        Returns:
            List of batches (one batch per call)
        """
        batches = []
        for call in calls:
            ep, path, q = self.registry.render(call["ep_name"], **call["params"])

            # BLS API uses POST with JSON body
            # Build the request body
            body = {
                "seriesid": call["params"].get("seriesid", []),
                "startyear": call["params"].get("startyear"),
                "endyear": call["params"].get("endyear")
            }

            # Add API key if available
            if self.api_key:
                body["registrationkey"] = self.api_key

            # Add optional parameters
            if call["params"].get("calculations"):
                body["calculations"] = True
            if call["params"].get("annualaverage"):
                body["annualaverage"] = True

            # Make POST request with JSON body
            # Note: This is a simplified implementation - you may need to modify
            # HttpClient to support POST with JSON body
            payload = self._post_json(ep.base, path, body, ep.method)

            # Navigate nested response key (e.g., "Results.series")
            data = payload
            for key in response_key.split("."):
                data = data.get(key, []) or []

            if isinstance(data, list):
                batches.append(data)
            else:
                batches.append([data])

        return batches

    def _post_json(self, base_key, path, body, method="POST"):
        """
        Helper method to make POST request with JSON body.

        Note: This is a workaround since HttpClient doesn't natively support POST bodies.
        Consider extending HttpClient to support POST with JSON body.
        """
        import urllib.request
        import json

        base = self.registry.base_urls[base_key].rstrip("/")
        url = f"{base}{path}"

        # Prepare headers
        headers = {k: v.replace("${API_KEY}", self.api_key or "")
                  for k, v in self.registry.headers.items()}

        # Convert body to JSON
        json_data = json.dumps(body).encode("utf-8")

        # Make request
        req = urllib.request.Request(url, data=json_data, headers=headers, method=method)

        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
