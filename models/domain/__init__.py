"""
Domain models - business-specific data models.

Domain models depend on foundation models (temporal, geography) and
may have dependencies on other domain models:

Securities:
- company: Corporate entities with SEC registration and fundamentals
- stocks: Stock securities with OHLCV prices and technical indicators
- options: Options contracts with Greeks (partial implementation)
- etf: Exchange-traded funds with holdings (skeleton)

Analytics:
- forecast: Time series forecasting models
- macro: Macroeconomic indicators (BLS data)
- city_finance: Municipal finance data (Chicago)
- actuarial: Mortality, demographics, and insurance risk analysis
"""
# Import models as they're needed - avoid circular imports
# Models should be imported directly from their module paths

__all__ = [
    'CompanyModel',
    'StocksModel',
    'ForecastModel',
    'MacroModel',
    'CityFinanceModel',
    'ActuarialModel',
]
