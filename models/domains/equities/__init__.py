"""
Equity-specific calculation patterns.

Contains:
- Weighting strategies (equal, volume, market cap, price, volatility)
- Technical indicators (SMA, RSI, MACD, Bollinger Bands, etc.)
- Risk metrics (beta, volatility, Sharpe ratio, max drawdown, alpha)
"""

from .weighting import (
    WeightingStrategy,
    EqualWeightStrategy,
    VolumeWeightStrategy,
    MarketCapWeightStrategy,
    PriceWeightStrategy,
    VolumeDeviationWeightStrategy,
    VolatilityWeightStrategy,
    get_weighting_strategy,
)

from .technical import (
    TechnicalIndicatorStrategy,
    SMAStrategy,
    EMAStrategy,
    RSIStrategy,
    MACDStrategy,
    BollingerBandsStrategy,
    ATRStrategy,
    OBVStrategy,
    get_technical_indicator_strategy,
)

from .risk import (
    RiskMetricStrategy,
    BetaStrategy,
    VolatilityStrategy as RiskVolatilityStrategy,  # Alias to avoid conflict
    SharpeRatioStrategy,
    MaxDrawdownStrategy,
    AlphaStrategy,
    get_risk_metric_strategy,
)

__all__ = [
    # Weighting strategies
    'WeightingStrategy',
    'EqualWeightStrategy',
    'VolumeWeightStrategy',
    'MarketCapWeightStrategy',
    'PriceWeightStrategy',
    'VolumeDeviationWeightStrategy',
    'VolatilityWeightStrategy',
    'get_weighting_strategy',
    # Technical indicators
    'TechnicalIndicatorStrategy',
    'SMAStrategy',
    'EMAStrategy',
    'RSIStrategy',
    'MACDStrategy',
    'BollingerBandsStrategy',
    'ATRStrategy',
    'OBVStrategy',
    'get_technical_indicator_strategy',
    # Risk metrics
    'RiskMetricStrategy',
    'BetaStrategy',
    'RiskVolatilityStrategy',
    'SharpeRatioStrategy',
    'MaxDrawdownStrategy',
    'AlphaStrategy',
    'get_risk_metric_strategy',
]
