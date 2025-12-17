from urllib.parse import urlparse, parse_qs
from datapipelines.providers.chicago.chicago_registry import ChicagoRegistry
from datapipelines.base.http_client import HttpClient
from datapipelines.base.key_pool import ApiKeyPool
from datapipelines.ingestors.bronze_sink import BronzeSink
from datapipelines.ingestors.base_ingestor import Ingestor

class ChicagoIngestor(Ingestor):
    """
    Base ingestor for Chicago Data Portal (Socrata API).

    Socrata uses offset-based pagination with $offset and $limit parameters.
    """

    def __init__(self, chicago_cfg, storage_cfg, spark):
        super().__init__(storage_cfg=storage_cfg)
        self.registry = ChicagoRegistry(chicago_cfg)
        self.http = HttpClient(
            self.registry.base_urls,
            self.registry.headers,
            self.registry.rate_limit,
            ApiKeyPool((chicago_cfg.get("credentials") or {}).get("api_keys") or [], 90)
        )
        self.sink = BronzeSink(storage_cfg)
        self.spark = spark

    def _fetch_calls(self, calls, response_key=None, max_pages=None, enable_pagination=True):
        """
        Fetch data with automatic offset-based pagination for Socrata API.

        Args:
            calls: Iterator of call specs
            response_key: Key in response containing data (default: None, returns full response array)
            max_pages: Maximum pages to fetch per call (default: unlimited)
            enable_pagination: Whether to paginate through all results (default: True)

        Returns:
            List of batches (one batch per call, with all pages combined)
        """
        batches = []
        for call in calls:
            ep, path, q = self.registry.render(call["ep_name"], **call["params"])

            # Collect all pages for this call
            all_data = []
            page_count = 0
            offset = 0
            limit = int(q.get("$limit", 1000))

            while True:
                # Add offset to query for pagination
                query = q.copy()
                if offset > 0:
                    query["$offset"] = offset

                # Make request
                payload = self.http.request(ep.base, path, query, ep.method)

                # Socrata returns an array directly (no wrapper object)
                if response_key:
                    data = payload.get(response_key, []) or []
                else:
                    data = payload if isinstance(payload, list) else [payload]

                # If no data returned, we've reached the end
                if not data:
                    break

                all_data.extend(data)
                page_count += 1

                # Check if pagination is enabled
                if not enable_pagination:
                    break

                # If we got fewer results than the limit, we've reached the end
                if len(data) < limit:
                    break

                # Check page limit
                if max_pages and page_count >= max_pages:
                    break

                # Move to next page
                offset += limit

            batches.append(all_data)
        return batches
