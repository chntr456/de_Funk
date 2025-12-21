#!/usr/bin/env python3
"""
de_Funk Cluster Test Script

Tests the Ray cluster setup including:
1. Cluster connectivity
2. Resource availability
3. Distributed task execution
4. NFS storage access from workers
5. Distributed key manager

Usage:
    python scripts/cluster/test_cluster.py
"""

import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import ray


def print_header(title: str):
    """Print a section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def print_result(test: str, passed: bool, details: str = ""):
    """Print test result."""
    status = "\033[92mPASS\033[0m" if passed else "\033[91mFAIL\033[0m"
    print(f"  [{status}] {test}")
    if details:
        print(f"         {details}")


def test_cluster_connection():
    """Test 1: Connect to Ray cluster."""
    print_header("Test 1: Cluster Connection")

    try:
        # Try to connect to existing cluster
        ray.init(address="auto", ignore_reinit_error=True)
        print_result("Connected to Ray cluster", True)
        return True
    except Exception as e:
        print_result("Connected to Ray cluster", False, str(e))
        return False


def test_cluster_resources():
    """Test 2: Verify cluster resources."""
    print_header("Test 2: Cluster Resources")

    resources = ray.cluster_resources()

    cpu_count = resources.get("CPU", 0)
    memory_gb = resources.get("memory", 0) / (1024**3)
    object_store_gb = resources.get("object_store_memory", 0) / (1024**3)

    print(f"  Total CPUs:         {cpu_count}")
    print(f"  Total Memory:       {memory_gb:.2f} GB")
    print(f"  Object Store:       {object_store_gb:.2f} GB")
    print()

    # Check expected resources (4 nodes: 12 + 11 + 11 + 11 = 45 CPUs)
    cpu_ok = cpu_count >= 40  # Allow some margin
    mem_ok = memory_gb >= 20  # At least 20GB

    print_result(f"CPU count >= 40", cpu_ok, f"Got {cpu_count}")
    print_result(f"Memory >= 20GB", mem_ok, f"Got {memory_gb:.2f}GB")

    return cpu_ok and mem_ok


def test_node_count():
    """Test 3: Verify all nodes are connected."""
    print_header("Test 3: Node Count")

    nodes = ray.nodes()
    alive_nodes = [n for n in nodes if n["Alive"]]

    print(f"  Total nodes:  {len(nodes)}")
    print(f"  Alive nodes:  {len(alive_nodes)}")
    print()

    for node in alive_nodes:
        node_ip = node["NodeManagerAddress"]
        resources = node["Resources"]
        cpus = resources.get("CPU", 0)
        print(f"    - {node_ip}: {cpus} CPUs")

    print()
    expected_nodes = 4  # 1 head + 3 workers
    node_ok = len(alive_nodes) >= expected_nodes

    print_result(f"Node count >= {expected_nodes}", node_ok, f"Got {len(alive_nodes)}")

    return node_ok


def test_distributed_execution():
    """Test 4: Run distributed tasks across workers."""
    print_header("Test 4: Distributed Execution")

    @ray.remote
    def get_node_info():
        """Get info about the node running this task."""
        import socket
        import os
        return {
            "hostname": socket.gethostname(),
            "ip": socket.gethostbyname(socket.gethostname()),
            "pid": os.getpid(),
            "cpu_count": os.cpu_count()
        }

    try:
        # Launch tasks on all available CPUs
        num_tasks = 20
        print(f"  Launching {num_tasks} remote tasks...")

        start_time = time.time()
        futures = [get_node_info.remote() for _ in range(num_tasks)]
        results = ray.get(futures)
        elapsed = time.time() - start_time

        # Count unique nodes
        unique_nodes = set(r["hostname"] for r in results)

        print(f"  Completed in {elapsed:.2f}s")
        print(f"  Tasks distributed across {len(unique_nodes)} nodes:")

        for hostname in sorted(unique_nodes):
            count = sum(1 for r in results if r["hostname"] == hostname)
            print(f"    - {hostname}: {count} tasks")

        print()
        distributed_ok = len(unique_nodes) >= 2  # At least 2 nodes used
        print_result("Tasks distributed across multiple nodes", distributed_ok)

        return distributed_ok

    except Exception as e:
        print_result("Distributed execution", False, str(e))
        return False


def test_nfs_storage():
    """Test 5: Verify NFS storage is accessible from workers."""
    print_header("Test 5: NFS Storage Access")

    @ray.remote
    def check_storage_access():
        """Check if storage paths are accessible."""
        import os
        import socket

        paths_to_check = [
            "/shared/storage",
            "/shared/storage/bronze",
            "/shared/storage/silver",
        ]

        results = {
            "hostname": socket.gethostname(),
            "paths": {}
        }

        for path in paths_to_check:
            exists = os.path.exists(path)
            is_dir = os.path.isdir(path) if exists else False
            results["paths"][path] = {"exists": exists, "is_dir": is_dir}

        return results

    try:
        # Check storage from each node
        nodes = ray.nodes()
        alive_nodes = [n for n in nodes if n["Alive"]]

        # Run one task per node
        futures = [check_storage_access.remote() for _ in range(len(alive_nodes))]
        results = ray.get(futures)

        # Deduplicate by hostname
        by_host = {}
        for r in results:
            by_host[r["hostname"]] = r

        all_ok = True
        for hostname, result in sorted(by_host.items()):
            print(f"  {hostname}:")
            for path, status in result["paths"].items():
                ok = status["exists"] and status["is_dir"]
                status_str = "OK" if ok else "MISSING"
                print(f"    {path}: {status_str}")
                if not ok:
                    all_ok = False

        print()
        print_result("NFS storage accessible from all nodes", all_ok)

        return all_ok

    except Exception as e:
        print_result("NFS storage access", False, str(e))
        return False


def test_parallel_computation():
    """Test 6: Run a realistic parallel computation."""
    print_header("Test 6: Parallel Computation Benchmark")

    @ray.remote
    def compute_chunk(start: int, end: int) -> float:
        """Compute sum of squares for a range."""
        import math
        total = 0.0
        for i in range(start, end):
            total += math.sqrt(i) * math.sin(i)
        return total

    try:
        # Split work into chunks
        total_numbers = 10_000_000
        num_chunks = 40  # Distribute across workers
        chunk_size = total_numbers // num_chunks

        print(f"  Computing on {total_numbers:,} numbers...")
        print(f"  Split into {num_chunks} chunks of {chunk_size:,} each")

        # Sequential baseline (small sample)
        import math
        seq_start = time.time()
        sample_size = 100_000
        seq_result = sum(math.sqrt(i) * math.sin(i) for i in range(sample_size))
        seq_time = time.time() - seq_start
        estimated_seq_time = seq_time * (total_numbers / sample_size)
        print(f"  Estimated sequential time: {estimated_seq_time:.2f}s")

        # Parallel execution
        par_start = time.time()
        futures = [
            compute_chunk.remote(i * chunk_size, (i + 1) * chunk_size)
            for i in range(num_chunks)
        ]
        results = ray.get(futures)
        par_time = time.time() - par_start

        speedup = estimated_seq_time / par_time

        print(f"  Parallel time:             {par_time:.2f}s")
        print(f"  Speedup:                   {speedup:.1f}x")
        print()

        speedup_ok = speedup >= 2.0  # At least 2x speedup
        print_result(f"Parallel speedup >= 2x", speedup_ok, f"Got {speedup:.1f}x")

        return speedup_ok

    except Exception as e:
        print_result("Parallel computation", False, str(e))
        return False


def main():
    """Run all cluster tests."""
    print("\n" + "="*60)
    print("  de_Funk Ray Cluster Test Suite")
    print("="*60)

    results = {}

    # Run tests
    results["connection"] = test_cluster_connection()

    if results["connection"]:
        results["resources"] = test_cluster_resources()
        results["nodes"] = test_node_count()
        results["distributed"] = test_distributed_execution()
        results["nfs"] = test_nfs_storage()
        results["benchmark"] = test_parallel_computation()

    # Summary
    print_header("Test Summary")

    total = len(results)
    passed = sum(1 for v in results.values() if v)

    for test, result in results.items():
        status = "\033[92mPASS\033[0m" if result else "\033[91mFAIL\033[0m"
        print(f"  [{status}] {test}")

    print()
    print(f"  Results: {passed}/{total} tests passed")

    if passed == total:
        print("\n  \033[92mCluster is fully operational!\033[0m\n")
        return 0
    else:
        print("\n  \033[91mSome tests failed. Check configuration.\033[0m\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
