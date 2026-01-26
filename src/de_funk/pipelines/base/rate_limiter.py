"""
Token Bucket Rate Limiter - Per-provider rate limiting for API calls.

Implements the token bucket algorithm for smooth, burst-tolerant rate limiting.
Supports different rate limits per provider (Alpha Vantage, BLS, etc.).
"""
from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from typing import Dict, Optional
from datetime import datetime

from de_funk.config.logging import get_logger

logger = get_logger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for a rate limiter."""
    calls_per_minute: float = 60.0
    burst_size: int = 5  # Max tokens that can accumulate
    name: str = "default"

    @property
    def calls_per_second(self) -> float:
        return self.calls_per_minute / 60.0

    @property
    def refill_rate(self) -> float:
        """Tokens added per second."""
        return self.calls_per_second


# Pre-configured rate limits for known providers
PROVIDER_RATE_LIMITS: Dict[str, RateLimitConfig] = {
    # Alpha Vantage: Free tier = 5/min, Premium = 75/min
    # Using 60/min as conservative default for premium
    "alpha_vantage": RateLimitConfig(
        calls_per_minute=60.0,
        burst_size=5,
        name="alpha_vantage"
    ),
    "alpha_vantage_free": RateLimitConfig(
        calls_per_minute=5.0,
        burst_size=1,
        name="alpha_vantage_free"
    ),
    "alpha_vantage_premium": RateLimitConfig(
        calls_per_minute=75.0,
        burst_size=10,
        name="alpha_vantage_premium"
    ),
    # BLS: 500 queries per day, ~20/hour, ~0.33/min
    "bls": RateLimitConfig(
        calls_per_minute=20.0,  # Conservative hourly rate
        burst_size=5,
        name="bls"
    ),
    # Chicago Data Portal: Generally unlimited but be respectful
    "chicago": RateLimitConfig(
        calls_per_minute=60.0,
        burst_size=10,
        name="chicago"
    ),
    # Default for unknown providers
    "default": RateLimitConfig(
        calls_per_minute=30.0,
        burst_size=3,
        name="default"
    ),
}


@dataclass
class TokenBucket:
    """
    Token bucket implementation for rate limiting.

    The bucket starts full and tokens are consumed on each API call.
    Tokens are refilled at a constant rate up to the max capacity.
    """
    config: RateLimitConfig
    tokens: float = field(init=False)
    last_refill: float = field(init=False)
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    # Statistics
    total_requests: int = field(default=0, init=False)
    total_waits: int = field(default=0, init=False)
    total_wait_time: float = field(default=0.0, init=False)

    def __post_init__(self):
        self.tokens = float(self.config.burst_size)
        self.last_refill = time.monotonic()

    def _refill(self) -> None:
        """Add tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        new_tokens = elapsed * self.config.refill_rate
        self.tokens = min(self.config.burst_size, self.tokens + new_tokens)
        self.last_refill = now

    def acquire(self, tokens: int = 1, blocking: bool = True, timeout: float = None) -> bool:
        """
        Acquire tokens from the bucket.

        Args:
            tokens: Number of tokens to acquire (default 1)
            blocking: If True, wait until tokens are available
            timeout: Maximum time to wait (None = infinite)

        Returns:
            True if tokens were acquired, False if timed out or non-blocking failed
        """
        start_time = time.monotonic()

        with self.lock:
            self._refill()

            if self.tokens >= tokens:
                # Have enough tokens, consume and return
                self.tokens -= tokens
                self.total_requests += 1
                return True

            if not blocking:
                return False

            # Calculate wait time
            needed = tokens - self.tokens
            wait_time = needed / self.config.refill_rate

            if timeout is not None and wait_time > timeout:
                logger.warning(
                    f"Rate limit timeout: need {wait_time:.2f}s but timeout is {timeout:.2f}s"
                )
                return False

        # Wait outside the lock
        logger.debug(
            f"Rate limited ({self.config.name}): waiting {wait_time:.2f}s for {tokens} token(s)"
        )
        time.sleep(wait_time)

        # Re-acquire lock and consume tokens
        with self.lock:
            self._refill()
            self.tokens -= tokens
            self.total_requests += 1
            self.total_waits += 1
            self.total_wait_time += time.monotonic() - start_time

        return True

    def wait(self) -> None:
        """Convenience method: wait and acquire 1 token."""
        self.acquire(1, blocking=True)

    def try_acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens without waiting."""
        return self.acquire(tokens, blocking=False)

    @property
    def available_tokens(self) -> float:
        """Get current available tokens (for monitoring)."""
        with self.lock:
            self._refill()
            return self.tokens

    def get_stats(self) -> Dict:
        """Get statistics about this rate limiter."""
        return {
            "name": self.config.name,
            "calls_per_minute": self.config.calls_per_minute,
            "burst_size": self.config.burst_size,
            "available_tokens": self.available_tokens,
            "total_requests": self.total_requests,
            "total_waits": self.total_waits,
            "total_wait_time": round(self.total_wait_time, 2),
            "avg_wait_time": round(
                self.total_wait_time / self.total_waits if self.total_waits > 0 else 0, 3
            ),
        }


class RateLimiterManager:
    """
    Manages rate limiters for multiple providers.

    Thread-safe singleton that provides rate limiters per provider.
    """
    _instance: Optional['RateLimiterManager'] = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._buckets: Dict[str, TokenBucket] = {}
                cls._instance._bucket_lock = threading.Lock()
        return cls._instance

    def get_limiter(self, provider: str) -> TokenBucket:
        """
        Get or create a rate limiter for a provider.

        Args:
            provider: Provider name (e.g., 'alpha_vantage', 'bls')

        Returns:
            TokenBucket rate limiter for the provider
        """
        with self._bucket_lock:
            if provider not in self._buckets:
                config = PROVIDER_RATE_LIMITS.get(
                    provider,
                    PROVIDER_RATE_LIMITS["default"]
                )
                self._buckets[provider] = TokenBucket(config)
                logger.info(
                    f"Created rate limiter for '{provider}': "
                    f"{config.calls_per_minute}/min, burst={config.burst_size}"
                )
            return self._buckets[provider]

    def configure_provider(
        self,
        provider: str,
        calls_per_minute: float,
        burst_size: int = 5
    ) -> TokenBucket:
        """
        Configure or reconfigure a provider's rate limiter.

        Args:
            provider: Provider name
            calls_per_minute: API calls allowed per minute
            burst_size: Maximum burst capacity

        Returns:
            Configured TokenBucket
        """
        config = RateLimitConfig(
            calls_per_minute=calls_per_minute,
            burst_size=burst_size,
            name=provider
        )
        with self._bucket_lock:
            self._buckets[provider] = TokenBucket(config)
            logger.info(
                f"Configured rate limiter for '{provider}': "
                f"{calls_per_minute}/min, burst={burst_size}"
            )
            return self._buckets[provider]

    def wait(self, provider: str) -> None:
        """Wait for rate limit on a provider."""
        self.get_limiter(provider).wait()

    def try_acquire(self, provider: str) -> bool:
        """Try to acquire without waiting."""
        return self.get_limiter(provider).try_acquire()

    def get_all_stats(self) -> Dict[str, Dict]:
        """Get statistics for all rate limiters."""
        with self._bucket_lock:
            return {name: bucket.get_stats() for name, bucket in self._buckets.items()}

    def reset(self) -> None:
        """Reset all rate limiters (useful for testing)."""
        with self._bucket_lock:
            self._buckets.clear()


# Convenience functions for simple usage
_manager = RateLimiterManager()


def rate_limit(provider: str) -> None:
    """
    Wait for rate limit on a provider.

    Usage:
        rate_limit("alpha_vantage")
        response = requests.get(url)
    """
    _manager.wait(provider)


def get_rate_limiter(provider: str) -> TokenBucket:
    """Get the rate limiter for a provider."""
    return _manager.get_limiter(provider)


def configure_rate_limit(provider: str, calls_per_minute: float, burst_size: int = 5) -> None:
    """Configure rate limit for a provider."""
    _manager.configure_provider(provider, calls_per_minute, burst_size)


def get_rate_limit_stats() -> Dict[str, Dict]:
    """Get statistics for all rate limiters."""
    return _manager.get_all_stats()
