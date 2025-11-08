# Session Architecture Consolidation Plan

## Executive Summary

**Goal**: Consolidate three parallel session systems (ModelSession, UniversalSession, NotebookSession) into a unified architecture based on UniversalSession.

**Timeline**: 3-4 weeks (phased approach)
**Risk Level**: Medium (affects core data access layer)
**Impact**: All data-consuming components (UIs, scripts, services)

---

## Current State Analysis

### Three Parallel Session Systems

#### 1. ModelSession (Legacy)
- **File**: `models/api/session.py` (lines 15-98)
- **Backend**: Spark only
- **Scope**: Single model (CompanyModel hardcoded)
- **Used by**:
  - `app/ui/streamlit_app.py` (old Spark-based UI)
  - Service APIs: `PricesAPI`, `NewsAPI`, `CompanyAPI`
- **Status**: ⚠️ Legacy, should be deprecated

#### 2. UniversalSession (Modern)
- **File**: `models/api/session.py` (lines 104-268)
- **Backend**: Connection-agnostic (designed for Spark, can support DuckDB)
- **Scope**: Multi-model, registry-driven
- **Used by**:
  - `scripts/build_silver_layer.py`
  - `scripts/run_forecasts.py`
  - `scripts/run_forecasts_large_cap.py`
  - `run_full_pipeline.py`
- **Status**: ✅ Best foundation for consolidation

#### 3. NotebookSession (UI-specific)
- **File**: `app/notebook/api/notebook_session.py`
- **Backend**: DuckDB (via SilverStorageService)
- **Scope**: Notebook execution, includes parsing + data access
- **Used by**:
  - `app/ui/notebook_app_duckdb.py` (new DuckDB-based notebook UI)
- **Status**: ⚠️ Mixed concerns (parsing + data access)

---

## Compatibility Issues Identified

### Issue 1: API Inconsistency

**ModelSession API:**
```python
session.get_dimension_df(model_name, node_name)
session.get_fact_df(model_name, node_name)
session.ensure_built()  # Returns (dims, facts)
```

**UniversalSession API:**
```python
session.get_dimension_df(model_name, dim_id)
session.get_fact_df(model_name, fact_id)
session.get_table(model_name, table_name)
```

**NotebookSession API:**
```python
session.storage_service.get_table(model_name, table_name, filters)
session.get_exhibit_data(exhibit_id)
session.apply_filters(...)
```

**Impact**: Services using BaseAPI have workaround logic (see `models/base/service.py:42-52`)

---

### Issue 2: Backend Incompatibility

| Session Type | Backend | DataFrame Type | Filter Format |
|--------------|---------|----------------|---------------|
| ModelSession | Spark | pyspark.sql.DataFrame | Manual filtering |
| UniversalSession | Spark | pyspark.sql.DataFrame | Manual filtering |
| NotebookSession | DuckDB | duckdb.DuckDBPyRelation | SQL-based |

**Impact**: Cannot easily switch between sessions due to different DataFrame types

---

### Issue 3: Duplicate Filter Logic

Filter application exists in 3 places:
1. `models/base/service.py:54-84` (BaseAPI._apply_filters)
2. `app/notebook/api/notebook_session.py:180-250` (_build_filters)
3. `app/services/storage_service.py:80-120` (filter application)

**Impact**: Bug fixes must be applied in multiple places

---

### Issue 4: Model Initialization Duplication

Model loading logic exists in 2 places:
1. `models/api/session.py:162-202` (UniversalSession.load_model)
2. `app/notebook/api/notebook_session.py:97-136` (_initialize_model_sessions)

**Impact**: Different caching strategies, inconsistent behavior

---

## Affected Components Map

### Direct Session Users (Need Migration)

| Component | Current Session | Lines of Code | Complexity | Migration Risk |
|-----------|----------------|---------------|------------|----------------|
| `app/ui/streamlit_app.py` | ModelSession | ~400 | Medium | Medium |
| `scripts/build_silver_layer.py` | UniversalSession | ~150 | Low | Low |
| `scripts/run_forecasts.py` | UniversalSession | ~200 | Low | Low |
| `app/ui/notebook_app_duckdb.py` | NotebookSession | ~350 | High | High |
| Service APIs (3 files) | Both (via BaseAPI) | ~600 | Medium | Medium |

### Indirect Dependencies

| Component | Depends On | Impact |
|-----------|-----------|--------|
| `PricesAPI` | BaseAPI → ModelSession/UniversalSession | Must support unified session |
| `NewsAPI` | BaseAPI → ModelSession/UniversalSession | Must support unified session |
| `CompanyAPI` | BaseAPI → ModelSession/UniversalSession | Must support unified session |
| `SilverStorageService` | NotebookSession | Will be absorbed into UniversalSession |
| Markdown/YAML parsers | NotebookSession (indirectly) | No change needed |
| UI components | NotebookSession (via app) | No direct change |

---

## Consolidation Strategy

### Phase 1: Foundation (Week 1)
**Goal**: Make UniversalSession connection-agnostic and feature-complete

#### Tasks
1. ✅ **Add DuckDB Support to UniversalSession**
   - Detect connection type (Spark vs DuckDB)
   - Add `backend` property
   - Support both DataFrame types

2. ✅ **Unify Filter API**
   - Move filter logic to UniversalSession
   - Support both SQL (DuckDB) and DataFrame API (Spark)
   - Single filter specification format

3. ✅ **Add Caching Layer**
   - Move model session caching to UniversalSession
   - Support per-notebook caching strategy

4. ✅ **Testing Infrastructure**
   - Create UniversalSession test suite
   - Test both Spark and DuckDB backends
   - Test filter application

**Deliverables:**
- Enhanced `UniversalSession` class
- Test suite with 90%+ coverage
- Migration guide document

**Risk Mitigation:**
- Keep existing sessions functional during development
- Use feature flags for gradual rollout

---

### Phase 2: Service Layer Migration (Week 2)
**Goal**: Update service APIs and BaseAPI to use unified session

#### Tasks
1. ✅ **Update BaseAPI**
   - Remove ModelSession compatibility shims
   - Use UniversalSession exclusively
   - Update _get_table() and _apply_filters()

2. ✅ **Update Service APIs**
   - `PricesAPI`: Update initialization
   - `NewsAPI`: Update initialization
   - `CompanyAPI`: Update initialization
   - Test each service independently

3. ✅ **Update Scripts**
   - `build_silver_layer.py`: Already uses UniversalSession (no change)
   - `run_forecasts.py`: Already uses UniversalSession (no change)
   - `Bronze_pull.py`: Check dependencies

**Deliverables:**
- Updated service APIs
- Service integration tests
- Script validation

**Risk Mitigation:**
- Backward compatibility wrappers for external consumers
- Comprehensive integration testing

---

### Phase 3: UI Migration (Week 3)
**Goal**: Migrate both UIs to use UniversalSession

#### Tasks
1. ✅ **Migrate Old UI (streamlit_app.py)**
   - Replace ModelSession with UniversalSession
   - Update cached factories
   - Test all tabs (Prices, News, Company)
   - User acceptance testing

2. ✅ **Refactor NotebookSession**
   - Extract parsing logic → `NotebookManager`
   - Extract data access → delegate to UniversalSession
   - Keep notebook-specific features (exhibit rendering, etc.)

3. ✅ **Update New UI (notebook_app_duckdb.py)**
   - Replace NotebookSession with NotebookManager + UniversalSession
   - Test all markdown notebooks
   - Test filters, exhibits, collapsibles

4. ✅ **Update SilverStorageService**
   - Make it a thin wrapper over UniversalSession
   - Or deprecate entirely if redundant

**Deliverables:**
- Migrated old UI
- Refactored NotebookSession → NotebookManager
- Updated new UI
- UI regression test suite

**Risk Mitigation:**
- Deploy old UI and new UI separately
- Keep fallback branches
- Staged rollout to users

---

### Phase 4: Cleanup & Documentation (Week 4)
**Goal**: Remove deprecated code and finalize documentation

#### Tasks
1. ✅ **Deprecate ModelSession**
   - Mark as deprecated in docstrings
   - Add deprecation warnings
   - Keep code for 2 releases, then remove

2. ✅ **Rename NotebookSession**
   - Rename to NotebookManager (reflects true role)
   - Update all imports
   - Update documentation

3. ✅ **Documentation**
   - Update architecture diagrams
   - Create migration guide for external users
   - Update API documentation
   - Create troubleshooting guide

4. ✅ **Performance Testing**
   - Benchmark query performance (Spark vs DuckDB)
   - Memory profiling
   - Identify optimization opportunities

**Deliverables:**
- Deprecated ModelSession with migration path
- Renamed NotebookManager
- Complete documentation suite
- Performance benchmarks

**Risk Mitigation:**
- Communicate deprecation timeline to all users
- Provide migration examples

---

## Detailed Component Impact Analysis

### High Impact (Requires Code Changes)

#### 1. app/ui/streamlit_app.py
**Current:** Uses ModelSession
**Change Required:** Replace with UniversalSession
**Lines Affected:** ~50 lines
**Testing Effort:** High (UI regression testing)
**User Impact:** None (transparent change)

**Migration Steps:**
```python
# Before
from models.api.session import ModelSession
session = ModelSession(spark, repo_root, storage_cfg)

# After
from models.api.session import UniversalSession
session = UniversalSession(spark, storage_cfg, repo_root, models=['company'])
```

---

#### 2. app/ui/notebook_app_duckdb.py
**Current:** Uses NotebookSession (DuckDB)
**Change Required:** Use NotebookManager + UniversalSession
**Lines Affected:** ~100 lines
**Testing Effort:** Very High (core notebook functionality)
**User Impact:** None (transparent change)

**Migration Steps:**
```python
# Before
from app.notebook.api.notebook_session import NotebookSession
session = NotebookSession(connection, model_registry, repo_root)
notebook_config = session.load_notebook(path)
data = session.get_exhibit_data(exhibit_id)

# After
from app.notebook.api.notebook_manager import NotebookManager
from models.api.session import UniversalSession

universal_session = UniversalSession(connection, storage_cfg, repo_root)
notebook_manager = NotebookManager(universal_session)
notebook_config = notebook_manager.load_notebook(path)
data = universal_session.get_table(model_name, table_name)
```

---

#### 3. Service APIs (PricesAPI, NewsAPI, CompanyAPI)
**Current:** Use BaseAPI with compatibility shims
**Change Required:** Remove shims, use UniversalSession only
**Lines Affected:** ~30 lines (BaseAPI changes)
**Testing Effort:** Medium (service integration tests)
**User Impact:** None (internal change)

**Migration Steps:**
```python
# models/base/service.py
class BaseAPI(ABC):
    def __init__(self, session: UniversalSession, model_name: str):
        # Enforce UniversalSession only
        if not isinstance(session, UniversalSession):
            raise TypeError("BaseAPI requires UniversalSession")
        self.session = session
        self.model_name = model_name

    def _get_table(self, table_name: str):
        # No more compatibility logic
        return self.session.get_table(self.model_name, table_name)
```

---

### Medium Impact (Configuration Changes)

#### 4. Scripts (build_silver_layer.py, run_forecasts.py)
**Current:** Already use UniversalSession
**Change Required:** None (already compatible)
**Lines Affected:** 0
**Testing Effort:** Low (smoke tests only)
**User Impact:** None

---

#### 5. SilverStorageService
**Current:** Wraps connection + model registry
**Change Required:** Become thin wrapper over UniversalSession, or deprecate
**Lines Affected:** ~100 lines
**Testing Effort:** Medium
**User Impact:** None (internal service)

**Decision Required:**
- **Option A**: Keep as compatibility layer for DuckDB-specific optimizations
- **Option B**: Deprecate and use UniversalSession directly
- **Recommendation**: Option A (keep for caching/optimization)

---

### Low Impact (No Changes Required)

#### 6. Markdown/YAML Parsers
**Current:** Used by NotebookSession
**Change Required:** None (pure parsing logic)
**Impact:** Will be used by NotebookManager instead
**User Impact:** None

#### 7. UI Components (filters, exhibits, renderers)
**Current:** Receive data from NotebookSession
**Change Required:** None (data format unchanged)
**Impact:** Will receive data from UniversalSession via NotebookManager
**User Impact:** None

---

## Testing Strategy

### Unit Tests

| Component | Test Coverage | New Tests Needed |
|-----------|---------------|------------------|
| UniversalSession | 90% | 50 tests |
| NotebookManager | 85% | 30 tests |
| BaseAPI | 80% | 20 tests |
| Service APIs | 75% | 40 tests |

### Integration Tests

| Test Scenario | Priority | Estimated Time |
|---------------|----------|----------------|
| Spark backend queries | High | 4 hours |
| DuckDB backend queries | High | 4 hours |
| Filter application (both backends) | High | 6 hours |
| Model loading and caching | High | 4 hours |
| Cross-model queries | Medium | 3 hours |
| Old UI end-to-end | High | 8 hours |
| New UI end-to-end | High | 8 hours |
| Service API integration | Medium | 6 hours |

**Total Testing Effort:** ~43 hours

### Performance Testing

| Test | Baseline | Target | Impact |
|------|----------|--------|--------|
| Notebook load time | 2s | <2.5s | Low |
| Query latency (DuckDB) | 50ms | <75ms | Low |
| Query latency (Spark) | 500ms | <600ms | Low |
| Memory usage | 200MB | <250MB | Low |

---

## Risk Assessment

### High Risks

#### Risk 1: Breaking Existing Notebooks
**Probability:** Medium
**Impact:** High
**Mitigation:**
- Comprehensive regression testing
- Parallel deployment (keep old version available)
- Rollback plan

#### Risk 2: Performance Regression
**Probability:** Low
**Impact:** High
**Mitigation:**
- Performance benchmarks before/after
- Monitor query latencies in production
- Cache optimization

#### Risk 3: Data Access Bugs
**Probability:** Medium
**Impact:** High
**Mitigation:**
- Thorough integration testing
- Data validation checks
- Incremental rollout

### Medium Risks

#### Risk 4: Service API Compatibility
**Probability:** Low
**Impact:** Medium
**Mitigation:**
- Maintain backward compatibility wrappers
- Clear deprecation timeline
- Migration examples

#### Risk 5: DuckDB vs Spark Behavior Differences
**Probability:** Medium
**Impact:** Medium
**Mitigation:**
- Abstract common operations
- Document known differences
- Comprehensive testing on both backends

---

## Rollback Plan

### Phase 1 Rollback
**Trigger:** UniversalSession fails tests
**Action:**
1. Revert UniversalSession changes
2. Keep existing sessions functional
3. No user impact (internal only)

### Phase 2 Rollback
**Trigger:** Service APIs break
**Action:**
1. Revert BaseAPI changes
2. Re-enable compatibility shims
3. Notify dependent services

### Phase 3 Rollback
**Trigger:** UI functionality breaks
**Action:**
1. Revert to old session implementations
2. Keep both UIs on separate branches
3. Deploy old versions
4. Investigate and fix issues

### Phase 4 Rollback
**Trigger:** Performance degradation
**Action:**
1. Revert documentation only
2. Keep code changes (already tested)
3. Optimize problem areas

---

## Success Metrics

### Technical Metrics
- ✅ 100% of tests passing
- ✅ <5% performance degradation
- ✅ Single session API (UniversalSession)
- ✅ Zero deprecated ModelSession usage
- ✅ All UIs functional

### User Metrics
- ✅ Zero user-reported bugs
- ✅ No increase in query latency
- ✅ Notebooks load successfully
- ✅ Filters work correctly

### Code Quality Metrics
- ✅ Reduced code duplication (target: -30%)
- ✅ Improved test coverage (target: >85%)
- ✅ Documentation complete
- ✅ Architecture diagrams updated

---

## Dependencies & Blockers

### External Dependencies
- None (all changes internal to codebase)

### Internal Dependencies
- Phase 2 depends on Phase 1 completion
- Phase 3 depends on Phase 2 completion
- Phase 4 depends on Phase 3 completion

### Potential Blockers
- **Testing Infrastructure**: Need DuckDB + Spark test environments
- **User Acceptance**: Need stakeholder approval before UI migration
- **Performance Requirements**: Must meet latency SLAs

---

## Communication Plan

### Week 0 (Kickoff)
**Audience:** Engineering team
**Message:** Consolidation plan overview, timeline, responsibilities
**Format:** Team meeting + this document

### Week 1-4 (Progress Updates)
**Audience:** Engineering team + stakeholders
**Message:** Weekly progress, blockers, changes
**Format:** Status email + demo sessions

### Week 4 (Completion)
**Audience:** All users
**Message:** Migration complete, what changed, how to get help
**Format:** Announcement email + updated docs

### Ongoing
**Audience:** New developers
**Message:** Architecture guide, best practices
**Format:** Onboarding documentation

---

## Appendix A: File Inventory

### Files to Modify

| File | Change Type | Priority |
|------|-------------|----------|
| `models/api/session.py` | Enhance | P0 |
| `models/base/service.py` | Refactor | P0 |
| `app/notebook/api/notebook_session.py` | Refactor | P0 |
| `app/ui/streamlit_app.py` | Migrate | P1 |
| `app/ui/notebook_app_duckdb.py` | Migrate | P1 |
| `app/services/storage_service.py` | Refactor | P2 |
| `models/implemented/company/services/*.py` | Update | P1 |
| `scripts/*.py` | Validate | P2 |

### Files to Create

| File | Purpose |
|------|---------|
| `app/notebook/api/notebook_manager.py` | New NotebookManager class |
| `tests/integration/test_universal_session.py` | UniversalSession tests |
| `tests/integration/test_notebook_manager.py` | NotebookManager tests |
| `docs/MIGRATION_GUIDE.md` | User migration guide |
| `docs/SESSION_ARCHITECTURE.md` | Architecture documentation |

### Files to Deprecate

| File | Timeline | Removal Date |
|------|----------|--------------|
| ModelSession code in `models/api/session.py` | Deprecate Week 4 | 2 releases later |
| Compatibility shims in `models/base/service.py` | Remove Week 2 | Immediate |

---

## Appendix B: Code Examples

### Example 1: UniversalSession with DuckDB

```python
from models.api.session import UniversalSession
from core.connection import DuckDBConnection

# Initialize connection
connection = DuckDBConnection(db_path="data.duckdb")

# Create session
session = UniversalSession(
    connection=connection,
    storage_cfg=storage_config,
    repo_root=Path.cwd(),
    models=['company', 'forecast']
)

# Query data
prices = session.get_table('company', 'fact_prices')
forecasts = session.get_table('forecast', 'forecast_price')

# Cross-model query
merged = connection.query("""
    SELECT p.*, f.forecast_value
    FROM company.fact_prices p
    LEFT JOIN forecast.forecast_price f
      ON p.ticker = f.ticker AND p.trade_date = f.forecast_date
""")
```

### Example 2: NotebookManager (Refactored)

```python
from app.notebook.api.notebook_manager import NotebookManager
from models.api.session import UniversalSession

# Setup
universal_session = UniversalSession(connection, storage_cfg, repo_root)
notebook_manager = NotebookManager(universal_session)

# Load notebook
config = notebook_manager.load_notebook("notebooks/stock_analysis.md")

# Get exhibit data (delegates to UniversalSession)
data = notebook_manager.get_exhibit_data(
    exhibit_id="price_trend",
    filters={"ticker": ["AAPL", "GOOGL"]}
)

# Render (NotebookManager-specific)
notebook_manager.render_exhibit(exhibit_id="price_trend", data=data)
```

### Example 3: Migration Pattern for Services

```python
# Before (supports both sessions)
class PricesAPI(BaseAPI):
    def __init__(self, session):
        # Accepts ModelSession or UniversalSession
        super().__init__(session, model_name='company')

# After (UniversalSession only)
class PricesAPI(BaseAPI):
    def __init__(self, session: UniversalSession):
        if not isinstance(session, UniversalSession):
            raise TypeError("PricesAPI requires UniversalSession")
        super().__init__(session, model_name='company')
```

---

## Questions & Answers

**Q: Why not keep all three sessions?**
A: Maintenance burden is too high. Every new feature must be implemented 3 times, and bugs must be fixed in 3 places.

**Q: Why UniversalSession as the foundation?**
A: It's already model-agnostic, registry-driven, and designed for extensibility. Adding DuckDB support is easier than making the other sessions extensible.

**Q: What about performance?**
A: UniversalSession adds minimal overhead (~5ms per query). The real performance gain comes from DuckDB (10-100x vs Spark) which will still be available.

**Q: When can we remove ModelSession?**
A: After 2 releases (6 months) to give external consumers time to migrate. Mark as deprecated in Week 4, remove in 6 months.

**Q: Will notebooks break?**
A: No. Notebook files (markdown) don't change. The underlying execution changes, but behavior stays the same.

**Q: What if we find a blocker?**
A: Follow the rollback plan for that phase. Fix the issue, re-test, and proceed. Phased approach minimizes blast radius.

---

## Approval Sign-off

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Tech Lead | | | |
| Engineering Manager | | | |
| Product Owner | | | |
| QA Lead | | | |

---

**Document Version:** 1.0
**Created:** 2025-11-06
**Last Updated:** 2025-11-06
**Owner:** Architecture Team
