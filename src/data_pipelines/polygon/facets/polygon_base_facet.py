from __future__ import annotations
from typing import Iterable, List, Optional
from pyspark.sql import SparkSession
from src.data_pipelines.facets.base_facet import Facet

class PolygonFacet(Facet):
    """
    Polygon-specific ergonomics layered on top of Facet:
    - tracks tickers/date window
    - defines the abstract 'calls()' contract for ingest jobs to execute
    """
    def __init__(self, spark: SparkSession, *,
                 tickers: Optional[List[str]] = None,
                 date_from: Optional[str] = None,
                 date_to: Optional[str] = None,
                 **kwargs):
        super().__init__(spark, **kwargs)
        self._tickers = tickers or []
        self._date_from = date_from
        self._date_to = date_to

    def calls(self) -> Iterable[dict]:
        """
        Concrete Polygon facets must implement this and return an iterable of:
          { "ep_name": <endpoint_name_in_registry>, "params": {...} }
        No HTTP here — ingest job executes requests using registry + http_client.
        """
        raise NotImplementedError

    # helpers
    @property
    def tickers(self) -> List[str]: return self._tickers
    @property
    def date_from(self) -> Optional[str]: return self._date_from
    @property
    def date_to(self)   -> Optional[str]: return self._date_to
