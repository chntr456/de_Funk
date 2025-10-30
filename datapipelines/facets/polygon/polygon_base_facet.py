from datapipelines.facets.base_facet import Facet

class PolygonFacet(Facet):
    def __init__(self, spark, tickers=None, date_from=None, date_to=None):
        super().__init__(spark)
        self.tickers = tickers or []
        self.date_from = date_from
        self.date_to = date_to

    def calls(self):
        raise NotImplementedError
