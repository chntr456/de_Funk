# Proposal 011: Pipeline Orchestration Refactor

**Status**: Draft
**Author**: de_Funk Team
**Date**: December 2025
**Priority**: High

## Problem Statement

The current pipeline implementation has several issues:

1. **Tight Coupling to Alpha Vantage** - Pipeline logic is mixed with provider-specific code
2. **Code Duplication** - Similar fetch/normalize/write patterns repeated across facets
3. **Inconsistent Logging** - Mix of print statements, warnings, and different progress formats
4. **No Performance Monitoring** - No visibility into step timings or bottlenecks
5. **Single Provider Design** - Difficult to add new data sources (city, BLS, etc.)
6. **Hardcoded Configuration** - Pipeline settings scattered across code

## Proposed Architecture

### 1. Pipeline Configuration System

Create YAML-driven pipeline definitions:

```yaml
# configs/pipelines/alpha_vantage_stocks.yaml
pipeline:
  name: alpha_vantage_stocks
  description: "Stock data ingestion from Alpha Vantage"
  provider: alpha_vantage

# Ingestion settings
ingestion:
  batch_size: 20              # Tickers per write batch
  rate_limit: 1.0             # Requests per second
  max_retries: 3
  timeout_seconds: 30

# Data types to fetch (in order)
data_types:
  - name: reference
    endpoint: company_overview
    table: securities_reference
    key_columns: [ticker]
    partitions: [snapshot_dt, asset_type]
    enabled: true

  - name: prices
    endpoint: time_series_daily_adjusted
    table: securities_prices_daily
    key_columns: [ticker, trade_date]
    partitions: [asset_type, year, month]
    enabled: true

  - name: income_statement
    endpoint: income_statement
    table: income_statements
    key_columns: [ticker, fiscal_date_ending, report_type]
    partitions: [report_type, snapshot_date]
    enabled: true
    # ... more data types

# Ticker selection
ticker_selection:
  method: market_cap          # market_cap, bulk_listing, explicit
  max_tickers: 100
  min_market_cap: 1e9

# Output settings
output:
  format: delta
  mode: upsert                # upsert, append, overwrite
```

```yaml
# configs/pipelines/chicago_finance.yaml
pipeline:
  name: chicago_finance
  description: "Chicago municipal finance data"
  provider: chicago

ingestion:
  batch_size: 50
  rate_limit: 5.0

data_types:
  - name: budget
    endpoint: budget_allocations
    table: city_budget
    key_columns: [department, fiscal_year]
    partitions: [fiscal_year]
```

### 2. Provider Abstraction Layer

```
datapipelines/
├── base/
│   ├── provider.py          # Abstract BaseProvider class
│   ├── ingestor.py          # Generic IngestorEngine
│   ├── progress_tracker.py  # Unified progress (existing)
│   └── metrics.py           # NEW: Performance metrics
├── providers/
│   ├── alpha_vantage/
│   │   ├── provider.py      # AlphaVantageProvider(BaseProvider)
│   │   └── facets/          # Unchanged
│   ├── chicago/
│   │   ├── provider.py      # ChicagoProvider(BaseProvider)
│   │   └── facets/
│   └── bls/
│       ├── provider.py      # BLSProvider(BaseProvider)
│       └── facets/
└── orchestration/
    ├── pipeline_runner.py   # Generic pipeline executor
    ├── pipeline_config.py   # Config loader
    └── run_metrics.py       # Metrics reporting
```

### 3. Base Provider Interface

```python
# datapipelines/base/provider.py
from abc import ABC, abstractmethod
from typing import List, Dict, Iterator, Optional
from dataclasses import dataclass

@dataclass
class FetchResult:
    """Result from a single API fetch."""
    ticker: str
    data_type: str
    success: bool
    data: Optional[Dict] = None
    error: Optional[str] = None
    elapsed_ms: float = 0.0

class BaseProvider(ABC):
    """Abstract base class for data providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name (e.g., 'alpha_vantage', 'chicago')."""
        pass

    @abstractmethod
    def get_tickers(self, method: str, **kwargs) -> List[str]:
        """Get list of tickers/entities to process."""
        pass

    @abstractmethod
    def fetch_data(self, ticker: str, data_type: str, **kwargs) -> FetchResult:
        """Fetch a single data type for a single ticker."""
        pass

    @abstractmethod
    def normalize(self, result: FetchResult, data_type_config: Dict) -> "DataFrame":
        """Normalize fetched data to DataFrame."""
        pass

    def get_facet(self, data_type: str) -> "BaseFacet":
        """Get the facet class for a data type."""
        pass
```

### 4. Generic Ingestor Engine

```python
# datapipelines/base/ingestor.py
class IngestorEngine:
    """
    Generic ingestion engine that works with any provider.

    Handles:
    - Batch processing with configurable batch size
    - Progress tracking with clean display
    - Performance metrics collection
    - Error handling and retry logic
    - Writing to Bronze layer
    """

    def __init__(
        self,
        provider: BaseProvider,
        config: PipelineConfig,
        spark: SparkSession,
        metrics: Optional[MetricsCollector] = None
    ):
        self.provider = provider
        self.config = config
        self.spark = spark
        self.metrics = metrics or MetricsCollector()
        self.sink = BronzeSink(config.storage)

    def run(self, tickers: List[str] = None) -> RunResult:
        """
        Execute the pipeline.

        Returns:
            RunResult with metrics, errors, and paths
        """
        # Get tickers if not provided
        if tickers is None:
            with self.metrics.time("ticker_selection"):
                tickers = self.provider.get_tickers(
                    method=self.config.ticker_selection.method,
                    **self.config.ticker_selection.params
                )

        total = len(tickers)
        batch_size = self.config.ingestion.batch_size
        num_batches = (total + batch_size - 1) // batch_size

        # Initialize progress tracker
        tracker = BatchProgressTracker(
            total_tickers=total,
            batch_size=batch_size,
            data_types=[dt.name for dt in self.config.data_types if dt.enabled]
        )

        results = RunResult()

        # Process in batches
        for batch_idx in range(num_batches):
            batch_start = batch_idx * batch_size
            batch_tickers = tickers[batch_start:batch_start + batch_size]

            tracker.start_batch(batch_idx + 1, num_batches, batch_tickers)

            # Process each ticker in batch
            batch_data = self._process_batch(batch_tickers, tracker)

            # Write batch to storage
            with self.metrics.time(f"write_batch_{batch_idx + 1}"):
                self._write_batch(batch_data, results)

            tracker.complete_batch()

        # Finalize
        results.metrics = self.metrics.summary()
        tracker.finish()

        return results

    def _process_batch(self, tickers: List[str], tracker) -> Dict:
        """Process a batch of tickers."""
        batch_data = {dt.name: [] for dt in self.config.data_types if dt.enabled}

        for ticker in tickers:
            for data_type in self.config.data_types:
                if not data_type.enabled:
                    continue

                # Fetch with timing
                with self.metrics.time(f"fetch_{data_type.name}"):
                    result = self.provider.fetch_data(
                        ticker=ticker,
                        data_type=data_type.name,
                        **data_type.params
                    )

                tracker.update(ticker, data_type.name, result.success, result.error)

                if result.success and result.data:
                    # Normalize with timing
                    with self.metrics.time(f"normalize_{data_type.name}"):
                        df = self.provider.normalize(result, data_type)
                        if df.count() > 0:
                            batch_data[data_type.name].append(df)

            tracker.complete_ticker(ticker)

        return batch_data
```

### 5. Performance Metrics System

```python
# datapipelines/base/metrics.py
from dataclasses import dataclass, field
from typing import Dict, List
import time

@dataclass
class StepMetric:
    """Metrics for a single step."""
    name: str
    count: int = 0
    total_ms: float = 0.0
    min_ms: float = float('inf')
    max_ms: float = 0.0
    errors: int = 0

    @property
    def avg_ms(self) -> float:
        return self.total_ms / self.count if self.count > 0 else 0.0

class MetricsCollector:
    """Collects performance metrics during pipeline execution."""

    def __init__(self):
        self.steps: Dict[str, StepMetric] = {}
        self.start_time = time.time()

    def time(self, step_name: str):
        """Context manager for timing a step."""
        return TimingContext(self, step_name)

    def record(self, step_name: str, elapsed_ms: float, error: bool = False):
        """Record a timing measurement."""
        if step_name not in self.steps:
            self.steps[step_name] = StepMetric(name=step_name)

        metric = self.steps[step_name]
        metric.count += 1
        metric.total_ms += elapsed_ms
        metric.min_ms = min(metric.min_ms, elapsed_ms)
        metric.max_ms = max(metric.max_ms, elapsed_ms)
        if error:
            metric.errors += 1

    def summary(self) -> Dict:
        """Generate summary report."""
        return {
            'total_elapsed_s': time.time() - self.start_time,
            'steps': {
                name: {
                    'count': m.count,
                    'total_s': m.total_ms / 1000,
                    'avg_ms': m.avg_ms,
                    'min_ms': m.min_ms,
                    'max_ms': m.max_ms,
                    'errors': m.errors
                }
                for name, m in self.steps.items()
            }
        }

    def print_report(self):
        """Print formatted metrics report."""
        summary = self.summary()

        print("\n" + "═" * 70)
        print("📊 PERFORMANCE METRICS")
        print("═" * 70)
        print(f"\nTotal Elapsed: {summary['total_elapsed_s']:.1f}s")
        print(f"\n{'Step':<30} {'Count':>8} {'Total(s)':>10} {'Avg(ms)':>10} {'Errors':>8}")
        print("─" * 70)

        for name, m in sorted(summary['steps'].items(), key=lambda x: -x[1]['total_s']):
            print(f"{name:<30} {m['count']:>8} {m['total_s']:>10.2f} {m['avg_ms']:>10.1f} {m['errors']:>8}")

        print("═" * 70 + "\n")
```

### 6. Batch Progress Tracker (Enhanced)

```python
# datapipelines/base/progress_tracker.py (additions)

class BatchProgressTracker:
    """
    Progress tracker with batch-aware display.

    Display format:
    ══════════════════════════════════════════════════════════════════════
    📦 Batch 2/5 | Overall: [████████░░░░░░░░░░░░] 40% (40/100) | ETA: 12m
    ──────────────────────────────────────────────────────────────────────
      AAPL [12/20] reference ✓ prices ✓ income ✓ balance ◯ cashflow ◯
    ══════════════════════════════════════════════════════════════════════
    """

    def __init__(
        self,
        total_tickers: int,
        batch_size: int,
        data_types: List[str]
    ):
        self.total_tickers = total_tickers
        self.batch_size = batch_size
        self.data_types = data_types
        self.num_batches = (total_tickers + batch_size - 1) // batch_size

        # State
        self.current_batch = 0
        self.batch_tickers: List[str] = []
        self.completed_tickers = 0
        self.ticker_progress: Dict[str, Dict[str, bool]] = {}
        self.start_time = time.time()

        self._progress_bar = ProgressBar(width=20)

    def start_batch(self, batch_num: int, total_batches: int, tickers: List[str]):
        """Start a new batch."""
        self.current_batch = batch_num
        self.batch_tickers = tickers
        self.ticker_progress = {t: {dt: None for dt in self.data_types} for t in tickers}

        self._print_batch_header()

    def _print_batch_header(self):
        """Print batch header with overall progress."""
        overall_pct = (self.completed_tickers / self.total_tickers * 100) if self.total_tickers > 0 else 0
        bar = self._progress_bar.render(overall_pct, self.completed_tickers, self.total_tickers)
        eta = self._calculate_eta()

        print()
        print("═" * 70)
        print(f"📦 Batch {self.current_batch}/{self.num_batches} | Overall: {bar} | ETA: {eta}")
        print("─" * 70)
        sys.stdout.flush()

    def update(self, ticker: str, data_type: str, success: bool, error: str = None):
        """Update progress for a ticker's data type."""
        if ticker in self.ticker_progress:
            self.ticker_progress[ticker][data_type] = success

        self._update_display(ticker, error)

    def _update_display(self, ticker: str, error: str = None):
        """Update the current line with ticker progress."""
        if ticker not in self.ticker_progress:
            return

        # Build status icons for each data type
        status_parts = []
        for dt in self.data_types:
            status = self.ticker_progress[ticker].get(dt)
            if status is None:
                icon = "◯"  # Not started
            elif status:
                icon = "✓"  # Success
            else:
                icon = "✗"  # Failed
            # Use short names for display
            short_name = dt[:3]
            status_parts.append(f"{short_name}:{icon}")

        # Position in batch
        batch_pos = self.batch_tickers.index(ticker) + 1 if ticker in self.batch_tickers else 0

        status_str = " ".join(status_parts)
        line = f"\r  {ticker:8} [{batch_pos:2}/{len(self.batch_tickers)}] {status_str}"

        if error:
            line += f" | {error[:30]}"

        sys.stdout.write(line.ljust(90))
        sys.stdout.flush()

    def complete_ticker(self, ticker: str):
        """Mark ticker as complete."""
        self.completed_tickers += 1
        # Move to next line after ticker completes
        print()

    def complete_batch(self):
        """Mark current batch as complete."""
        print("─" * 70)
        print(f"  ✓ Batch {self.current_batch} complete: {len(self.batch_tickers)} tickers written to Delta Lake")
        sys.stdout.flush()

    def _calculate_eta(self) -> str:
        """Calculate ETA based on current pace."""
        if self.completed_tickers == 0:
            return "..."
        elapsed = time.time() - self.start_time
        rate = self.completed_tickers / elapsed
        remaining = self.total_tickers - self.completed_tickers
        eta_seconds = remaining / rate if rate > 0 else 0
        return format_duration(eta_seconds)

    def finish(self):
        """Print final summary."""
        elapsed = time.time() - self.start_time
        print()
        print("═" * 70)
        print(f"✓ Ingestion Complete: {self.completed_tickers}/{self.total_tickers} tickers in {format_duration(elapsed)}")
        print("═" * 70)
```

### 7. Pipeline Runner CLI

```python
# scripts/run_pipeline.py
"""
Generic Pipeline Runner

Usage:
    # Run Alpha Vantage stocks pipeline
    python -m scripts.run_pipeline --config alpha_vantage_stocks --max-tickers 100

    # Run Chicago finance pipeline
    python -m scripts.run_pipeline --config chicago_finance

    # Run with custom settings
    python -m scripts.run_pipeline --config alpha_vantage_stocks --batch-size 20 --skip-fundamentals

    # Dry run (show what would be done)
    python -m scripts.run_pipeline --config alpha_vantage_stocks --dry-run
"""

def main():
    parser = argparse.ArgumentParser(description="Run data pipeline")

    parser.add_argument('--config', required=True, help='Pipeline config name')
    parser.add_argument('--max-tickers', type=int, help='Override max tickers')
    parser.add_argument('--batch-size', type=int, help='Override batch size')
    parser.add_argument('--dry-run', action='store_true', help='Show plan without executing')
    parser.add_argument('--skip-fundamentals', action='store_true')
    parser.add_argument('--skip-silver', action='store_true')
    parser.add_argument('--skip-forecasts', action='store_true')

    args = parser.parse_args()

    # Load config
    config = PipelineConfig.load(args.config)

    # Apply overrides
    if args.max_tickers:
        config.ticker_selection.max_tickers = args.max_tickers
    if args.batch_size:
        config.ingestion.batch_size = args.batch_size

    # Get provider
    provider = get_provider(config.pipeline.provider)

    # Run with metrics
    metrics = MetricsCollector()
    engine = IngestorEngine(provider, config, spark, metrics)

    result = engine.run()

    # Print metrics report
    metrics.print_report()
```

## Migration Plan

### Phase 1: Foundation (This PR)
1. Create `datapipelines/base/metrics.py`
2. Enhance `progress_tracker.py` with `BatchProgressTracker`
3. Update ingestor to use metrics and new progress tracker
4. Change default batch_write_size to 20

### Phase 2: Configuration (Next PR)
1. Create `configs/pipelines/` directory structure
2. Implement `PipelineConfig` loader
3. Create Alpha Vantage pipeline config YAML
4. Refactor `run_full_pipeline.py` to use config

### Phase 3: Provider Abstraction (Future PR)
1. Create `BaseProvider` abstract class
2. Refactor `AlphaVantageIngestor` → `AlphaVantageProvider`
3. Create `ChicagoProvider` for city data
4. Create `IngestorEngine` generic runner

### Phase 4: Unified Runner (Future PR)
1. Create `scripts/run_pipeline.py` generic runner
2. Deprecate provider-specific scripts
3. Add dry-run and validation modes

## Immediate Actions (This Session)

For now, let's implement the quick wins:

1. **Add MetricsCollector** to track timing
2. **Update BatchProgressTracker** with cleaner display
3. **Change default batch_write_size to 20**
4. **Clean up logging inconsistencies**
5. **Add metrics report at end of run**

## Benefits

1. **Extensible** - Easy to add new providers (city, BLS, etc.)
2. **Configurable** - YAML-driven pipeline definitions
3. **Observable** - Built-in metrics and progress tracking
4. **Maintainable** - Less code duplication
5. **Testable** - Provider abstraction enables mocking
6. **User-Friendly** - Clean, consistent progress display
