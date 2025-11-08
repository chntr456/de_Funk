# Core Session Component - Overview

## Introduction

The **Core Session Component** provides the foundational infrastructure for application initialization, database connectivity, and cross-cutting concerns like filtering. It establishes the runtime environment and manages connections to different backend systems.

## Components

### 1. Repo Context (`core/context.py`)
- Environment initialization
- Configuration loading
- Connection factory
- Backend selection (Spark vs DuckDB)

### 2. Connections (`core/connection.py`)
- Abstract connection interface
- Spark connection implementation
- DuckDB connection implementation
- Backend-agnostic query API

### 3. Filter Engine (`core/session/filters.py`)
- Centralized filter application
- Multi-backend support
- Consistent filter semantics

## Architecture Diagram

```
┌────────────────────────────────────────────────────────────┐
│                    Application Start                       │
└─────────────────────────┬──────────────────────────────────┘
                          │
                          ▼
┌────────────────────────────────────────────────────────────┐
│                     RepoContext                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ - Load configurations (storage.json, etc.)           │  │
│  │ - Detect backend type (spark or duckdb)              │  │
│  │ - Create connection via ConnectionFactory            │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────┬──────────────────────────────────┘
                          │
          ┌───────────────┴───────────────┐
          │                               │
          ▼                               ▼
┌───────────────────┐           ┌──────────────────┐
│ SparkConnection   │           │ DuckDBConnection │
│ - Spark backend   │           │ - DuckDB backend │
│ - For ETL/heavy   │           │ - For OLAP/fast  │
└─────────┬─────────┘           └────────┬─────────┘
          │                              │
          └──────────────┬───────────────┘
                         │
                         ▼
        ┌────────────────────────────────┐
        │       FilterEngine             │
        │  - Apply filters to both       │
        │  - Unified filter semantics    │
        └────────────────────────────────┘
```

## Key Features

### 1. Unified Connection API

Single interface works with both Spark and DuckDB:

```python
# Works with both backends
df = connection.read_table("storage/silver/fact_prices")
filtered = connection.apply_filters(df, {'ticker': 'AAPL'})
pdf = connection.to_pandas(filtered)
```

### 2. Automatic Backend Detection

```python
# Automatically detects and configures backend
ctx = RepoContext.from_repo_root()

# Uses storage.json configuration
# {
#   "connection": {
#     "type": "duckdb"  # or "spark"
#   }
# }
```

### 3. Centralized Filter Logic

```python
# Same filter syntax for both backends
filters = {
    'ticker': ['AAPL', 'GOOGL'],
    'date': {'start': '2024-01-01', 'end': '2024-12-31'}
}

df = FilterEngine.apply_filters(df, filters, backend='duckdb')
```

## Usage Examples

### Basic Initialization

```python
from core.context import RepoContext

# Initialize application context
ctx = RepoContext.from_repo_root()

# Access components
storage_cfg = ctx.storage
connection = ctx.connection
backend_type = ctx.connection_type  # 'spark' or 'duckdb'
```

### Query with Filters

```python
from core.session.filters import FilterEngine

# Read data
df = ctx.connection.read_table("storage/silver/fact_prices")

# Apply filters
filters = {
    'ticker': 'AAPL',
    'date': {'min': '2024-01-01', 'max': '2024-12-31'}
}
filtered = FilterEngine.apply_filters(df, filters, ctx.connection_type)

# Convert to Pandas
pdf = ctx.connection.to_pandas(filtered)
```

### Backend Selection

```python
# Force DuckDB backend (fast analytics)
ctx = RepoContext.from_repo_root(connection_type='duckdb')

# Force Spark backend (large-scale ETL)
ctx = RepoContext.from_repo_root(connection_type='spark')
```

---

**File**: `/home/user/de_Funk/docs/guide/3-architecture/components/core-session/overview.md`
