"""Forecast model package"""
from models.implemented.forecast.company_forecast_model import CompanyForecastModel

# Backward compatibility alias
ForecastModel = CompanyForecastModel

__all__ = ['CompanyForecastModel', 'ForecastModel']
