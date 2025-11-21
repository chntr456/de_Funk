# Notebook System - Issues Quick Reference

## File-by-File Issues Map

### 🔴 CRITICAL FILES (High Priority)

#### 1. `/app/ui/notebook_app_duckdb.py` (905 lines)
**Status**: MONOLITHIC MESS

| Issue | Line(s) | Severity | Fix Time |
|-------|---------|----------|----------|
| Monolithic app class | 107-905 | CRITICAL | 1 week (refactor) |
| Dead code: `_render_filter_context_info_OLD()` | 338-510 | HIGH | 5 min (delete) |
| Duplicate filter display logic | 247-261, 450-462 | HIGH | 30 min (extract) |
| Inconsistent expander defaults | 251, 447, 474 | MEDIUM | 15 min (fix) |
| Debug code in sidebar | 104 | MEDIUM | 5 min (remove) |

**Recommended Action**: Extract into 5-6 component classes with <150 lines each

---

#### 2. `/app/ui/components/markdown_renderer.py` (250+ lines)
**Status**: COMPLEX RENDERING LOGIC

| Issue | Line(s) | Severity | Fix Time |
|-------|---------|----------|----------|
| Excessive expander wrapping | 225-233 | CRITICAL | 1 hour |
| Duplicate exhibit rendering | 97-146 | HIGH | 1 hour (use registry) |
| Complex collapsible logic | 149-179 | MEDIUM | 2 hours |
| Debug statements | 104-115 | MEDIUM | 5 min (remove) |
| Missing type hints | 13-180 | MEDIUM | 1 hour |

**Recommended Action**: Reduce to 100 lines by using exhibit registry and removing excessive expanders

---

#### 3. `/app/notebook/managers/notebook_manager.py` (943 lines)
**Status**: COMPLEX FILTER MERGING

| Issue | Line(s) | Severity | Fix Time |
|-------|---------|----------|----------|
| Complex filter merging | 203-247 | HIGH | 2 hours (simplify) |
| Print debugging | 580, 600, 650 | MEDIUM | 15 min (use logging) |
| Hardcoded skip filters | 843 | MEDIUM | 30 min (config) |
| Multiple filter strategies | 687-810 | HIGH | 3 hours (consolidate) |
| Missing type hints | Multiple | LOW | 2 hours |

**Recommended Action**: Simplify filter merging, add logging, extract reusable components

---

### 🟠 HIGH PRIORITY FILES

#### 4. `/app/notebook/parsers/markdown_parser.py` (593 lines)
**Status**: REGEX BRITTLE

| Issue | Line(s) | Severity | Fix Time |
|-------|---------|----------|----------|
| Brittle regex patterns | 54-57 | HIGH | 4 hours (replace with proper parser) |
| Complex placeholder logic | 190-371 | MEDIUM | 3 hours (AST-based) |
| No error recovery | Multiple | MEDIUM | 2 hours (add validation) |

**Recommended Action**: Replace with AST-based parser library (e.g., `frontmatter`)

---

#### 5. `/app/ui/components/sidebar.py` (150+ lines)
**Status**: NOTEBOOK DISCOVERY

| Issue | Line(s) | Severity | Fix Time |
|-------|---------|----------|----------|
| No notebook creation UI | Full | MEDIUM | 2 hours (add feature) |
| Expander styling inconsistent | 48 | LOW | 15 min (fix) |

---

### 🟡 MEDIUM PRIORITY FILES

#### 6. `/app/ui/components/exhibits/__init__.py`
**Status**: HARDCODED IMPORTS

| Issue | Line(s) | Severity | Fix Time |
|-------|---------|----------|----------|
| Manual exhibit registration | 7-22 | MEDIUM | 1 hour (create registry) |
| No plugin system | Full | MEDIUM | 2 hours (implement) |

**Action**: Create `exhibits/registry.py` with EXHIBIT_RENDERERS dict

---

#### 7. `/app/ui/components/dynamic_filters.py` (200+ lines)
**Status**: FILTER WIDGETS

| Issue | Line(s) | Severity | Fix Time |
|-------|---------|----------|----------|
| State management complexity | 99-108 | MEDIUM | 1 hour |
| Folder clearing logic | 38-54 | LOW | 20 min |

---

#### 8. `/app/notebook/filters/dynamic.py` (150+ lines)
**Status**: FILTER MODELS

| Issue | Line(s) | Severity | Fix Time |
|-------|---------|----------|----------|
| Three filter representations | Full | MEDIUM | 2 hours (simplify) |
| FilterState/FilterConfig overlap | ~40-100 | MEDIUM | 1 hour (consolidate) |

---

## Code Duplication Heat Map

### Duplicate Code Locations

```
Filter Display Logic (appearing 3+ times):
├── notebook_app_duckdb.py:247-261
├── notebook_app_duckdb.py:450-462
└── active_filters_display.py:[location]
📊 Impact: Changes required in 3 places
💡 Solution: Extract to `filter_display.py` component

Exhibit Rendering Dispatch (appearing 2+ times):
├── notebook_view.py:71-123
└── markdown_renderer.py:97-146
📊 Impact: 10+ places need updates when adding exhibit types
💡 Solution: Create EXHIBIT_RENDERERS registry

Filter Type Inference (appearing 2 times):
├── notebook_app_duckdb.py:377-410
└── notebook_manager.py:287-367
📊 Impact: Same logic, different implementations
💡 Solution: Create utils/filter_inference.py
```

---

## Session State Chaos

### Inconsistent Session State Keys

```python
# Current state (MESSY)
st.session_state.open_tabs              # List
st.session_state.active_tab             # String
st.session_state.edit_mode[nb_id]       # Dict
st.session_state.markdown_content[nb]   # Dict
st.session_state.show_graph_viewer      # Bool
st.session_state.filter_editor_open     # Bool
st.session_state['filter_' + id]        # Namespaced
st.session_state['date_start_' + id]    # Namespaced
st.session_state.last_filter_folder     # String
st.session_state.notebook_model_sessions[id]  # Dict
st.session_state.current_notebook_id    # String
st.session_state.theme                  # String
st.session_state.repo_context           # Object
st.session_state.model_registry         # Object
st.session_state.universal_session      # Object
st.session_state.notebook_manager       # Object

# Recommended (CLEAN)
state = UIState.get()
state.open_tabs
state.active_tab
state.edit_mode[nb_id]
state.markdown_content[nb]
state.show_graph_viewer
# ... all initialized, typed, and centralized
```

---

## Filter System Nightmare

### Current Filter Flow (Complex)

```
Markdown $filter${} block
    ↓ parse_filter()
FilterConfig (id, type, label, source, operator, ...)
    ↓ FilterCollection.add_filter()
FilterState (filter_id, config, current_value, available_options, ...)
    ↓ render_dynamic_filters()
st.session_state['filter_{id}']
    ↓ notebook_manager._sync_session_state_to_filters()
FilterState.current_value updated
    ↓ notebook_manager._build_filters()
Dict[str, Any] for UniversalSession
    ↓ FilterEngine.build_filter_sql()
SQL WHERE clause
```

**Issues**:
- 7 transformation steps → 7 places for bugs
- FilterConfig vs FilterState confusion
- Multiple merging strategies
- Cross-model validation mixed in

**Recommended**: 3-step flow
1. Filter definition (FilterConfig)
2. Runtime state (FilterValue)
3. Query execution (filter dict)

---

## Expander Overuse Analysis

### Current Expander Locations

```
notebook_view.py:122             ✗ Detail expander for errors
markdown_renderer.py:55          ✗ Error details expander
markdown_renderer.py:143         ✓ Exhibit collapsible (OK)
markdown_renderer.py:162         ✓ Section collapsible (OK)
markdown_renderer.py:232         ✗ ALL text wrapped in expander (BAD)
notebook_app_duckdb.py:251       ✗ Active filters (usually empty)
notebook_app_duckdb.py:447       ✗ Global context
notebook_app_duckdb.py:474       ✗ Folder context
sidebar.py:48                    ✓ Folder nav (OK)
sidebar.py:58                    ✓ Model graph (OK)
exhibits/forecast_chart.py       ✗ Extra expanders
exhibits/base_renderer.py        ✗ Configuration expanders
exhibits/weighted_aggregate_...  ✗ Summary expanders

TOTAL: 12+ expanders on typical page
SHOULD BE: 2-3 expanders max
```

**Problem**: Users expand expanders → find empty content → close → repeat

**Solution**: Only use expanders for:
- Advanced/optional content
- Troubleshooting sections
- Rarely-used settings

---

## Refactoring Priority Queue

### Week 1 (Quick Wins)
- [ ] Remove `_render_filter_context_info_OLD()` - 5 min
- [ ] Replace print() with logging - 15 min
- [ ] Remove debug st.caption() calls - 5 min
- [ ] Create UIState manager - 2 hours
- [ ] Create EXHIBIT_RENDERERS registry - 1 hour

### Week 2 (Medium Refactoring)
- [ ] Extract filter_display component - 1 hour
- [ ] Extract header component - 2 hours
- [ ] Fix expander overuse in markdown_renderer - 1 hour
- [ ] Add comprehensive type hints - 2 hours
- [ ] Create filter_inference utility - 1 hour

### Week 3-4 (Major Architecture)
- [ ] Split monolithic app (notebook_app_duckdb.py) - 3 days
- [ ] Replace regex parser with AST - 2 days
- [ ] Simplify filter merging logic - 1 day
- [ ] Add notebook creation UI - 1 day
- [ ] Comprehensive logging throughout - 1 day

---

## Testing Strategy

### Add Unit Tests for:
1. `markdown_parser.py` - Regex edge cases, YAML parsing
2. `notebook_manager.py` - Filter merging logic
3. `dynamic.py` - Filter state transitions
4. `markdown_ast.py` - AST building (once created)

### Add Integration Tests for:
1. Markdown → Exhibit rendering
2. Filter → Exhibit data flow
3. Folder context switching
4. Notebook reload on changes

### Add E2E Tests for:
1. Create notebook → Edit → Save → Render
2. Apply filter → Data updates
3. Switch folders → Filters reset

---

## File Dependencies (Change Impact)

### If you modify...

**markdown_parser.py**
- Check: notebook_manager.py, markdown_renderer.py, tests

**notebook_manager.py**
- Check: notebook_app_duckdb.py, markdown_renderer.py, exhibits/*

**markdown_renderer.py**
- Check: notebook_app_duckdb.py, dynamic_filters.py

**dynamic_filters.py**
- Check: notebook_manager.py, sidebar.py

**exhibits/__init__.py**
- Check: notebook_view.py, markdown_renderer.py, registry.py (new)

**notebook_app_duckdb.py**
- Check: ALL other files (depends on everything)

---

## Key Metrics

```
Complexity Analysis:

Component                 | Lines | Cyclomatic | Status
--------------------------|-------|-----------|----------
notebook_app_duckdb       | 905   | 25+       | CRITICAL
notebook_manager          | 943   | 20+       | HIGH
markdown_renderer         | 250+  | 15+       | HIGH
markdown_parser           | 593   | 12+       | MEDIUM
dynamic_filters           | 200+  | 10+       | MEDIUM
sidebar                   | 150   | 8         | LOW
folder_context            | 200   | 6         | LOW
schema                    | 400   | 2         | OK
dynamic.py                | 150   | 3         | OK
parser_filter_helpers     | 114   | 2         | OK

Total LOC (app/):         10,176
Tested coverage:          ~10% (estimated)
```

---

## Success Criteria

### After Refactoring

- [ ] Single file ≤ 250 lines
- [ ] No duplicate code patterns
- [ ] <5 expanders per page
- [ ] 80%+ test coverage
- [ ] Zero dead code
- [ ] Logging instead of print()
- [ ] Complete type hints
- [ ] Plugin-based exhibit system
- [ ] <30 second notebook render time
- [ ] Zero hardcoded values

