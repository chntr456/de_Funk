from datapipelines.facets.base_facet import Facet

class BLSFacet(Facet):
    """
    Base facet for Bureau of Labor Statistics (BLS) data sources.

    BLS API returns time series data with series IDs and date ranges.
    """

    def __init__(self, spark, series_ids=None, start_year=None, end_year=None,
                 calculations=False, annual_average=False):
        super().__init__(spark)
        self.series_ids = series_ids or []
        self.start_year = start_year
        self.end_year = end_year
        self.calculations = calculations
        self.annual_average = annual_average

    def calls(self):
        raise NotImplementedError
