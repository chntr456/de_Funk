"""
Model builders for specialized table/view construction.

Contains builders for creating materialized views, aggregates, and other
derived tables from model configurations.
"""

from .weighted_aggregate_builder import WeightedAggregateBuilder

__all__ = ['WeightedAggregateBuilder']
