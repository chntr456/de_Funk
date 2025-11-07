# Quick Debug Checklist - Folder Filters Not Working

## Symptoms Reported
"things are loaded but still not working right"

## Quick Diagnostic Commands

```bash
# 1. Verify folder context exists and loads
python -c "
from pathlib import Path
from app.notebook.folder_context import FolderFilterContextManager

mgr = FolderFilterContextManager()
folder = Path('configs/notebooks/Financial Analysis')
filters = mgr.get_filters(folder)
print('Folder filters:', filters)
"

# Expected: {'ticker': ['AAPL', 'MSFT'], 'volume': 5000000, 'trade_date': {...}}
```

```bash
# 2. Test notebook loading
python -c "
from pathlib import Path
from core.context import RepoContext
from models.api.session import UniversalSession
from app.notebook.managers.notebook_manager import NotebookManager

ctx = RepoContext.from_repo_root(connection_type='duckdb')
session = UniversalSession(ctx.connection, ctx.storage, ctx.repo)
mgr = NotebookManager(session, ctx.repo, Path('configs/notebooks'))

nb_path = 'configs/notebooks/Financial Analysis/stock_analysis.md'
config = mgr.load_notebook(nb_path)

print('Filter collection:', config._filter_collection)
if config._filter_collection:
    states = config._filter_collection.get_active_filters()
    print('Active filters:', states)

print('Extra filters:', mgr._extra_folder_filters)
"

# Expected active filters: ticker=[AAPL,MSFT], volume=5000000, trade_date={Q4}
# Expected extra filters: {} (should be empty if filters match notebook)
```

```bash
# 3. Test filter building
python -c "
from pathlib import Path
from core.context import RepoContext
from models.api.session import UniversalSession
from app.notebook.managers.notebook_manager import NotebookManager
from app.notebook.schema import Exhibit, ExhibitType

ctx = RepoContext.from_repo_root(connection_type='duckdb')
session = UniversalSession(ctx.connection, ctx.storage, ctx.repo)
mgr = NotebookManager(session, ctx.repo, Path('configs/notebooks'))

nb_path = 'configs/notebooks/Financial Analysis/stock_analysis.md'
config = mgr.load_notebook(nb_path)

mock_exhibit = Exhibit(
    id='test',
    title='Test',
    type=ExhibitType.METRIC_CARDS,
    source='company.fact_prices',
    metrics=[]
)

filters = mgr._build_filters(mock_exhibit)
print('Built filters:', filters)
"

# Expected: {'ticker': ['AAPL', 'MSFT'], 'volume': {'min': 5000000}, 'trade_date': {...}}
```

## What to Look For

### ✅ Good Signs:
- Folder filters load: `{'ticker': ['AAPL', 'MSFT'], ...}` ✓
- Active filters match folder: ticker, volume, trade_date ✓
- Built filters include all 3 filters ✓
- Filter values are from folder context, NOT markdown defaults ✓

### ❌ Bad Signs (and what they mean):

| Symptom | Meaning | Fix Location |
|---------|---------|--------------|
| Folder filters empty {} | .filter_context.yaml not found or invalid | Check file exists |
| Active filters show defaults (2024-01-01) | _filter_collection not updated | `load_notebook()` line 139 |
| Active filters empty {} | get_active_filters() broken | Check FilterCollection class |
| Built filters missing ticker/volume | _build_filters() not including them | Line 405-417 |
| Extra filters has all 3 | Filters not recognized as in notebook | Line 136 get_state() failing |

## Add Debug Prints

### In load_notebook() (line 139):
```python
filter_state.current_value = value
print(f"DEBUG: Set filter {key} = {value}")  # ← ADD THIS
print(f"DEBUG: Verify: {filter_state.current_value}")  # ← AND THIS
```

### In _build_filters() (line 357):
```python
active_filters = filter_collection.get_active_filters()
print(f"DEBUG: Active filters from collection: {active_filters}")  # ← ADD THIS
```

### In _build_filters() (line 453):
```python
# Apply exhibit-level filters (override notebook filters)
print(f"DEBUG: Final filters before exhibit override: {filters}")  # ← ADD THIS
```

## Common Issues & Solutions

### Issue 1: "Widgets show default values, not folder values"
**Cause:** `_filter_collection` not being updated in `load_notebook()`

**Check:**
```python
# In load_notebook(), add print after line 139:
print(f"Filter state for {key}: {filter_state.current_value}")
```

**Fix:** Verify `filter_state` is not None and assignment succeeds

---

### Issue 2: "Data not filtered, shows all rows"
**Cause:** `_build_filters()` returns empty or incorrect filters

**Check:**
```python
# In _build_filters(), add print after line 357:
active_filters = filter_collection.get_active_filters()
print(f"Active filters: {active_filters}")
```

**Fix:** If empty, `get_active_filters()` may not be reading state correctly

---

### Issue 3: "Filters show but wrong values"
**Cause:** Streamlit session state overriding folder context

**Check:** Look at Streamlit sidebar - do widgets have values?

**Fix:** Clear Streamlit cache:
```bash
# In terminal where Streamlit is running:
# Press 'c' then Enter to clear cache
# Or add to code:
st.cache_data.clear()
st.cache_resource.clear()
```

---

### Issue 4: "All folder filters in _extra_folder_filters"
**Cause:** `get_state(key)` returning None (filter not found in collection)

**Check:**
```python
# In load_notebook(), add print before line 136:
print(f"Looking for filter: {key}")
filter_state = self.notebook_config._filter_collection.get_state(key)
print(f"Found state: {filter_state}")
```

**Fix:** Verify filter IDs in markdown match folder context keys exactly

---

## Quick Fix Attempts

### If widgets show defaults:
```python
# In app/ui/components/dynamic_filters.py, line 111
# Change priority order - force folder context first:
if notebook_session and hasattr(notebook_session, '_extra_folder_filters'):
    if filter_id in notebook_session._extra_folder_filters:
        current_value = notebook_session._extra_folder_filters[filter_id]
        print(f"DEBUG: Using folder value for {filter_id}: {current_value}")
```

### If data not filtered:
```python
# In app/notebook/managers/notebook_manager.py, line 357
# Force folder filters into active_filters:
active_filters = filter_collection.get_active_filters()
if hasattr(self, '_extra_folder_filters'):
    active_filters.update(self._extra_folder_filters)
print(f"DEBUG: Active filters after merge: {active_filters}")
```

## Files to Check

1. **app/notebook/managers/notebook_manager.py**
   - Line 139: Filter state assignment
   - Line 357: get_active_filters() call
   - Line 405-417: Extra folder filters merge

2. **app/ui/components/dynamic_filters.py**
   - Line 99-117: Current value retrieval
   - Line 61: render_filter() call

3. **app/notebook/filters/dynamic.py**
   - FilterCollection.get_active_filters() method
   - FilterState dataclass

## Expected Flow

```
User opens Financial Analysis notebook
    ↓
load_notebook() called
    ↓
Folder filters: {ticker: [AAPL, MSFT], volume: 5000000, trade_date: {...}}
    ↓
For each filter:
  - get_state('ticker') → FilterState object
  - filter_state.current_value = ['AAPL', 'MSFT']  ← SET HERE
    ↓
Render UI widgets
    ↓
dynamic_filters.py gets current_value
    ↓
Should show folder values in widgets ✓
    ↓
User clicks exhibit
    ↓
_build_filters(exhibit) called
    ↓
get_active_filters() → {ticker: [AAPL, MSFT], volume: 5000000, ...}  ← READ HERE
    ↓
FilterEngine.apply_from_session(df, filters)
    ↓
Filtered data shown in exhibit ✓
```

## If All Else Fails

1. Add extensive debug prints throughout the pipeline
2. Capture Streamlit session state: `st.write(st.session_state)`
3. Capture filter collection state: `st.write(notebook_config._filter_collection.states)`
4. Compare expected vs actual at each step
5. Share debug output for analysis

---

**TL;DR:** Most likely issue is `_filter_collection.get_active_filters()` not returning folder values. Add debug prints at lines 139 and 357 first.
