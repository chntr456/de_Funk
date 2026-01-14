"""
Socrata (SODA) API Client.

Provides HTTP client functionality for Socrata Open Data APIs used by
Chicago Data Portal and Cook County Data Portal.

Features:
- Offset-based pagination with configurable page size
- CSV bulk download for large datasets (streaming)
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

    # Fetch all records with pagination (JSON API)
    records = client.fetch_all(
        resource_id="ijzp-q8t2",
        query_params={"$where": "year > 2020"},
        limit=50000
    )

    # Fetch via CSV bulk download (faster for large datasets)
    for batch in client.fetch_csv(resource_id="sxs8-h27x", batch_size=50000):
        process(batch)

Author: de_Funk Team
Date: January 2026
"""

from __future__ import annotations

import csv
import io
import json
import socket
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

            except (TimeoutError, socket.timeout, ConnectionError) as e:
                # TimeoutError: read/connection timeout
                # socket.timeout: socket-level timeout (alias for TimeoutError in Python 3.10+)
                # ConnectionError: ConnectionResetError, BrokenPipeError, ConnectionAbortedError
                # All are transient network issues - retryable
                error_type = type(e).__name__
                if attempt < self.MAX_RETRIES - 1:
                    # Use longer backoff for timeouts since the server may be overloaded
                    wait = min(60.0, backoff_base ** (attempt + 1))
                    logger.warning(
                        f"{error_type}: {e}. Waiting {wait:.1f}s before retry {attempt + 1}/{self.MAX_RETRIES}"
                    )
                    time.sleep(wait)
                    continue
                logger.error(f"{error_type} after {self.MAX_RETRIES} attempts for {url}: {e}")
                raise RuntimeError(f"{error_type} after {self.MAX_RETRIES} attempts: {e}") from e

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

    def fetch_csv(
        self,
        resource_id: str,
        batch_size: int = 50000,
        max_records: Optional[int] = None,
        label: Optional[str] = None
    ) -> Generator[List[Dict], None, None]:
        """
        Fetch all records via CSV bulk download (streaming).

        This is faster and more reliable than JSON pagination for large datasets.
        The CSV is streamed and processed in batches to avoid memory issues.

        CSV export URL format:
            https://data.cityofchicago.org/api/views/{view_id}/rows.csv?accessType=DOWNLOAD

        Args:
            resource_id: The 4x4 resource identifier (view_id)
            batch_size: Number of records per batch to yield (default: 50000)
            max_records: Optional maximum total records to fetch
            label: Optional label for logging (e.g., endpoint name)

        Yields:
            List of records (dicts) for each batch

        Example:
            for batch in client.fetch_csv("sxs8-h27x", label="traffic"):
                for record in batch:
                    process(record)
        """
        url = f"{self.base_url}/api/views/{resource_id}/rows.csv?accessType=DOWNLOAD"
        log_name = f"{label} ({resource_id})" if label else resource_id
        backoff_base = 2.0

        logger.info(f"Starting CSV bulk download for {log_name}")

        for attempt in range(self.MAX_RETRIES):
            self._throttle()

            try:
                req = urllib.request.Request(url, headers={
                    **self.headers,
                    "Accept": "text/csv"
                }, method="GET")

                # Use longer timeout for CSV downloads (can be very large)
                csv_timeout = max(self.timeout, 600)  # At least 10 minutes

                with urllib.request.urlopen(req, timeout=csv_timeout) as resp:
                    # Stream the response and process in batches
                    total_fetched = 0
                    batch = []

                    # Wrap response in text wrapper for csv.DictReader
                    text_stream = io.TextIOWrapper(resp, encoding='utf-8', errors='replace')
                    reader = csv.DictReader(text_stream)

                    for row in reader:
                        batch.append(row)
                        total_fetched += 1

                        # Check max_records limit
                        if max_records and total_fetched >= max_records:
                            if batch:
                                logger.info(
                                    f"CSV {log_name}: yielding final batch of {len(batch):,} "
                                    f"(reached max_records={max_records:,})"
                                )
                                yield batch
                            logger.info(f"Finished CSV {log_name}: {total_fetched:,} total records (max_records limit)")
                            return

                        # Yield batch when full
                        if len(batch) >= batch_size:
                            logger.info(f"CSV {log_name}: yielding batch of {len(batch):,} (total: {total_fetched:,})")
                            yield batch
                            batch = []

                    # Yield remaining records
                    if batch:
                        logger.info(f"CSV {log_name}: yielding final batch of {len(batch):,}")
                        yield batch

                    logger.info(f"Finished CSV {log_name}: {total_fetched:,} total records")
                    return

            except HTTPError as e:
                body = None
                try:
                    body = e.read().decode("utf-8")[:500]
                except (IOError, UnicodeDecodeError):
                    pass

                if e.code == 429:
                    retry_after = e.headers.get("Retry-After")
                    wait = float(retry_after) if retry_after and retry_after.isdigit() else min(120.0, backoff_base ** attempt)
                    logger.warning(f"CSV rate limited (429): waiting {wait:.1f}s before retry {attempt + 1}/{self.MAX_RETRIES}")
                    time.sleep(wait)
                    continue

                if 500 <= e.code < 600:
                    wait = min(60.0, backoff_base ** attempt)
                    logger.warning(f"CSV server error ({e.code}): waiting {wait:.1f}s before retry {attempt + 1}/{self.MAX_RETRIES}")
                    time.sleep(wait)
                    continue

                logger.error(f"CSV client error ({e.code}) for {url}: {body}")
                raise RuntimeError(f"CSV HTTP {e.code} for {url}: {body}") from e

            except (URLError, TimeoutError, socket.timeout, ConnectionError) as e:
                error_type = type(e).__name__
                if attempt < self.MAX_RETRIES - 1:
                    wait = min(120.0, backoff_base ** (attempt + 1))
                    logger.warning(
                        f"CSV {error_type}: {e}. Waiting {wait:.1f}s before retry {attempt + 1}/{self.MAX_RETRIES}"
                    )
                    time.sleep(wait)
                    continue
                logger.error(f"CSV {error_type} after {self.MAX_RETRIES} attempts for {url}: {e}")
                raise RuntimeError(f"CSV {error_type} after {self.MAX_RETRIES} attempts: {e}") from e

        raise RuntimeError(f"CSV download failed after {self.MAX_RETRIES} attempts: {url}")

    def download_csv_to_file(
        self,
        resource_id: str,
        output_path: str,
        label: Optional[str] = None,
        resume: bool = True
    ) -> int:
        """
        Download CSV to a file on disk with resume support.

        This is more reliable than streaming for very large datasets because:
        - Supports resume on interrupted downloads
        - File can be verified before processing
        - No memory pressure during download
        - Can be retried independently of Bronze ingestion

        Args:
            resource_id: The 4x4 resource identifier (view_id)
            output_path: Path to save the CSV file
            label: Optional label for logging
            resume: If True, skip download if file exists with content

        Returns:
            Number of bytes downloaded (0 if skipped due to existing file)
        """
        from pathlib import Path
        import shutil

        url = f"{self.base_url}/api/views/{resource_id}/rows.csv?accessType=DOWNLOAD"
        log_name = f"{label} ({resource_id})" if label else resource_id
        output_file = Path(output_path)
        backoff_base = 2.0

        # Check if file already exists and has content
        if resume and output_file.exists():
            file_size = output_file.stat().st_size
            if file_size > 100:  # More than just a header
                logger.info(f"CSV {log_name}: file exists ({file_size:,} bytes), skipping download")
                return 0

        # Ensure parent directory exists
        output_file.parent.mkdir(parents=True, exist_ok=True)
        temp_path = output_file.with_suffix('.csv.tmp')

        logger.info(f"Starting CSV download to file for {log_name}")
        logger.info(f"  URL: {url}")
        logger.info(f"  Output: {output_path}")

        for attempt in range(self.MAX_RETRIES):
            self._throttle()

            try:
                req = urllib.request.Request(url, headers={
                    **self.headers,
                    "Accept": "text/csv"
                }, method="GET")

                # Use longer timeout for CSV downloads
                csv_timeout = max(self.timeout, 1800)  # At least 30 minutes for large files

                with urllib.request.urlopen(req, timeout=csv_timeout) as resp:
                    # Get content length if available
                    content_length = resp.headers.get('Content-Length')
                    if content_length:
                        logger.info(f"CSV {log_name}: downloading {int(content_length):,} bytes")

                    # Stream to temp file
                    bytes_downloaded = 0
                    with open(temp_path, 'wb') as f:
                        while True:
                            chunk = resp.read(8192 * 16)  # 128KB chunks
                            if not chunk:
                                break
                            f.write(chunk)
                            bytes_downloaded += len(chunk)

                            # Log progress every 50MB
                            if bytes_downloaded % (50 * 1024 * 1024) < 8192 * 16:
                                logger.info(f"CSV {log_name}: downloaded {bytes_downloaded:,} bytes")

                # Move temp file to final location
                shutil.move(str(temp_path), str(output_file))
                logger.info(f"CSV {log_name}: download complete ({bytes_downloaded:,} bytes)")
                return bytes_downloaded

            except HTTPError as e:
                body = None
                try:
                    body = e.read().decode("utf-8")[:500]
                except (IOError, UnicodeDecodeError):
                    pass

                if e.code == 429:
                    wait = min(120.0, backoff_base ** attempt)
                    logger.warning(f"CSV download rate limited (429): waiting {wait:.1f}s")
                    time.sleep(wait)
                    continue

                if 500 <= e.code < 600:
                    wait = min(60.0, backoff_base ** attempt)
                    logger.warning(f"CSV download server error ({e.code}): waiting {wait:.1f}s")
                    time.sleep(wait)
                    continue

                logger.error(f"CSV download client error ({e.code}): {body}")
                raise RuntimeError(f"CSV download HTTP {e.code}: {body}") from e

            except (URLError, TimeoutError, socket.timeout, ConnectionError) as e:
                error_type = type(e).__name__
                if attempt < self.MAX_RETRIES - 1:
                    wait = min(120.0, backoff_base ** (attempt + 1))
                    logger.warning(f"CSV download {error_type}: {e}. Retrying in {wait:.1f}s")
                    time.sleep(wait)
                    continue
                logger.error(f"CSV download {error_type} after {self.MAX_RETRIES} attempts: {e}")
                raise RuntimeError(f"CSV download failed: {e}") from e

            finally:
                # Clean up temp file on failure
                if temp_path.exists():
                    try:
                        temp_path.unlink()
                    except OSError:
                        pass

        raise RuntimeError(f"CSV download failed after {self.MAX_RETRIES} attempts")

    def fetch_csv_from_file(
        self,
        file_path: str,
        batch_size: int = 50000,
        max_records: Optional[int] = None,
        label: Optional[str] = None
    ) -> Generator[List[Dict], None, None]:
        """
        Read CSV from a file on disk and yield batches.

        This reads from a previously downloaded CSV file, allowing the download
        and ingestion steps to be separated for reliability.

        Args:
            file_path: Path to the CSV file
            batch_size: Number of records per batch to yield
            max_records: Optional maximum total records to read
            label: Optional label for logging

        Yields:
            List of records (dicts) for each batch
        """
        from pathlib import Path

        csv_file = Path(file_path)
        log_name = label or csv_file.name

        if not csv_file.exists():
            raise FileNotFoundError(f"CSV file not found: {file_path}")

        file_size = csv_file.stat().st_size
        logger.info(f"Reading CSV from file: {log_name} ({file_size:,} bytes)")

        total_fetched = 0
        batch = []

        with open(csv_file, 'r', encoding='utf-8', errors='replace') as f:
            reader = csv.DictReader(f)

            for row in reader:
                batch.append(row)
                total_fetched += 1

                # Check max_records limit
                if max_records and total_fetched >= max_records:
                    if batch:
                        logger.info(f"CSV {log_name}: yielding final batch of {len(batch):,} (max_records reached)")
                        yield batch
                    logger.info(f"Finished CSV {log_name}: {total_fetched:,} records (max_records limit)")
                    return

                # Yield batch when full
                if len(batch) >= batch_size:
                    logger.info(f"CSV {log_name}: yielding batch of {len(batch):,} (total: {total_fetched:,})")
                    yield batch
                    batch = []

            # Yield remaining records
            if batch:
                logger.info(f"CSV {log_name}: yielding final batch of {len(batch):,}")
                yield batch

            logger.info(f"Finished CSV {log_name}: {total_fetched:,} total records")
