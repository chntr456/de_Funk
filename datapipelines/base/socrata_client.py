"""
Socrata (SODA) API Client.

Provides HTTP client functionality for Socrata Open Data APIs used by
Chicago Data Portal and Cook County Data Portal.

Features:
- Offset-based pagination with configurable page size
- SoQL query parameter handling ($select, $where, $order, $limit, $offset)
- Rate limiting with app token support
- Automatic retry with exponential backoff

Usage:
    from datapipelines.base.socrata_client import SocrataClient

    client = SocrataClient(
        base_url="https://data.cityofchicago.org",
        app_token="your_token",
        rate_limit_per_sec=5.0
    )

    # Fetch all records with pagination
    records = client.fetch_all(
        resource_id="ijzp-q8t2",
        query_params={"$where": "year > 2020"},
        limit=50000
    )

Author: de_Funk Team
Date: January 2026
"""

from __future__ import annotations

import json
import time
import urllib.request
import urllib.parse
from typing import Dict, List, Optional, Any, Generator
from urllib.error import HTTPError, URLError

from config.logging import get_logger

logger = get_logger(__name__)


class SocrataClient:
    """
    HTTP client for Socrata Open Data APIs (SODA).

    Handles the specifics of SODA API including:
    - App token authentication via X-App-Token header
    - SoQL query parameters ($limit, $offset, $where, etc.)
    - Offset-based pagination for bulk downloads
    - Rate limiting (5 req/sec with token, throttled without)
    """

    DEFAULT_LIMIT = 50000  # SODA allows up to 50k per request
    MAX_RETRIES = 6
    DEFAULT_TIMEOUT = 300  # 5 minutes for large datasets

    def __init__(
        self,
        base_url: str,
        app_token: Optional[str] = None,
        rate_limit_per_sec: float = 5.0,
        timeout: int = 300
    ):
        """
        Initialize Socrata client.

        Args:
            base_url: Base URL for the Socrata portal (e.g., "https://data.cityofchicago.org")
            app_token: Optional app token for higher rate limits
            rate_limit_per_sec: Maximum requests per second (default: 5.0 with token)
            timeout: Request timeout in seconds (default: 300 for large datasets)
        """
        self.base_url = base_url.rstrip("/")
        self.app_token = app_token
        self.rate_limit = rate_limit_per_sec
        self.timeout = timeout
        self._last_request_time = 0.0

        # Build default headers
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        # Token is optional - Socrata works without it (just slower: ~1 req/sec)
        if app_token and isinstance(app_token, str) and len(app_token.strip()) >= 10:
            self.headers["X-App-Token"] = app_token.strip()
            logger.info(f"SocrataClient: using app token ({app_token[:4]}...)")
        else:
            # No token - throttle to 1 req/sec to avoid rate limits
            self.rate_limit = 1.0
            logger.info("SocrataClient: no token, using throttled rate (1 req/sec)")

        logger.debug(
            f"SocrataClient initialized: base_url={base_url}, "
            f"has_token={app_token is not None}, rate_limit={rate_limit_per_sec}"
        )

    def _throttle(self) -> None:
        """Apply rate limiting between requests."""
        if self.rate_limit <= 0:
            return
        min_interval = 1.0 / self.rate_limit
        elapsed = time.time() - self._last_request_time
        if elapsed < min_interval:
            sleep_time = min_interval - elapsed
            logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)
        self._last_request_time = time.time()

    def _build_url(
        self,
        resource_id: str,
        query_params: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Build full URL for SODA resource.

        Args:
            resource_id: The 4x4 resource identifier (e.g., "ijzp-q8t2")
            query_params: SoQL query parameters

        Returns:
            Full URL string
        """
        url = f"{self.base_url}/resource/{resource_id}.json"
        if query_params:
            # Encode SoQL parameters (handle $ prefix correctly)
            encoded = urllib.parse.urlencode(query_params, doseq=True)
            url = f"{url}?{encoded}"
        return url

    def request(
        self,
        resource_id: str,
        query_params: Optional[Dict[str, Any]] = None
    ) -> List[Dict]:
        """
        Make a single request to a Socrata resource.

        Args:
            resource_id: The 4x4 resource identifier
            query_params: SoQL query parameters

        Returns:
            List of records (dicts)

        Raises:
            RuntimeError: If request fails after all retries
        """
        backoff_base = 2.0
        url = self._build_url(resource_id, query_params)

        for attempt in range(self.MAX_RETRIES):
            self._throttle()

            try:
                logger.debug(f"Request attempt {attempt + 1}/{self.MAX_RETRIES}: {url}")
                req = urllib.request.Request(url, headers=self.headers, method="GET")

                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    logger.debug(f"Request successful: {len(data)} records")
                    return data

            except HTTPError as e:
                body = None
                try:
                    body = e.read().decode("utf-8")
                except (IOError, UnicodeDecodeError):
                    pass

                # 429 → backoff + retry
                if e.code == 429:
                    retry_after = e.headers.get("Retry-After")
                    wait = float(retry_after) if retry_after and retry_after.isdigit() else min(120.0, backoff_base ** attempt)
                    logger.warning(f"Rate limited (429): waiting {wait:.1f}s before retry {attempt + 1}/{self.MAX_RETRIES}")
                    time.sleep(wait)
                    continue

                # 5xx → retry
                if 500 <= e.code < 600:
                    wait = min(60.0, backoff_base ** attempt)
                    logger.warning(f"Server error ({e.code}): waiting {wait:.1f}s before retry {attempt + 1}/{self.MAX_RETRIES}")
                    time.sleep(wait)
                    continue

                # 4xx → raise with details
                logger.error(f"Client error ({e.code}) for {url}: {body}")
                raise RuntimeError(f"HTTP {e.code} for {url}: {body}") from e

            except URLError as e:
                if attempt < self.MAX_RETRIES - 1:
                    wait = min(30.0, backoff_base ** attempt)
                    logger.warning(f"URL error: {e}. Waiting {wait:.1f}s before retry {attempt + 1}/{self.MAX_RETRIES}")
                    time.sleep(wait)
                    continue
                logger.error(f"URLError after {self.MAX_RETRIES} attempts for {url}: {e}")
                raise RuntimeError(f"URLError after {self.MAX_RETRIES} attempts: {e}") from e

        raise RuntimeError(f"Request failed after {self.MAX_RETRIES} attempts: {url}")

    def fetch_all(
        self,
        resource_id: str,
        query_params: Optional[Dict[str, Any]] = None,
        limit: int = DEFAULT_LIMIT,
        max_records: Optional[int] = None,
        label: Optional[str] = None
    ) -> Generator[List[Dict], None, None]:
        """
        Fetch all records from a resource using pagination.

        This is a generator that yields batches of records, allowing
        efficient processing of large datasets.

        Args:
            resource_id: The 4x4 resource identifier
            query_params: Base SoQL query parameters (without $limit/$offset)
            limit: Records per page (default: 50000)
            max_records: Optional maximum total records to fetch
            label: Optional label for logging (e.g., endpoint name)

        Yields:
            List of records for each page

        Example:
            for batch in client.fetch_all("ijzp-q8t2", label="budget"):
                for record in batch:
                    process(record)
        """
        params = dict(query_params or {})
        params["$limit"] = limit
        offset = 0
        total_fetched = 0
        log_name = f"{label} ({resource_id})" if label else resource_id

        while True:
            params["$offset"] = offset
            logger.info(f"Fetching {log_name} offset={offset} limit={limit}")

            batch = self.request(resource_id, params)
            if not batch:
                logger.info(f"Finished {log_name}: {total_fetched:,} total records")
                break

            yield batch
            total_fetched += len(batch)

            # Check if we've hit max_records limit
            if max_records and total_fetched >= max_records:
                logger.info(f"Reached max_records limit ({max_records:,}) for {log_name}")
                break

            # If we got fewer records than limit, we've reached the end
            if len(batch) < limit:
                logger.info(f"Finished {log_name}: {total_fetched:,} total records")
                break

            offset += limit

    def fetch_all_flat(
        self,
        resource_id: str,
        query_params: Optional[Dict[str, Any]] = None,
        limit: int = DEFAULT_LIMIT,
        max_records: Optional[int] = None
    ) -> List[Dict]:
        """
        Fetch all records from a resource, returning a flat list.

        Convenience wrapper around fetch_all() that collects all batches.
        Use fetch_all() for large datasets to avoid memory issues.

        Args:
            resource_id: The 4x4 resource identifier
            query_params: Base SoQL query parameters
            limit: Records per page (default: 50000)
            max_records: Optional maximum total records to fetch

        Returns:
            Flat list of all records
        """
        all_records = []
        for batch in self.fetch_all(resource_id, query_params, limit, max_records):
            all_records.extend(batch)
            if max_records and len(all_records) >= max_records:
                return all_records[:max_records]
        return all_records

    def get_row_count(self, resource_id: str, where_clause: Optional[str] = None) -> int:
        """
        Get the total row count for a resource.

        Uses SoQL COUNT(*) for efficient counting without fetching data.

        Args:
            resource_id: The 4x4 resource identifier
            where_clause: Optional $where filter

        Returns:
            Total row count
        """
        params = {"$select": "count(*) as count"}
        if where_clause:
            params["$where"] = where_clause

        result = self.request(resource_id, params)
        if result and len(result) > 0:
            return int(result[0].get("count", 0))
        return 0

    def get_metadata(self, resource_id: str) -> Dict:
        """
        Get metadata for a resource.

        Args:
            resource_id: The 4x4 resource identifier

        Returns:
            Resource metadata dict
        """
        url = f"{self.base_url}/api/views/{resource_id}.json"
        req = urllib.request.Request(url, headers=self.headers, method="GET")

        self._throttle()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            logger.warning(f"Failed to get metadata for {resource_id}: {e}")
            return {}
