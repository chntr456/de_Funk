"""
Performance Metrics Collector for Pipeline Operations.

Provides timing and statistics collection for monitoring pipeline performance.
Helps identify bottlenecks and track execution time for each step.

Usage:
    from de_funk.pipelines.base.metrics import MetricsCollector

    metrics = MetricsCollector()

    # Time a step
    with metrics.time("fetch_prices"):
        data = fetch_prices(ticker)

    # Or manually record
    start = time.time()
    do_something()
    metrics.record("my_step", (time.time() - start) * 1000)

    # Print report at end
    metrics.print_report()

Author: de_Funk Team
Date: December 2025
"""

from __future__ import annotations

import time
import sys
from dataclasses import dataclass, field
from typing import Dict, Optional
from contextlib import contextmanager

from de_funk.config.logging import get_logger

logger = get_logger(__name__)


@dataclass
class StepMetric:
    """Metrics for a single step/operation."""
    name: str
    count: int = 0
    total_ms: float = 0.0
    min_ms: float = float('inf')
    max_ms: float = 0.0
    errors: int = 0

    @property
    def avg_ms(self) -> float:
        """Average time in milliseconds."""
        return self.total_ms / self.count if self.count > 0 else 0.0

    @property
    def total_seconds(self) -> float:
        """Total time in seconds."""
        return self.total_ms / 1000.0

    def record(self, elapsed_ms: float, error: bool = False):
        """Record a single measurement."""
        self.count += 1
        self.total_ms += elapsed_ms
        self.min_ms = min(self.min_ms, elapsed_ms)
        self.max_ms = max(self.max_ms, elapsed_ms)
        if error:
            self.errors += 1


class TimingContext:
    """Context manager for timing operations."""

    def __init__(self, collector: 'MetricsCollector', step_name: str):
        self.collector = collector
        self.step_name = step_name
        self.start_time: float = 0.0
        self.error: bool = False

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed_ms = (time.time() - self.start_time) * 1000
        self.error = exc_type is not None
        self.collector.record(self.step_name, elapsed_ms, self.error)
        return False  # Don't suppress exceptions


class MetricsCollector:
    """
    Collects performance metrics during pipeline execution.

    Tracks timing for each step and provides summary reports.

    Example:
        metrics = MetricsCollector()

        for ticker in tickers:
            with metrics.time("fetch_reference"):
                fetch_reference(ticker)

            with metrics.time("fetch_prices"):
                fetch_prices(ticker)

            with metrics.time("write_delta"):
                write_to_delta(df)

        metrics.print_report()
    """

    def __init__(self, name: str = "pipeline"):
        """
        Initialize metrics collector.

        Args:
            name: Name for this metrics collection (for logging)
        """
        self.name = name
        self.steps: Dict[str, StepMetric] = {}
        self.start_time = time.time()
        self.end_time: Optional[float] = None

    def time(self, step_name: str) -> TimingContext:
        """
        Context manager for timing a step.

        Usage:
            with metrics.time("fetch_prices"):
                data = api.fetch(ticker)

        Args:
            step_name: Name of the step being timed

        Returns:
            TimingContext that records elapsed time on exit
        """
        return TimingContext(self, step_name)

    def record(self, step_name: str, elapsed_ms: float, error: bool = False):
        """
        Record a timing measurement.

        Args:
            step_name: Name of the step
            elapsed_ms: Elapsed time in milliseconds
            error: Whether an error occurred
        """
        if step_name not in self.steps:
            self.steps[step_name] = StepMetric(name=step_name)

        self.steps[step_name].record(elapsed_ms, error)

        # Also log at debug level
        logger.debug(f"[metrics] {step_name}: {elapsed_ms:.1f}ms" +
                     (" (error)" if error else ""))

    def finish(self):
        """Mark metrics collection as complete."""
        self.end_time = time.time()

    @property
    def elapsed_seconds(self) -> float:
        """Total elapsed time in seconds."""
        end = self.end_time if self.end_time else time.time()
        return end - self.start_time

    def summary(self) -> Dict:
        """
        Generate summary dictionary.

        Returns:
            Dict with total elapsed time and per-step metrics
        """
        return {
            'name': self.name,
            'total_elapsed_s': self.elapsed_seconds,
            'steps': {
                name: {
                    'count': m.count,
                    'total_s': m.total_seconds,
                    'avg_ms': m.avg_ms,
                    'min_ms': m.min_ms if m.min_ms != float('inf') else 0,
                    'max_ms': m.max_ms,
                    'errors': m.errors
                }
                for name, m in self.steps.items()
            }
        }

    def print_report(self):
        """Print formatted metrics report to console."""
        self.finish()
        summary = self.summary()

        print()
        print("═" * 80)
        print(f"📊 PERFORMANCE METRICS: {self.name}")
        print("═" * 80)
        print(f"\n  Total Elapsed: {summary['total_elapsed_s']:.1f}s")

        if not self.steps:
            print("  No steps recorded.")
            print("═" * 80)
            return

        # Sort by total time descending
        sorted_steps = sorted(
            summary['steps'].items(),
            key=lambda x: -x[1]['total_s']
        )

        print(f"\n  {'Step':<35} {'Count':>8} {'Total(s)':>10} {'Avg(ms)':>10} {'Min(ms)':>10} {'Max(ms)':>10} {'Errors':>8}")
        print("  " + "─" * 91)

        for name, m in sorted_steps:
            print(f"  {name:<35} {m['count']:>8} {m['total_s']:>10.2f} {m['avg_ms']:>10.1f} "
                  f"{m['min_ms']:>10.1f} {m['max_ms']:>10.1f} {m['errors']:>8}")

        print()
        print("═" * 80)
        print()
        sys.stdout.flush()

    def get_slowest_steps(self, n: int = 5) -> list:
        """
        Get the N slowest steps by total time.

        Args:
            n: Number of steps to return

        Returns:
            List of (step_name, total_seconds) tuples
        """
        sorted_steps = sorted(
            self.steps.items(),
            key=lambda x: -x[1].total_seconds
        )
        return [(name, step.total_seconds) for name, step in sorted_steps[:n]]
