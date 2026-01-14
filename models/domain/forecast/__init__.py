"""
Forecast model - BACKWARD COMPATIBILITY LAYER.

DEPRECATED: Import from models.domains.securities.forecast instead.

Example:
    # Old (deprecated)
    from models.domain.forecast import ForecastModel

    # New (recommended)
    from models.domains.securities.forecast import ForecastModel
"""

from models.domains.securities.forecast import (
    CompanyForecastModel,
    ForecastModel,
    ForecastBuilder,
    training_methods,
)

__all__ = ['CompanyForecastModel', 'ForecastModel', 'ForecastBuilder', 'training_methods']
