"""Forecast model package"""
from .company_forecast_model import CompanyForecastModel
from .builder import ForecastBuilder

# Backward compatibility alias
ForecastModel = CompanyForecastModel

__all__ = ['CompanyForecastModel', 'ForecastModel', 'ForecastBuilder']
