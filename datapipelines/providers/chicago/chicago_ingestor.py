"""
Chicago Data Portal Ingestor.

Ingests data from Chicago's Socrata Open Data Portal.

Usage:
    from datapipelines.providers.chicago import ChicagoIngestor

    ingestor = ChicagoIngestor(
        chicago_cfg=ctx.get_api_config('chicago'),
        storage_cfg=ctx.storage,
        spark=ctx.spark
    )
    results = ingestor.run()
"""
from __future__ import annotations

from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

from datapipelines.providers.chicago.chicago_registry import ChicagoRegistry
from datapipelines.base.http_client import HttpClient
from datapipelines.base.key_pool import ApiKeyPool
from datapipelines.ingestors.bronze_sink import BronzeSink
from datapipelines.ingestors.base_ingestor import Ingestor

logger = logging.getLogger(__name__)


class ChicagoIngestor(Ingestor):
    """
    Ingestor for Chicago Data Portal (Socrata API).

    Fetches and stores:
    - Building permits
    - Unemployment rates by community area
    - Business licenses
    - Economic indicators

    Socrata uses offset-based pagination with $offset and $limit parameters.
    """

    def __init__(self, chicago_cfg: Dict, storage_cfg: Dict, spark):
        """
        Initialize Chicago ingestor.

        Args:
            chicago_cfg: Chicago API configuration
            storage_cfg: Storage configuration
            spark: SparkSession
        """
        super().__init__(storage_cfg=storage_cfg)
        self.chicago_cfg = chicago_cfg
        self.registry = ChicagoRegistry(chicago_cfg)
        self.http = HttpClient(
            self.registry.base_urls,
            self.registry.headers,
            self.registry.rate_limit,
            ApiKeyPool((chicago_cfg.get("credentials") or {}).get("api_keys") or [], 90)
        )
        self.sink = BronzeSink(storage_cfg)
        self.spark = spark

    def run(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        datasets: Optional[List[str]] = None,
        max_pages: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Run Chicago data ingestion.

        Args:
            date_from: Start date for filtering (YYYY-MM-DD)
            date_to: End date for filtering (YYYY-MM-DD)
            datasets: List of datasets to ingest (default: all)
                      Options: 'building_permits', 'unemployment_rates',
                              'business_licenses', 'economic_indicators'
            max_pages: Maximum pages to fetch per dataset (for testing)

        Returns:
            Dictionary with ingestion results
        """
        results = {
            'start_time': datetime.now().isoformat(),
            'datasets': {},
            'errors': [],
            'status': 'running'
        }

        # Default to all datasets
        if datasets is None:
            datasets = ['building_permits', 'unemployment_rates']

        logger.info(f"Starting Chicago ingestion for datasets: {datasets}")

        # Ingest each dataset
        for dataset in datasets:
            try:
                if dataset == 'building_permits':
                    result = self._ingest_building_permits(
                        date_from=date_from,
                        date_to=date_to,
                        max_pages=max_pages
                    )
                elif dataset == 'unemployment_rates':
                    result = self._ingest_unemployment_rates(
                        date_from=date_from,
                        date_to=date_to,
                        max_pages=max_pages
                    )
                elif dataset == 'business_licenses':
                    result = self._ingest_business_licenses(max_pages=max_pages)
                elif dataset == 'economic_indicators':
                    result = self._ingest_economic_indicators(
                        date_from=date_from,
                        date_to=date_to,
                        max_pages=max_pages
                    )
                else:
                    logger.warning(f"Unknown dataset: {dataset}")
                    continue

                results['datasets'][dataset] = result
                logger.info(f"  ✓ {dataset}: {result.get('rows', 0)} rows")

            except Exception as e:
                error_msg = f"{dataset} failed: {str(e)}"
                logger.error(error_msg, exc_info=True)
                results['errors'].append(error_msg)
                results['datasets'][dataset] = {
                    'status': 'failed',
                    'error': str(e)
                }

        results['end_time'] = datetime.now().isoformat()
        results['status'] = 'completed' if not results['errors'] else 'completed_with_errors'

        return results

    def _ingest_building_permits(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        max_pages: Optional[int] = None
    ) -> Dict[str, Any]:
        """Ingest building permits data."""
        from datapipelines.providers.chicago.facets.building_permits_facet import BuildingPermitsFacet

        facet = BuildingPermitsFacet(
            date_from=date_from,
            date_to=date_to
        )

        # Fetch data
        batches = self._fetch_calls(
            facet.calls(),
            response_key=None,
            max_pages=max_pages
        )

        # Flatten batches
        all_data = []
        for batch in batches:
            all_data.extend(batch)

        if not all_data:
            return {'rows': 0, 'status': 'no_data'}

        # Create DataFrame and transform
        df = self.spark.createDataFrame(all_data)
        df = facet.postprocess(df)

        # Write to Bronze
        row_count = df.count()
        self.sink.write(
            df,
            table_name='chicago_building_permits',
            mode='overwrite',
            partition_cols=None
        )

        return {
            'rows': row_count,
            'status': 'success',
            'table': 'chicago_building_permits'
        }

    def _ingest_unemployment_rates(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        max_pages: Optional[int] = None
    ) -> Dict[str, Any]:
        """Ingest unemployment rates by community area."""
        from datapipelines.providers.chicago.facets.unemployment_rates_facet import UnemploymentRatesFacet

        facet = UnemploymentRatesFacet(
            date_from=date_from,
            date_to=date_to
        )

        # Fetch data
        batches = self._fetch_calls(
            facet.calls(),
            response_key=None,
            max_pages=max_pages
        )

        # Flatten batches
        all_data = []
        for batch in batches:
            all_data.extend(batch)

        if not all_data:
            return {'rows': 0, 'status': 'no_data'}

        # Create DataFrame and transform
        df = self.spark.createDataFrame(all_data)
        df = facet.postprocess(df)

        # Write to Bronze
        row_count = df.count()
        self.sink.write(
            df,
            table_name='chicago_unemployment_rates',
            mode='overwrite',
            partition_cols=None
        )

        return {
            'rows': row_count,
            'status': 'success',
            'table': 'chicago_unemployment_rates'
        }

    def _ingest_business_licenses(
        self,
        max_pages: Optional[int] = None
    ) -> Dict[str, Any]:
        """Ingest business licenses data."""
        # Fetch data directly (no facet yet)
        batches = self._fetch_calls(
            [{"ep_name": "business_licenses", "params": {}}],
            response_key=None,
            max_pages=max_pages or 10  # Limit for testing
        )

        all_data = []
        for batch in batches:
            all_data.extend(batch)

        if not all_data:
            return {'rows': 0, 'status': 'no_data'}

        # Create DataFrame
        df = self.spark.createDataFrame(all_data)
        row_count = df.count()

        # Write to Bronze
        self.sink.write(
            df,
            table_name='chicago_business_licenses',
            mode='overwrite',
            partition_cols=None
        )

        return {
            'rows': row_count,
            'status': 'success',
            'table': 'chicago_business_licenses'
        }

    def _ingest_economic_indicators(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        max_pages: Optional[int] = None
    ) -> Dict[str, Any]:
        """Ingest economic indicators data."""
        params = {}
        if date_from:
            params["$where"] = f"date >= '{date_from}'"
        if date_to:
            if "$where" in params:
                params["$where"] += f" AND date <= '{date_to}'"
            else:
                params["$where"] = f"date <= '{date_to}'"

        batches = self._fetch_calls(
            [{"ep_name": "economic_indicators", "params": params}],
            response_key=None,
            max_pages=max_pages
        )

        all_data = []
        for batch in batches:
            all_data.extend(batch)

        if not all_data:
            return {'rows': 0, 'status': 'no_data'}

        # Create DataFrame
        df = self.spark.createDataFrame(all_data)
        row_count = df.count()

        # Write to Bronze
        self.sink.write(
            df,
            table_name='chicago_economic_indicators',
            mode='overwrite',
            partition_cols=None
        )

        return {
            'rows': row_count,
            'status': 'success',
            'table': 'chicago_economic_indicators'
        }

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
                try:
                    payload = self.http.request(ep.base, path, query, ep.method)
                except Exception as e:
                    logger.error(f"HTTP request failed: {e}")
                    break

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
