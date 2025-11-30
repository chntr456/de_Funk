# Proposal: Metadata Model & Platform Observability

**Status**: Draft
**Author**: Claude
**Date**: 2025-11-29
**Updated**: 2025-11-29
**Priority**: Medium

---

## Summary

This proposal defines a metadata model for tracking model statistics, data freshness, table sizes, column profiles, and build history. The metadata model will provide platform-wide observability and enable data quality monitoring, SLA tracking, and capacity planning.

---

## Motivation

### Current State

The codebase has basic metadata capabilities scattered across modules:

| Component | Location | Capability |
|-----------|----------|------------|
| ModelRegistry | `models/registry.py` | Model discovery, config loading |
| ParquetLoader | `models/base/parquet_loader.py` | Manifest with row count + timestamp |
| ModelGraph | `models/api/graph.py` | Dependency analysis, build order |
| BaseModel | `models/base/model.py` | `get_metadata()`, `get_table_schema()` |

**What's Missing**:
- Centralized metadata storage
- Historical statistics (row counts over time)
- Column-level profiling (nulls, cardinality, min/max)
- Build duration tracking
- Data freshness monitoring
- SLA violation detection
- Query statistics
- Data lineage

### Why This Matters

1. **Capacity Planning**: Know table sizes and growth rates
2. **Data Quality**: Detect anomalies in row counts, null rates
3. **SLA Monitoring**: Alert when data is stale
4. **Debugging**: Track when data was last updated
5. **Documentation**: Auto-generate data dictionaries
6. **Performance**: Identify slow builds, large tables

---

## Detailed Design

### Metadata Model Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     METADATA MODEL (meta)                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  DIMENSIONS                          FACTS                          │
│  ├── dim_model                       ├── fact_table_stats           │
│  ├── dim_table                       ├── fact_column_stats          │
│  ├── dim_column                      ├── fact_build_history         │
│  └── dim_data_source                 └── fact_query_stats           │
│                                                                     │
│  AGGREGATES                          ALERTS                         │
│  ├── agg_model_summary               ├── vw_stale_tables            │
│  └── agg_daily_stats                 └── vw_anomaly_detection       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    METADATA SERVICES                                │
├─────────────────────────────────────────────────────────────────────┤
│  MetadataCollector     - Gathers stats from tables                  │
│  FreshnessMonitor      - Checks SLA compliance                      │
│  ProfilerService       - Column-level profiling                     │
│  LineageTracker        - Data flow tracking                         │
└─────────────────────────────────────────────────────────────────────┘
```

### Schema Definition

**File**: `configs/models/meta/schema.yaml`

```yaml
model: meta
version: 2.0
description: "Platform metadata model for observability and monitoring"

metadata:
  owner: "platform_team"
  domain: "platform"
  sla_hours: 1  # Metadata should be fresh
  tags: [platform, metadata, monitoring]

schema:
  dimensions:
    # ========================================
    # Model Dimension
    # ========================================
    dim_model:
      description: "Registered data models"
      columns:
        model_id: string              # Primary key (model name)
        model_name: string            # Human-readable name
        model_version: string         # Version (e.g., "2.0")
        description: string           # From YAML description
        owner: string                 # Team/person responsible
        domain: string                # Business domain
        tier: integer                 # Dependency tier (0=foundation)
        depends_on: string            # Comma-separated dependencies
        storage_root: string          # Storage path
        config_path: string           # YAML config path
        is_active: boolean            # Currently enabled
        created_at: timestamp
        updated_at: timestamp
      primary_key: [model_id]
      tags: [dim, model, metadata]

    # ========================================
    # Table Dimension
    # ========================================
    dim_table:
      description: "Tables within models"
      columns:
        table_id: string              # {model}.{table_name}
        model_id: string              # FK to dim_model
        table_name: string            # Table name
        table_type: string            # dimension, fact, bridge
        storage_path: string          # Full path to Parquet
        partition_columns: string     # Comma-separated partition cols
        primary_key: string           # Primary key columns
        description: string
        created_at: timestamp
        updated_at: timestamp
      primary_key: [table_id]
      tags: [dim, table, metadata]

    # ========================================
    # Column Dimension
    # ========================================
    dim_column:
      description: "Columns within tables"
      columns:
        column_id: string             # {table_id}.{column_name}
        table_id: string              # FK to dim_table
        column_name: string
        data_type: string             # string, integer, double, etc.
        is_nullable: boolean
        is_primary_key: boolean
        is_partition_key: boolean
        is_foreign_key: boolean
        foreign_key_ref: string       # {model}.{table}.{column}
        description: string
        created_at: timestamp
      primary_key: [column_id]
      tags: [dim, column, metadata]

    # ========================================
    # Data Source Dimension
    # ========================================
    dim_data_source:
      description: "External data sources"
      columns:
        source_id: string             # Provider/endpoint combo
        provider: string              # alpha_vantage, bls, chicago
        endpoint: string              # API endpoint name
        base_url: string
        rate_limit_per_second: double
        last_successful_fetch: timestamp
        is_active: boolean
      primary_key: [source_id]
      tags: [dim, source, metadata]

  facts:
    # ========================================
    # Table Statistics (Point-in-Time)
    # ========================================
    fact_table_stats:
      description: "Table-level statistics captured at build time"
      columns:
        stats_id: string              # UUID
        table_id: string              # FK to dim_table
        snapshot_ts: timestamp        # When stats were captured
        snapshot_date: date           # For partitioning

        # Size metrics
        row_count: long
        column_count: integer
        partition_count: integer
        file_count: integer
        size_bytes: long
        size_mb: double

        # Time metrics
        oldest_record_date: date      # Min date in data
        newest_record_date: date      # Max date in data
        data_span_days: integer       # newest - oldest

        # Quality metrics
        null_column_count: integer    # Columns with any nulls
        duplicate_row_count: long     # Based on primary key

        # Build metrics
        build_duration_seconds: double
        build_status: string          # success, partial, failed
        build_method: string          # full, incremental, repair

      primary_key: [stats_id]
      partitions: [snapshot_date]
      tags: [fact, stats, metadata]

    # ========================================
    # Column Statistics (Point-in-Time)
    # ========================================
    fact_column_stats:
      description: "Column-level profiling statistics"
      columns:
        stats_id: string
        column_id: string             # FK to dim_column
        table_id: string              # FK to dim_table
        snapshot_ts: timestamp
        snapshot_date: date

        # Null analysis
        null_count: long
        null_pct: double
        non_null_count: long

        # Cardinality
        distinct_count: long
        distinct_pct: double          # distinct / total

        # For numeric columns
        min_value: double
        max_value: double
        mean_value: double
        std_value: double
        median_value: double

        # For string columns
        min_length: integer
        max_length: integer
        avg_length: double
        empty_count: long

        # For date columns
        min_date: date
        max_date: date

        # Top values (JSON array)
        top_values_json: string       # [{"value": "X", "count": 100}, ...]

      primary_key: [stats_id]
      partitions: [snapshot_date]
      tags: [fact, column, profiling]

    # ========================================
    # Build History
    # ========================================
    fact_build_history:
      description: "Model and table build history"
      columns:
        build_id: string              # UUID
        model_id: string              # FK to dim_model
        table_id: string              # FK to dim_table (null for full model)
        build_type: string            # full, incremental, repair
        build_status: string          # started, running, success, failed
        started_at: timestamp
        completed_at: timestamp
        duration_seconds: double

        # Input/Output
        input_row_count: long
        output_row_count: long
        rows_inserted: long
        rows_updated: long
        rows_deleted: long

        # Error info
        error_message: string
        error_stack: string

        # Trigger
        triggered_by: string          # schedule, manual, dependency
        trigger_details: string

      primary_key: [build_id]
      partitions: [started_at]
      tags: [fact, build, history]

    # ========================================
    # Query Statistics
    # ========================================
    fact_query_stats:
      description: "Query execution statistics"
      columns:
        query_id: string
        session_id: string
        executed_at: timestamp
        executed_date: date

        # Query info
        query_text: string            # SQL query
        query_hash: string            # For deduplication
        tables_accessed: string       # Comma-separated

        # Performance
        duration_ms: double
        rows_returned: long
        bytes_scanned: long

        # User context
        user_id: string
        notebook_id: string

      primary_key: [query_id]
      partitions: [executed_date]
      tags: [fact, query, performance]
```

### Service Implementation

**File**: `models/implemented/meta/services/metadata_collector.py`

```python
"""
Metadata Collector Service.

Gathers statistics from all models and tables.

IMPORTANT: This service uses Spark for batch processing (pre-calculation)
and session abstraction for backend-agnostic queries. Never import
DuckDB or Spark directly - use UniversalSession or SparkSession from core.
"""

import os
import json
import uuid
from pathlib import Path
from datetime import datetime, date
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

import pandas as pd

from config.logging import get_logger
from core.session.universal_session import UniversalSession
from models.registry import ModelRegistry

logger = get_logger(__name__)


@dataclass
class TableStats:
    """Statistics for a single table."""
    table_id: str
    snapshot_ts: datetime
    snapshot_date: date
    row_count: int
    column_count: int
    partition_count: int
    file_count: int
    size_bytes: int
    size_mb: float
    oldest_record_date: Optional[date]
    newest_record_date: Optional[date]
    data_span_days: Optional[int]
    build_duration_seconds: float
    build_status: str


@dataclass
class ColumnStats:
    """Statistics for a single column."""
    column_id: str
    table_id: str
    snapshot_ts: datetime
    null_count: int
    null_pct: float
    distinct_count: int
    distinct_pct: float
    min_value: Optional[Any] = None
    max_value: Optional[Any] = None
    mean_value: Optional[float] = None


class MetadataCollector:
    """Collect metadata from all models and tables.

    Uses Spark backend for batch processing since metadata collection
    is a pre-calculation task that benefits from Spark's distributed
    processing capabilities.
    """

    def __init__(self, registry: ModelRegistry, storage_root: Path, backend: str = "spark"):
        self.registry = registry
        self.storage_root = storage_root
        # Use session abstraction - Spark preferred for batch/pre-calculation tasks
        self.session = UniversalSession(backend=backend)

    def collect_all(self) -> Dict[str, pd.DataFrame]:
        """Collect all metadata and return as DataFrames."""
        logger.info("Starting metadata collection")

        results = {
            'dim_model': self._collect_model_dim(),
            'dim_table': self._collect_table_dim(),
            'dim_column': self._collect_column_dim(),
            'fact_table_stats': self._collect_table_stats(),
        }

        logger.info(f"Collected metadata for {len(results['dim_model'])} models")
        return results

    def _collect_model_dim(self) -> pd.DataFrame:
        """Collect model dimension data."""
        models = []

        for model_name in self.registry.list_models():
            config = self.registry.get_model_config(model_name)
            if config:
                models.append({
                    'model_id': model_name,
                    'model_name': model_name,
                    'model_version': config.get('version', '1.0'),
                    'description': config.get('description', ''),
                    'owner': config.get('metadata', {}).get('owner', 'unknown'),
                    'domain': config.get('metadata', {}).get('domain', 'unknown'),
                    'tier': self._calculate_tier(model_name),
                    'depends_on': ','.join(config.get('depends_on', [])),
                    'storage_root': str(config.get('storage', {}).get('root', '')),
                    'config_path': str(self.registry.get_config_path(model_name)),
                    'is_active': True,
                    'created_at': datetime.now(),
                    'updated_at': datetime.now(),
                })

        return pd.DataFrame(models)

    def _collect_table_dim(self) -> pd.DataFrame:
        """Collect table dimension data."""
        tables = []

        for model_name in self.registry.list_models():
            config = self.registry.get_model_config(model_name)
            schema = config.get('schema', {})

            # Dimensions
            for table_name, table_config in schema.get('dimensions', {}).items():
                tables.append(self._table_record(
                    model_name, table_name, 'dimension', table_config
                ))

            # Facts
            for table_name, table_config in schema.get('facts', {}).items():
                tables.append(self._table_record(
                    model_name, table_name, 'fact', table_config
                ))

        return pd.DataFrame(tables)

    def _table_record(
        self,
        model_name: str,
        table_name: str,
        table_type: str,
        config: Dict
    ) -> Dict:
        """Create a table dimension record."""
        return {
            'table_id': f"{model_name}.{table_name}",
            'model_id': model_name,
            'table_name': table_name,
            'table_type': table_type,
            'storage_path': self._get_table_path(model_name, table_name),
            'partition_columns': ','.join(config.get('partitions', [])),
            'primary_key': ','.join(config.get('primary_key', [])),
            'description': config.get('description', ''),
            'created_at': datetime.now(),
            'updated_at': datetime.now(),
        }

    def _collect_column_dim(self) -> pd.DataFrame:
        """Collect column dimension data."""
        columns = []

        for model_name in self.registry.list_models():
            config = self.registry.get_model_config(model_name)
            schema = config.get('schema', {})

            for table_type in ['dimensions', 'facts']:
                for table_name, table_config in schema.get(table_type, {}).items():
                    table_id = f"{model_name}.{table_name}"
                    pk_cols = table_config.get('primary_key', [])
                    partition_cols = table_config.get('partitions', [])

                    for col_name, col_type in table_config.get('columns', {}).items():
                        columns.append({
                            'column_id': f"{table_id}.{col_name}",
                            'table_id': table_id,
                            'column_name': col_name,
                            'data_type': col_type,
                            'is_nullable': True,  # Default
                            'is_primary_key': col_name in pk_cols,
                            'is_partition_key': col_name in partition_cols,
                            'is_foreign_key': False,  # Would need FK analysis
                            'description': '',
                            'created_at': datetime.now(),
                        })

        return pd.DataFrame(columns)

    def _collect_table_stats(self) -> pd.DataFrame:
        """Collect table statistics from Parquet files."""
        stats = []
        snapshot_ts = datetime.now()
        snapshot_date = snapshot_ts.date()

        for model_name in self.registry.list_models():
            config = self.registry.get_model_config(model_name)
            storage_root = Path(config.get('storage', {}).get('root', ''))

            if not storage_root.exists():
                continue

            schema = config.get('schema', {})

            for table_type in ['dimensions', 'facts']:
                for table_name in schema.get(table_type, {}).keys():
                    table_path = storage_root / table_name

                    if table_path.exists():
                        table_stats = self._profile_table(
                            f"{model_name}.{table_name}",
                            table_path,
                            snapshot_ts,
                            snapshot_date
                        )
                        if table_stats:
                            stats.append(asdict(table_stats))

        return pd.DataFrame(stats)

    def _profile_table(
        self,
        table_id: str,
        table_path: Path,
        snapshot_ts: datetime,
        snapshot_date: date
    ) -> Optional[TableStats]:
        """Profile a single table using session abstraction."""
        try:
            # Count files and size
            parquet_files = list(table_path.glob("**/*.parquet"))
            file_count = len(parquet_files)
            size_bytes = sum(f.stat().st_size for f in parquet_files)

            if file_count == 0:
                return None

            # Query for row count using session abstraction (backend-agnostic)
            df = self.session.query(f"""
                SELECT
                    COUNT(*) as row_count,
                    COUNT(DISTINCT *) as distinct_count
                FROM read_parquet('{table_path}/**/*.parquet')
            """)

            row_count = int(df['row_count'].iloc[0])

            # Get column count via schema inspection
            schema_df = self.session.query(f"""
                SELECT * FROM read_parquet('{table_path}/**/*.parquet') LIMIT 0
            """)
            column_count = len(schema_df.columns)

            return TableStats(
                table_id=table_id,
                snapshot_ts=snapshot_ts,
                snapshot_date=snapshot_date,
                row_count=row_count,
                column_count=column_count,
                partition_count=len(list(table_path.iterdir())),
                file_count=file_count,
                size_bytes=size_bytes,
                size_mb=size_bytes / (1024 * 1024),
                oldest_record_date=None,  # Would need date column analysis
                newest_record_date=None,
                data_span_days=None,
                build_duration_seconds=0,
                build_status='success',
            )

        except Exception as e:
            logger.error(f"Failed to profile table {table_id}: {e}", exc_info=True)
            return None

    def _calculate_tier(self, model_name: str) -> int:
        """Calculate model tier based on dependencies."""
        from models.api.graph import ModelGraph
        graph = ModelGraph(self.registry)
        stats = graph.get_model_stats(model_name)
        return stats.get('depth', 0)

    def _get_table_path(self, model_name: str, table_name: str) -> str:
        """Get storage path for a table."""
        config = self.registry.get_model_config(model_name)
        storage_root = config.get('storage', {}).get('root', '')
        return str(Path(storage_root) / table_name)
```

**File**: `models/implemented/meta/services/freshness_monitor.py`

```python
"""
Data Freshness Monitor.

Tracks data freshness and SLA compliance.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass

from config.logging import get_logger
from models.registry import ModelRegistry

logger = get_logger(__name__)


@dataclass
class FreshnessStatus:
    """Freshness status for a table."""
    table_id: str
    model_id: str
    last_updated: Optional[datetime]
    sla_hours: int
    is_stale: bool
    hours_since_update: float
    status: str  # 'fresh', 'warning', 'stale', 'unknown'


class FreshnessMonitor:
    """Monitor data freshness and SLA compliance."""

    def __init__(self, registry: ModelRegistry):
        self.registry = registry

    def check_all(self) -> List[FreshnessStatus]:
        """Check freshness for all tables."""
        results = []

        for model_name in self.registry.list_models():
            config = self.registry.get_model_config(model_name)
            sla_hours = config.get('metadata', {}).get('sla_hours', 24)

            # Check each table's manifest
            storage_root = config.get('storage', {}).get('root', '')
            manifest_dir = Path(storage_root) / '_meta' / 'manifests'

            schema = config.get('schema', {})
            for table_type in ['dimensions', 'facts']:
                for table_name in schema.get(table_type, {}).keys():
                    status = self._check_table_freshness(
                        model_name, table_name, manifest_dir, sla_hours
                    )
                    results.append(status)

        return results

    def _check_table_freshness(
        self,
        model_name: str,
        table_name: str,
        manifest_dir: Path,
        sla_hours: int
    ) -> FreshnessStatus:
        """Check freshness for a single table."""
        table_id = f"{model_name}.{table_name}"

        # Find latest manifest
        last_updated = self._get_last_update_time(manifest_dir, table_name)

        if last_updated is None:
            return FreshnessStatus(
                table_id=table_id,
                model_id=model_name,
                last_updated=None,
                sla_hours=sla_hours,
                is_stale=True,
                hours_since_update=float('inf'),
                status='unknown'
            )

        hours_since = (datetime.now() - last_updated).total_seconds() / 3600
        is_stale = hours_since > sla_hours
        warning_threshold = sla_hours * 0.8

        if hours_since > sla_hours:
            status = 'stale'
        elif hours_since > warning_threshold:
            status = 'warning'
        else:
            status = 'fresh'

        return FreshnessStatus(
            table_id=table_id,
            model_id=model_name,
            last_updated=last_updated,
            sla_hours=sla_hours,
            is_stale=is_stale,
            hours_since_update=hours_since,
            status=status
        )

    def _get_last_update_time(
        self,
        manifest_dir: Path,
        table_name: str
    ) -> Optional[datetime]:
        """Get last update time from manifest."""
        if not manifest_dir.exists():
            return None

        # Find manifests for this table
        manifests = list(manifest_dir.glob(f"*__{table_name}.json"))
        if not manifests:
            return None

        # Get latest by filename (timestamp prefix)
        latest = sorted(manifests)[-1]

        try:
            import json
            with open(latest) as f:
                data = json.load(f)
                return datetime.fromisoformat(data.get('written_at', ''))
        except Exception:
            return None

    def get_stale_tables(self) -> List[FreshnessStatus]:
        """Get all stale tables."""
        all_status = self.check_all()
        return [s for s in all_status if s.is_stale]

    def get_freshness_summary(self) -> Dict:
        """Get summary of freshness across platform."""
        all_status = self.check_all()

        return {
            'total_tables': len(all_status),
            'fresh': len([s for s in all_status if s.status == 'fresh']),
            'warning': len([s for s in all_status if s.status == 'warning']),
            'stale': len([s for s in all_status if s.status == 'stale']),
            'unknown': len([s for s in all_status if s.status == 'unknown']),
            'sla_compliance_pct': (
                len([s for s in all_status if not s.is_stale]) /
                len(all_status) * 100 if all_status else 0
            ),
        }
```

### Views for Monitoring

**File**: `configs/models/meta/views.sql`

```sql
-- Stale Tables View
CREATE OR REPLACE VIEW vw_stale_tables AS
SELECT
    t.table_id,
    t.model_id,
    m.owner,
    m.sla_hours,
    s.snapshot_ts as last_updated,
    DATEDIFF('hour', s.snapshot_ts, CURRENT_TIMESTAMP) as hours_since_update,
    CASE
        WHEN DATEDIFF('hour', s.snapshot_ts, CURRENT_TIMESTAMP) > m.sla_hours THEN 'STALE'
        WHEN DATEDIFF('hour', s.snapshot_ts, CURRENT_TIMESTAMP) > m.sla_hours * 0.8 THEN 'WARNING'
        ELSE 'FRESH'
    END as status
FROM dim_table t
JOIN dim_model m ON t.model_id = m.model_id
LEFT JOIN (
    SELECT table_id, MAX(snapshot_ts) as snapshot_ts
    FROM fact_table_stats
    GROUP BY table_id
) s ON t.table_id = s.table_id
WHERE DATEDIFF('hour', s.snapshot_ts, CURRENT_TIMESTAMP) > m.sla_hours
ORDER BY hours_since_update DESC;

-- Model Summary View
CREATE OR REPLACE VIEW vw_model_summary AS
SELECT
    m.model_id,
    m.model_name,
    m.owner,
    m.domain,
    m.tier,
    COUNT(DISTINCT t.table_id) as table_count,
    SUM(s.row_count) as total_rows,
    SUM(s.size_mb) as total_size_mb,
    MAX(s.snapshot_ts) as last_updated,
    AVG(s.build_duration_seconds) as avg_build_seconds
FROM dim_model m
LEFT JOIN dim_table t ON m.model_id = t.model_id
LEFT JOIN fact_table_stats s ON t.table_id = s.table_id
GROUP BY m.model_id, m.model_name, m.owner, m.domain, m.tier;

-- Daily Stats Trend View
CREATE OR REPLACE VIEW vw_daily_stats_trend AS
SELECT
    snapshot_date,
    COUNT(DISTINCT table_id) as tables_updated,
    SUM(row_count) as total_rows,
    SUM(size_mb) as total_size_mb,
    AVG(build_duration_seconds) as avg_build_seconds,
    SUM(CASE WHEN build_status = 'failed' THEN 1 ELSE 0 END) as failed_builds
FROM fact_table_stats
WHERE snapshot_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY snapshot_date
ORDER BY snapshot_date;
```

---

## Backend Selection Guidelines

The metadata model follows the platform's backend-agnostic architecture:

### When to Use Spark (Default for Metadata Collection)

| Operation | Backend | Rationale |
|-----------|---------|-----------|
| Metadata collection | **Spark** | Batch processing, can run scheduled |
| Table profiling | **Spark** | Full table scans, distributed |
| Column statistics | **Spark** | Aggregations over large datasets |
| Build history recording | **Spark** | Part of model build pipeline |

### When to Use DuckDB

| Operation | Backend | Rationale |
|-----------|---------|-----------|
| Freshness queries | **DuckDB** | Simple lookups, interactive |
| Dashboard rendering | **DuckDB** | Fast response for UI |
| SLA violation alerts | **DuckDB** | Point queries on small result sets |

### Code Pattern

```python
# ❌ WRONG - Never import backend directly
import duckdb
conn = duckdb.connect()
result = conn.execute("SELECT ...").fetchdf()

# ✅ CORRECT - Always use session abstraction
from core.session.universal_session import UniversalSession

# For batch/pre-calculation tasks (metadata, model builds)
session = UniversalSession(backend="spark")

# For interactive/query tasks (UI, notebooks)
session = UniversalSession(backend="duckdb")

result = session.query("SELECT ...")
```

---

## Implementation Plan

### Phase 1: Foundation
1. Create `meta` model directory structure
2. Define schema YAML
3. Implement `MetadataCollector`
4. Register in model registry

### Phase 2: Statistics Collection (Week 2)
1. Implement table profiling
2. Implement column profiling
3. Add build history tracking
4. Create collection scripts

### Phase 3: Monitoring (Week 3)
1. Implement `FreshnessMonitor`
2. Create monitoring views
3. Add alerting hooks
4. Create dashboard notebook

### Phase 4: Integration (Week 4)
1. Hook into model builds
2. Add query logging
3. Create API endpoints
4. Document usage

---

## Open Questions

1. How long to retain historical stats (30 days? 90 days?)?
2. Should we profile all columns or just key columns?
3. What alerting system to integrate with?
4. Should query stats include the full SQL or just hash?

---

## References

- Current manifest system: `/models/base/parquet_loader.py`
- Model registry: `/models/registry.py`
- Model graph: `/models/api/graph.py`
