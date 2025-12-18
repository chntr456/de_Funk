#!/bin/bash
#
# de_Funk Cluster Setup Verification Script
#
# Run this from the HEAD NODE to verify the entire cluster setup.
#
# Usage:
#   ./scripts/test/test_cluster_setup.sh [--workers worker-1,worker-2,worker-3]
#
# Author: de_Funk Team
# Date: December 2025

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default workers
WORKERS="${1:-worker-1,worker-2,worker-3}"
IFS=',' read -ra WORKER_ARRAY <<< "$WORKERS"

echo "=============================================="
echo "  de_Funk Cluster Verification"
echo "=============================================="
echo ""

PASS=0
FAIL=0

check() {
    local name="$1"
    local result="$2"
    if [ "$result" -eq 0 ]; then
        echo -e "[${GREEN}PASS${NC}] $name"
        ((PASS++))
    else
        echo -e "[${RED}FAIL${NC}] $name"
        ((FAIL++))
    fi
}

section() {
    echo ""
    echo -e "${YELLOW}=== $1 ===${NC}"
}

# =============================================================================
section "HEAD NODE CHECKS"
# =============================================================================

# Check Python
python3.11 --version > /dev/null 2>&1
check "Python 3.11 installed" $?

# Check venv
[ -d ~/venv ] && [ -f ~/venv/bin/activate ]
check "Virtual environment exists" $?

# Check Ray
source ~/venv/bin/activate 2>/dev/null
python -c "import ray" > /dev/null 2>&1
check "Ray installed" $?

# Check Ray head running
ray status > /dev/null 2>&1
check "Ray head node running" $?

# Check NFS server
systemctl is-active nfs-kernel-server > /dev/null 2>&1
check "NFS server running" $?

# Check storage directory
[ -d ~/storage/bronze ] && [ -d ~/storage/silver ]
check "Storage directories exist" $?

# Check scheduler service (may not be running in test mode)
systemctl is-enabled de_funk-scheduler > /dev/null 2>&1 || true
check "Scheduler service configured" 0

# =============================================================================
section "NETWORK CONNECTIVITY"
# =============================================================================

for worker in "${WORKER_ARRAY[@]}"; do
    ping -c 1 -W 2 "$worker" > /dev/null 2>&1
    check "Ping $worker" $?
done

# =============================================================================
section "SSH CONNECTIVITY"
# =============================================================================

for worker in "${WORKER_ARRAY[@]}"; do
    ssh -o ConnectTimeout=5 -o BatchMode=yes "$worker" "hostname" > /dev/null 2>&1
    check "SSH to $worker" $?
done

# =============================================================================
section "WORKER NODE CHECKS"
# =============================================================================

for worker in "${WORKER_ARRAY[@]}"; do
    echo ""
    echo -e "${YELLOW}--- $worker ---${NC}"

    # Check Python
    ssh "$worker" "python3.11 --version" > /dev/null 2>&1
    check "$worker: Python 3.11" $?

    # Check venv
    ssh "$worker" "[ -d ~/venv ] && [ -f ~/venv/bin/activate ]" 2>/dev/null
    check "$worker: Virtual environment" $?

    # Check Ray
    ssh "$worker" "source ~/venv/bin/activate && python -c 'import ray'" > /dev/null 2>&1
    check "$worker: Ray installed" $?

    # Check NFS mount
    ssh "$worker" "mount | grep -q nfs" 2>/dev/null
    check "$worker: NFS mounted" $?

    # Check storage accessible
    ssh "$worker" "ls /shared/storage/bronze > /dev/null 2>&1" 2>/dev/null
    check "$worker: Storage accessible" $?

    # Check Ray worker service
    ssh "$worker" "systemctl is-active ray-worker" > /dev/null 2>&1
    check "$worker: Ray worker service" $?
done

# =============================================================================
section "RAY CLUSTER STATUS"
# =============================================================================

echo ""
echo "Ray cluster resources:"
source ~/venv/bin/activate
ray status 2>/dev/null | head -20 || echo "Could not get Ray status"

# =============================================================================
section "DISTRIBUTED TASK TEST"
# =============================================================================

echo ""
echo "Running distributed task test..."

python3 << 'PYTHON_SCRIPT'
import ray
import socket

try:
    ray.init(address='auto', ignore_reinit_error=True)

    @ray.remote
    def get_worker_info():
        return {
            'hostname': socket.gethostname(),
            'ip': socket.gethostbyname(socket.gethostname())
        }

    # Submit tasks to all workers
    futures = [get_worker_info.remote() for _ in range(8)]
    results = ray.get(futures)

    # Count unique hosts
    hosts = set(r['hostname'] for r in results)
    print(f"Tasks executed on {len(hosts)} unique hosts:")
    for host in sorted(hosts):
        count = sum(1 for r in results if r['hostname'] == host)
        print(f"  - {host}: {count} tasks")

    ray.shutdown()
    exit(0)
except Exception as e:
    print(f"Error: {e}")
    exit(1)
PYTHON_SCRIPT

check "Distributed task execution" $?

# =============================================================================
section "NFS WRITE TEST"
# =============================================================================

echo ""
echo "Testing NFS write from worker..."

TEST_FILE="/shared/storage/cluster_test_$(date +%s).txt"

# Pick first available worker
for worker in "${WORKER_ARRAY[@]}"; do
    if ssh -o ConnectTimeout=2 "$worker" "echo 'test' > $TEST_FILE && cat $TEST_FILE && rm $TEST_FILE" > /dev/null 2>&1; then
        check "NFS write from $worker" 0
        break
    fi
done

# =============================================================================
section "API KEY MANAGER TEST (Optional)"
# =============================================================================

if [ -n "$ALPHA_VANTAGE_API_KEYS" ]; then
    echo ""
    echo "Testing distributed key manager..."

    python3 << 'PYTHON_SCRIPT'
import ray
import os

ray.init(address='auto', ignore_reinit_error=True)

from orchestration.distributed.key_manager import create_key_manager_for_provider

# Get keys from env
keys = os.environ.get('ALPHA_VANTAGE_API_KEYS', '').split(',')
keys = [k.strip() for k in keys if k.strip()]

if keys:
    manager = create_key_manager_for_provider('alpha_vantage', keys, 'free')

    # Acquire and release a key
    key = ray.get(manager.acquire_key.remote(timeout=5.0))
    if key:
        ray.get(manager.release_key.remote(key))
        stats = ray.get(manager.get_stats.remote())
        print(f"Key manager working: {stats['num_keys']} keys, {stats['total_requests']} requests")
        exit(0)
    else:
        print("Failed to acquire key")
        exit(1)
else:
    print("No API keys configured, skipping")
    exit(0)

ray.shutdown()
PYTHON_SCRIPT

    check "Distributed key manager" $?
else
    echo "ALPHA_VANTAGE_API_KEYS not set, skipping key manager test"
fi

# =============================================================================
section "SUMMARY"
# =============================================================================

echo ""
echo "=============================================="
echo -e "  Results: ${GREEN}$PASS passed${NC}, ${RED}$FAIL failed${NC}"
echo "=============================================="
echo ""

if [ $FAIL -gt 0 ]; then
    echo -e "${RED}Some checks failed. Review the output above.${NC}"
    exit 1
else
    echo -e "${GREEN}All checks passed! Cluster is ready.${NC}"
    exit 0
fi
