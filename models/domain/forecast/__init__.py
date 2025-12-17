"""Forecast model package"""
from .company_forecast_model import CompanyForecastModel

# Backward compatibility alias
ForecastModel = CompanyForecastModel

__all__ = ['CompanyForecastModel', 'ForecastModel']
