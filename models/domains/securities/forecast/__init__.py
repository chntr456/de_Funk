"""
Forecast model - time series forecasting for stocks.

Provides:
- ForecastModel: Domain model for stock price forecasting
- ForecastBuilder: Builder that runs ML training pipeline
- training_methods: ARIMA, Prophet, RandomForest implementations
"""

from .company_forecast_model import CompanyForecastModel
from .builder import ForecastBuilder
from . import training_methods

# Backward compatibility alias
ForecastModel = CompanyForecastModel

__all__ = ['CompanyForecastModel', 'ForecastModel', 'ForecastBuilder', 'training_methods']
