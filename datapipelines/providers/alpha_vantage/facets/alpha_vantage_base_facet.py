"""
Base facet for Alpha Vantage API data transformations.

Alpha Vantage uses a different API structure than Polygon:
- Single base URL with function parameter
- API key passed as query parameter
- Response format varies by endpoint (some nested, some flat)
- Rate limits are more restrictive (5 calls/min for free tier)
"""

from datapipelines.facets.base_facet import Facet


class AlphaVantageFacet(Facet):
    """
    Base facet for Alpha Vantage data providers.

    Key Differences from Polygon:
    - API key in query params (not headers)
    - Function-based endpoint selection
    - Varied response structures
    - Lower rate limits

    Attributes:
        tickers: List of ticker symbols to fetch
        date_from: Start date for time series data
        date_to: End date for time series data
        extra: Additional parameters (interval, outputsize, etc.)
    """

    def __init__(self, spark, tickers=None, date_from=None, date_to=None, **extra):
        """
        Initialize Alpha Vantage facet.

        Args:
            spark: SparkSession
            tickers: List of ticker symbols (optional)
            date_from: Start date for time series (YYYY-MM-DD)
            date_to: End date for time series (YYYY-MM-DD)
            **extra: Additional parameters:
                - interval: Time interval for intraday/technical indicators
                - outputsize: 'compact' (100 days) or 'full' (20+ years)
                - adjusted: Whether to use adjusted prices
        """
        super().__init__(spark)
        self.tickers = tickers or []
        self.date_from = date_from
        self.date_to = date_to
        self.extra = extra

    def calls(self):
        """
        Generate API calls for this facet.

        Must be implemented by subclass.
        Returns iterable of dicts with ep_name and params.
        """
        raise NotImplementedError

    def normalize(self, raw_batches):
        """
        Override normalize to pre-clean Alpha Vantage's "None" strings.

        Alpha Vantage returns the literal string "None" for missing values,
        which causes Spark 4.0.1's aggressive optimizer to fail during casting.

        Replace "None"/"N/A"/"-" with empty strings (not None) so Spark can
        infer schema as StringType. Empty strings are safe to cast to NULL.
        """
        # Clean the raw data at Python level
        cleaned_batches = []
        for batch in raw_batches:
            cleaned_batch = []
            for item in batch:
                if isinstance(item, dict):
                    # Replace invalid strings with empty string
                    cleaned_item = {}
                    for key, value in item.items():
                        if value == "None" or value == "N/A" or value == "-":
                            cleaned_item[key] = ""  # Empty string, not None
                        elif value is None:
                            cleaned_item[key] = ""  # Convert None to empty string too
                        else:
                            cleaned_item[key] = value
                    cleaned_batch.append(cleaned_item)
                else:
                    cleaned_batch.append(item)
            cleaned_batches.append(cleaned_batch)

        # Now call parent's normalize with cleaned data
        return super().normalize(cleaned_batches)
