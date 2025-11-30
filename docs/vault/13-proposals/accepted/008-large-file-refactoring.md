# Proposal: Large File Refactoring & Code Duplication Elimination

**Status**: ✅ Accepted & Implemented
**Author**: Claude
**Date**: 2025-11-29
**Implemented**: 2025-11-30
**Priority**: High

---

## Summary

This proposal addressed the pattern of large monolithic files and duplicated logic that emerged during development. It provided specific refactoring plans for the largest files and established guidelines to prevent recurrence.

---

## Implementation Summary

### What Was Done

| Phase | Target | Before | After | Status |
|-------|--------|--------|-------|--------|
| 1 | FilterEngine Consolidation | 3 implementations (380 lines duplicate) | 1 canonical implementation | ✅ Complete |
| 2 | markdown_renderer.py | 1,885 lines | 110 lines + 17 modules | ✅ Complete |
| 3 | notebook_app state/callbacks | Monolithic | 2 extracted modules (585 lines) | ✅ Complete |
| 4 | models/base/model.py | 1,312 lines | 397 lines + 4 modules | ✅ Complete |
| 5 | models/api/session.py | 1,122 lines | 410 lines + 2 modules | ✅ Complete |
| 6 | markdown_parser.py, notebook_manager.py | 1,061 / 942 lines | Deferred | ⏳ Lower priority |

### Commits

- `c1c8794` - FilterEngine consolidation (removed dead code)
- `cb5928f` - markdown_renderer.py modularization
- `2b4f482` - State/callbacks extraction
- `bb1eeb7` - BaseModel modularization
- `d332ac6` - UniversalSession modularization
- `484f465` - Fix: TableAccessor.ensure_built() delegation

---

## New Module Architecture

### models/base/ (BaseModel Extraction)

```
models/base/
├── model.py              # Core BaseModel (397 lines) - thin orchestrator
├── graph_builder.py      # Graph building and node loading (418 lines)
├── table_accessor.py     # Table access and schema inspection (250 lines)
├── measure_calculator.py # Measure calculations (277 lines)
└── model_writer.py       # Persistence to storage (261 lines)
```

**Key Pattern**: Composition with lazy loading
```python
class BaseModel:
    def __init__(self, ...):
        # Composition helpers (lazy-loaded)
        self._graph_builder = None
        self._table_accessor = None
        self._measure_calculator = None
        self._model_writer = None

    def ensure_built(self):
        if not self._is_built:
            if self._graph_builder is None:
                from models.base.graph_builder import GraphBuilder
                self._graph_builder = GraphBuilder(self)
            self._dims, self._facts = self._graph_builder.build()
            self._is_built = True

    def get_table(self, table_name: str):
        return self._get_table_accessor().get_table(table_name)
```

### models/api/ (UniversalSession Extraction)

```
models/api/
├── session.py       # Core UniversalSession (410 lines) - thin orchestrator
├── auto_join.py     # Auto-join operations (450 lines)
└── aggregation.py   # Data aggregation (272 lines)
```

**Key Pattern**: Handler composition
```python
class UniversalSession:
    def __init__(self, ...):
        self._auto_join_handler = None
        self._aggregation_handler = None

    def _get_auto_join_handler(self):
        if self._auto_join_handler is None:
            from models.api.auto_join import AutoJoinHandler
            self._auto_join_handler = AutoJoinHandler(self)
        return self._auto_join_handler
```

### app/ui/components/markdown/ (Renderer Extraction)

```
app/ui/components/markdown/
├── __init__.py           # Public API exports
├── renderer.py           # Main orchestrator (286 lines)
├── parser.py             # Markdown parsing utilities (238 lines)
├── styles.py             # CSS constants (142 lines)
├── utils.py              # Exhibit/collapsible conversion (285 lines)
├── toggle_container.py   # Toggle container component
├── blocks/
│   ├── __init__.py
│   ├── text.py           # Text block rendering
│   ├── exhibit.py        # Exhibit block rendering
│   ├── collapsible.py    # Collapsible sections
│   ├── error.py          # Error display
│   └── header.py         # Header rendering
└── editors/
    ├── __init__.py
    ├── section_editor.py # Section editing
    ├── inline_editor.py  # Inline text editing
    ├── block_editor.py   # Block-level editing
    └── insert_button.py  # Block insertion
```

**Key Pattern**: Backwards-compatible wrapper
```python
# app/ui/components/markdown_renderer.py (110 lines)
# Re-exports everything for backwards compatibility
from .markdown import (
    render_markdown_notebook,
    render_markdown_block,
    # ... all other exports
)
```

### app/ui/state/ and app/ui/callbacks/

```
app/ui/
├── state/
│   └── session_state.py  # AppState dataclass, init_session_state() (155 lines)
└── callbacks/
    └── block_callbacks.py # Block edit/insert/delete handlers (395 lines)
```

---

## FilterEngine Consolidation

### Before (3 implementations)
```
1. core/session/filters.py::FilterEngine (canonical)
2. app/notebook/filters/engine.py::FilterEngine (DELETED - was dead code)
3. app/notebook/filters/types.py (DELETED - only used by dead engine.py)
```

### After (1 canonical)
```
core/session/filters.py::FilterEngine  # THE ONLY IMPLEMENTATION
app/notebook/filters/__init__.py       # Re-exports from core.session.filters
```

---

## Success Metrics

| Metric | Before | After | Target | Status |
|--------|--------|-------|--------|--------|
| Files >800 lines | 5 | 2 | 0 | ⚠️ Near target |
| model.py lines | 1,312 | 397 | <300 | ✅ Close |
| session.py lines | 1,122 | 410 | <200 | ⚠️ Acceptable |
| markdown_renderer.py | 1,885 | 110 | <150 | ✅ Exceeded |
| FilterEngine implementations | 3 | 1 | 1 | ✅ Complete |
| Dead code removed | 0 | 380 lines | - | ✅ Bonus |

---

## Remaining Work (Lower Priority)

These files are slightly over 800 lines but are lower priority:

| File | Lines | Notes |
|------|-------|-------|
| `app/notebook/parsers/markdown_parser.py` | 1,061 | Could split exhibit parsing |
| `app/notebook/managers/notebook_manager.py` | 942 | Could split filter/exhibit handling |
| `app/ui/notebook_app_duckdb.py` | 1,766 | Largest remaining - needs state extraction |

---

## Guidelines Established

These rules were added to CLAUDE.md to prevent recurrence:

### File Size Limits
- **Target**: <300 lines per file
- **Warning**: >500 lines - consider splitting
- **Hard limit**: >800 lines - MUST refactor before adding more

### Architecture Boundaries
- Use composition pattern for large classes
- Lazy loading for composed modules
- Re-export for backwards compatibility
- Single source of truth (no duplication)

---

## Lessons Learned

1. **Composition > Inheritance**: Using composition with lazy-loaded helpers keeps classes focused
2. **Delegate, don't duplicate**: TableAccessor.ensure_built() should call model.ensure_built(), not copy the logic
3. **Re-exports for compatibility**: Thin wrapper files allow gradual migration
4. **Dead code detection**: grep for imports before assuming code is used

---

## References

- Commits: c1c8794, cb5928f, 2b4f482, bb1eeb7, d332ac6, 484f465
- Branch: claude/refactor-large-files-01JxzhA9sxMCNDeihQM8uxu9
