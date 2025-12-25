#!/bin/bash
#
# Ray Cleanup Script
#
# Removes Ray-based orchestration components after migrating to Airflow + Spark.
#
# Usage:
#   ./cleanup-ray.sh --dry-run    # Preview what will be removed
#   ./cleanup-ray.sh              # Actually remove files
#   ./cleanup-ray.sh --all        # Remove files + uninstall Ray from all nodes
#
# Prerequisites:
#   - Airflow pipeline tested and working
#   - Spark cluster verified
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

DRY_RUN=false
UNINSTALL_RAY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --all)
            UNINSTALL_RAY=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --dry-run    Preview changes without removing"
            echo "  --all        Also uninstall Ray from all nodes"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "======================================================================"
echo "  Ray Cleanup"
echo "======================================================================"
echo ""
echo "Dry run: $DRY_RUN"
echo "Uninstall Ray: $UNINSTALL_RAY"
echo ""

# =============================================================================
# Files to Remove
# =============================================================================

RAY_FILES=(
    # Ray-specific scripts (keep setup-worker.sh if it's been replaced)
    "scripts/cluster/run_distributed_pipeline.py"
    "scripts/cluster/run_production.sh"
    "scripts/cluster/cluster-init.sh"
    "scripts/cluster/test_cluster.py"
    "scripts/cluster/test_cluster_ingestion.py"

    # Ray orchestration module
    "orchestration/distributed/ray_cluster.py"
    "orchestration/distributed/key_manager.py"
    "orchestration/distributed/tasks.py"
    "orchestration/distributed/config.py"
    "orchestration/distributed/__init__.py"

    # Test files
    "scripts/test/test_distributed_key_manager.py"
    "scripts/test/test_cluster_setup.sh"
)

RAY_DIRS=(
    "orchestration/distributed"
    "scripts/cluster/__pycache__"
)

# =============================================================================
# Preview / Remove Files
# =============================================================================

echo "----------------------------------------------------------------------"
echo "Files to remove:"
echo "----------------------------------------------------------------------"

for file in "${RAY_FILES[@]}"; do
    full_path="$PROJECT_ROOT/$file"
    if [ -f "$full_path" ]; then
        echo "  - $file"
        if [ "$DRY_RUN" = false ]; then
            rm -f "$full_path"
        fi
    fi
done

echo ""
echo "----------------------------------------------------------------------"
echo "Directories to remove:"
echo "----------------------------------------------------------------------"

for dir in "${RAY_DIRS[@]}"; do
    full_path="$PROJECT_ROOT/$dir"
    if [ -d "$full_path" ]; then
        echo "  - $dir/"
        if [ "$DRY_RUN" = false ]; then
            rm -rf "$full_path"
        fi
    fi
done

# =============================================================================
# Stop Ray Services
# =============================================================================

if [ "$DRY_RUN" = false ]; then
    echo ""
    echo "----------------------------------------------------------------------"
    echo "Stopping Ray services..."
    echo "----------------------------------------------------------------------"

    # Stop Ray on head node
    if command -v ray &> /dev/null; then
        ray stop 2>/dev/null || true
        echo "  ✓ Ray stopped on head node"
    fi

    # Stop Ray worker systemd service
    if systemctl is-active --quiet ray-worker 2>/dev/null; then
        sudo systemctl stop ray-worker
        sudo systemctl disable ray-worker
        sudo rm -f /etc/systemd/system/ray-worker.service
        sudo systemctl daemon-reload
        echo "  ✓ ray-worker service removed"
    fi
fi

# =============================================================================
# Uninstall Ray (Optional)
# =============================================================================

if [ "$UNINSTALL_RAY" = true ] && [ "$DRY_RUN" = false ]; then
    echo ""
    echo "----------------------------------------------------------------------"
    echo "Uninstalling Ray from all nodes..."
    echo "----------------------------------------------------------------------"

    # Head node
    pip uninstall ray -y 2>/dev/null || true
    echo "  ✓ Ray uninstalled from head node"

    # Workers
    WORKERS="bark-1 bark-2 bark-3"
    for worker in $WORKERS; do
        echo "  Uninstalling from $worker..."
        ssh -o ConnectTimeout=5 "$worker" "pip uninstall ray -y 2>/dev/null" || true
        ssh -o ConnectTimeout=5 "$worker" "sudo systemctl stop ray-worker 2>/dev/null; sudo systemctl disable ray-worker 2>/dev/null; sudo rm -f /etc/systemd/system/ray-worker.service" || true
    done
    echo "  ✓ Ray uninstalled from workers"
fi

# =============================================================================
# Summary
# =============================================================================

echo ""
echo "======================================================================"
if [ "$DRY_RUN" = true ]; then
echo "  Dry Run Complete - No files removed"
echo "======================================================================"
echo ""
echo "Run without --dry-run to actually remove files:"
echo "  $0"
echo ""
echo "Or remove files AND uninstall Ray from all nodes:"
echo "  $0 --all"
else
echo "  Ray Cleanup Complete"
echo "======================================================================"
echo ""
echo "Removed:"
echo "  - Ray-specific scripts"
echo "  - orchestration/distributed/"
echo "  - Ray test files"
echo ""
if [ "$UNINSTALL_RAY" = true ]; then
echo "  - Ray package from all nodes"
echo ""
fi
echo "Kept:"
echo "  - scripts/spark-cluster/* (Spark cluster)"
echo "  - orchestration/airflow/* (Airflow DAGs)"
echo "  - scripts/seed/* (seeding)"
echo "  - scripts/build/* (model building)"
echo "  - scripts/ingest/* (bronze ingestion)"
fi
echo ""
