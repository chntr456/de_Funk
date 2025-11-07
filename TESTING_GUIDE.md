# Filter System Testing Guide

This guide helps you verify that the folder filter system is working correctly.

## Quick Start

Run these three test scripts in order:

```bash
# Test 1: Core filter system functionality
python test_filter_system.py

# Test 2: Expected UI state
python test_ui_state.py

# Test 3: Run the actual Streamlit app
streamlit run app/ui/notebook_app_duckdb.py
```

## Test Scripts

### 1. `test_filter_system.py` - Core Functionality Test

**What it tests:**
- Folder context files exist and can be loaded
- FolderFilterContextManager works
- NotebookManager initializes correctly
- Filter context loads with folder values
- `_build_filters()` includes all folder filters
- FilterEngine applies filters to data

**How to interpret results:**

```
✓ = Working correctly
✗ = Failing (needs investigation)
ℹ = Informational (may or may not be an issue)
```

**Key sections to check:**

1. **TEST 4: Notebook Loading & Filter Context**
   - Should show filter context contains folder filter values
   - Should show `_extra_folder_filters` if folder defines filters not in notebook

2. **TEST 5: Filter Building**
   - Should show ALL folder filters in the filters dict
   - Both 'ticker' and 'volume' should say "WILL BE APPLIED"

3. **TEST 6: FilterEngine Application**
   - Should show filtered data contains only AAPL/MSFT
   - Should show minimum volume >= 5M

### 2. `test_ui_state.py` - UI State Test

**What it tests:**
- What should appear in the Streamlit sidebar
- Which filter widgets should be auto-generated
- Which filters will be applied to exhibits

**How to interpret results:**

The output shows a mock of what the Streamlit UI should display:

```
📁 FOLDER FILTER EDITOR SECTION
  Shows: Folder name and active filters from .filter_context.yaml

🎛️ FILTER WIDGETS SECTION
  Shows: Auto-generated widgets for folder filters
  Shows: Notebook-defined filter widgets

📊 MAIN CONTENT - EXHIBITS
  Shows: Which filters will be applied to each exhibit
```

**Compare this output to what you see in the actual Streamlit UI.**

### 3. Streamlit App - Manual Testing

**Steps:**

1. **Start the app:**
   ```bash
   streamlit run app/ui/notebook_app_duckdb.py
   ```

2. **Open Financial Analysis notebook:**
   - Navigate to `Financial Analysis/stock_analysis.md`

3. **Check the sidebar:**

   **Section 1: Folder Filter Editor**
   - Should show: "📁 Folder: Financial Analysis"
   - Should show: Active filters (ticker, volume, trade_date)

   **Section 2: Filter Widgets**
   - Should show: "📁 Folder Filters (applied automatically)"
   - Should show: Auto-generated widgets for each folder filter
   - OR if notebook defines those variables, they appear in regular section

4. **Check the main content:**
   - Exhibits should show ONLY filtered data
   - If ticker filter = [AAPL, MSFT], exhibits show only those tickers
   - If volume filter = 5000000, exhibits show only volume >= 5M

5. **Test folder switching:**
   - Open a notebook from the root folder (not Financial Analysis)
   - Sidebar should update to show different folder filters
   - Widget values should reset (not show Financial Analysis values)
   - Exhibits should show different filtered data

## Troubleshooting

### Problem: No filters showing in UI

**Check:**
1. Does `.filter_context.yaml` exist in the folder?
   ```bash
   ls -la configs/notebooks/Financial\ Analysis/.filter_context.yaml
   ```

2. Does `test_filter_system.py` show folder filters loaded?
   - Look at TEST 2 output

3. Does `test_ui_state.py` show expected widgets?
   - Compare to actual UI

**Fix:**
- If file doesn't exist, create it using the Folder Filter Editor in the UI
- If file exists but not loading, check YAML syntax

### Problem: Filters not applying to data

**Check:**
1. Does `test_filter_system.py` TEST 5 show filters "WILL BE APPLIED"?
2. Does TEST 6 show filtered results?

**Debug:**
- Add print statements to `_build_filters()` to see what's returned
- Check FilterEngine is being called in `get_exhibit_data()`

### Problem: Segmentation fault

**Cause:** Likely DuckDB threading issue

**Fix:**
- Make sure `load_notebook()` is NOT called during render
- Check `_render_notebook_content()` doesn't call `load_notebook()`
- Look at commit ebec835 for the correct implementation

### Problem: Filters from wrong folder

**Cause:** Widget state not clearing when switching folders

**Fix:**
- Check `render_filters_section()` has folder change detection (lines 64-80)
- Check `st.session_state.last_filter_folder` is being updated
- Clear browser cache and restart Streamlit

## Expected Test Results

### test_filter_system.py - Success Output

```
TEST 1: Folder Context Files
✓ Financial Analysis: configs/notebooks/Financial Analysis/.filter_context.yaml
✓ Root: configs/notebooks/.filter_context.yaml

TEST 2: Folder Context Manager Loading
✓ FolderFilterContextManager initialized
✓ Financial Analysis folder filters loaded:
  - ticker: ['AAPL', 'MSFT']
  - trade_date: {'start': '2024-10-01', 'end': '2024-12-31'}
  - volume: 5000000

TEST 4: Notebook Loading & Filter Context
✓ FilterContext loaded with 3 filters:
  - ticker: ['AAPL', 'MSFT']
  - trade_date: {...}
  - volume: 5000000

TEST 5: Filter Building (_build_filters)
✓ Filters built for exhibit:
  - ticker: ['AAPL', 'MSFT']
  - trade_date: {...}
  - volume: {'min': 5000000}

ℹ Testing filter application:
  ✓ 'ticker' filter WILL BE APPLIED: ['AAPL', 'MSFT']
  ✓ 'volume' filter WILL BE APPLIED: {'min': 5000000}

TEST 6: FilterEngine Application
✓ Got raw data from company.fact_prices
✓ FilterEngine.apply_from_session() executed
✓ Converted to pandas: 156 rows
  Unique tickers in result: ['AAPL', 'MSFT']
  ✓ Ticker filter WORKING (only AAPL/MSFT)
  Minimum volume in result: 5234567
  ✓ Volume filter WORKING (all >= 5M)
```

### test_ui_state.py - Success Output

Should show clear sections for what appears in UI, with widgets auto-generated for folder filters.

## Reporting Issues

If tests fail, include this information:

1. **Which test failed:**
   - TEST number and section name

2. **Error message:**
   - Full error output

3. **What you expected:**
   - Based on this guide

4. **What you got:**
   - Actual output or UI state

5. **Screenshots:**
   - If UI doesn't match expected state

6. **Environment:**
   ```bash
   python --version
   streamlit --version
   ```

## Files Modified

If you need to verify the latest changes:

```bash
git log --oneline -10
```

Should show:
```
ebec835 MAJOR FIX: Folder-driven filter architecture
bef3b8c CRITICAL FIX: Reload notebook context when switching tabs
2066d40 CRITICAL FIX: Clear widget state when switching folders
```

Key files:
- `app/ui/notebook_app_duckdb.py` - Folder context loading during tab switch
- `app/notebook/managers/notebook_manager.py` - Filter building and application
- `app/ui/components/filters.py` - Dynamic widget generation
