# Proposal: Large File Refactoring & Code Duplication Elimination

**Status**: Draft
**Author**: Claude
**Date**: 2025-11-29
**Updated**: 2025-11-29
**Priority**: High

---

## Summary

This proposal addresses the pattern of large monolithic files and duplicated logic that emerged during development. It provides specific refactoring plans for the 4 largest files and establishes guidelines to prevent recurrence.

---

## Root Cause Analysis

### Why Did This Happen?

When Claude adds features without explicit guidance:

1. **Path of least resistance**: Adding a function to an existing file is easier than creating a new module
2. **No file size constraints**: Without a rule like "files should be <300 lines", growth happens organically
3. **Context limitations**: Each session doesn't see the full history of a file's growth
4. **Feature creep**: "Just add one more function" compounds over time
5. **No architecture review**: No checkpoint asking "should this be a new module?"

### The Pattern

```
Session 1: Create markdown_renderer.py (200 lines)
Session 2: Add toggle support (+150 lines = 350 lines)
Session 3: Add editing capability (+300 lines = 650 lines)
Session 4: Add block types (+200 lines = 850 lines)
Session 5: Add styling (+150 lines = 1000 lines)
...
Session N: 1,885 lines, 35+ functions, no refactoring
```

---

## Files Requiring Refactoring

### 1. `app/ui/components/markdown_renderer.py` (1,885 lines)

**Current State**: Monolithic file handling rendering, editing, parsing, and styling.

**Proposed Structure**:
```
app/ui/components/markdown/
├── __init__.py              # Public API exports
├── renderer.py              # Main render() entry point (~150 lines)
├── parser.py                # Markdown parsing logic (~200 lines)
├── blocks/
│   ├── __init__.py
│   ├── base.py              # BlockRenderer base class
│   ├── text.py              # Paragraphs, headers
│   ├── code.py              # Code blocks, syntax highlighting
│   ├── toggle.py            # Collapsible sections
│   ├── table.py             # Table rendering
│   ├── exhibit.py           # Data exhibits ($exhibits${})
│   └── filter.py            # Filter blocks ($filter${})
├── editors/
│   ├── __init__.py
│   ├── inline_editor.py     # In-place text editing
│   └── block_editor.py      # Block-level editing
├── styles.py                # CSS and styling constants (~100 lines)
└── utils.py                 # Helper functions (~100 lines)
```

**Refactoring Steps**:

```python
# Step 1: Extract styles (easiest, no dependencies)
# FROM: markdown_renderer.py lines 1-50 (CSS constants)
# TO: styles.py

# styles.py
BLOCK_STYLES = {
    'code': 'background: #f5f5f5; padding: 10px;',
    'toggle': 'border-left: 3px solid #007bff;',
    # ...
}

def get_block_style(block_type: str) -> str:
    return BLOCK_STYLES.get(block_type, '')
```

```python
# Step 2: Extract parser
# FROM: markdown_renderer.py (parsing functions)
# TO: parser.py

# parser.py
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class ParsedBlock:
    block_type: str
    content: str
    metadata: dict
    line_start: int
    line_end: int

class MarkdownParser:
    def parse(self, content: str) -> List[ParsedBlock]:
        """Parse markdown into structured blocks."""
        blocks = []
        # ... parsing logic
        return blocks

    def _parse_exhibit_block(self, content: str) -> ParsedBlock:
        """Parse $exhibits${...} syntax."""
        pass

    def _parse_filter_block(self, content: str) -> ParsedBlock:
        """Parse $filter${...} syntax."""
        pass
```

```python
# Step 3: Extract block renderers (one per type)
# FROM: markdown_renderer.py (render_* functions)
# TO: blocks/*.py

# blocks/base.py
from abc import ABC, abstractmethod
import streamlit as st

class BlockRenderer(ABC):
    """Base class for all block renderers."""

    @abstractmethod
    def render(self, block: ParsedBlock, context: RenderContext) -> None:
        """Render the block to Streamlit."""
        pass

    @abstractmethod
    def can_edit(self) -> bool:
        """Whether this block type supports editing."""
        pass

# blocks/toggle.py
class ToggleBlockRenderer(BlockRenderer):
    """Render collapsible toggle sections."""

    def render(self, block: ParsedBlock, context: RenderContext) -> None:
        with st.expander(block.metadata.get('title', 'Toggle')):
            st.markdown(block.content)

    def can_edit(self) -> bool:
        return True
```

```python
# Step 4: Main renderer becomes thin orchestrator
# renderer.py (~150 lines)

from .parser import MarkdownParser
from .blocks import get_renderer_for_block
from .styles import apply_styles

class MarkdownRenderer:
    def __init__(self):
        self.parser = MarkdownParser()
        self.renderers = self._load_renderers()

    def render(self, content: str, editable: bool = False) -> None:
        """Main entry point - render markdown content."""
        blocks = self.parser.parse(content)

        for block in blocks:
            renderer = self.renderers.get(block.block_type)
            if renderer:
                renderer.render(block, self._create_context(editable))
            else:
                self._render_default(block)
```

---

### 2. `app/ui/notebook_app_duckdb.py` (1,766 lines)

**Current State**: Entire Streamlit app in one file - UI, state, queries, callbacks.

**Proposed Structure**:
```
app/ui/
├── notebook_app.py           # Main entry point (~100 lines)
├── state/
│   ├── __init__.py
│   ├── session_state.py      # st.session_state management
│   └── app_state.py          # Application state dataclass
├── pages/
│   ├── __init__.py
│   ├── notebook_page.py      # Notebook viewing/editing
│   ├── sidebar.py            # Sidebar navigation
│   └── settings_page.py      # Settings UI
├── components/
│   ├── __init__.py
│   ├── filter_panel.py       # Filter UI components
│   ├── exhibit_panel.py      # Data visualization
│   └── toolbar.py            # Action buttons
├── services/
│   ├── __init__.py
│   ├── notebook_service.py   # Notebook loading/saving
│   └── query_service.py      # Data queries
└── callbacks/
    ├── __init__.py
    └── notebook_callbacks.py # Event handlers
```

**Key Extractions**:

```python
# state/app_state.py
from dataclasses import dataclass, field
from typing import Optional, List, Dict

@dataclass
class AppState:
    """Centralized application state."""
    current_notebook: Optional[str] = None
    active_filters: Dict[str, any] = field(default_factory=dict)
    selected_model: Optional[str] = None
    sidebar_expanded: bool = True
    edit_mode: bool = False

    def to_session_state(self) -> None:
        """Sync to Streamlit session state."""
        for key, value in self.__dict__.items():
            st.session_state[f'app_{key}'] = value

    @classmethod
    def from_session_state(cls) -> 'AppState':
        """Load from Streamlit session state."""
        return cls(
            current_notebook=st.session_state.get('app_current_notebook'),
            # ...
        )
```

```python
# services/notebook_service.py
class NotebookService:
    """Business logic for notebook operations."""

    def __init__(self, storage_path: Path):
        self.storage_path = storage_path

    def list_notebooks(self, category: Optional[str] = None) -> List[NotebookMeta]:
        """List available notebooks."""
        pass

    def load_notebook(self, notebook_id: str) -> Notebook:
        """Load notebook content and metadata."""
        pass

    def save_notebook(self, notebook: Notebook) -> None:
        """Save notebook changes."""
        pass
```

```python
# notebook_app.py - Thin entry point
import streamlit as st
from app.ui.state import AppState
from app.ui.pages import NotebookPage, Sidebar
from app.ui.services import NotebookService

def main():
    st.set_page_config(page_title="de_Funk Notebooks", layout="wide")

    # Initialize state
    state = AppState.from_session_state()
    services = _init_services()

    # Render UI
    with st.sidebar:
        Sidebar(state, services).render()

    NotebookPage(state, services).render()

    # Sync state back
    state.to_session_state()

if __name__ == "__main__":
    main()
```

---

### 3. `models/base/model.py` (1,312 lines)

**Current State**: BaseModel does everything - table access, measures, filters, metadata.

**Proposed Structure**:
```
models/base/
├── model.py                  # Core BaseModel (~300 lines)
├── table_accessor.py         # Table loading and caching
├── measure_executor.py       # Measure calculation logic
├── filter_applicator.py      # Filter application
├── metadata_provider.py      # Model metadata methods
├── schema_validator.py       # Schema validation
└── mixins/
    ├── __init__.py
    ├── queryable.py          # Query-related methods
    └── cacheable.py          # Caching behavior
```

**Separation of Concerns**:

```python
# table_accessor.py
class TableAccessor:
    """Handles table loading and caching."""

    def __init__(self, storage_path: Path, backend: str):
        self.storage_path = storage_path
        self.backend = backend
        self._cache: Dict[str, DataFrame] = {}

    def get_table(self, table_name: str, use_cache: bool = True) -> DataFrame:
        """Load table from storage."""
        if use_cache and table_name in self._cache:
            return self._cache[table_name]

        df = self._load_from_parquet(table_name)

        if use_cache:
            self._cache[table_name] = df

        return df

    def invalidate_cache(self, table_name: Optional[str] = None) -> None:
        """Clear cached tables."""
        if table_name:
            self._cache.pop(table_name, None)
        else:
            self._cache.clear()
```

```python
# measure_executor.py
class MeasureExecutor:
    """Execute measure calculations."""

    def __init__(self, model_config: Dict, table_accessor: TableAccessor):
        self.config = model_config
        self.tables = table_accessor
        self._python_measures = self._load_python_measures()

    def calculate(
        self,
        measure_name: str,
        filters: Optional[Dict] = None,
        **kwargs
    ) -> Any:
        """Calculate a measure by name."""
        measure_def = self._get_measure_definition(measure_name)

        if measure_def.get('type') == 'python':
            return self._execute_python_measure(measure_name, filters, kwargs)
        else:
            return self._execute_yaml_measure(measure_def, filters)
```

```python
# model.py - Now much cleaner
class BaseModel:
    """Base class for all domain models."""

    def __init__(self, connection, storage_cfg: Dict, model_cfg: Dict):
        self.connection = connection
        self.config = model_cfg

        # Compose from focused components
        self._tables = TableAccessor(storage_cfg['root'], self._detect_backend())
        self._measures = MeasureExecutor(model_cfg, self._tables)
        self._filters = FilterApplicator(self._detect_backend())
        self._metadata = MetadataProvider(model_cfg)

    # Delegate to components
    def get_table(self, name: str) -> DataFrame:
        return self._tables.get_table(name)

    def calculate_measure(self, name: str, **kwargs) -> Any:
        return self._measures.calculate(name, **kwargs)

    def get_metadata(self) -> Dict:
        return self._metadata.get_all()
```

---

### 4. `models/api/session.py` (1,121 lines)

**Proposed Structure**:
```
models/api/
├── session.py               # UniversalSession (~200 lines)
├── query_executor.py        # SQL execution
├── model_loader.py          # Dynamic model loading
├── result_formatter.py      # DataFrame formatting
└── cross_model_joiner.py    # Cross-model join logic
```

---

## Code Duplication: FilterEngine Consolidation

### Current State: 3 Implementations

```
1. core/session/filters.py::FilterEngine (177 lines)
   - apply_filters(df, filters, backend)
   - _apply_spark_filters()
   - _apply_duckdb_filters()

2. app/notebook/filters/engine.py::FilterEngine (250+ lines)
   - apply_filters(df, filter_context)
   - _apply_date_range_filter()
   - _apply_dimension_filter()
   - Uses Variable types

3. models/base/service.py::_apply_filters() (inline method)
   - Similar to #1 but embedded in class
```

### Consolidated Design

```python
# core/filters/engine.py - Single source of truth

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Protocol
from dataclasses import dataclass

@dataclass
class FilterSpec:
    """Unified filter specification."""
    column: str
    operator: str  # eq, ne, in, not_in, gt, lt, gte, lte, between, like
    value: Any

    @classmethod
    def from_dict(cls, d: Dict) -> 'FilterSpec':
        """Create from dictionary (legacy format support)."""
        return cls(
            column=d.get('column'),
            operator=d.get('operator', 'eq'),
            value=d.get('value')
        )

class FilterBackend(Protocol):
    """Protocol for backend-specific filtering."""

    def apply(self, df: Any, filters: List[FilterSpec]) -> Any:
        """Apply filters to dataframe."""
        ...

class SparkFilterBackend:
    """Spark DataFrame filtering."""

    def apply(self, df: 'SparkDataFrame', filters: List[FilterSpec]) -> 'SparkDataFrame':
        for f in filters:
            df = self._apply_single(df, f)
        return df

    def _apply_single(self, df, filter_spec: FilterSpec):
        from pyspark.sql import functions as F

        col = F.col(filter_spec.column)

        if filter_spec.operator == 'eq':
            return df.filter(col == filter_spec.value)
        elif filter_spec.operator == 'in':
            return df.filter(col.isin(filter_spec.value))
        # ... other operators

class DuckDBFilterBackend:
    """DuckDB relation filtering."""

    def apply(self, df: 'DuckDBRelation', filters: List[FilterSpec]) -> 'DuckDBRelation':
        conditions = [self._to_sql_condition(f) for f in filters]
        if conditions:
            return df.filter(' AND '.join(conditions))
        return df

    def _to_sql_condition(self, f: FilterSpec) -> str:
        if f.operator == 'eq':
            return f"{f.column} = {self._quote(f.value)}"
        elif f.operator == 'in':
            values = ', '.join(self._quote(v) for v in f.value)
            return f"{f.column} IN ({values})"
        # ... other operators

class FilterEngine:
    """
    Unified filter engine - THE ONLY IMPLEMENTATION.

    Usage:
        engine = FilterEngine(backend='duckdb')
        filtered = engine.apply(df, filters)
    """

    BACKENDS = {
        'spark': SparkFilterBackend,
        'duckdb': DuckDBFilterBackend,
    }

    def __init__(self, backend: str):
        if backend not in self.BACKENDS:
            raise ValueError(f"Unknown backend: {backend}")
        self._backend = self.BACKENDS[backend]()

    def apply(
        self,
        df: Any,
        filters: List[Dict | FilterSpec]
    ) -> Any:
        """Apply filters to dataframe."""
        # Normalize to FilterSpec
        specs = [
            f if isinstance(f, FilterSpec) else FilterSpec.from_dict(f)
            for f in filters
        ]

        return self._backend.apply(df, specs)


# Notebook-specific extensions (inherits, doesn't duplicate)
# app/notebook/filters/notebook_filter_engine.py

class NotebookFilterEngine(FilterEngine):
    """Extended filter engine for notebook contexts."""

    def __init__(self, backend: str, filter_context: 'FilterContext'):
        super().__init__(backend)
        self.context = filter_context

    def apply_with_context(self, df: Any) -> Any:
        """Apply filters from notebook context."""
        filters = self.context.get_active_filters()
        return self.apply(df, filters)
```

---

## Guidelines to Prevent Recurrence

### Rule 1: File Size Limits

```markdown
## CLAUDE.md Addition

### File Size Guidelines

- **Target**: <300 lines per file
- **Warning**: >500 lines - consider splitting
- **Hard limit**: >800 lines - MUST refactor before adding more

When approaching limits:
1. STOP adding to the file
2. Identify logical groupings
3. Extract to new modules
4. Update imports
```

### Rule 2: Single Responsibility Check

```markdown
Before adding a function, ask:
1. Does this file already do multiple things?
2. Would a new developer know where to find this?
3. Can I describe this file's purpose in ONE sentence?

If the file does >1 thing, extract before adding.
```

### Rule 3: Duplication Detection

```markdown
Before implementing:
1. Search codebase for similar functionality
2. If found, extend existing code OR consolidate
3. Never create a "similar but different" version
```

### Rule 4: Architecture Decision Records

```markdown
When creating new modules, document:
- WHY this is a separate module
- WHAT it should and should NOT contain
- WHERE related code should go instead
```

---

## Implementation Plan

### Phase 1: Establish Guidelines (Week 1)
1. Add file size rules to CLAUDE.md
2. Create architecture decision template
3. Document module boundaries

### Phase 2: FilterEngine Consolidation (Week 2)
1. Create unified FilterEngine
2. Update core/session to use it
3. Update app/notebook to extend it
4. Remove duplicates

### Phase 3: markdown_renderer.py (Week 3-4)
1. Extract styles.py
2. Extract parser.py
3. Extract block renderers
4. Extract editors
5. Test thoroughly

### Phase 4: notebook_app_duckdb.py (Week 5-6)
1. Extract state management
2. Extract services
3. Extract page components
4. Extract callbacks

### Phase 5: BaseModel (Week 7)
1. Extract TableAccessor
2. Extract MeasureExecutor
3. Extract FilterApplicator
4. Update all model implementations

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Files >500 lines | 10+ | 0 |
| Files >300 lines | 25+ | <10 |
| Avg file size | ~250 lines | <150 lines |
| FilterEngine implementations | 3 | 1 |
| Code duplication | ~15% | <5% |

---

## Open Questions

1. Should we use a linter rule to enforce file size?
2. How to handle circular imports during extraction?
3. Should we add pre-commit hook for file size check?

---

## References

- Current large files: See analysis above
- Python module best practices: PEP 8, Clean Code
- Streamlit app structure: Streamlit docs
