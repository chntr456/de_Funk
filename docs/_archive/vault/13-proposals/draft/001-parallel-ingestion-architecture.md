# Proposal: Parallel Ingestion Architecture & Offloading

**Status**: Draft
**Author**: Claude
**Date**: 2025-11-29
**Updated**: 2025-12-02
**Priority**: High

---

## Current Implementation Status (Dec 2025)

### What Was Implemented

| Feature | Status | Notes |
|---------|--------|-------|
| `REALTIME_BULK_QUOTES` endpoint | ✅ Added | 100 symbols per call |
| `refresh_market_cap_rankings.py` | ✅ Created | Standalone OVERVIEW ingestion |
| `--skip-silver-build` flag | ✅ Added | Separate build from forecast |
| Time estimation | ✅ Added | Shows estimated runtime before long operations |
| Confirmation prompts | ✅ Added | User approval for 2+ hour operations |

### What Was NOT Implemented

| Feature | Status | Notes |
|---------|--------|-------|
| Celery task queue | ❌ Not started | Proposal only |
| Redis backend | ❌ Not started | Proposal only |
| Token bucket rate limiter | ❌ Not started | Still using simple throttle |
| Checkpoint/resume | ❌ Not started | No crash recovery |
| Circuit breaker | ❌ Not started | Proposal only |
| Scheduled jobs | ❌ Not started | Manual execution only |
| Per-provider rate limiting | ❌ Not started | Global throttle still used |

### Data Quality Blockers

| Issue | Impact |
|-------|--------|
| `securities_reference` has 0 market_cap values | Must run OVERVIEW for all tickers first |
| OVERVIEW requires 1 call per ticker | ~7,000 calls = ~2 hours at premium rate |
| No parallel workers | Sequential processing only |

---

## Next Steps: Mini-PC Cluster Extension

See **Proposal 011: Distributed Cluster Architecture** for extending this proposal with mini-PC worker nodes.

---

## Summary

This proposal outlines a comprehensive redesign of the ingestion pipeline to support parallel processing, task offloading, daily scheduling, and resilient error recovery. The current architecture processes data sequentially with limited concurrency, creating bottlenecks for large-scale data ingestion.

---

## Motivation

### Current State Analysis

The existing ingestion pipeline has several limitations:

| Issue | Impact | Current State |
|-------|--------|---------------|
| **Sequential Processing** | Slow ingestion | Provider → Provider executed serially |
| **GIL-Limited Threading** | CPU overhead | ThreadPoolExecutor bound by Python GIL |
| **Global HTTP Throttle** | Bottleneck | Single `_last_ts` limits all workers to 1 RPS |
| **No Task Queue** | No crash recovery | Failed ingestions must restart from beginning |
| **No Scheduling** | Manual execution | No daily/hourly automated runs |
| **No Checkpointing** | Lost progress | No resume capability mid-pipeline |

### Current Architecture Flow

```
API Provider → HttpClient (rate limited) → Facet → Bronze Sink → Silver Model
                     ↓
         Single-threaded throttle
         (1 request per second globally)
```

### Measured Bottlenecks

1. **Alpha Vantage**: 5 calls/min (free tier) = 12 seconds per ticker
2. **For 500 tickers**: 500 × 12s = 100 minutes minimum
3. **With concurrent workers**: Still 100 minutes (global throttle)
4. **BLS**: 25 queries/day limit without key
5. **Chicago**: 5 RPS but no parallelization implemented

---

## Detailed Design

### Proposed Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        ORCHESTRATION LAYER                          │
├─────────────────────────────────────────────────────────────────────┤
│  Scheduler (APScheduler/Celery Beat)                                │
│    ├── Daily: securities_reference (6:00 AM)                        │
│    ├── Daily: securities_prices (market close + 30min)              │
│    ├── Weekly: company_fundamentals (Sunday midnight)               │
│    └── Monthly: chicago_economic_indicators (1st of month)          │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         TASK QUEUE LAYER                            │
├─────────────────────────────────────────────────────────────────────┤
│  Redis + Celery (or RQ for simpler setup)                           │
│    ├── Queue: ingestion.alpha_vantage (priority: high)              │
│    ├── Queue: ingestion.chicago (priority: medium)                  │
│    ├── Queue: ingestion.bls (priority: low)                         │
│    └── Queue: build.silver_models (priority: normal)                │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                    ┌────────────┼────────────┐
                    ▼            ▼            ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│   Worker 1   │ │   Worker 2   │ │   Worker 3   │
│ (AV tickers) │ │ (AV tickers) │ │  (Chicago)   │
└──────────────┘ └──────────────┘ └──────────────┘
        │                │                │
        ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      BRONZE LAYER (Parquet)                         │
│  ├── securities_reference/                                          │
│  ├── securities_prices_daily/                                       │
│  └── chicago_*/                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Component Design

#### 1. Task Queue System (Celery + Redis)

**New Files:**
```
orchestration/
├── celery_app.py              # Celery configuration
├── tasks/
│   ├── __init__.py
│   ├── ingestion_tasks.py     # @celery.task decorators
│   ├── build_tasks.py         # Silver model building
│   └── maintenance_tasks.py   # Cleanup, archival
├── scheduler/
│   ├── __init__.py
│   ├── schedules.py           # Periodic task definitions
│   └── triggers.py            # Event-based triggers
└── workers/
    ├── __init__.py
    └── worker_config.py       # Worker configuration
```

**celery_app.py:**
```python
from celery import Celery
from config import ConfigLoader

config = ConfigLoader().load()

app = Celery(
    'de_funk',
    broker=config.redis_url or 'redis://localhost:6379/0',
    backend=config.redis_url or 'redis://localhost:6379/1',
    include=[
        'orchestration.tasks.ingestion_tasks',
        'orchestration.tasks.build_tasks',
    ]
)

app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='America/Chicago',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max per task
    worker_prefetch_multiplier=1,  # Fair distribution
    task_acks_late=True,  # Acknowledge after completion
    task_reject_on_worker_lost=True,  # Requeue on worker crash
)
```

**ingestion_tasks.py:**
```python
from celery import shared_task, chain, group
from orchestration.celery_app import app
from datapipelines.providers.alpha_vantage import AlphaVantageIngestor

@app.task(bind=True, max_retries=3, default_retry_delay=60)
def ingest_ticker_reference(self, ticker: str, snapshot_dt: str):
    """Ingest reference data for a single ticker."""
    try:
        ingestor = AlphaVantageIngestor()
        result = ingestor.ingest_ticker_reference(ticker, snapshot_dt)
        return {'ticker': ticker, 'status': 'success', 'rows': result.row_count}
    except RateLimitError as e:
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
    except Exception as e:
        return {'ticker': ticker, 'status': 'failed', 'error': str(e)}

@app.task(bind=True, max_retries=3)
def ingest_ticker_prices(self, ticker: str, start_date: str, end_date: str):
    """Ingest price data for a single ticker."""
    try:
        ingestor = AlphaVantageIngestor()
        result = ingestor.ingest_prices(ticker, start_date, end_date)
        return {'ticker': ticker, 'status': 'success', 'rows': result.row_count}
    except Exception as e:
        raise self.retry(exc=e)

@app.task
def ingest_all_tickers(tickers: list, snapshot_dt: str):
    """Fan-out to ingest all tickers in parallel."""
    # Create a group of tasks (parallel execution)
    job = group(
        ingest_ticker_reference.s(ticker, snapshot_dt)
        for ticker in tickers
    )
    return job.apply_async()

@app.task
def ingest_chicago_dataset(dataset_id: str, date_from: str, date_to: str):
    """Ingest a Chicago Data Portal dataset."""
    from datapipelines.providers.chicago import ChicagoIngestor
    ingestor = ChicagoIngestor()
    return ingestor.ingest_dataset(dataset_id, date_from, date_to)
```

#### 2. Per-Provider Rate Limiting

**New: Token Bucket Rate Limiter**

```python
# datapipelines/base/rate_limiter.py
import time
import threading
from dataclasses import dataclass
from typing import Optional

@dataclass
class RateLimitConfig:
    requests_per_second: float
    burst_size: int = 1
    cooldown_on_429: float = 60.0

class TokenBucketRateLimiter:
    """Thread-safe token bucket rate limiter."""

    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.tokens = config.burst_size
        self.last_update = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self, timeout: Optional[float] = None) -> bool:
        """Acquire a token, blocking if necessary."""
        deadline = time.monotonic() + (timeout or float('inf'))

        while True:
            with self._lock:
                self._refill()
                if self.tokens >= 1:
                    self.tokens -= 1
                    return True

                # Calculate wait time
                wait_time = (1 - self.tokens) / self.config.requests_per_second

            if time.monotonic() + wait_time > deadline:
                return False

            time.sleep(min(wait_time, 0.1))

    def _refill(self):
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self.last_update
        self.tokens = min(
            self.config.burst_size,
            self.tokens + elapsed * self.config.requests_per_second
        )
        self.last_update = now


# Provider-specific limiters
RATE_LIMITERS = {
    'alpha_vantage_free': TokenBucketRateLimiter(
        RateLimitConfig(requests_per_second=5/60, burst_size=5)  # 5 per minute
    ),
    'alpha_vantage_premium': TokenBucketRateLimiter(
        RateLimitConfig(requests_per_second=75/60, burst_size=15)  # 75 per minute
    ),
    'chicago': TokenBucketRateLimiter(
        RateLimitConfig(requests_per_second=5.0, burst_size=10)
    ),
    'bls': TokenBucketRateLimiter(
        RateLimitConfig(requests_per_second=0.5, burst_size=1)
    ),
}
```

#### 3. Checkpoint & Resume System

**New: IngestionCheckpoint**

```python
# orchestration/checkpoint.py
import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict
from datetime import datetime

@dataclass
class IngestionCheckpoint:
    """Track ingestion progress for resume capability."""
    job_id: str
    provider: str
    started_at: str
    total_items: int
    completed_items: List[str]
    failed_items: Dict[str, str]  # item -> error message
    last_updated: str
    status: str  # 'running', 'completed', 'failed', 'paused'

class CheckpointManager:
    """Manage ingestion checkpoints for crash recovery."""

    def __init__(self, checkpoint_dir: Path = None):
        self.checkpoint_dir = checkpoint_dir or Path("storage/.checkpoints")
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def create(self, job_id: str, provider: str, items: List[str]) -> IngestionCheckpoint:
        """Create a new checkpoint for an ingestion job."""
        checkpoint = IngestionCheckpoint(
            job_id=job_id,
            provider=provider,
            started_at=datetime.utcnow().isoformat(),
            total_items=len(items),
            completed_items=[],
            failed_items={},
            last_updated=datetime.utcnow().isoformat(),
            status='running'
        )
        self._save(checkpoint)
        return checkpoint

    def mark_completed(self, job_id: str, item: str):
        """Mark an item as completed."""
        checkpoint = self.load(job_id)
        if checkpoint and item not in checkpoint.completed_items:
            checkpoint.completed_items.append(item)
            checkpoint.last_updated = datetime.utcnow().isoformat()
            self._save(checkpoint)

    def mark_failed(self, job_id: str, item: str, error: str):
        """Mark an item as failed."""
        checkpoint = self.load(job_id)
        if checkpoint:
            checkpoint.failed_items[item] = error
            checkpoint.last_updated = datetime.utcnow().isoformat()
            self._save(checkpoint)

    def get_remaining(self, job_id: str, all_items: List[str]) -> List[str]:
        """Get items not yet processed (for resume)."""
        checkpoint = self.load(job_id)
        if not checkpoint:
            return all_items
        processed = set(checkpoint.completed_items) | set(checkpoint.failed_items.keys())
        return [item for item in all_items if item not in processed]

    def load(self, job_id: str) -> Optional[IngestionCheckpoint]:
        """Load a checkpoint from disk."""
        path = self.checkpoint_dir / f"{job_id}.json"
        if path.exists():
            with open(path) as f:
                data = json.load(f)
                return IngestionCheckpoint(**data)
        return None

    def _save(self, checkpoint: IngestionCheckpoint):
        """Save checkpoint to disk."""
        path = self.checkpoint_dir / f"{checkpoint.job_id}.json"
        with open(path, 'w') as f:
            json.dump(asdict(checkpoint), f, indent=2)
```

#### 4. Scheduling Configuration

**schedules.py:**
```python
from celery.schedules import crontab
from orchestration.celery_app import app

app.conf.beat_schedule = {
    # Securities reference data - daily at 6:00 AM CT
    'ingest-securities-reference-daily': {
        'task': 'orchestration.tasks.ingestion_tasks.ingest_securities_reference_batch',
        'schedule': crontab(hour=6, minute=0),
        'kwargs': {'top_n': 500},
    },

    # Securities prices - daily 30 min after market close (4:30 PM ET = 3:30 PM CT)
    'ingest-securities-prices-daily': {
        'task': 'orchestration.tasks.ingestion_tasks.ingest_securities_prices_batch',
        'schedule': crontab(hour=15, minute=30),
        'kwargs': {'lookback_days': 1},
    },

    # Chicago unemployment - monthly on 1st
    'ingest-chicago-unemployment-monthly': {
        'task': 'orchestration.tasks.ingestion_tasks.ingest_chicago_dataset',
        'schedule': crontab(day_of_month=1, hour=2, minute=0),
        'kwargs': {'dataset_id': 'ane4-dwhs'},
    },

    # Chicago building permits - daily
    'ingest-chicago-permits-daily': {
        'task': 'orchestration.tasks.ingestion_tasks.ingest_chicago_dataset',
        'schedule': crontab(hour=3, minute=0),
        'kwargs': {'dataset_id': 'ydr8-5enu'},
    },

    # BLS economic indicators - weekly on Sunday
    'ingest-bls-indicators-weekly': {
        'task': 'orchestration.tasks.ingestion_tasks.ingest_bls_batch',
        'schedule': crontab(day_of_week=0, hour=1, minute=0),
    },

    # Silver model rebuild - daily after all ingestion
    'rebuild-silver-models-daily': {
        'task': 'orchestration.tasks.build_tasks.rebuild_all_silver_models',
        'schedule': crontab(hour=5, minute=0),  # 5 AM CT (after overnight ingestion)
    },

    # Cleanup old checkpoints - weekly
    'cleanup-checkpoints-weekly': {
        'task': 'orchestration.tasks.maintenance_tasks.cleanup_old_checkpoints',
        'schedule': crontab(day_of_week=0, hour=0, minute=0),
        'kwargs': {'older_than_days': 7},
    },
}
```

#### 5. Circuit Breaker Pattern

```python
# datapipelines/base/circuit_breaker.py
import time
from enum import Enum
from dataclasses import dataclass
from typing import Callable, Any

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if recovered

@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5      # Failures before opening
    success_threshold: int = 2      # Successes to close from half-open
    timeout: float = 60.0           # Seconds before half-open

class CircuitBreaker:
    """Prevent cascading failures by failing fast when service is down."""

    def __init__(self, name: str, config: CircuitBreakerConfig = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.config.timeout:
                self.state = CircuitState.HALF_OPEN
            else:
                raise CircuitOpenError(f"Circuit {self.name} is OPEN")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _on_success(self):
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0

    def _on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.config.failure_threshold:
            self.state = CircuitState.OPEN
            self.success_count = 0

class CircuitOpenError(Exception):
    pass
```

---

## Migration Path

### Phase 1: Foundation (Week 1-2)
1. Add Redis and Celery to requirements.txt
2. Create `orchestration/celery_app.py` with basic configuration
3. Implement `TokenBucketRateLimiter` and update HttpClient
4. Add `CheckpointManager` for progress tracking

### Phase 2: Task Migration (Week 3-4)
1. Convert existing ingestors to Celery tasks
2. Add per-provider rate limiters
3. Implement circuit breaker for each provider
4. Create batch orchestration tasks

### Phase 3: Scheduling (Week 5)
1. Configure Celery Beat schedules
2. Add monitoring endpoints
3. Create management CLI commands
4. Document operational procedures

### Phase 4: Production Hardening (Week 6)
1. Add dead letter queue for failed tasks
2. Implement retry policies
3. Add alerting on persistent failures
4. Performance testing and tuning

---

## Alternatives Considered

| Alternative | Pros | Cons | Decision |
|-------------|------|------|----------|
| **RQ (Redis Queue)** | Simpler than Celery | Less features, no scheduling | Rejected |
| **APScheduler** | Lightweight | No distributed workers | Rejected |
| **Airflow** | Enterprise-grade | Heavy, overkill for this scale | Rejected |
| **Celery** | Balanced, proven | Some complexity | **Selected** |
| **asyncio + aiohttp** | Native Python | No persistence, no scheduling | Partial use |

---

## Impact

### Benefits
- **10x faster ingestion** with parallel workers
- **Crash recovery** via checkpointing
- **Automated scheduling** with Celery Beat
- **Better rate limit handling** with per-provider token buckets
- **Failure isolation** with circuit breakers
- **Observable** with task status tracking

### Drawbacks
- **New dependencies**: Redis, Celery
- **Operational complexity**: More moving parts
- **Learning curve**: Team must understand Celery

### Breaking Changes
- None - existing ingestion scripts can still work
- New parallel mode is opt-in

---

## Implementation Plan

1. **Phase 1**: Add Redis, Celery, implement rate limiters
2. **Phase 2**: Convert ingestors to Celery tasks
3. **Phase 3**: Add scheduling and monitoring
4. **Phase 4**: Production hardening and documentation

---

## Dependencies

**New Python Packages:**
```
celery>=5.3.0
redis>=4.5.0
flower>=2.0.0  # Celery monitoring UI (optional)
```

**Infrastructure:**
- Redis server (can use Docker: `docker run -d -p 6379:6379 redis`)

---

## Open Questions

1. Should we use Redis Cluster for high availability?
2. What alerting system should we integrate with (Slack, PagerDuty)?
3. Should failed items go to a dead letter queue or retry indefinitely?
4. How many workers should we run in production?

---

## References

- [Celery Documentation](https://docs.celeryq.dev/)
- [Token Bucket Algorithm](https://en.wikipedia.org/wiki/Token_bucket)
- [Circuit Breaker Pattern](https://martinfowler.com/bliki/CircuitBreaker.html)
- Current implementation: `/datapipelines/base/http_client.py`
