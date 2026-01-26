# Proposal: Architecture Guidelines & Boundary Definitions

**Status**: Draft
**Author**: Claude
**Date**: 2025-11-29
**Updated**: 2025-11-29
**Priority**: High

---

## Summary

This proposal establishes clear architectural boundaries, module responsibilities, and guidelines for Claude to follow when making changes. It addresses the root cause of architectural drift: lack of explicit rules about where code should live.

---

## Problem Statement

### How Architecture Degraded

Without explicit boundaries, code ends up in the "closest" or "most familiar" location:

```
❌ "I need to add a filter" → adds to existing FilterEngine
   (even though a different FilterEngine exists elsewhere)

❌ "I need to render a new block type" → adds function to markdown_renderer.py
   (even though file is already 1,500 lines)

❌ "I need to query data" → adds method to BaseModel
   (even though BaseModel already has 40+ methods)
```

### The Missing Guidance

Claude needs explicit answers to:
1. **Where does this code belong?** (module boundaries)
2. **What should this module contain?** (responsibilities)
3. **What should this module NOT contain?** (anti-patterns)
4. **When should I create a new module?** (triggers)

---

## Architecture Boundary Definitions

### Layer 1: Configuration (`config/`, `configs/`)

```
┌─────────────────────────────────────────────────────────────────┐
│                      CONFIGURATION LAYER                        │
├─────────────────────────────────────────────────────────────────┤
│  config/                    │  configs/                         │
│  ├── __init__.py           │  ├── models/         (YAML)       │
│  ├── loader.py             │  │   ├── {model}/                 │
│  ├── model_loader.py       │  │   │   ├── model.yaml           │
│  ├── models.py (dataclass) │  │   │   ├── schema.yaml          │
│  └── constants.py          │  │   │   ├── graph.yaml           │
│                             │  │   │   └── measures.yaml        │
│  PYTHON CONFIG LOADING      │  │   └── _base/                   │
│                             │  ├── storage.json                 │
│                             │  ├── *_endpoints.json             │
│                             │  └── notebooks/                   │
│                             │                                    │
│                             │  DECLARATIVE CONFIGURATION        │
└─────────────────────────────────────────────────────────────────┘

RESPONSIBILITIES:
✅ Load and validate configuration files
✅ Provide typed configuration objects
✅ Handle configuration precedence (env > file > default)
✅ Discover and merge modular YAML files

DOES NOT:
❌ Contain business logic
❌ Query data
❌ Handle HTTP requests
❌ Manage state
```

### Layer 2: Core Infrastructure (`core/`)

```
┌─────────────────────────────────────────────────────────────────┐
│                      CORE INFRASTRUCTURE                        │
├─────────────────────────────────────────────────────────────────┤
│  core/                                                          │
│  ├── context.py            RepoContext - environment setup      │
│  ├── exceptions.py         Custom exception hierarchy (NEW)     │
│  ├── session/                                                   │
│  │   ├── filters.py        FilterEngine (SINGLE IMPLEMENTATION)│
│  │   ├── connection.py     Database connections                 │
│  │   └── universal_session.py  Cross-model queries             │
│  └── duckdb_connection.py  DuckDB-specific connection          │
└─────────────────────────────────────────────────────────────────┘

RESPONSIBILITIES:
✅ Database connection management
✅ Filter application (ONE implementation)
✅ Cross-cutting infrastructure concerns
✅ Environment/context setup

DOES NOT:
❌ Contain domain/business logic
❌ Define model schemas
❌ Handle UI concerns
❌ Make HTTP requests
```

### Layer 3: Data Pipelines (`datapipelines/`)

```
┌─────────────────────────────────────────────────────────────────┐
│                      DATA PIPELINE LAYER                        │
├─────────────────────────────────────────────────────────────────┤
│  datapipelines/                                                 │
│  ├── base/                                                      │
│  │   ├── http_client.py    HTTP with rate limiting             │
│  │   ├── key_pool.py       API key rotation                    │
│  │   ├── rate_limiter.py   Token bucket (NEW)                  │
│  │   └── facet.py          Base transformation class           │
│  ├── facets/               Schema transformations               │
│  ├── ingestors/            Orchestration per provider          │
│  │   └── bronze_sink.py    Write to Bronze layer (Delta)       │
│  └── providers/            Provider-specific code              │
│      ├── alpha_vantage/                                        │
│      ├── bls/                                                  │
│      └── chicago/                                              │
└─────────────────────────────────────────────────────────────────┘

RESPONSIBILITIES:
✅ Fetch data from external APIs
✅ Transform raw data to normalized schemas (Facets)
✅ Write to Bronze layer (Delta Lake - default format)
✅ Handle rate limiting, retries, errors

DOES NOT:
❌ Query data (only writes)
❌ Build Silver layer models
❌ Handle UI concerns
❌ Define business measures
```

### Layer 4: Models (`models/`)

```
┌─────────────────────────────────────────────────────────────────┐
│                         MODEL LAYER                             │
├─────────────────────────────────────────────────────────────────┤
│  models/                                                        │
│  ├── base/                                                      │
│  │   ├── model.py          BaseModel (MAX 300 LINES)           │
│  │   ├── table_accessor.py Table loading (NEW)                 │
│  │   ├── measure_executor.py Measure calc (NEW)                │
│  │   └── parquet_loader.py Storage operations                  │
│  ├── api/                                                       │
│  │   ├── registry.py       Model discovery                     │
│  │   ├── session.py        UniversalSession                    │
│  │   └── graph.py          Dependency graph                    │
│  ├── measures/             Measure framework                    │
│  │   ├── framework.py      Core measure logic                  │
│  │   └── strategies/       Aggregation strategies              │
│  └── implemented/          Domain models                        │
│      ├── core/             Calendar dimension                  │
│      ├── stocks/           Stock model + measures.py           │
│      ├── company/          Company model + measures.py         │
│      └── {domain}/         Pattern: model.py + measures.py     │
└─────────────────────────────────────────────────────────────────┘

RESPONSIBILITIES:
✅ Define domain models (schema, graph, measures)
✅ Build Silver layer from Bronze
✅ Calculate measures
✅ Provide query interface

DOES NOT:
❌ Fetch external data (that's datapipelines/)
❌ Handle UI concerns
❌ Manage application state
```

### Layer 5: Application (`app/`)

```
┌─────────────────────────────────────────────────────────────────┐
│                      APPLICATION LAYER                          │
├─────────────────────────────────────────────────────────────────┤
│  app/                                                           │
│  ├── notebook/             Notebook system                      │
│  │   ├── parser.py         Markdown parsing                    │
│  │   ├── manager.py        Notebook CRUD                       │
│  │   └── filters/          Notebook filter context             │
│  ├── services/             Business logic services              │
│  │   └── query_service.py  Query execution                     │
│  └── ui/                   Streamlit UI                         │
│      ├── notebook_app.py   Main entry (MAX 100 LINES)          │
│      ├── state/            Session state management            │
│      ├── pages/            Page components                      │
│      ├── components/       Reusable UI components              │
│      │   └── markdown/     Markdown rendering (SPLIT)          │
│      └── callbacks/        Event handlers                       │
└─────────────────────────────────────────────────────────────────┘

RESPONSIBILITIES:
✅ Streamlit UI rendering
✅ Application state management
✅ User interaction handling
✅ Notebook parsing and display

DOES NOT:
❌ Implement core data logic (delegate to models/)
❌ Make direct API calls (use datapipelines/)
❌ Define model schemas
```

---

## Module Responsibility Cards

### Card Template

```markdown
## Module: {path}

**Purpose**: One sentence description

**Contains**:
- Thing 1
- Thing 2

**Does NOT Contain**:
- Anti-pattern 1
- Anti-pattern 2

**Max Size**: {N} lines

**Dependencies**: List of allowed imports

**Depended On By**: Who can import this
```

### Example Cards

```markdown
## Module: core/session/filters.py

**Purpose**: Apply filters to DataFrames regardless of backend.

**Contains**:
- FilterSpec dataclass
- FilterEngine class
- Backend-specific filter implementations

**Does NOT Contain**:
- Notebook-specific filter logic (extend in app/notebook/)
- SQL query building (that's query_executor)
- UI filter rendering (that's app/ui/components/)

**Max Size**: 250 lines

**Dependencies**:
- typing, dataclasses (stdlib)
- pyspark.sql (optional)
- duckdb (optional)

**Depended On By**:
- models/base/model.py
- models/api/session.py
- app/notebook/filters/ (extends)
```

```markdown
## Module: models/base/model.py

**Purpose**: Base class defining the model interface.

**Contains**:
- BaseModel class
- Model lifecycle methods (init, build, validate)
- Delegation to specialized components

**Does NOT Contain**:
- Table loading implementation (→ table_accessor.py)
- Measure calculation implementation (→ measure_executor.py)
- Filter application implementation (→ core/session/filters.py)
- 40+ methods (extract to components)

**Max Size**: 300 lines

**Dependencies**:
- models/base/table_accessor.py
- models/base/measure_executor.py
- core/session/filters.py

**Depended On By**:
- All models/implemented/{domain}/model.py
```

```markdown
## Module: app/ui/notebook_app.py (main entry)

**Purpose**: Streamlit application entry point and layout.

**Contains**:
- main() function
- Page layout structure
- Service initialization

**Does NOT Contain**:
- Page implementations (→ app/ui/pages/)
- Component implementations (→ app/ui/components/)
- State management logic (→ app/ui/state/)
- Query logic (→ app/services/)
- More than ~100 lines

**Max Size**: 100 lines

**Dependencies**:
- app/ui/pages/*
- app/ui/state/*
- app/services/*
```

---

## Decision Tree: Where Does This Code Go?

```
START: I need to add functionality for X

Q1: Is X about fetching external data?
    YES → datapipelines/providers/{provider}/
    NO  → Continue

Q2: Is X about transforming raw data to a schema?
    YES → datapipelines/facets/
    NO  → Continue

Q3: Is X about loading/validating configuration?
    YES → config/ (Python) or configs/ (YAML)
    NO  → Continue

Q4: Is X a reusable infrastructure concern (DB, filters, errors)?
    YES → core/
    NO  → Continue

Q5: Is X about a specific domain model?
    YES → models/implemented/{domain}/
         - Schema/graph → configs/models/{domain}/*.yaml
         - Complex measures → {domain}/measures.py
         - Convenience methods → {domain}/model.py
    NO  → Continue

Q6: Is X about the measure framework itself?
    YES → models/measures/
    NO  → Continue

Q7: Is X about model discovery/registry/cross-model?
    YES → models/api/
    NO  → Continue

Q8: Is X about UI rendering?
    YES → app/ui/components/
         - If component exists and <200 lines → add to it
         - If component >200 lines → create submodule
    NO  → Continue

Q9: Is X about application state?
    YES → app/ui/state/
    NO  → Continue

Q10: Is X about notebook parsing/management?
    YES → app/notebook/
    NO  → Continue

Q11: Is X a script for operations?
    YES → scripts/{category}/
    NO  → Ask for clarification
```

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: The God File

```python
# ❌ BAD: One file does everything
# models/base/model.py (1,312 lines)
class BaseModel:
    def get_table(self): ...      # Table access
    def calculate_measure(self): ... # Measure logic
    def apply_filters(self): ...  # Filter logic
    def get_metadata(self): ...   # Metadata
    def build_silver(self): ...   # Build logic
    # ... 35 more methods

# ✅ GOOD: Composed from focused components
class BaseModel:
    def __init__(self):
        self._tables = TableAccessor(...)
        self._measures = MeasureExecutor(...)
        self._filters = FilterEngine(...)
```

### Anti-Pattern 2: Duplicate Implementations

```python
# ❌ BAD: Three different filter engines
core/session/filters.py::FilterEngine
app/notebook/filters/engine.py::FilterEngine
models/base/service.py::_apply_filters()

# ✅ GOOD: One implementation, extended as needed
core/session/filters.py::FilterEngine  # Single source
app/notebook/filters/engine.py::NotebookFilterEngine(FilterEngine)  # Extends
```

### Anti-Pattern 3: Cross-Layer Imports

```python
# ❌ BAD: UI layer importing from pipeline layer
# app/ui/notebook_app.py
from datapipelines.providers.alpha_vantage import AlphaVantageIngestor

# ✅ GOOD: UI calls service, service calls pipeline
# app/ui/notebook_app.py
from app.services import DataService

# app/services/data_service.py
from datapipelines.providers.alpha_vantage import AlphaVantageIngestor
```

### Anti-Pattern 4: Business Logic in UI

```python
# ❌ BAD: Query building in Streamlit code
# app/ui/notebook_app.py
df = conn.execute(f"""
    SELECT * FROM {table}
    WHERE date >= '{start_date}'
    AND ticker IN ({','.join(tickers)})
""").fetchdf()

# ✅ GOOD: Delegate to service
# app/ui/notebook_app.py
df = query_service.get_data(table, start_date=start_date, tickers=tickers)
```

---

## Guidelines for Claude

### Before Writing Code

```markdown
1. **Check file size**: Is target file >300 lines?
   - YES → Create new module first
   - NO → Continue

2. **Check responsibility**: Does function fit file's purpose?
   - YES → Continue
   - NO → Find correct location using decision tree

3. **Check for duplicates**: Does similar code exist?
   - YES → Extend existing OR consolidate
   - NO → Continue

4. **Check dependencies**: Am I importing across layers incorrectly?
   - YES → Add intermediary service
   - NO → Continue
```

### When Creating New Modules

```markdown
1. Create module responsibility card (in docstring)
2. Define max file size in docstring
3. List what module should NOT contain
4. Add to __init__.py exports
5. Update CLAUDE.md if new pattern
```

### When Modifying Existing Code

```markdown
1. Check current file size after change
2. If >300 lines, propose extraction before adding
3. If adding >50 lines to a function, consider splitting
4. If duplicating logic, refactor to shared location
```

---

## Implementation Plan

### Phase 1: Document Boundaries (This Week)
1. Add architecture section to CLAUDE.md
2. Create module responsibility cards for key files
3. Add decision tree as reference

### Phase 2: Establish Tooling (Next Week)
1. Add file size check to pre-commit (warn >300, fail >500)
2. Add import layer check (no cross-layer imports)
3. Create refactoring templates

### Phase 3: Enforce Going Forward
1. All new code follows guidelines
2. Refactoring proposals for existing violations
3. Regular architecture review

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Files >300 lines | 25+ | <10 |
| Cross-layer imports | Many | 0 |
| Duplicate implementations | 5+ | 0 |
| Modules with responsibility docs | 0 | 100% |

---

## Additions to CLAUDE.md

```markdown
## Architecture Guidelines

### File Size Limits
- **Target**: <300 lines per file
- **Warning**: >500 lines requires justification
- **Action**: >800 lines must be split before adding more

### Module Boundaries
See `/docs/vault/13-proposals/draft/009-architecture-guidelines.md` for:
- Layer definitions
- Module responsibility cards
- Decision tree for code placement

### Before Adding Code
1. Check target file size
2. Verify code fits module responsibility
3. Search for existing similar code
4. Verify import doesn't cross layers
```

---

## Open Questions

1. Should we enforce these with linting rules?
2. How to handle legacy code that violates boundaries?
3. Should architecture decisions require explicit approval?

---

## References

- Clean Architecture (Robert Martin)
- Current codebase structure analysis
- Large file refactoring proposal (008)
