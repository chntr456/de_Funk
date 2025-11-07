# Unified Filter System Design

## Current Problems

### 1. **Fragmented Filter Storage**
Filters are stored in 3 separate places:
- `_filter_collection` (markdown notebooks) - FilterConfig + FilterState objects
- `filter_context` (YAML notebooks) - Variable definitions
- `_extra_folder_filters` (overflow dict) - raw folder filters that don't match notebook

**Issue:** No single source of truth for merged filters.

### 2. **UI Only Renders Notebook Filters**
Sidebar renders EITHER:
- `render_dynamic_filters(_filter_collection)` for markdown
- `render_filters_section(variables)` for YAML

**Issue:** Folder-only filters never appear in sidebar. User can't see or modify them.

### 3. **No Proper Merge Strategy**
Current logic in `load_notebook()`:
- If filter in notebook → update its value
- If filter NOT in notebook → put in `_extra_folder_filters`

**Issue:** Two separate systems. User wants ONE unified system where folder supersedes notebook.

### 4. **Query Building Is Fragmented**
`_build_filters()` has two paths:
- Path 1: Get from `_filter_collection.get_active_filters()` + merge `_extra_folder_filters`
- Path 2: Get from `filter_context.get_all()` + merge `_extra_folder_filters`

**Issue:** Complex, hard to maintain, doesn't properly supersede.

## User Requirements

> "I want both the filters in the folder context and the actively viewed notebook to talk to same filter system to generate side bar filters. Notebook filters get superseded by the folder context so no duplicate filters are generated. The joint filter context then communicates to apply filters on the data pull requests."

### Translation:
1. **Unified Merge:** Folder context + Notebook filters = ONE merged set
2. **Folder Supersedes:** If filter exists in both, use folder value (not notebook default)
3. **Sidebar Shows All:** Display ALL merged filters (notebook + folder-only)
4. **No Duplicates:** Each filter appears once with correct value
5. **Queries Use Merged:** All data queries use the unified merged filters

## Proposed Solution

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    load_notebook()                           │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  1. Load Notebook Filters                                    │
│     ├─ Markdown: _filter_collection (FilterConfig objects)   │
│     └─ YAML: variables (Variable objects)                    │
│                                                               │
│  2. Load Folder Context Filters                              │
│     └─ folder_context.yaml (raw dict)                        │
│                                                               │
│  3. Merge Into Unified Filter Collection                     │
│     ├─ For each notebook filter:                             │
│     │   ├─ If exists in folder context: USE FOLDER VALUE     │
│     │   └─ If NOT in folder context: USE NOTEBOOK DEFAULT    │
│     └─ For each folder-only filter:                          │
│         └─ ADD to collection (no notebook definition)        │
│                                                               │
│  4. Result: ONE _filter_collection with all merged filters   │
│     └─ Each FilterState has correct current_value            │
│                                                               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   UI Sidebar Rendering                       │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  render_dynamic_filters(_filter_collection)                  │
│     ├─ Iterate ALL filters in collection                     │
│     ├─ Render widgets for each (notebook + folder-only)      │
│     └─ Widget defaults from FilterState.current_value        │
│                                                               │
│  Result: User sees ALL filters with folder values            │
│                                                               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Query Building                             │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  _build_filters(exhibit)                                     │
│     ├─ Get from _filter_collection.get_active_filters()      │
│     ├─ Convert to FilterEngine format                        │
│     └─ Return dict of filters                                │
│                                                               │
│  Result: Simple, single source of truth                      │
│                                                               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   FilterEngine                               │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  FilterEngine.apply_from_session(df, filters, session)       │
│     └─ Apply all filters to DataFrame                        │
│                                                               │
│  Result: Filtered data for exhibits                          │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## Implementation Plan

### Phase 1: Create Unified Merge Logic

**File:** `app/notebook/managers/notebook_manager.py`

```python
def load_notebook(self, notebook_path: str) -> NotebookConfig:
    # ... existing parsing code ...

    # Load folder filters
    folder_filters = self.folder_context_manager.get_filters(new_folder)

    # UNIFIED MERGE STRATEGY
    self._merge_filters_unified(folder_filters)

    return self.notebook_config

def _merge_filters_unified(self, folder_filters: Dict[str, Any]):
    """
    Merge folder context with notebook filters into ONE unified collection.

    Strategy:
    1. For notebook filters: Override value if exists in folder context
    2. For folder-only filters: Add to collection as new filters
    3. Result: Single _filter_collection with all filters
    """
    # Ensure we have a filter collection (create if needed)
    if not hasattr(self.notebook_config, '_filter_collection') or not self.notebook_config._filter_collection:
        from app.notebook.filters.dynamic import FilterCollection
        self.notebook_config._filter_collection = FilterCollection()

    filter_collection = self.notebook_config._filter_collection

    if not folder_filters:
        return

    # Track which folder filters we've processed
    processed_folder_filters = set()

    # Phase 1: Update notebook filters with folder values
    for filter_id in list(filter_collection.filters.keys()):
        if filter_id in folder_filters:
            # Folder context supersedes notebook default
            filter_state = filter_collection.get_state(filter_id)
            if filter_state:
                filter_state.current_value = folder_filters[filter_id]
            processed_folder_filters.add(filter_id)

    # Phase 2: Add folder-only filters (not in notebook)
    for filter_id, value in folder_filters.items():
        if filter_id not in processed_folder_filters:
            # Create FilterConfig for folder-only filter
            filter_config = self._create_filter_config_from_value(filter_id, value)
            filter_collection.add_filter(filter_config)
            # Set the value
            filter_state = filter_collection.get_state(filter_id)
            if filter_state:
                filter_state.current_value = value

def _create_filter_config_from_value(self, filter_id: str, value: Any) -> FilterConfig:
    """
    Auto-create FilterConfig from folder context value.

    Infers filter type from value structure.
    """
    from app.notebook.filters.dynamic import FilterConfig, FilterType, FilterOperator

    # Infer type from value
    if isinstance(value, list):
        # Multi-select
        return FilterConfig(
            id=filter_id,
            type=FilterType.SELECT,
            label=filter_id.replace('_', ' ').title(),
            multi=True,
            options=value,
            default=value
        )
    elif isinstance(value, dict) and 'start' in value and 'end' in value:
        # Date range
        return FilterConfig(
            id=filter_id,
            type=FilterType.DATE_RANGE,
            label=filter_id.replace('_', ' ').title(),
            default=value
        )
    elif isinstance(value, (int, float)):
        # Number slider
        return FilterConfig(
            id=filter_id,
            type=FilterType.SLIDER,
            label=filter_id.replace('_', ' ').title(),
            min_value=0,
            max_value=value * 10,
            default=value,
            operator=FilterOperator.GREATER_EQUAL
        )
    else:
        # Text search fallback
        return FilterConfig(
            id=filter_id,
            type=FilterType.TEXT_SEARCH,
            label=filter_id.replace('_', ' ').title(),
            default=str(value)
        )
```

### Phase 2: Simplify Query Building

```python
def _build_filters(self, exhibit: Exhibit) -> Dict[str, Any]:
    """
    Build filters from UNIFIED filter collection.

    Now simple: just get active filters and convert to FilterEngine format.
    """
    filters = {}

    # Single source of truth: _filter_collection
    if (self.notebook_config and
        hasattr(self.notebook_config, '_filter_collection') and
        self.notebook_config._filter_collection):

        filter_collection = self.notebook_config._filter_collection
        active_filters = filter_collection.get_active_filters()

        # Convert to FilterEngine format
        from app.notebook.filters.dynamic import FilterType, FilterOperator

        for filter_id, value in active_filters.items():
            if value is None:
                continue

            filter_config = filter_collection.get_filter(filter_id)
            if not filter_config:
                filters[filter_id] = value
                continue

            # Convert based on filter type
            if filter_config.type == FilterType.DATE_RANGE:
                filters[filter_id] = value
            elif filter_config.type == FilterType.SELECT:
                if value:
                    filters[filter_id] = value
            elif filter_config.type == FilterType.SLIDER:
                if filter_config.operator == FilterOperator.GREATER_EQUAL:
                    if value > 0:
                        filters[filter_id] = {'min': value}
                # ... other conversions
            else:
                filters[filter_id] = value

    # Apply exhibit-level filters (override)
    if hasattr(exhibit, 'filters') and exhibit.filters:
        filters.update(exhibit.filters)

    return filters
```

### Phase 3: UI Already Works!

The UI already renders `_filter_collection`, so once we merge everything into it, the sidebar will automatically show all filters:

```python
# In notebook_app_duckdb.py _render_filters()
# This code ALREADY exists and will work with unified collection
if (hasattr(notebook_config, '_filter_collection') and
    notebook_config._filter_collection and
    notebook_config._filter_collection.filters):
    render_dynamic_filters(
        notebook_config._filter_collection,  # ← Now contains ALL merged filters
        self.notebook_manager,
        self.ctx.connection,
        self.universal_session
    )
```

## Benefits

1. **Single Source of Truth:** All filters in `_filter_collection`
2. **No Duplicates:** Each filter appears once
3. **Folder Supersedes:** Folder values override notebook defaults
4. **All Filters Visible:** Sidebar shows notebook + folder-only filters
5. **Simple Query Building:** Just read from `_filter_collection`
6. **No More `_extra_folder_filters`:** Everything unified

## Migration Notes

- Remove `_extra_folder_filters` dict (no longer needed)
- Remove old `filter_context` system (YAML notebooks use `_filter_collection` too)
- Simplify `_build_filters()` to single path
- Backward compatible: existing markdown notebooks work unchanged

## Testing Checklist

- [ ] Load Financial Analysis notebook
- [ ] Verify ticker widget shows [AAPL, MSFT] (folder value, not empty)
- [ ] Verify volume widget shows 5000000 (folder value, not 0)
- [ ] Verify trade_date shows Q4 2024 (folder value, not Q1)
- [ ] Verify exhibits show only AAPL/MSFT data
- [ ] Verify no duplicate filters in sidebar
- [ ] Switch folders → filters reset to new folder context
- [ ] Add folder-only filter (not in notebook) → appears in sidebar
