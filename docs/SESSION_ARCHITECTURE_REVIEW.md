# Session Architecture Review & Recommendations

**Date:** 2025-11-06
**Status:** POST-CONSOLIDATION REVIEW
**Focus:** Orchestration vs Session Management Architecture

---

## Current Architecture Analysis

### 1. **Orchestration Layer** (`orchestration/`)

**Purpose:** Pipeline orchestration and Spark session lifecycle
**Location:** `/orchestration/common/spark_session.py`

```python
# orchestration/common/spark_session.py
def get_spark(app_name: str, config: Dict) -> SparkSession:
    """Factory for creating SparkSession instances"""
    builder = SparkSession.builder.appName(app_name)...
    return builder.getOrCreate()
```

**Responsibilities:**
- ✅ Create SparkSession instances
- ✅ Configure Spark settings (timezone, partitions, etc.)
- ✅ Pipeline orchestration (Orchestrator class)
- ✅ Run end-to-end data pipelines (bronze → silver)

**Does NOT:**
- ❌ Query data from models
- ❌ Manage model lifecycle
- ❌ Provide data access APIs
- ❌ Handle filters or transformations

**Verdict:** ✅ **CORRECT LOCATION** - Orchestration is infrastructure-level

---

### 2. **Session Management Layer** (`models/api/`)

**Purpose:** Data access and model querying
**Location:** `/models/api/session.py`

```python
# models/api/session.py
class UniversalSession:
    """Model-agnostic data access session"""
    def get_table(model_name, table_name) -> DataFrame
    def load_model(model_name) -> BaseModel
    def get_dimension_df(...) -> DataFrame
    def get_fact_df(...) -> DataFrame
```

**Responsibilities:**
- ✅ Query data from built models
- ✅ Manage model lifecycle (load, cache)
- ✅ Multi-model support via registry
- ✅ Backend-agnostic (Spark/DuckDB)
- ✅ Filter application via FilterEngine

**Does NOT:**
- ❌ Create Spark sessions
- ❌ Run pipelines
- ❌ Build models from scratch
- ❌ Orchestrate workflows

**Current Location:** `models/api/session.py`

---

## Architectural Layers Comparison

```
┌─────────────────────────────────────────────────────────────┐
│                    APPLICATION LAYER                         │
│  (UIs, Scripts, Notebooks)                                   │
│  - streamlit_app.py                                          │
│  - notebook_app_duckdb.py                                    │
│  - run_forecasts.py                                          │
└──────────────────┬──────────────────────────────────────────┘
                   │
      ┌────────────┼────────────┐
      │            │            │
      ▼            ▼            ▼
┌──────────┐ ┌─────────────┐ ┌──────────────┐
│ Notebook │ │ Service APIs│ │ Orchestrator │
│ Manager  │ │ (Prices,    │ │ (Pipelines)  │
│          │ │  News, etc.)│ │              │
└────┬─────┘ └──────┬──────┘ └──────┬───────┘
     │              │               │
     └──────────────┼───────────────┘
                    │
         ┌──────────▼───────────┐
         │  SESSION LAYER       │  ← WHERE SHOULD THIS LIVE?
         │  UniversalSession    │
         │  (Query & Access)    │
         └──────────┬───────────┘
                    │
         ┌──────────▼───────────┐
         │  ORCHESTRATION LAYER │
         │  get_spark()         │
         │  (Infrastructure)    │
         └──────────────────────┘
```

---

## The Question: Should Sessions Move?

### Option 1: Keep in `models/api/` ✅ CURRENT

**Pros:**
- ✅ Sessions query models → logically grouped with models
- ✅ `models/api/` is the "public API" for model access
- ✅ Clear separation: models = data, orchestration = infrastructure
- ✅ Matches common patterns (API layer lives with domain)

**Cons:**
- ⚠️ `models/` implies "model definitions", not "model access"
- ⚠️ Service APIs also in `models/api/` - getting crowded
- ⚠️ Not immediately obvious this is the "query layer"

**Structure:**
```
models/
├── api/
│   ├── session.py         # UniversalSession (data access)
│   ├── services.py        # Service APIs (Prices, News, Company)
│   └── dal.py             # Data access layer abstractions
├── base/
│   ├── model.py           # BaseModel abstract class
│   └── service.py         # BaseAPI abstract class
└── implemented/
    ├── company/           # CompanyModel implementation
    └── forecast/          # ForecastModel implementation
```

---

### Option 2: Move to `core/session/` 🤔 ALTERNATIVE

**Pros:**
- ✅ `core/` is for cross-cutting infrastructure
- ✅ Sessions are used everywhere (UIs, scripts, services)
- ✅ Already created `core/session/filters.py`
- ✅ Clearer separation: core = infrastructure, models = domain

**Cons:**
- ⚠️ `core/` currently has connections, context, validation (lower-level)
- ⚠️ UniversalSession tightly coupled to models (uses ModelRegistry)
- ⚠️ Would need to reorganize imports across entire codebase
- ⚠️ Less clear that it's model-specific access

**Structure:**
```
core/
├── session/
│   ├── __init__.py
│   ├── universal.py       # UniversalSession (moved from models/api/)
│   ├── filters.py         # FilterEngine (already exists)
│   └── cache.py           # Cache strategies (future)
├── connection.py          # DataConnection abstraction
├── context.py             # RepoContext
└── validation.py
```

---

### Option 3: Create `sessions/` top-level 🤔 ALTERNATIVE

**Pros:**
- ✅ Very clear: dedicated to session management
- ✅ Follows microservices pattern (dedicated layer)
- ✅ Easy to find all session-related code

**Cons:**
- ⚠️ Creates new top-level directory (more complexity)
- ⚠️ Over-engineered for current size
- ⚠️ Still tightly coupled to models

**Structure:**
```
sessions/
├── __init__.py
├── universal.py           # UniversalSession
├── filters.py             # FilterEngine (moved from core/)
└── cache.py               # Cache strategies
```

---

## Recommendation: KEEP CURRENT STRUCTURE ✅

**Verdict:** `models/api/session.py` is the **correct location**

### Reasoning:

1. **Separation of Concerns is CORRECT:**
   - `orchestration/` = Infrastructure (create Spark, run pipelines)
   - `models/api/` = Data Access (query built models)
   - These serve different purposes and should stay separate

2. **UniversalSession is Model-Focused:**
   - Uses ModelRegistry
   - Calls model.get_table()
   - Returns model DataFrames
   - → Belongs with models, not core infrastructure

3. **FilterEngine Location is GOOD:**
   - `core/session/filters.py` is appropriate
   - Filters are generic (used by sessions, but not model-specific)
   - Core = reusable utilities ✅

4. **Orchestration Should NOT Move:**
   - `orchestration/` is for pipeline execution
   - Spark session creation is infrastructure
   - Would be confusing to mix with data querying

---

## Clarification: What Each Layer Does

### Orchestration Layer
```python
# orchestration/common/spark_session.py
# PURPOSE: Create Spark infrastructure
spark = get_spark(app_name="MyApp")

# orchestration/orchestrator.py
# PURPOSE: Run end-to-end pipelines
orchestrator.run_company_pipeline(date_from="2024-01-01", date_to="2024-12-31")
# → Ingests data (bronze)
# → Builds models (silver)
# → Returns final DataFrame
```

### Session Layer
```python
# models/api/session.py
# PURPOSE: Query already-built models
session = UniversalSession(spark, storage_cfg, repo_root)
prices = session.get_table('company', 'fact_prices')
# → Reads from silver layer
# → Applies filters
# → Returns DataFrame for analysis
```

**Key Difference:**
- **Orchestration** = Build data (bronze → silver)
- **Session** = Query data (silver → app)

---

## Optional Future Improvements

### If `models/api/` Gets Too Large:

**Consider:**
```
models/
├── session/              # NEW: Dedicated session directory
│   ├── __init__.py
│   ├── universal.py      # UniversalSession
│   └── cache.py          # Cache strategies
├── services/             # NEW: Dedicated services directory
│   ├── __init__.py
│   ├── prices.py         # PricesAPI
│   ├── news.py           # NewsAPI
│   └── company.py        # CompanyAPI
├── base/
│   ├── model.py
│   └── service.py
└── implemented/
    ├── company/
    └── forecast/
```

**Benefits:**
- ✅ Better organization as codebase grows
- ✅ Clearer separation (session vs services)
- ✅ Easier to navigate

**When to do this:**
- ⏳ When `models/api/` has >10 files
- ⏳ When team is confused about structure
- ⏳ Not urgent right now

---

## Summary & Action Items

### ✅ **NO CHANGES NEEDED** - Current structure is correct!

| Layer | Location | Purpose | Status |
|-------|----------|---------|--------|
| **Orchestration** | `orchestration/` | Pipeline execution, Spark creation | ✅ CORRECT |
| **Session** | `models/api/session.py` | Data querying, model access | ✅ CORRECT |
| **Filters** | `core/session/filters.py` | Generic filter logic | ✅ CORRECT |
| **Services** | `models/api/services.py` | Typed data access APIs | ✅ CORRECT |

### 📋 Documentation Action Items:

1. **Create Architecture Diagram** showing layer separation
2. **Update README** to explain orchestration vs session
3. **Add docstrings** clarifying each layer's purpose
4. **Create "When to Use" guide**:
   - Use `orchestration/` when: Building data pipelines
   - Use `UniversalSession` when: Querying built models
   - Use Service APIs when: Need typed, domain-specific access

---

## Conclusion

The current architecture is **well-designed and appropriate**:

- ✅ Orchestration handles infrastructure (correct placement)
- ✅ Sessions handle data access (correct placement)
- ✅ Clear separation of concerns
- ✅ No overlap or confusion

**Recommendation:** Keep current structure, add better documentation explaining the layers.

---

**Document Version:** 1.0
**Created:** 2025-11-06
**Status:** Architecture Review Complete
**Verdict:** KEEP CURRENT STRUCTURE ✅

