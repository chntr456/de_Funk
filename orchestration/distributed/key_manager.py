"""
Distributed API Key Manager using Ray Actors.

Coordinates API key distribution across Ray workers to prevent
rate limit violations when multiple workers make API calls.

Usage:
    # On head node
    key_manager = DistributedKeyManager.remote(
        provider="alpha_vantage",
        keys=["key1", "key2", "key3"],
        calls_per_minute_per_key=5
    )

    # On any worker
    key = ray.get(key_manager.acquire_key.remote())
    # ... make API call ...
    ray.get(key_manager.release_key.remote(key))

Author: de_Funk Team
Date: December 2025
"""
from __future__ import annotations

import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from collections import deque
import threading


def _get_ray():
    """Lazy import ray."""
    try:
        import ray
        return ray
    except ImportError:
        raise ImportError("Ray not installed. Install with: pip install 'ray[default]'")


@dataclass
class KeyState:
    """State tracking for a single API key."""
    key: str
    calls_this_minute: int = 0
    minute_start: float = field(default_factory=time.time)
    total_calls: int = 0
    total_waits: int = 0
    in_use: bool = False
    last_used: float = 0.0


def create_distributed_key_manager():
    """
    Create the DistributedKeyManager Ray Actor.

    Returns a Ray Actor class that manages API keys across the cluster.
    """
    ray = _get_ray()

    @ray.remote
    class DistributedKeyManager:
        """
        Ray Actor that manages API key distribution across workers.

        Features:
        - Round-robin key distribution
        - Per-key rate limiting
        - Automatic cooldown tracking
        - Statistics collection
        - Multi-provider support
        """

        def __init__(
            self,
            provider: str,
            keys: List[str],
            calls_per_minute_per_key: int = 5,
            cooldown_seconds: float = 12.0
        ):
            """
            Initialize the key manager.

            Args:
                provider: Provider name (alpha_vantage, bls, chicago)
                keys: List of API keys
                calls_per_minute_per_key: Rate limit per key per minute
                cooldown_seconds: Minimum seconds between calls with same key
            """
            self.provider = provider
            self.calls_per_minute = calls_per_minute_per_key
            self.cooldown = cooldown_seconds

            # Initialize key states
            self.key_states: Dict[str, KeyState] = {}
            self.key_queue = deque()

            for key in keys:
                self.key_states[key] = KeyState(key=key)
                self.key_queue.append(key)

            # Statistics
            self.total_requests = 0
            self.total_waits = 0
            self.start_time = time.time()

            print(f"[KeyManager] Initialized {provider} with {len(keys)} keys, "
                  f"{calls_per_minute_per_key}/min/key")

        def acquire_key(self, timeout: float = 60.0) -> Optional[str]:
            """
            Acquire an available API key.

            Blocks until a key is available or timeout is reached.

            Args:
                timeout: Maximum seconds to wait

            Returns:
                API key string, or None if timeout
            """
            start = time.time()

            while (time.time() - start) < timeout:
                key = self._try_acquire()
                if key:
                    return key

                # Wait before retry
                self.total_waits += 1
                time.sleep(0.5)

            return None

        def _try_acquire(self) -> Optional[str]:
            """Try to acquire a key without blocking."""
            now = time.time()

            # Try each key in round-robin order
            for _ in range(len(self.key_queue)):
                key = self.key_queue[0]
                state = self.key_states[key]

                # Reset minute counter if minute has passed
                if now - state.minute_start >= 60.0:
                    state.calls_this_minute = 0
                    state.minute_start = now

                # Check if key is available
                can_use = (
                    not state.in_use and
                    state.calls_this_minute < self.calls_per_minute and
                    (now - state.last_used) >= self.cooldown
                )

                if can_use:
                    # Mark key as in use
                    state.in_use = True
                    state.last_used = now
                    state.calls_this_minute += 1
                    state.total_calls += 1
                    self.total_requests += 1

                    # Rotate queue
                    self.key_queue.rotate(-1)
                    return key

                # Try next key
                self.key_queue.rotate(-1)

            return None

        def release_key(self, key: str) -> bool:
            """
            Release a key back to the pool.

            Args:
                key: The API key to release

            Returns:
                True if released successfully
            """
            if key in self.key_states:
                self.key_states[key].in_use = False
                return True
            return False

        def get_stats(self) -> Dict[str, Any]:
            """Get statistics for this key manager."""
            now = time.time()
            runtime = now - self.start_time

            key_stats = []
            for key, state in self.key_states.items():
                key_stats.append({
                    'key': f"{key[:8]}...",  # Truncate for security
                    'total_calls': state.total_calls,
                    'calls_this_minute': state.calls_this_minute,
                    'in_use': state.in_use,
                    'seconds_until_available': max(
                        0, self.cooldown - (now - state.last_used)
                    )
                })

            return {
                'provider': self.provider,
                'num_keys': len(self.key_states),
                'calls_per_minute_per_key': self.calls_per_minute,
                'total_requests': self.total_requests,
                'total_waits': self.total_waits,
                'runtime_seconds': runtime,
                'requests_per_minute': (self.total_requests / runtime) * 60 if runtime > 0 else 0,
                'keys': key_stats
            }

        def get_available_count(self) -> int:
            """Get number of currently available keys."""
            now = time.time()
            available = 0

            for state in self.key_states.values():
                if now - state.minute_start >= 60.0:
                    state.calls_this_minute = 0
                    state.minute_start = now

                if (not state.in_use and
                    state.calls_this_minute < self.calls_per_minute and
                    (now - state.last_used) >= self.cooldown):
                    available += 1

            return available

        def add_key(self, key: str) -> bool:
            """Add a new key to the pool at runtime."""
            if key not in self.key_states:
                self.key_states[key] = KeyState(key=key)
                self.key_queue.append(key)
                print(f"[KeyManager] Added new key to {self.provider} pool")
                return True
            return False

        def remove_key(self, key: str) -> bool:
            """Remove a key from the pool (e.g., if it becomes invalid)."""
            if key in self.key_states:
                del self.key_states[key]
                self.key_queue = deque(k for k in self.key_queue if k != key)
                print(f"[KeyManager] Removed key from {self.provider} pool")
                return True
            return False

    return DistributedKeyManager


# Provider-specific rate limits
PROVIDER_LIMITS = {
    'alpha_vantage_free': {'calls_per_minute': 5, 'cooldown': 12.0},
    'alpha_vantage_premium': {'calls_per_minute': 75, 'cooldown': 0.8},
    'alpha_vantage': {'calls_per_minute': 5, 'cooldown': 12.0},  # Default to free
    'bls': {'calls_per_minute': 20, 'cooldown': 3.0},  # ~500/day limit
    'chicago': {'calls_per_minute': 60, 'cooldown': 1.0},  # Generally unlimited
}


def create_key_manager_for_provider(
    provider: str,
    keys: List[str],
    tier: str = None
) -> Any:
    """
    Create a DistributedKeyManager for a specific provider.

    Args:
        provider: Provider name (alpha_vantage, bls, chicago)
        keys: List of API keys
        tier: Optional tier (e.g., 'premium' for alpha_vantage)

    Returns:
        Ray Actor handle for the key manager
    """
    ray = _get_ray()

    # Get provider limits
    lookup_key = f"{provider}_{tier}" if tier else provider
    limits = PROVIDER_LIMITS.get(lookup_key, PROVIDER_LIMITS.get(provider, {
        'calls_per_minute': 30,
        'cooldown': 2.0
    }))

    DistributedKeyManager = create_distributed_key_manager()

    return DistributedKeyManager.remote(
        provider=provider,
        keys=keys,
        calls_per_minute_per_key=limits['calls_per_minute'],
        cooldown_seconds=limits['cooldown']
    )


class KeyManagerRegistry:
    """
    Registry for managing multiple DistributedKeyManager actors.

    Provides a single point of access to key managers for all providers.

    Usage:
        registry = KeyManagerRegistry()
        registry.register_provider('alpha_vantage', ['key1', 'key2'])
        registry.register_provider('bls', ['bls_key'])

        # Get key for API call
        key = ray.get(registry.get_manager('alpha_vantage').acquire_key.remote())
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._managers: Dict[str, Any] = {}
            cls._instance._initialized = False
        return cls._instance

    def register_provider(
        self,
        provider: str,
        keys: List[str],
        tier: str = None
    ) -> Any:
        """
        Register a provider with its API keys.

        Args:
            provider: Provider name
            keys: List of API keys
            tier: Optional tier for rate limit selection

        Returns:
            Ray Actor handle for the key manager
        """
        if not keys:
            raise ValueError(f"No keys provided for {provider}")

        manager = create_key_manager_for_provider(provider, keys, tier)
        self._managers[provider] = manager
        return manager

    def get_manager(self, provider: str) -> Any:
        """Get the key manager for a provider."""
        if provider not in self._managers:
            raise KeyError(f"Provider '{provider}' not registered. "
                          f"Available: {list(self._managers.keys())}")
        return self._managers[provider]

    def has_provider(self, provider: str) -> bool:
        """Check if a provider is registered."""
        return provider in self._managers

    def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics for all registered providers."""
        ray = _get_ray()
        stats = {}
        for provider, manager in self._managers.items():
            stats[provider] = ray.get(manager.get_stats.remote())
        return stats

    def list_providers(self) -> List[str]:
        """List all registered providers."""
        return list(self._managers.keys())


def init_key_managers_from_env() -> KeyManagerRegistry:
    """
    Initialize key managers from environment variables.

    Reads:
        ALPHA_VANTAGE_API_KEYS - comma-separated keys
        ALPHA_VANTAGE_TIER - 'free' or 'premium'
        BLS_API_KEYS - comma-separated keys
        CHICAGO_API_KEYS - comma-separated keys

    Returns:
        Configured KeyManagerRegistry
    """
    import os

    registry = KeyManagerRegistry()

    # Alpha Vantage
    av_keys = os.environ.get('ALPHA_VANTAGE_API_KEYS', '')
    if av_keys:
        keys = [k.strip() for k in av_keys.split(',') if k.strip()]
        tier = os.environ.get('ALPHA_VANTAGE_TIER', 'free')
        if keys:
            registry.register_provider('alpha_vantage', keys, tier)
            print(f"[KeyManager] Registered alpha_vantage: {len(keys)} keys, tier={tier}")

    # BLS
    bls_keys = os.environ.get('BLS_API_KEYS', '')
    if bls_keys:
        keys = [k.strip() for k in bls_keys.split(',') if k.strip()]
        if keys:
            registry.register_provider('bls', keys)
            print(f"[KeyManager] Registered bls: {len(keys)} keys")

    # Chicago
    chicago_keys = os.environ.get('CHICAGO_API_KEYS', '')
    if chicago_keys:
        keys = [k.strip() for k in chicago_keys.split(',') if k.strip()]
        if keys:
            registry.register_provider('chicago', keys)
            print(f"[KeyManager] Registered chicago: {len(keys)} keys")

    return registry
