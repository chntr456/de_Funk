# Graph Architecture Refactor - Code Scan

**Goal:** Centralize graph orchestration in UniversalSession, remove redundant graph deployment from BaseModel

---

## 1. BaseModel Graph Deployment Methods

### Methods to Remove/Simplify:
- `models/base/model.py::_build_nodes()` - **KEEP** (loads tables from Bronze)
- `models/base/model.py::_apply_edges()` - **REMOVE** (edge validation, already skipped for DuckDB)
- `models/base/model.py::_materialize_paths()` - **REMOVE** (path materialization, already skipped for DuckDB)

### Usage:
```
./models/base/model.py:224        nodes = self._build_nodes()
./models/base/model.py:225        self._apply_edges(nodes)
./models/base/model.py:226        paths = self._materialize_paths(nodes)
```

**Action:** Simplify `build()` to only call `_build_nodes()`, remove edge/path logic

---

## 2. ModelGraph Usage

### Current Instantiation:
```python
# models/api/session.py:102
self.model_graph = ModelGraph()
self.model_graph.build_from_config_dir(models_dir)
```

**Status:** ✅ Already centralized in UniversalSession

### Usage Points:

#### A. Notebook Manager (Filter Validation)
```python
# app/notebook/managers/notebook_manager.py:672
return self.session.model_graph.are_related(model_a, model_b)

# app/notebook/managers/notebook_manager.py:~580
elif not self._models_are_related(exhibit_model, filter_model):
    continue  # Skip cross-model filter
```

**Action:** Move `are_related()` check to UniversalSession method

#### B. UI Components (Visualization)
```python
# app/ui/notebook_app_duckdb.py
model_graph = self.notebook_manager.session.model_graph

# app/ui/components/sidebar.py
model_graph = self.notebook_session.session.model_graph

# app/ui/components/model_graph_viewer.py
- metrics = model_graph.get_metrics()
- stats = model_graph.get_model_stats(node)
- build_order = model_graph.get_build_order()
- path = model_graph.get_join_path(model_a, model_b)
- related = model_graph.are_related(model_a, model_b)
```

**Action:** Access via `session.model_graph` (no change needed, already goes through session)

#### C. Debug Script
```python
# debug_forecast_view.py
list(session.model_graph.graph.nodes())
```

**Action:** Update to use session methods

---

## 3. GraphQueryPlanner Usage

### Current Instantiation:
```python
# models/base/model.py:101
self._query_planner = None

# models/base/model.py:128 (@property)
if self._query_planner is None:
    from models.api.query_planner import GraphQueryPlanner
    self._query_planner = GraphQueryPlanner(self)
return self._query_planner
```

**Status:** ❌ Instantiated per-model, should be managed by session

### Usage Points:

#### A. BaseModel Methods
```python
# models/base/model.py:753
return self.query_planner.get_table_enriched(table_name, enrich_with, columns)
```

**Action:** Keep property for backwards compat, but instantiate via session

#### B. Measure Executor
```python
# models/base/measures/executor.py:325
query_planner = self.model.query_planner
tables_with_column = query_planner.find_tables_with_column(column)
join_path = query_planner.get_join_path(base_table, target_table)
```

**Action:** No change needed (accesses via model.query_planner property)

#### C. Examples (Documentation)
```python
# examples/measure_auto_enrich_demo.py
# examples/dual_backend_example.py
# examples/measure_auto_enrich_example.py
# examples/query_planner_example.py
planner = equity_model.query_planner
```

**Action:** Examples still work via property

---

## 4. Direct YAML Graph Config Access

### UniversalSession Reading YAML Directly:
```python
# models/api/session.py:338 (get_filter_column_mappings)
model_config = self.registry.get_model_config(model_name)
if 'graph' not in model_config or 'edges' not in model_config['graph']:
    return mappings
for edge in model_config['graph']['edges']:
    # Process edges...

# models/api/session.py:562 (_plan_auto_joins)
model_config = self.registry.get_model_config(model_name)
graph_config = model_config.get('graph', {})
for edge in graph_config.get('edges', []):
    # Process edges...
```

**Status:** ❌ Bypasses ModelGraph, reads YAML directly

**Action:** Refactor to use ModelGraph methods for edge queries

---

## 5. model.build() Calls

### Build Scripts:
```python
# scripts/build_all_models.py:563
dims, facts = model.build()

# scripts/clear_and_refresh.py
dims, facts = model.build()

# scripts/build_equity_silver.py
dims, facts = equity_model.build()
```

**Action:** No change needed (build() signature stays same)

### Model Internal:
```python
# models/base/model.py:184
self._dims, self._facts = self.build()  # Lazy load
```

**Action:** Works as-is after simplification

---

## 6. Filter Relationship Logic

### Current Flow:
```
NotebookManager._models_are_related()
  → session.model_graph.are_related()
    → Used to skip cross-model filters
```

### Proposed Flow:
```
UniversalSession.should_apply_filter(filter_model, target_model)
  → self.model_graph.are_related()
    → Centralized filter validation
```

**Action:** Add method to UniversalSession, update NotebookManager

---

## Refactoring Plan

### Phase 1: Simplify BaseModel (No Breaking Changes)
1. Remove `_apply_edges()` logic (already no-op for DuckDB)
2. Remove `_materialize_paths()` logic (already no-op for DuckDB)
3. Simplify `build()` to just call `_build_nodes()`

### Phase 2: Centralize Graph Access
4. Add UniversalSession methods:
   - `should_apply_cross_model_filter(source_model, target_model) -> bool`
   - `get_model_relationship_path(model_a, model_b) -> Optional[List[str]]`
   - Expose ModelGraph methods directly on session

5. Refactor UniversalSession internal methods:
   - `get_filter_column_mappings()` - use ModelGraph instead of YAML
   - `_plan_auto_joins()` - use ModelGraph instead of YAML

### Phase 3: Update Consumers
6. Update NotebookManager to use session methods
7. Update UI components (already use session.model_graph, minimal changes)
8. Update debug scripts

### Phase 4: GraphQueryPlanner (Optional)
9. Consider moving GraphQueryPlanner instantiation to session
10. Keep BaseModel.query_planner property for convenience

---

## Files Requiring Changes

### Critical:
- ✅ `models/base/model.py` - Simplify build(), remove edge/path deployment
- ✅ `models/api/session.py` - Add convenience methods, use ModelGraph internally
- ✅ `app/notebook/managers/notebook_manager.py` - Use session methods for filter validation

### Minor Updates:
- `app/ui/components/model_graph_viewer.py` - Already uses session.model_graph ✅
- `app/ui/components/sidebar.py` - Already uses session.model_graph ✅
- `debug_forecast_view.py` - Update to use session methods

### Examples (Documentation):
- `examples/measure_auto_enrich_demo.py`
- `examples/dual_backend_example.py`
- `examples/measure_auto_enrich_example.py`
- `examples/query_planner_example.py`

**Note:** Examples continue to work via model.query_planner property

---

## Expected Benefits

1. **Simpler BaseModel** - Just builds tables, no graph logic
2. **Centralized orchestration** - UniversalSession owns all graph operations
3. **No redundancy** - Single source of truth for graph traversal
4. **Cleaner separation** - Build time vs Query time clearly separated
5. **Easier testing** - Graph logic in one place

---

## Risk Assessment

**Low Risk:**
- BaseModel changes (graph deployment already disabled for DuckDB)
- UI changes (already use session.model_graph)
- Filter validation (moving to session, cleaner)

**Zero Risk:**
- Build scripts (model.build() signature unchanged)
- Examples (still work via properties)

**No Breaking Changes:**
- Keep model.query_planner property
- Keep ModelGraph public API
- All external APIs remain compatible
