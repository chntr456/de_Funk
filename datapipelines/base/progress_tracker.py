"""
Progress Tracker for Pipeline Operations.

Provides clean, non-flooding status updates for long-running pipeline operations.
Uses in-place terminal updates with progress bars for visual feedback.

Key Features:
- Single-line updating status (no terminal flooding)
- Multi-phase progress tracking (reference → prices → fundamentals)
- Overall progress across entire pipeline run
- ETA calculation based on current pace
- Both console and log output support

Usage:
    from datapipelines.base.progress_tracker import PipelineProgressTracker

    # Create tracker for overall pipeline
    tracker = PipelineProgressTracker(
        total_tickers=100,
        phases=['reference', 'prices', 'income', 'balance', 'cashflow', 'earnings']
    )

    # Update progress for a phase
    tracker.update('reference', ticker='AAPL', success=True)
    tracker.update('prices', ticker='AAPL', success=True)
    tracker.complete_ticker('AAPL')  # Mark ticker as fully complete

    # At end of run
    tracker.finish()  # Print final summary

Author: de_Funk Team
Date: December 2025
"""

from __future__ import annotations

import sys
import time
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta

from config.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PhaseProgress:
    """Progress tracking for a single phase (e.g., 'prices', 'earnings')."""
    name: str
    total: int = 0
    completed: int = 0
    errors: int = 0
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    current_ticker: str = ""

    @property
    def percent(self) -> float:
        """Percentage complete (0-100)."""
        return (self.completed / self.total * 100) if self.total > 0 else 0.0

    @property
    def elapsed_seconds(self) -> float:
        """Seconds elapsed since phase started."""
        if self.start_time is None:
            return 0.0
        end = self.end_time if self.end_time else time.time()
        return end - self.start_time

    @property
    def eta_seconds(self) -> Optional[float]:
        """Estimated seconds remaining for this phase."""
        if self.completed == 0 or self.elapsed_seconds == 0:
            return None
        rate = self.completed / self.elapsed_seconds
        remaining = self.total - self.completed
        return remaining / rate if rate > 0 else None

    @property
    def is_complete(self) -> bool:
        """Whether this phase is complete."""
        return self.completed >= self.total and self.total > 0


@dataclass
class PipelineStats:
    """Overall pipeline statistics."""
    total_tickers: int = 0
    completed_tickers: int = 0
    total_api_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    start_time: Optional[float] = None
    end_time: Optional[float] = None

    @property
    def elapsed_seconds(self) -> float:
        """Total elapsed time."""
        if self.start_time is None:
            return 0.0
        end = self.end_time if self.end_time else time.time()
        return end - self.start_time

    def format_elapsed(self) -> str:
        """Format elapsed time as human-readable string."""
        return format_duration(self.elapsed_seconds)


def format_duration(seconds: float) -> str:
    """Format seconds as human-readable duration string."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        mins = seconds / 60
        return f"{mins:.1f}m"
    else:
        hours = seconds / 3600
        mins = (seconds % 3600) / 60
        return f"{hours:.0f}h {mins:.0f}m"


def format_eta(seconds: Optional[float]) -> str:
    """Format ETA as human-readable string."""
    if seconds is None:
        return "..."
    return format_duration(seconds)


class ProgressBar:
    """
    Renders a text-based progress bar.

    Example output:
        [████████████░░░░░░░░] 60% (30/50)
    """

    def __init__(self, width: int = 30, fill_char: str = "█", empty_char: str = "░"):
        self.width = width
        self.fill_char = fill_char
        self.empty_char = empty_char

    def render(self, percent: float, current: int = 0, total: int = 0) -> str:
        """Render progress bar string."""
        filled = int(self.width * percent / 100)
        empty = self.width - filled
        bar = self.fill_char * filled + self.empty_char * empty

        if total > 0:
            return f"[{bar}] {percent:5.1f}% ({current}/{total})"
        else:
            return f"[{bar}] {percent:5.1f}%"


class PipelineProgressTracker:
    """
    Unified progress tracker for pipeline operations.

    Tracks progress across multiple phases and provides clean console output
    that doesn't flood the terminal.

    Features:
    - In-place terminal updates (single line that updates)
    - Multi-phase progress tracking
    - Overall ticker completion tracking
    - ETA calculation
    - Summary statistics

    Usage:
        tracker = PipelineProgressTracker(
            total_tickers=100,
            phases=['reference', 'prices', 'income', 'balance', 'cashflow', 'earnings'],
            show_phase_bars=True
        )

        # For each API call
        tracker.update_phase('reference', 'AAPL', success=True)

        # When all data for a ticker is complete
        tracker.complete_ticker('AAPL')

        # At end
        tracker.finish()
    """

    def __init__(
        self,
        total_tickers: int = 0,
        phases: Optional[List[str]] = None,
        show_phase_bars: bool = True,
        show_overall_bar: bool = True,
        update_interval: float = 0.5,  # Min seconds between display updates
        silent: bool = False,  # Suppress all console output
    ):
        """
        Initialize progress tracker.

        Args:
            total_tickers: Total number of tickers to process
            phases: List of phase names (e.g., ['reference', 'prices', ...])
            show_phase_bars: Show per-phase progress bars
            show_overall_bar: Show overall progress bar
            update_interval: Minimum seconds between display updates
            silent: If True, suppress console output (still logs)
        """
        self.stats = PipelineStats(total_tickers=total_tickers)
        self.phases: Dict[str, PhaseProgress] = {}
        self.show_phase_bars = show_phase_bars
        self.show_overall_bar = show_overall_bar
        self.update_interval = update_interval
        self.silent = silent

        # Initialize phases
        if phases:
            for phase_name in phases:
                self.phases[phase_name] = PhaseProgress(
                    name=phase_name,
                    total=total_tickers
                )

        # Tracking state
        self._completed_tickers: Set[str] = set()
        self._last_display_time: float = 0.0
        self._lock = threading.Lock()
        self._progress_bar = ProgressBar(width=25)
        self._current_phase: str = ""
        self._lines_printed: int = 0

        # Start time
        self.stats.start_time = time.time()

    def set_phase_total(self, phase: str, total: int) -> None:
        """Set the total count for a specific phase."""
        with self._lock:
            if phase not in self.phases:
                self.phases[phase] = PhaseProgress(name=phase, total=total)
            else:
                self.phases[phase].total = total

    def start_phase(self, phase: str, total: int = 0) -> None:
        """Mark a phase as started."""
        with self._lock:
            if phase not in self.phases:
                self.phases[phase] = PhaseProgress(name=phase, total=total)

            self.phases[phase].start_time = time.time()
            self.phases[phase].total = total if total > 0 else self.phases[phase].total
            self._current_phase = phase

            # Print phase header
            if not self.silent:
                self._print_phase_header(phase)

    def _print_phase_header(self, phase: str) -> None:
        """Print a clean phase header."""
        phase_display = phase.replace('_', ' ').title()
        print(f"\n{'─' * 50}")
        print(f"📊 Phase: {phase_display}")
        print(f"{'─' * 50}")
        sys.stdout.flush()

    def update_phase(
        self,
        phase: str,
        ticker: str,
        success: bool = True,
        error: Optional[str] = None,
        force_display: bool = False
    ) -> None:
        """
        Update progress for a specific phase.

        Args:
            phase: Phase name (e.g., 'reference', 'prices')
            ticker: Current ticker being processed
            success: Whether the operation succeeded
            error: Error message if failed
            force_display: Force immediate display update
        """
        with self._lock:
            # Ensure phase exists
            if phase not in self.phases:
                self.phases[phase] = PhaseProgress(name=phase, total=self.stats.total_tickers)
                self.phases[phase].start_time = time.time()

            phase_progress = self.phases[phase]
            phase_progress.completed += 1
            phase_progress.current_ticker = ticker

            # Update stats
            self.stats.total_api_calls += 1
            if success:
                self.stats.successful_calls += 1
            else:
                self.stats.failed_calls += 1
                phase_progress.errors += 1

            # Log (always)
            if success:
                logger.debug(f"[{phase}] {ticker} ({phase_progress.completed}/{phase_progress.total})")
            else:
                logger.warning(f"[{phase}] {ticker} failed: {error}")

            # Update display if enough time has passed
            now = time.time()
            if force_display or (now - self._last_display_time >= self.update_interval):
                self._last_display_time = now
                self._update_display(phase, ticker, success, error)

    def _update_display(
        self,
        phase: str,
        ticker: str,
        success: bool,
        error: Optional[str]
    ) -> None:
        """Update the console display with current progress."""
        if self.silent:
            return

        phase_progress = self.phases[phase]

        # Build status line
        status_icon = "✓" if success else "✗"
        eta_str = format_eta(phase_progress.eta_seconds)
        bar = self._progress_bar.render(
            phase_progress.percent,
            phase_progress.completed,
            phase_progress.total
        )

        # Error suffix
        error_str = f" | {error[:40]}" if error else ""

        # Build the status line
        status_line = f"\r  {status_icon} {ticker:8} {bar} | ETA: {eta_str}{error_str}"

        # Pad to clear previous line content
        status_line = status_line.ljust(100)

        # Print with carriage return (overwrites current line)
        sys.stdout.write(status_line)
        sys.stdout.flush()

    def complete_phase(self, phase: str) -> None:
        """Mark a phase as complete and print summary."""
        with self._lock:
            if phase in self.phases:
                self.phases[phase].end_time = time.time()
                phase_progress = self.phases[phase]

                if not self.silent:
                    # Clear the status line
                    sys.stdout.write("\r" + " " * 100 + "\r")

                    # Print phase completion summary
                    elapsed = format_duration(phase_progress.elapsed_seconds)
                    success_rate = (
                        (phase_progress.completed - phase_progress.errors)
                        / phase_progress.completed * 100
                        if phase_progress.completed > 0 else 0
                    )
                    print(f"  ✓ {phase}: {phase_progress.completed} items "
                          f"({success_rate:.1f}% success) in {elapsed}")
                    sys.stdout.flush()

    def complete_ticker(self, ticker: str) -> None:
        """Mark a ticker as fully complete (all phases done for this ticker)."""
        with self._lock:
            if ticker not in self._completed_tickers:
                self._completed_tickers.add(ticker)
                self.stats.completed_tickers += 1

    def get_overall_progress(self) -> float:
        """Get overall progress percentage (0-100)."""
        if self.stats.total_tickers == 0:
            return 0.0
        return self.stats.completed_tickers / self.stats.total_tickers * 100

    def print_overall_status(self) -> None:
        """Print overall pipeline status (called periodically or on demand)."""
        if self.silent:
            return

        with self._lock:
            overall_pct = self.get_overall_progress()
            bar = self._progress_bar.render(
                overall_pct,
                self.stats.completed_tickers,
                self.stats.total_tickers
            )
            elapsed = format_duration(self.stats.elapsed_seconds)

            print(f"\n{'═' * 60}")
            print(f"📈 Overall Progress: {bar}")
            print(f"   Elapsed: {elapsed} | API Calls: {self.stats.total_api_calls} "
                  f"(✓{self.stats.successful_calls} ✗{self.stats.failed_calls})")
            print(f"{'═' * 60}\n")
            sys.stdout.flush()

    def finish(self) -> Dict:
        """
        Finalize tracking and print summary.

        Returns:
            Dictionary with final statistics
        """
        self.stats.end_time = time.time()

        if not self.silent:
            # Clear any in-progress line
            sys.stdout.write("\r" + " " * 100 + "\r")

            print("\n" + "═" * 60)
            print("📊 PIPELINE COMPLETE")
            print("═" * 60)

            # Overall stats
            elapsed = format_duration(self.stats.elapsed_seconds)
            print(f"\n  Total Time: {elapsed}")
            print(f"  Tickers Processed: {self.stats.completed_tickers}/{self.stats.total_tickers}")
            print(f"  API Calls: {self.stats.total_api_calls}")
            print(f"    ✓ Success: {self.stats.successful_calls}")
            print(f"    ✗ Failed: {self.stats.failed_calls}")

            # Per-phase summary
            if self.phases:
                print(f"\n  Phases:")
                for phase_name, phase in self.phases.items():
                    if phase.total > 0:
                        elapsed = format_duration(phase.elapsed_seconds)
                        error_pct = (phase.errors / phase.completed * 100) if phase.completed > 0 else 0
                        print(f"    {phase_name:20} {phase.completed:5}/{phase.total} "
                              f"({elapsed}, {error_pct:.1f}% errors)")

            print("\n" + "═" * 60 + "\n")
            sys.stdout.flush()

        # Return stats as dict
        return {
            'total_tickers': self.stats.total_tickers,
            'completed_tickers': self.stats.completed_tickers,
            'total_api_calls': self.stats.total_api_calls,
            'successful_calls': self.stats.successful_calls,
            'failed_calls': self.stats.failed_calls,
            'elapsed_seconds': self.stats.elapsed_seconds,
            'phases': {
                name: {
                    'completed': p.completed,
                    'errors': p.errors,
                    'elapsed_seconds': p.elapsed_seconds
                }
                for name, p in self.phases.items()
            }
        }


class TickerProgressCallback:
    """
    Progress callback adapter for existing _fetch_calls interface.

    This allows the new progress tracker to integrate with the existing
    ingestor methods that use the ProgressCallback protocol.

    Usage:
        tracker = PipelineProgressTracker(...)
        callback = TickerProgressCallback(tracker, phase='reference')

        # Pass to existing methods
        ingestor._fetch_calls(calls, progress_callback=callback)
    """

    def __init__(self, tracker: PipelineProgressTracker, phase: str):
        self.tracker = tracker
        self.phase = phase

    def __call__(self, info) -> None:
        """Handle progress info from _fetch_calls."""
        self.tracker.update_phase(
            phase=self.phase,
            ticker=info.ticker,
            success=info.success,
            error=info.error
        )


class BatchProgressTracker:
    """
    Progress tracker with batch-aware display for per-ticker ingestion.

    Displays progress in a clean format showing:
    - Overall progress across all tickers
    - Current batch info (batch X of Y)
    - Per-ticker progress within the batch
    - Data type status for current ticker

    Display format:
    ══════════════════════════════════════════════════════════════════════════════
    📦 Batch 2/5 | Overall: [████████░░░░░░░░░░░░] 40% (40/100) | ETA: 12m 30s
    ──────────────────────────────────────────────────────────────────────────────
      AAPL [12/20] ref:✓ prc:✓ inc:✓ bal:◯ csh:◯ ern:◯
    ══════════════════════════════════════════════════════════════════════════════

    Usage:
        tracker = BatchProgressTracker(
            total_tickers=100,
            batch_size=20,
            data_types=['reference', 'prices', 'income', 'balance', 'cashflow', 'earnings']
        )

        tracker.start_batch(1, 5, batch_tickers)
        for ticker in batch_tickers:
            tracker.update(ticker, 'reference', success=True)
            tracker.update(ticker, 'prices', success=True)
            tracker.complete_ticker(ticker)
        tracker.complete_batch()

        tracker.finish()
    """

    # Short names for data types (max 3 chars for compact display)
    DATA_TYPE_SHORT_NAMES = {
        'reference': 'ref',
        'prices': 'prc',
        'income': 'inc',
        'income_statement': 'inc',
        'balance': 'bal',
        'balance_sheet': 'bal',
        'cashflow': 'csh',
        'cash_flow': 'csh',
        'earnings': 'ern',
    }

    def __init__(
        self,
        total_tickers: int,
        batch_size: int,
        data_types: List[str],
        silent: bool = False
    ):
        """
        Initialize batch progress tracker.

        Args:
            total_tickers: Total number of tickers to process
            batch_size: Number of tickers per batch
            data_types: List of data type names to track
            silent: If True, suppress console output
        """
        self.total_tickers = total_tickers
        self.batch_size = batch_size
        self.data_types = data_types
        self.silent = silent
        self.num_batches = (total_tickers + batch_size - 1) // batch_size if batch_size > 0 else 1

        # State
        self.current_batch = 0
        self.current_batch_tickers: List[str] = []
        self.completed_tickers = 0
        self.total_errors = 0
        self.ticker_status: Dict[str, Dict[str, Optional[bool]]] = {}
        self.start_time = time.time()

        # For ETA calculation
        self._progress_bar = ProgressBar(width=20)

    def start_batch(self, batch_num: int, total_batches: int, tickers: List[str]):
        """
        Start a new batch.

        Args:
            batch_num: Current batch number (1-indexed)
            total_batches: Total number of batches
            tickers: List of tickers in this batch
        """
        self.current_batch = batch_num
        self.current_batch_tickers = tickers
        self.ticker_status = {
            t: {dt: None for dt in self.data_types}
            for t in tickers
        }

        if not self.silent:
            self._print_batch_header()

    def _print_batch_header(self):
        """Print batch header with overall progress bar."""
        overall_pct = (self.completed_tickers / self.total_tickers * 100) if self.total_tickers > 0 else 0
        bar = self._progress_bar.render(overall_pct, self.completed_tickers, self.total_tickers)
        eta = self._calculate_eta()

        print()
        print("═" * 80)
        print(f"📦 Batch {self.current_batch}/{self.num_batches} | Overall: {bar} | ETA: {eta}")
        print("─" * 80)
        sys.stdout.flush()

    def update(
        self,
        ticker: str,
        data_type: str,
        success: bool,
        error: Optional[str] = None
    ):
        """
        Update progress for a ticker's data type.

        Args:
            ticker: Ticker symbol
            data_type: Data type name (e.g., 'reference', 'prices')
            success: Whether the operation succeeded
            error: Error message if failed
        """
        if ticker in self.ticker_status:
            self.ticker_status[ticker][data_type] = success
            if not success:
                self.total_errors += 1

        if not self.silent:
            self._update_display(ticker, error)

    def _update_display(self, ticker: str, error: Optional[str] = None):
        """Update the current line with ticker progress."""
        if ticker not in self.ticker_status:
            return

        # Build status icons for each data type
        status_parts = []
        for dt in self.data_types:
            status = self.ticker_status[ticker].get(dt)
            if status is None:
                icon = "◯"  # Not started
            elif status:
                icon = "✓"  # Success
            else:
                icon = "✗"  # Failed

            # Get short name
            short_name = self.DATA_TYPE_SHORT_NAMES.get(dt, dt[:3])
            status_parts.append(f"{short_name}:{icon}")

        # Position in batch
        try:
            batch_pos = self.current_batch_tickers.index(ticker) + 1
        except ValueError:
            batch_pos = 0

        status_str = " ".join(status_parts)
        line = f"\r  {ticker:8} [{batch_pos:2}/{len(self.current_batch_tickers)}] {status_str}"

        if error:
            line += f" | {error[:25]}"

        # Pad and write
        sys.stdout.write(line.ljust(95))
        sys.stdout.flush()

    def complete_ticker(self, ticker: str):
        """
        Mark a ticker as complete.

        Args:
            ticker: Ticker symbol that completed
        """
        self.completed_tickers += 1
        if not self.silent:
            print()  # Move to next line after ticker completes
            sys.stdout.flush()

    def complete_batch(self, write_time_ms: float = 0):
        """
        Mark current batch as complete.

        Args:
            write_time_ms: Time spent writing to Delta Lake (for metrics display)
        """
        if not self.silent:
            batch_tickers_count = len(self.current_batch_tickers)
            write_info = f" | Write: {write_time_ms/1000:.1f}s" if write_time_ms > 0 else ""
            print("─" * 80)
            print(f"  ✓ Batch {self.current_batch} complete: "
                  f"{batch_tickers_count} tickers written to Delta Lake{write_info}")
            sys.stdout.flush()

    def _calculate_eta(self) -> str:
        """Calculate ETA based on current pace."""
        if self.completed_tickers == 0:
            return "calculating..."
        elapsed = time.time() - self.start_time
        rate = self.completed_tickers / elapsed
        remaining = self.total_tickers - self.completed_tickers
        eta_seconds = remaining / rate if rate > 0 else 0
        return format_duration(eta_seconds)

    def finish(self) -> Dict:
        """
        Print final summary and return statistics.

        Returns:
            Dictionary with final statistics
        """
        elapsed = time.time() - self.start_time

        if not self.silent:
            print()
            print("═" * 80)
            print(f"✓ INGESTION COMPLETE")
            print("═" * 80)
            print(f"  Tickers: {self.completed_tickers}/{self.total_tickers}")
            print(f"  Batches: {self.current_batch}/{self.num_batches}")
            print(f"  Errors: {self.total_errors}")
            print(f"  Elapsed: {format_duration(elapsed)}")
            print("═" * 80)
            print()
            sys.stdout.flush()

        return {
            'total_tickers': self.total_tickers,
            'completed_tickers': self.completed_tickers,
            'num_batches': self.num_batches,
            'total_errors': self.total_errors,
            'elapsed_seconds': elapsed
        }
