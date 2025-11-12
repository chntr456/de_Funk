"""
Equity-specific calculation patterns.

Contains weighting strategies and other equity-specific calculations.
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

__all__ = [
    'WeightingStrategy',
    'EqualWeightStrategy',
    'VolumeWeightStrategy',
    'MarketCapWeightStrategy',
    'PriceWeightStrategy',
    'VolumeDeviationWeightStrategy',
    'VolatilityWeightStrategy',
    'get_weighting_strategy',
]
