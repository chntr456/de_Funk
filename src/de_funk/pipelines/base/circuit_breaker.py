"""
Circuit Breaker Pattern - Failure isolation for API calls.

Prevents cascading failures by:
- Tracking failure rates per provider/endpoint
- Opening circuit after threshold failures
- Allowing test requests after cooldown
- Auto-closing circuit on success

States:
- CLOSED: Normal operation, requests pass through
- OPEN: Requests fail immediately (fast-fail)
- HALF_OPEN: Allow limited test requests to check recovery
"""
from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, Callable, Any
from functools import wraps

from config.logging import get_logger

logger = get_logger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"       # Normal operation
    OPEN = "open"          # Failing fast
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Configuration for a circuit breaker."""
    failure_threshold: int = 5      # Failures before opening
    success_threshold: int = 2      # Successes to close from half-open
    timeout_seconds: float = 60.0   # Time before attempting recovery
    half_open_max_calls: int = 3    # Max test calls in half-open state
    name: str = "default"


@dataclass
class CircuitStats:
    """Statistics for a circuit breaker."""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0  # Calls rejected due to open circuit
    state_changes: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0


class CircuitBreaker:
    """
    Circuit breaker implementation.

    Usage:
        cb = CircuitBreaker(config)

        # Manual usage
        if cb.allow_request():
            try:
                result = api_call()
                cb.record_success()
            except Exception as e:
                cb.record_failure()

        # Decorator usage
        @cb.protect
        def api_call():
            return requests.get(url)
    """

    def __init__(self, config: CircuitBreakerConfig = None):
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._stats = CircuitStats()
        self._last_state_change = time.monotonic()
        self._half_open_calls = 0
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        with self._lock:
            self._check_state_transition()
            return self._state

    @property
    def stats(self) -> CircuitStats:
        """Get circuit statistics."""
        return self._stats

    def _check_state_transition(self) -> None:
        """Check if state should transition (called while holding lock)."""
        if self._state == CircuitState.OPEN:
            # Check if timeout has elapsed
            elapsed = time.monotonic() - self._last_state_change
            if elapsed >= self.config.timeout_seconds:
                self._transition_to(CircuitState.HALF_OPEN)

    def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to a new state (called while holding lock)."""
        if self._state != new_state:
            old_state = self._state
            self._state = new_state
            self._last_state_change = time.monotonic()
            self._stats.state_changes += 1

            if new_state == CircuitState.HALF_OPEN:
                self._half_open_calls = 0

            logger.info(
                f"Circuit '{self.config.name}' state change: "
                f"{old_state.value} -> {new_state.value}"
            )

    def allow_request(self) -> bool:
        """
        Check if a request should be allowed.

        Returns:
            True if request should proceed, False if circuit is open
        """
        with self._lock:
            self._check_state_transition()

            if self._state == CircuitState.CLOSED:
                return True

            elif self._state == CircuitState.OPEN:
                self._stats.rejected_calls += 1
                return False

            elif self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls < self.config.half_open_max_calls:
                    self._half_open_calls += 1
                    return True
                else:
                    self._stats.rejected_calls += 1
                    return False

        return False

    def record_success(self) -> None:
        """Record a successful request."""
        with self._lock:
            self._stats.total_calls += 1
            self._stats.successful_calls += 1
            self._stats.last_success_time = time.monotonic()
            self._stats.consecutive_successes += 1
            self._stats.consecutive_failures = 0

            if self._state == CircuitState.HALF_OPEN:
                if self._stats.consecutive_successes >= self.config.success_threshold:
                    self._transition_to(CircuitState.CLOSED)

            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success in closed state
                pass

            logger.debug(
                f"Circuit '{self.config.name}' success recorded "
                f"(consecutive: {self._stats.consecutive_successes})"
            )

    def record_failure(self, error: Exception = None) -> None:
        """Record a failed request."""
        with self._lock:
            self._stats.total_calls += 1
            self._stats.failed_calls += 1
            self._stats.last_failure_time = time.monotonic()
            self._stats.consecutive_failures += 1
            self._stats.consecutive_successes = 0

            if self._state == CircuitState.CLOSED:
                if self._stats.consecutive_failures >= self.config.failure_threshold:
                    self._transition_to(CircuitState.OPEN)

            elif self._state == CircuitState.HALF_OPEN:
                # Any failure in half-open returns to open
                self._transition_to(CircuitState.OPEN)

            logger.warning(
                f"Circuit '{self.config.name}' failure recorded "
                f"(consecutive: {self._stats.consecutive_failures})"
                + (f" - {error}" if error else "")
            )

    def reset(self) -> None:
        """Reset circuit to closed state."""
        with self._lock:
            self._transition_to(CircuitState.CLOSED)
            self._stats.consecutive_failures = 0
            self._stats.consecutive_successes = 0
            logger.info(f"Circuit '{self.config.name}' manually reset")

    def protect(self, func: Callable) -> Callable:
        """
        Decorator to protect a function with circuit breaker.

        Usage:
            @circuit_breaker.protect
            def api_call():
                return requests.get(url)
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not self.allow_request():
                raise CircuitOpenError(
                    f"Circuit '{self.config.name}' is open - request rejected"
                )

            try:
                result = func(*args, **kwargs)
                self.record_success()
                return result
            except Exception as e:
                self.record_failure(e)
                raise

        return wrapper

    def get_status(self) -> Dict[str, Any]:
        """Get detailed status of the circuit breaker."""
        with self._lock:
            self._check_state_transition()
            return {
                "name": self.config.name,
                "state": self._state.value,
                "config": {
                    "failure_threshold": self.config.failure_threshold,
                    "success_threshold": self.config.success_threshold,
                    "timeout_seconds": self.config.timeout_seconds,
                },
                "stats": {
                    "total_calls": self._stats.total_calls,
                    "successful_calls": self._stats.successful_calls,
                    "failed_calls": self._stats.failed_calls,
                    "rejected_calls": self._stats.rejected_calls,
                    "state_changes": self._stats.state_changes,
                    "consecutive_failures": self._stats.consecutive_failures,
                    "consecutive_successes": self._stats.consecutive_successes,
                },
                "time_since_last_change": round(
                    time.monotonic() - self._last_state_change, 1
                ),
            }


class CircuitOpenError(Exception):
    """Raised when circuit is open and request is rejected."""
    pass


class CircuitBreakerManager:
    """
    Manages circuit breakers for multiple endpoints/providers.

    Thread-safe singleton that provides circuit breakers per endpoint.
    """
    _instance: Optional['CircuitBreakerManager'] = None
    _lock: threading.Lock = threading.Lock()

    # Default configurations per provider
    DEFAULT_CONFIGS: Dict[str, CircuitBreakerConfig] = {
        "alpha_vantage": CircuitBreakerConfig(
            failure_threshold=5,
            success_threshold=2,
            timeout_seconds=60.0,
            name="alpha_vantage"
        ),
        "bls": CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=2,
            timeout_seconds=120.0,
            name="bls"
        ),
        "chicago": CircuitBreakerConfig(
            failure_threshold=5,
            success_threshold=2,
            timeout_seconds=60.0,
            name="chicago"
        ),
    }

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._breakers: Dict[str, CircuitBreaker] = {}
                cls._instance._breaker_lock = threading.Lock()
        return cls._instance

    def get_breaker(self, name: str) -> CircuitBreaker:
        """
        Get or create a circuit breaker.

        Args:
            name: Breaker name (e.g., 'alpha_vantage', 'alpha_vantage.prices')

        Returns:
            CircuitBreaker instance
        """
        with self._breaker_lock:
            if name not in self._breakers:
                # Check for provider-level config
                provider = name.split('.')[0]
                config = self.DEFAULT_CONFIGS.get(
                    provider,
                    CircuitBreakerConfig(name=name)
                )
                # Override name to match requested name
                config.name = name
                self._breakers[name] = CircuitBreaker(config)
                logger.info(f"Created circuit breaker: {name}")

            return self._breakers[name]

    def configure(
        self,
        name: str,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout_seconds: float = 60.0
    ) -> CircuitBreaker:
        """Configure a circuit breaker."""
        config = CircuitBreakerConfig(
            failure_threshold=failure_threshold,
            success_threshold=success_threshold,
            timeout_seconds=timeout_seconds,
            name=name
        )
        with self._breaker_lock:
            self._breakers[name] = CircuitBreaker(config)
            return self._breakers[name]

    def get_all_status(self) -> Dict[str, Dict]:
        """Get status of all circuit breakers."""
        with self._breaker_lock:
            return {name: cb.get_status() for name, cb in self._breakers.items()}

    def reset_all(self) -> None:
        """Reset all circuit breakers."""
        with self._breaker_lock:
            for cb in self._breakers.values():
                cb.reset()


# Convenience functions
_manager = CircuitBreakerManager()


def get_circuit_breaker(name: str) -> CircuitBreaker:
    """Get a circuit breaker by name."""
    return _manager.get_breaker(name)


def circuit_protected(name: str):
    """
    Decorator to protect a function with a named circuit breaker.

    Usage:
        @circuit_protected("alpha_vantage")
        def fetch_prices(ticker):
            return requests.get(url)
    """
    def decorator(func: Callable) -> Callable:
        cb = _manager.get_breaker(name)

        @wraps(func)
        def wrapper(*args, **kwargs):
            if not cb.allow_request():
                raise CircuitOpenError(f"Circuit '{name}' is open")

            try:
                result = func(*args, **kwargs)
                cb.record_success()
                return result
            except Exception as e:
                cb.record_failure(e)
                raise

        return wrapper

    return decorator


def get_circuit_status() -> Dict[str, Dict]:
    """Get status of all circuit breakers."""
    return _manager.get_all_status()
