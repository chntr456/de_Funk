from datapipelines.facets.base_facet import Facet

class ChicagoFacet(Facet):
    """
    Base facet for Chicago Data Portal (Socrata API) data sources.

    Chicago uses Socrata API which returns JSON arrays directly.
    """

    def __init__(self, spark, date_from=None, date_to=None, filters=None):
        super().__init__(spark)
        self.date_from = date_from
        self.date_to = date_to
        self.filters = filters or {}

    def calls(self):
        raise NotImplementedError
