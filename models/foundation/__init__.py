"""
Foundation models - core reference dimensions.

Foundation models have no dependencies and provide shared
reference data that domain models can join against:

- temporal: Time and calendar dimensions (dates, weeks, months, quarters, years)
- geography: US location dimensions (states, counties, cities, ZIP codes)

All domain models depend on one or more foundation models.
"""
from models.foundation.temporal.model import TemporalModel
from models.foundation.geography.model import GeographyModel

__all__ = ['TemporalModel', 'GeographyModel']
