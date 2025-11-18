"""
Alpha Vantage Registry

Manages endpoint definitions and request rendering for Alpha Vantage API.

Key Differences from Polygon:
- API key passed as query parameter (apikey=XXX)
- Function parameter determines endpoint type
- No path templates (all queries go to same base URL)
- Rate limits are lower (5 calls/min for free tier)
"""

from datapipelines.base.endpoint_registry import EndpointRegistry, Endpoint


class AlphaVantageRegistry(EndpointRegistry):
    """
    Registry for Alpha Vantage API endpoints.

    Alpha Vantage uses a single base URL with function-based routing:
    https://www.alphavantage.co/query?function=OVERVIEW&symbol=IBM&apikey=demo

    All endpoints use GET method and query parameters.
    """

    def __init__(self, config):
        """
        Initialize Alpha Vantage registry from configuration.

        Args:
            config: Alpha Vantage configuration dict from alpha_vantage_endpoints.json
        """
        super().__init__(config)

    def render(self, ep_name, **params):
        """
        Render an endpoint with given parameters.

        Alpha Vantage specific handling:
        - API key injected into query parameters
        - Function parameter set from default_query
        - All requests go to same base URL (no path templates)

        Args:
            ep_name: Endpoint name (e.g., 'company_overview', 'time_series_daily')
            **params: Parameters to fill in (e.g., symbol='AAPL')

        Returns:
            Tuple of (endpoint, path, query_params)
        """
        ep = self.endpoints.get(ep_name)
        if not ep:
            raise ValueError(f"Unknown endpoint: {ep_name}")

        # Alpha Vantage has no path templates (empty path)
        path = ep.path_template or ""

        # Build query parameters
        query = {}

        # 1. Start with default query (includes function parameter)
        if ep.default_query:
            query.update(ep.default_query)

        # 2. Add provided params
        query.update(params)

        # 3. Add API key (required for all endpoints)
        # Note: API key is injected by HttpClient via ApiKeyPool
        # but we need to ensure the 'apikey' parameter placeholder exists
        if 'apikey' not in query:
            query['apikey'] = '${API_KEY}'  # Placeholder for HttpClient

        return ep, path, query
