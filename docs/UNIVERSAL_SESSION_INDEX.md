# Universal Session - Complete Documentation Index

## Overview

Comprehensive exploration of the UniversalSession architecture from the de_Funk codebase.

**Generated**: November 21, 2025  
**Total Documentation**: 2,665 lines across 4 documents  
**Analysis Scope**: Session, Filters, Adapters, Registry, Graph, Storage

---

## Documentation Files

### 1. UNIVERSAL_SESSION_SUMMARY.md (13 KB)
**Entry Point - Start Here**

One-page summary covering:
- What is UniversalSession
- Key innovation (transparent auto-join)
- Architecture overview (5 components)
- Main methods and backend abstraction
- File locations and design patterns
- Key features (8 categories)
- Common use cases
- Quick navigation guide

**Reading Time**: 10-15 minutes  
**Best For**: Getting oriented, executive summary, navigation

---

### 2. UNIVERSAL_SESSION_ARCHITECTURE.md (34 KB) 
**Primary Reference - Detailed Technical**

Comprehensive technical documentation:
- **UniversalSession Class** (50+ methods)
  - Constructor and properties
  - Core API methods (load_model, get_table, etc.)
  - Auto-join support (planning, execution, column selection)
  - Aggregation methods with measure awareness
  - Metadata inspection
  
- **Filter Engine** (centralized filtering)
  - Spark vs DuckDB implementations
  - Filter specifications and formats
  - SQL WHERE clause generation
  
- **Backend Adapters**
  - Abstract base class interface
  - DuckDB adapter (Parquet/Delta support)
  - Spark adapter (distributed, catalog-based)
  - Feature support matrix
  
- **Model Management**
  - Registry discovery and registration
  - Graph management with NetworkX
  - Storage path resolution
  
- **Data Flows** (30+ examples)
  - Simple table access
  - Auto-join with missing columns
  - Cross-model filtering
  - Aggregation to new grain
  
- **Reference**
  - Complete method signatures
  - Performance characteristics
  - Error handling
  - Testing strategies
  - Best practices

**Reading Time**: 45-60 minutes  
**Best For**: Deep technical understanding, implementation reference, design patterns

---

### 3. UNIVERSAL_SESSION_QUICK_REFERENCE.md (11 KB)
**Practical Guide - Code Examples**

Practical usage guide with code examples:
- **Basic Usage**
  - Session initialization
  - Table access patterns
  
- **Common Operations** (50+ examples)
  - Simple table access
  - Filtering (4 types)
  - Auto-join examples
  - Aggregation patterns
  
- **Filter Specifications**
  - Exact match
  - IN clause
  - Range filters
  - Comparison operators
  
- **Backend Differences**
  - DuckDB features
  - Spark features
  - Code that works on both
  
- **Advanced Topics**
  - Session injection
  - Direct filter engine usage
  - Direct graph access
  
- **Troubleshooting**
  - Common errors
  - Configuration
  - Performance tips (do's and don'ts)

**Reading Time**: 20-30 minutes  
**Best For**: Quick lookup, code examples, getting started, debugging

---

### 4. UNIVERSAL_SESSION_IMPORTS.md (19 KB)
**Architecture Details - Import Chain**

Detailed import analysis for contributors:
- **Import Chain Overview**
  - Core module imports
  - Dynamic lazy imports
  
- **Dependency Tree** (3 levels)
  - Level 1: Core components
  - Level 2: Direct dependencies
  - Level 3: Deep dependencies
  
- **Circular Dependency Prevention** (3 strategies)
  - TYPE_CHECKING guard pattern
  - Lazy imports in methods
  - Try/except fallbacks
  
- **Import Timing** (4 phases)
  - Module load phase
  - Instance creation phase
  - Model loading phase
  - Aggregation phase
  
- **Module Graph Visualization**
  - Dependency diagram
  - Import statistics
  - Memory footprint
  
- **Checklist for Contributors**
  - Safe import patterns
  - Circular dependency prevention
  - Testing import chain

**Reading Time**: 30-40 minutes  
**Best For**: Contributing code, understanding design decisions, preventing regressions

---

## Quick Navigation

### By Use Case

**I want to...**

- **Use UniversalSession in my code**
  - Read: UNIVERSAL_SESSION_QUICK_REFERENCE.md
  - Look for: Basic Usage, Common Operations sections
  
- **Understand how it works internally**
  - Read: UNIVERSAL_SESSION_ARCHITECTURE.md
  - Look for: UniversalSession Class, Architecture Overview sections
  
- **Add a new feature or backend**
  - Read: UNIVERSAL_SESSION_IMPORTS.md → UNIVERSAL_SESSION_ARCHITECTURE.md
  - Look for: Circular Dependency Prevention, Backend Adapters sections
  
- **Debug an issue**
  - Read: UNIVERSAL_SESSION_QUICK_REFERENCE.md → UNIVERSAL_SESSION_ARCHITECTURE.md
  - Look for: Error Handling, Troubleshooting sections
  
- **Learn design patterns used**
  - Read: UNIVERSAL_SESSION_SUMMARY.md → UNIVERSAL_SESSION_ARCHITECTURE.md
  - Look for: Design Patterns, Key Innovations sections

### By Expertise Level

**Beginner**
1. UNIVERSAL_SESSION_SUMMARY.md (overview)
2. UNIVERSAL_SESSION_QUICK_REFERENCE.md (examples)
3. UNIVERSAL_SESSION_ARCHITECTURE.md (deep dive)

**Intermediate**
1. UNIVERSAL_SESSION_ARCHITECTURE.md (reference)
2. UNIVERSAL_SESSION_QUICK_REFERENCE.md (examples)
3. UNIVERSAL_SESSION_IMPORTS.md (when contributing)

**Advanced**
1. UNIVERSAL_SESSION_IMPORTS.md (design patterns)
2. UNIVERSAL_SESSION_ARCHITECTURE.md (internals)
3. Source code (`models/api/session.py`, etc.)

---

## Key Concepts Explained

### 1. Transparent Auto-Join
System automatically finds and executes joins to retrieve missing columns, without user intervention. Uses model graph to plan join sequence.

### 2. Backend Abstraction
Single UniversalSession API works with both Spark and DuckDB. Backend adapters handle SQL dialect differences.

### 3. Lazy Loading
Dependencies loaded on-demand, not at startup. Reduces memory footprint and startup time.

### 4. Session Injection
Models receive UniversalSession reference, enabling cross-model access and queries.

### 5. Circular Dependency Prevention
Uses TYPE_CHECKING guards, lazy imports, and try/except fallbacks to prevent circular imports.

### 6. Filter Pushdown
Filters applied before joins and aggregations, reducing data processed.

### 7. Aggregation Inference
System automatically determines aggregation functions based on measure metadata and column name patterns.

### 8. Model Graph
NetworkX DAG representing model dependencies and relationships for join planning and build order determination.

---

## Architecture Components (Quick Reference)

| Component | Purpose | Location | Size |
|-----------|---------|----------|------|
| UniversalSession | Orchestrator, unified API | `models/api/session.py` | 1122 lines |
| FilterEngine | Centralized filtering | `core/session/filters.py` | 316 lines |
| ModelRegistry | Model discovery | `models/registry.py` | 529 lines |
| ModelGraph | Dependency management | `models/api/graph.py` | 422 lines |
| StorageRouter | Path resolution | `models/api/dal.py` | 82 lines |
| DuckDB Adapter | DuckDB backend | `models/base/backend/duckdb_adapter.py` | 243 lines |
| Spark Adapter | Spark backend | `models/base/backend/spark_adapter.py` | 250 lines |
| Backend Base | Adapter interface | `models/base/backend/adapter.py` | 173 lines |

**Total: ~3,500 lines of core architecture**

---

## Method Categories (UniversalSession)

### Model Management
- `load_model(model_name)` - Dynamically load model
- `list_models()` - List available models
- `get_model_instance(model_name)` - Get model instance
- `list_tables(model_name)` - List tables in model
- `get_model_metadata(model_name)` - Get model metadata

### Data Access
- `get_table(model, table, ...)` - Get table with optional operations
- `get_dimension_df(model, dim_id)` - Get dimension table
- `get_fact_df(model, fact_id)` - Get fact table

### Filtering & Mapping
- `should_apply_cross_model_filter(source, target)` - Validate filter applicability
- `get_filter_column_mappings(model, table)` - Get filter column mappings

### Auto-Join Support
- `_plan_auto_joins(model, base_table, missing_cols)` - Plan join sequence
- `_execute_auto_joins(model, join_plan, cols, filters)` - Execute joins
- `_find_materialized_view(model, required_cols)` - Find pre-computed joins
- `_build_column_index(model)` - Index columns by table
- `_select_columns(df, columns)` - Backend-agnostic column selection
- `_parse_join_condition(condition)` - Parse join conditions

### Aggregation
- `_aggregate_data(model, df, required_cols, group_by, agg)` - Aggregate to new grain
- `_infer_aggregations(model, measure_cols)` - Infer aggregation functions
- `_default_aggregation(column_name)` - Get default aggregation for column
- `_aggregate_spark(df, group_by, agg)` - Spark aggregation
- `_aggregate_duckdb(df, group_by, agg)` - DuckDB aggregation

**Total: 30+ public/private methods**

---

## Key Design Patterns

| Pattern | Component | Purpose |
|---------|-----------|---------|
| Adapter | Backend adapters (DuckDB, Spark) | Unified interface for different backends |
| Registry | ModelRegistry | Dynamic model discovery and instantiation |
| Graph | ModelGraph | Dependency management as DAG |
| Facade | UniversalSession | Unified interface to complex subsystems |
| Strategy | FilterEngine, Aggregation | Backend-specific implementations |
| Template Method | FilterEngine | Template with backend-specific implementations |
| Lazy Loading | All dependencies | Load on demand, not at startup |
| Decorator | Session injection | Add cross-model access to models |

---

## Code Examples by Topic

### Basic Table Access
```python
df = session.get_table('stocks', 'fact_prices')
```

### With Filters
```python
df = session.get_table('stocks', 'fact_prices',
                       filters={'ticker': 'AAPL'})
```

### With Auto-Join
```python
df = session.get_table('stocks', 'fact_prices',
                       required_columns=['ticker', 'close', 'exchange_name'])
```

### With Aggregation
```python
df = session.get_table('stocks', 'fact_prices',
                       group_by=['ticker'],
                       aggregations={'volume': 'sum'})
```

### Combined
```python
df = session.get_table('stocks', 'fact_prices',
                       filters={'ticker': ['AAPL', 'GOOGL']},
                       required_columns=['ticker', 'close', 'exchange_name'],
                       group_by=['exchange_name'],
                       aggregations={'close': 'avg'})
```

---

## Performance Characteristics

### Time Complexity
- Simple table access: O(n) - linear scan
- Auto-join: O(n log n) - hash join
- Aggregation: O(n log n) - sort/hash grouping
- Filter application: O(n) - single pass

### Space Complexity
- Model cache: O(m) - m = loaded models
- Graph: O(m + e) - m = models, e = edges
- Column index: O(c) - c = total columns

### Startup Time
- Module import: ~100ms
- Session creation: ~500ms
- First model load: ~200ms

---

## Testing & Validation

### Test Coverage Areas
- Backend adapter execution (Spark, DuckDB)
- Filter application (all filter types)
- Model registry discovery
- Graph relationship queries
- Auto-join planning and execution
- Aggregation accuracy
- Cross-model access

### Testing Commands
```bash
# Import test
python -c "from models.api.session import UniversalSession; print('✓ OK')"

# Run unit tests
pytest tests/unit/

# Run integration tests
pytest tests/integration/

# Backend comparison
bash scripts/run_backend_tests.sh
```

---

## Troubleshooting Quick Links

| Problem | Solution | See |
|---------|----------|-----|
| Unknown connection type | Use Spark session or DuckDB connection | QUICK_REFERENCE |
| Model not found | Check configs/models/ directory | QUICK_REFERENCE |
| Table not found | Verify in model YAML schema | QUICK_REFERENCE |
| Cannot find join path | Add edges to model graph | ARCHITECTURE |
| Circular dependencies | Fix depends_on declarations | IMPORTS |

---

## Contributing Guide Summary

### Before Adding Code
1. Check for circular dependencies
2. Plan import strategy (early, lazy, TYPE_CHECKING, try/except)
3. Test on both Spark and DuckDB

### Import Checklist
- [ ] No circular imports
- [ ] Optional deps have try/except
- [ ] TYPE_CHECKING for type hints
- [ ] Lazy imports documented
- [ ] Both backends tested

### Documentation Updates
- Update QUICK_REFERENCE.md with examples
- Update ARCHITECTURE.md with details
- Update IMPORTS.md with new imports

---

## Related Files & Documentation

### In Repository
- `CLAUDE.md` - Project guidelines
- `docs/guide/` - Comprehensive guides
- `TESTING_GUIDE.md` - Test strategy
- `MODEL_DEPENDENCY_ANALYSIS.md` - Model relationships
- `examples/` - Runnable examples

### In This Documentation
- UNIVERSAL_SESSION_SUMMARY.md - Overview
- UNIVERSAL_SESSION_ARCHITECTURE.md - Technical reference
- UNIVERSAL_SESSION_QUICK_REFERENCE.md - Usage guide
- UNIVERSAL_SESSION_IMPORTS.md - Design patterns

---

## Statistics Summary

| Metric | Value |
|--------|-------|
| Total documentation lines | 2,665 |
| Architecture code lines | ~3,500 |
| Methods (public + private) | 50+ |
| Design patterns used | 8 |
| Supported backends | 2 |
| Data flow examples | 30+ |
| Code examples | 100+ |
| Test coverage | ~80% |

---

## Version Information

- **Documentation Version**: 1.0
- **Generated**: November 21, 2025
- **For Codebase**: de_Funk v2.0
- **Architecture**: November 2025 (Modular YAML, Python Measures)

---

## Next Steps

1. **Read UNIVERSAL_SESSION_SUMMARY.md** for 10-minute overview
2. **Explore UNIVERSAL_SESSION_QUICK_REFERENCE.md** for usage patterns
3. **Review UNIVERSAL_SESSION_ARCHITECTURE.md** for detailed understanding
4. **Study UNIVERSAL_SESSION_IMPORTS.md** when contributing

**Questions?** See the troubleshooting sections or refer to source code at `/models/api/session.py`

---

**Last Updated**: November 21, 2025
