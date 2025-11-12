"""
General-purpose measure implementations.

Contains measure types that apply across all domains:
- SimpleMeasure: Direct aggregations (avg, sum, min, max, count)
- ComputedMeasure: Expression-based calculations
- WeightedMeasure: Weighted aggregations
"""

from .simple import SimpleMeasure
from .computed import ComputedMeasure
from .weighted import WeightedMeasure

__all__ = [
    'SimpleMeasure',
    'ComputedMeasure',
    'WeightedMeasure',
]
