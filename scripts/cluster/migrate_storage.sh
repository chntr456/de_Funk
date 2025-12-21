#!/bin/bash
#
# de_Funk Storage Migration Script
#
# Migrates existing storage data to the shared NFS storage location
# and sets up the symlink from the project directory.
#
# Usage:
#   ./scripts/cluster/migrate_storage.sh [--dry-run]
#
# Options:
#   --dry-run    Show what would be done without making changes
#

set -e

# =============================================================================
# Configuration
# =============================================================================

PROJECT_PATH="/home/ms_trixie/PycharmProjects/de_Funk"
OLD_STORAGE="$PROJECT_PATH/storage"
NEW_STORAGE="/data/de_funk"
DE_FUNK_USER="ms_trixie"

# =============================================================================
# Colors
# =============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${GREEN}[+]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }
info() { echo -e "${BLUE}[*]${NC} $1"; }

# =============================================================================
# Parse Arguments
# =============================================================================

DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# =============================================================================
# Main
# =============================================================================

echo ""
echo "=============================================="
echo "  de_Funk Storage Migration"
echo "=============================================="
echo ""
echo "  Project:      $PROJECT_PATH"
echo "  Old Storage:  $OLD_STORAGE"
echo "  New Storage:  $NEW_STORAGE"
echo "  Dry Run:      $DRY_RUN"
echo ""

# Check if new storage exists
if [ ! -d "$NEW_STORAGE" ]; then
    error "New storage location does not exist: $NEW_STORAGE

  Run setup-head.sh first to create the storage volume."
fi

# Check current state of old storage
if [ -L "$OLD_STORAGE" ]; then
    LINK_TARGET=$(readlink -f "$OLD_STORAGE")
    if [ "$LINK_TARGET" = "$NEW_STORAGE" ]; then
        log "Storage symlink already points to $NEW_STORAGE"
        log "Migration complete - nothing to do!"
        exit 0
    else
        warn "Storage is a symlink pointing to: $LINK_TARGET"
        warn "Will update to point to: $NEW_STORAGE"
    fi
elif [ -d "$OLD_STORAGE" ]; then
    # Calculate size
    STORAGE_SIZE=$(du -sh "$OLD_STORAGE" 2>/dev/null | cut -f1)
    log "Found existing storage directory: $STORAGE_SIZE"

    # List contents
    echo ""
    info "Current storage contents:"
    ls -la "$OLD_STORAGE" 2>/dev/null || true
    echo ""
elif [ ! -e "$OLD_STORAGE" ]; then
    log "No existing storage directory found"
fi

# Confirm with user
if [ "$DRY_RUN" = false ]; then
    echo ""
    read -p "Proceed with migration? (y/N) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 0
    fi
fi

# =============================================================================
# Step 1: Create directory structure in new storage
# =============================================================================

log "Creating directory structure in $NEW_STORAGE..."

DIRS_TO_CREATE=(
    "bronze"
    "silver"
    "duckdb"
    "bronze/alpha_vantage"
    "bronze/bls"
    "bronze/chicago"
    "silver/core"
    "silver/company"
    "silver/stocks"
)

for dir in "${DIRS_TO_CREATE[@]}"; do
    if [ "$DRY_RUN" = true ]; then
        info "[DRY RUN] Would create: $NEW_STORAGE/$dir"
    else
        mkdir -p "$NEW_STORAGE/$dir"
        info "Created: $NEW_STORAGE/$dir"
    fi
done

# =============================================================================
# Step 2: Copy existing data (if any)
# =============================================================================

if [ -d "$OLD_STORAGE" ] && [ ! -L "$OLD_STORAGE" ]; then
    log "Copying existing data to new storage..."

    # Check for bronze data
    if [ -d "$OLD_STORAGE/bronze" ] && [ "$(ls -A $OLD_STORAGE/bronze 2>/dev/null)" ]; then
        if [ "$DRY_RUN" = true ]; then
            BRONZE_SIZE=$(du -sh "$OLD_STORAGE/bronze" 2>/dev/null | cut -f1)
            info "[DRY RUN] Would copy bronze data ($BRONZE_SIZE)"
        else
            log "Copying bronze data..."
            cp -rv "$OLD_STORAGE/bronze/"* "$NEW_STORAGE/bronze/" 2>/dev/null || true
        fi
    fi

    # Check for silver data
    if [ -d "$OLD_STORAGE/silver" ] && [ "$(ls -A $OLD_STORAGE/silver 2>/dev/null)" ]; then
        if [ "$DRY_RUN" = true ]; then
            SILVER_SIZE=$(du -sh "$OLD_STORAGE/silver" 2>/dev/null | cut -f1)
            info "[DRY RUN] Would copy silver data ($SILVER_SIZE)"
        else
            log "Copying silver data..."
            cp -rv "$OLD_STORAGE/silver/"* "$NEW_STORAGE/silver/" 2>/dev/null || true
        fi
    fi

    # Check for duckdb data
    if [ -d "$OLD_STORAGE/duckdb" ] && [ "$(ls -A $OLD_STORAGE/duckdb 2>/dev/null)" ]; then
        if [ "$DRY_RUN" = true ]; then
            DUCKDB_SIZE=$(du -sh "$OLD_STORAGE/duckdb" 2>/dev/null | cut -f1)
            info "[DRY RUN] Would copy duckdb data ($DUCKDB_SIZE)"
        else
            log "Copying duckdb data..."
            cp -rv "$OLD_STORAGE/duckdb/"* "$NEW_STORAGE/duckdb/" 2>/dev/null || true
        fi
    fi
fi

# =============================================================================
# Step 3: Set ownership
# =============================================================================

if [ "$DRY_RUN" = true ]; then
    info "[DRY RUN] Would set ownership to $DE_FUNK_USER"
else
    log "Setting ownership..."
    chown -R $DE_FUNK_USER:$DE_FUNK_USER "$NEW_STORAGE"
fi

# =============================================================================
# Step 4: Backup and replace old storage with symlink
# =============================================================================

if [ -d "$OLD_STORAGE" ] && [ ! -L "$OLD_STORAGE" ]; then
    BACKUP_PATH="${OLD_STORAGE}_backup_$(date +%Y%m%d_%H%M%S)"

    if [ "$DRY_RUN" = true ]; then
        info "[DRY RUN] Would backup $OLD_STORAGE to $BACKUP_PATH"
        info "[DRY RUN] Would create symlink: $OLD_STORAGE -> $NEW_STORAGE"
    else
        log "Backing up old storage to $BACKUP_PATH..."
        mv "$OLD_STORAGE" "$BACKUP_PATH"

        log "Creating symlink..."
        ln -s "$NEW_STORAGE" "$OLD_STORAGE"
        chown -h $DE_FUNK_USER:$DE_FUNK_USER "$OLD_STORAGE"
    fi
elif [ -L "$OLD_STORAGE" ]; then
    if [ "$DRY_RUN" = true ]; then
        info "[DRY RUN] Would update symlink: $OLD_STORAGE -> $NEW_STORAGE"
    else
        log "Updating symlink..."
        rm "$OLD_STORAGE"
        ln -s "$NEW_STORAGE" "$OLD_STORAGE"
        chown -h $DE_FUNK_USER:$DE_FUNK_USER "$OLD_STORAGE"
    fi
else
    if [ "$DRY_RUN" = true ]; then
        info "[DRY RUN] Would create symlink: $OLD_STORAGE -> $NEW_STORAGE"
    else
        log "Creating symlink..."
        ln -s "$NEW_STORAGE" "$OLD_STORAGE"
        chown -h $DE_FUNK_USER:$DE_FUNK_USER "$OLD_STORAGE"
    fi
fi

# =============================================================================
# Verification
# =============================================================================

echo ""
echo "=============================================="
echo "  Migration Complete!"
echo "=============================================="
echo ""

if [ "$DRY_RUN" = false ]; then
    log "Verifying setup..."
    echo ""
    echo "  Symlink:"
    ls -la "$OLD_STORAGE"
    echo ""
    echo "  New storage contents:"
    ls -la "$NEW_STORAGE"
    echo ""
    echo "  Storage usage:"
    df -h "$NEW_STORAGE"
    echo ""

    log "Storage migration complete!"
    echo ""
    echo "  Your project's storage/ directory now points to the shared NFS storage."
    echo "  All workers can access this data via /shared/storage"
    echo ""
else
    info "[DRY RUN] No changes were made. Run without --dry-run to apply."
fi
