# Folder Filter System

## Overview

The folder filter system provides **contextual filtering** that is shared within a folder but **completely isolated** across folders. This allows you to:
- Share filter settings across all notebooks in a folder
- Create reusable analytical views by copying folders
- Maintain complete isolation between different analysis contexts
- Edit filters directly in the UI using YAML format

## Architecture

### Simple Folder-Level Isolation

```
notebooks/
├── .filter_context.yaml              # Filters for root notebooks
├── Financial Analysis/
│   ├── .filter_context.yaml          # Filters for Financial Analysis notebooks
│   ├── stock_analysis.md
│   └── portfolio_analysis.md
└── Market Trends/
    ├── .filter_context.yaml          # Completely separate filters
    └── trend_analysis.md
```

**Key Principles:**
- ✅ **Folder-scoped**: Each folder has its own `.filter_context.yaml`
- ✅ **Shared within folder**: All notebooks in a folder use the same filters
- ✅ **Complete isolation**: Switching folders completely resets filters
- ✅ **No global filters**: Nothing is shared across folders
- ✅ **YAML-based**: Editable like notebook markdown

## Using Folder Filters

### 1. Viewing Active Filters

When you load a notebook, the sidebar shows the **Folder Filter Editor**:

```
📁 Folder: Financial Analysis
Filters shared by all notebooks in this folder

✅ .filter_context.yaml exists

📊 Active Filters
  ticker: ['AAPL', 'MSFT']
  trade_date: 2024-10-01 to 2024-12-31
  volume: 5000000

[✏️ Edit Filter Context]
```

### 2. Editing Filters

Click **"Edit Filter Context"** to open the YAML editor:

```yaml
# Folder Filter Context for Financial Analysis
# These filters are shared by all notebooks in this folder

filters:
  # Filter to Apple and Microsoft stocks
  ticker:
    - AAPL
    - MSFT

  # Date range for Q4 2024
  trade_date:
    start: "2024-10-01"
    end: "2024-12-31"

  # Minimum volume threshold
  volume: 5000000

metadata:
  created: "2025-11-06T00:00:00"
  last_updated: "2025-11-06T00:00:00"
  folder: "Financial Analysis"
```

**Actions:**
- **💾 Save**: Validates YAML and saves to disk
- **❌ Cancel**: Discards changes
- **🗑️ Delete**: Removes the filter context file

### 3. Creating New Filter Contexts

If no `.filter_context.yaml` exists, the UI shows helpful guidance:

```
📝 No filters set

Click 'Edit Filter Context' below to add filters.

Example:
```yaml
filters:
  ticker: AAPL
  date_range:
    start: 2024-10-01
    end: 2024-11-01
```

### 4. Filter Format Examples

#### Single Value Filter
```yaml
filters:
  ticker: AAPL
```

#### Multi-Value Filter (List)
```yaml
filters:
  ticker:
    - AAPL
    - MSFT
    - GOOG
```

#### Date Range Filter
```yaml
filters:
  trade_date:
    start: "2024-10-01"
    end: "2024-12-31"
```

#### Numeric Range Filter
```yaml
filters:
  volume:
    min: 1000000
    max: 100000000
```

#### Combined Filters
```yaml
filters:
  ticker:
    - AAPL
    - MSFT
  trade_date:
    start: "2024-10-01"
    end: "2024-12-31"
  volume: 5000000
  sector: Technology
```

## Folder Isolation

### Switching Between Folders

When you switch from one notebook to another in a **different folder**, the filters **completely reset**:

```
Financial Analysis/stock_analysis.md
  Filters: ticker=[AAPL, MSFT], date=[Q4 2024]

↓ Switch to different folder ↓

Market Trends/trend_analysis.md
  Filters: ticker=[GOOG], date=[Q3 2024]
  (Completely different - no carryover)
```

### Sharing Within Folders

All notebooks in the **same folder** share the same filters:

```
Financial Analysis/
├── .filter_context.yaml (ticker=[AAPL, MSFT])
├── stock_analysis.md → Uses AAPL, MSFT
└── portfolio_analysis.md → Uses AAPL, MSFT
```

## Creating Reusable Views

To create a reusable analytical view:

1. **Set up filters** in a folder's `.filter_context.yaml`
2. **Copy the entire folder** with notebooks + filter context
3. **Modify filters** in the new folder as needed

Example:
```bash
# Original view
Financial Analysis/.filter_context.yaml (ticker=[AAPL, MSFT])

# Copy folder to create new view
cp -r "Financial Analysis" "Tech Giants Analysis"

# Edit new folder's filters
Tech Giants Analysis/.filter_context.yaml (ticker=[AAPL, MSFT, GOOG, META])
```

Both views remain **completely isolated** - changing one doesn't affect the other.

## Technical Details

### Filter Application Priority

1. **Folder filters** are loaded from `.filter_context.yaml`
2. **Only valid filters** (matching notebook variables) are applied
3. **User can override** via UI filter widgets during session
4. **Persisted filters** save back to `.filter_context.yaml`

### File Location

Filter context files are always named `.filter_context.yaml` and located in the notebook folder:

```
/configs/notebooks/<folder-name>/.filter_context.yaml
```

### Validation

The UI validates YAML syntax before saving:
- ✅ Valid YAML structure
- ✅ `filters` section exists
- ✅ Metadata is optional
- ❌ Syntax errors shown with details

### Backend Compatibility

The folder filter system works with **both Spark and DuckDB** backends. Filters are translated to the appropriate query format automatically.

## Examples

### Example 1: Financial Analysis Folder

**File**: `configs/notebooks/Financial Analysis/.filter_context.yaml`

```yaml
filters:
  ticker:
    - AAPL
    - MSFT
  trade_date:
    start: "2024-10-01"
    end: "2024-12-31"
  volume: 5000000

metadata:
  created: "2025-11-06T00:00:00"
  last_updated: "2025-11-06T00:00:00"
  folder: "Financial Analysis"
```

**Effect**: All notebooks in `Financial Analysis/` folder will:
- Filter to AAPL and MSFT stocks
- Show Q4 2024 data
- Only include trades with volume >= 5M

### Example 2: Market Trends Folder

**File**: `configs/notebooks/Market Trends/.filter_context.yaml`

```yaml
filters:
  ticker: GOOG
  trade_date:
    start: "2024-07-01"
    end: "2024-09-30"

metadata:
  folder: "Market Trends"
```

**Effect**: All notebooks in `Market Trends/` folder will:
- Filter to GOOG stock only
- Show Q3 2024 data
- Completely isolated from Financial Analysis filters

## Best Practices

1. **Use descriptive folder names** that reflect the analytical context
2. **Document filters** with YAML comments for clarity
3. **Keep folders focused** - each folder should represent a coherent analytical view
4. **Copy folders** to preserve historical views
5. **Version control** `.filter_context.yaml` files with your notebooks
6. **Test filters** after editing to ensure they apply correctly

## Migration from Previous Systems

If you have old global filter configurations, they need to be migrated to folder-level contexts:

**Old (Global)**:
```python
GLOBAL_FILTERS = ['ticker', 'date_range']  # Shared everywhere
```

**New (Folder-scoped)**:
```yaml
# Each folder has its own .filter_context.yaml
filters:
  ticker: AAPL
  trade_date:
    start: "2024-01-01"
    end: "2024-12-31"
```

The new system provides **cleaner isolation** and **better reproducibility**.

## How Filter Pre-Population Works

When you load a notebook, the filter widgets automatically pre-populate with folder context values:

### Flow

1. **Notebook loads** → `NotebookManager.load_notebook()`
2. **Folder detected** → Gets the notebook's parent folder
3. **Folder filters loaded** → Reads `.filter_context.yaml` from that folder
4. **Filter context initialized** → Creates `FilterContext` with notebook variables
5. **Folder filters applied** → Updates `FilterContext` with folder filter values
6. **UI renders** → Filter widgets read current values from `FilterContext`

### Example

**Folder context file**: `Financial Analysis/.filter_context.yaml`
```yaml
filters:
  ticker:
    - AAPL
    - MSFT
  volume: 5000000
```

**Result in UI**:
- Ticker multi-select shows "AAPL, MSFT" pre-selected
- Volume number input shows "5000000"
- All other filters show their notebook defaults

### Priority Order

Filter widgets follow this priority when determining default values:

1. **Folder context value** (from `.filter_context.yaml`) ← Highest priority
2. **Notebook default** (from `$filter$` block in `.md` file)
3. **Variable type default** (e.g., empty list, 0, false)

This ensures folder-level filters always take precedence over notebook defaults.

## Troubleshooting

### Filters Not Appearing in Editor

1. **Check folder**: Is there a `.filter_context.yaml` file in the notebook's folder?
2. **Validate YAML**: Open the file and check for syntax errors
3. **Reload notebook**: Switch away and back to reload filters
4. **Check UI**: The folder filter editor should show active filters

### Filters Not Pre-Populating Widgets

1. **Verify filter names** match notebook variable IDs exactly
2. **Check filter context**: Use folder filter editor to see active filters
3. **Reload notebook**: Switch to different notebook and back
4. **Check console**: Look for any JavaScript errors in browser console

### Filters Not Applying to Data

1. **Verify filter names** match notebook variable IDs
2. **Check data**: Ensure data exists matching the filter criteria
3. **Test filters**: Clear filters and re-apply to see effect
4. **Check backend**: Both Spark and DuckDB are supported

### YAML Syntax Errors

The UI will show validation errors when saving. Common issues:
- **Indentation**: YAML requires consistent indentation (2 spaces)
- **Quotes**: Use quotes for dates and special characters
- **Lists**: Use `- item` format for lists
- **Colons**: Must have space after colon (`key: value`)

## Summary

The folder filter system provides:
- ✅ **Contextual filtering** scoped to folders
- ✅ **Complete isolation** between folders
- ✅ **Reusable views** via folder copying
- ✅ **YAML-based editing** in the UI
- ✅ **No global filters** - clean architecture
- ✅ **Backend-agnostic** - works with Spark and DuckDB

This design ensures your analytical views are **reproducible**, **shareable**, and **completely isolated** from each other.
