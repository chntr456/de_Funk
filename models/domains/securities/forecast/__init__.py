"""
Forecast model for securities price and volume predictions.

This module provides time series forecasting using ARIMA, Prophet, and
Random Forest models for stock price and volume predictions.
"""
from models.domains.securities.forecast.model import ForecastModel

__all__ = ['ForecastModel']
