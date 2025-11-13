from urllib.parse import urlparse, parse_qs
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from datapipelines.providers.polygon.polygon_registry import PolygonRegistry
from datapipelines.base.http_client import HttpClient
from datapipelines.base.key_pool import ApiKeyPool
from datapipelines.ingestors.bronze_sink import BronzeSink
from datapipelines.ingestors.base_ingestor import Ingestor

class PolygonIngestor(Ingestor):
    def __init__(self, polygon_cfg, storage_cfg, spark):
        super().__init__(storage_cfg=storage_cfg)
        self.registry = PolygonRegistry(polygon_cfg)
        self.http = HttpClient(
            self.registry.base_urls,
            self.registry.headers,
            self.registry.rate_limit,
            ApiKeyPool((polygon_cfg.get("credentials") or {}).get("api_keys") or [], 90)
        )
        self.sink = BronzeSink(storage_cfg)
        self.spark = spark
        self._http_lock = threading.Lock()  # For thread-safe HTTP requests

    @staticmethod
    def _cursor_from_next(next_url):
        """Extract Polygon 'cursor' parameter from a next_url, if present."""
        if not next_url:
            return None
        qs = parse_qs(urlparse(next_url).query)
        vals = qs.get("cursor")
        return vals[0] if vals else None

    def _fetch_calls(self, calls, response_key="results", max_pages=None, enable_pagination=True):
        """
        Fetch data with automatic pagination support.

        Args:
            calls: Iterator of call specs
            response_key: Key in response containing data (default: "results")
            max_pages: Maximum pages to fetch per call (default: unlimited)
            enable_pagination: Whether to follow next_url for pagination (default: True)

        Returns:
            List of batches (one batch per call, with all pages combined)
        """
        batches = []
        for call in calls:
            ep, path, q = self.registry.render(call["ep_name"], **call["params"])

            # Collect all pages for this call
            all_data = []
            page_count = 0
            next_cursor = None

            while True:
                # Add cursor to query if paginating
                query = q.copy()
                if next_cursor:
                    query["cursor"] = next_cursor

                # Make request
                payload = self.http.request(ep.base, path, query, ep.method)

                # Extract data
                data = payload.get(response_key, []) or []
                if isinstance(data, list):
                    all_data.extend(data)
                else:
                    all_data.append(data)

                page_count += 1

                # Check if pagination is enabled and if there's a next page
                if not enable_pagination:
                    break

                next_url = payload.get("next_url")
                if not next_url:
                    break  # No more pages

                # Extract cursor from next_url
                next_cursor = self._cursor_from_next(next_url)
                if not next_cursor:
                    break  # Can't parse cursor

                # Check page limit
                if max_pages and page_count >= max_pages:
                    break

            batches.append(all_data)
        return batches

    def _fetch_calls_concurrent(self, calls, response_key="results", max_workers=10, enable_pagination=True):
        """
        Fetch data with concurrent requests for better throughput.

        Args:
            calls: Iterator of call specs
            response_key: Key in response containing data (default: "results")
            max_workers: Maximum concurrent workers (default: 10)
            enable_pagination: Whether to follow next_url for pagination (default: True)

        Returns:
            List of batches (one batch per call, with all pages combined)
        """
        calls_list = list(calls)
        batches = [None] * len(calls_list)  # Preserve order

        def fetch_single_call(idx, call):
            """Fetch a single call with pagination"""
            ep, path, q = self.registry.render(call["ep_name"], **call["params"])

            all_data = []
            next_cursor = None

            while True:
                # Add cursor to query if paginating
                query = q.copy()
                if next_cursor:
                    query["cursor"] = next_cursor

                # Make request (thread-safe)
                with self._http_lock:
                    payload = self.http.request(ep.base, path, query, ep.method)

                # Extract data
                data = payload.get(response_key, []) or []
                if isinstance(data, list):
                    all_data.extend(data)
                else:
                    all_data.append(data)

                # Check pagination
                if not enable_pagination:
                    break

                next_url = payload.get("next_url")
                if not next_url:
                    break

                next_cursor = self._cursor_from_next(next_url)
                if not next_cursor:
                    break

            return idx, all_data

        # Execute concurrent requests
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(fetch_single_call, idx, call): idx
                for idx, call in enumerate(calls_list)
            }

            for future in as_completed(futures):
                idx, data = future.result()
                batches[idx] = data

        return batches
