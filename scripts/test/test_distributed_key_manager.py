#!/usr/bin/env python
"""
Test script for the Distributed API Key Manager.

Tests the Ray Actor-based key manager that coordinates API key
distribution across workers for rate limiting.

Usage:
    # Quick local test (no actual API calls)
    python -m scripts.test.test_distributed_key_manager --quick

    # Full test with API call simulation
    python -m scripts.test.test_distributed_key_manager

    # Test with actual API keys from env
    python -m scripts.test.test_distributed_key_manager --use-env

Author: de_Funk Team
Date: December 2025
"""
from __future__ import annotations

import argparse
import time
import sys
from pathlib import Path

# Setup imports
sys.path.insert(0, str(Path(__file__).parents[2]))


def test_local_key_manager():
    """Test key manager in local Ray mode."""
    import ray

    print("=== Test 1: Local Key Manager ===")

    # Initialize Ray locally
    ray.init(ignore_reinit_error=True)

    from orchestration.distributed.key_manager import create_key_manager_for_provider

    # Create manager with test keys
    test_keys = ['test_key_1', 'test_key_2', 'test_key_3']
    manager = create_key_manager_for_provider(
        provider='alpha_vantage',
        keys=test_keys,
        tier='free'  # 5 calls/min, 12s cooldown
    )

    # Test acquire and release
    print(f"\nCreated manager with {len(test_keys)} keys")

    acquired_keys = []
    for i in range(3):
        key = ray.get(manager.acquire_key.remote(timeout=5.0))
        if key:
            acquired_keys.append(key)
            print(f"  Acquired key {i+1}: {key[:10]}...")
        else:
            print(f"  Failed to acquire key {i+1}")

    # Release keys
    for key in acquired_keys:
        ray.get(manager.release_key.remote(key))
    print(f"  Released {len(acquired_keys)} keys")

    # Check stats
    stats = ray.get(manager.get_stats.remote())
    print(f"\nStats:")
    print(f"  Provider: {stats['provider']}")
    print(f"  Keys: {stats['num_keys']}")
    print(f"  Total requests: {stats['total_requests']}")
    print(f"  Total waits: {stats['total_waits']}")

    ray.shutdown()
    print("\n[PASS] Local key manager test")
    return True


def test_concurrent_workers():
    """Test key manager with concurrent worker tasks."""
    import ray

    print("\n=== Test 2: Concurrent Workers ===")

    ray.init(ignore_reinit_error=True)

    from orchestration.distributed.key_manager import create_key_manager_for_provider

    # Create manager with 4 keys, faster rate for testing
    test_keys = ['key_a', 'key_b', 'key_c', 'key_d']
    manager = create_key_manager_for_provider('alpha_vantage', test_keys, 'free')

    @ray.remote
    def simulated_api_call(task_id: int, key_manager):
        """Simulated API call that acquires key, waits, releases."""
        import time

        # Acquire key
        key = ray.get(key_manager.acquire_key.remote(timeout=60.0))
        if not key:
            return {'task_id': task_id, 'status': 'timeout', 'key': None}

        # Simulate API call (0.5 second)
        time.sleep(0.5)

        # Release key
        ray.get(key_manager.release_key.remote(key))

        return {'task_id': task_id, 'status': 'success', 'key': key[:8]}

    # Submit 10 concurrent tasks (more than keys available)
    print(f"\nSubmitting 10 concurrent tasks with 4 keys...")
    start = time.time()

    futures = [simulated_api_call.remote(i, manager) for i in range(10)]
    results = ray.get(futures)

    elapsed = time.time() - start

    # Analyze results
    successful = sum(1 for r in results if r['status'] == 'success')
    print(f"\nResults:")
    print(f"  Successful: {successful}/10")
    print(f"  Total time: {elapsed:.2f}s")
    print(f"  Throughput: {successful/elapsed:.2f} tasks/sec")

    # Show which keys were used
    keys_used = set(r['key'] for r in results if r['key'])
    print(f"  Keys used: {keys_used}")

    # Get final stats
    stats = ray.get(manager.get_stats.remote())
    print(f"\nKey Manager Stats:")
    print(f"  Total requests: {stats['total_requests']}")
    print(f"  Total waits: {stats['total_waits']}")
    print(f"  Requests/min: {stats['requests_per_minute']:.1f}")

    ray.shutdown()

    if successful == 10:
        print("\n[PASS] Concurrent workers test")
        return True
    else:
        print("\n[FAIL] Some tasks did not complete")
        return False


def test_multi_provider():
    """Test multiple provider key managers."""
    import ray

    print("\n=== Test 3: Multi-Provider Registry ===")

    ray.init(ignore_reinit_error=True)

    from orchestration.distributed.key_manager import KeyManagerRegistry

    registry = KeyManagerRegistry()

    # Register multiple providers
    registry.register_provider('alpha_vantage', ['av_key_1', 'av_key_2'], 'free')
    registry.register_provider('bls', ['bls_key_1'])
    registry.register_provider('chicago', ['chi_key_1', 'chi_key_2', 'chi_key_3'])

    print(f"\nRegistered providers: {registry.list_providers()}")

    # Test each provider
    for provider in registry.list_providers():
        manager = registry.get_manager(provider)
        key = ray.get(manager.acquire_key.remote(timeout=5.0))
        if key:
            ray.get(manager.release_key.remote(key))
            print(f"  {provider}: OK (key: {key[:8]}...)")
        else:
            print(f"  {provider}: FAILED")

    # Get all stats
    all_stats = registry.get_all_stats()
    print(f"\nAll provider stats:")
    for provider, stats in all_stats.items():
        print(f"  {provider}: {stats['num_keys']} keys, {stats['total_requests']} requests")

    ray.shutdown()
    print("\n[PASS] Multi-provider registry test")
    return True


def test_with_env_keys():
    """Test with actual keys from environment variables."""
    import ray
    import os

    print("\n=== Test 4: Environment Keys ===")

    # Check for keys
    av_keys = os.environ.get('ALPHA_VANTAGE_API_KEYS', '')
    if not av_keys:
        print("  ALPHA_VANTAGE_API_KEYS not set, skipping")
        return True

    ray.init(ignore_reinit_error=True)

    from orchestration.distributed.key_manager import init_key_managers_from_env

    registry = init_key_managers_from_env()

    if registry.has_provider('alpha_vantage'):
        manager = registry.get_manager('alpha_vantage')
        stats = ray.get(manager.get_stats.remote())
        print(f"\n  Alpha Vantage: {stats['num_keys']} keys loaded from env")
        print(f"  Rate limit: {stats['calls_per_minute_per_key']}/min/key")
    else:
        print("  No Alpha Vantage keys loaded")

    ray.shutdown()
    print("\n[PASS] Environment keys test")
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--quick',
        action='store_true',
        help='Run quick local test only'
    )
    parser.add_argument(
        '--use-env',
        action='store_true',
        help='Test with actual API keys from environment'
    )
    args = parser.parse_args()

    print("=" * 50)
    print("  Distributed Key Manager Tests")
    print("=" * 50)

    results = []

    # Always run local test
    results.append(('Local Key Manager', test_local_key_manager()))

    if not args.quick:
        results.append(('Concurrent Workers', test_concurrent_workers()))
        results.append(('Multi-Provider', test_multi_provider()))

    if args.use_env:
        results.append(('Environment Keys', test_with_env_keys()))

    # Summary
    print("\n" + "=" * 50)
    print("  Summary")
    print("=" * 50)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"  [{status}] {name}")

    print(f"\n  Total: {passed}/{total} tests passed")

    return 0 if passed == total else 1


if __name__ == '__main__':
    sys.exit(main())
