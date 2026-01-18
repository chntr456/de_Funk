"""
General-purpose measure implementations.

Contains measure types that apply across all domains:
- SimpleMeasure: Direct aggregations (avg, sum, min, max, count)
- ComputedMeasure: Expression-based calculations
"""

from .simple import SimpleMeasure
from .computed import ComputedMeasure

__all__ = [
    'SimpleMeasure',
    'ComputedMeasure',
]
