# Notebook Vault UX Guide

## Overview

The Notebook Vault provides a sophisticated, vault-style interface for managing and viewing financial modeling notebooks.

## Key Features

### 📁 Directory Tree Navigation

Organize notebooks in folders for better organization:

```
configs/notebooks/
├── Financial Analysis/
│   ├── stock_analysis.yaml
│   ├── portfolio_performance.yaml
│   └── risk_assessment.yaml
├── Market Research/
│   ├── sector_analysis.yaml
│   └── competitor_analysis.yaml
└── macro_indicators.yaml
```

**Usage**:
- Folders are automatically detected
- Click on any notebook to open it
- Open files appear with 📄 icon
- Active file appears with 📖 icon and bold text

### 🗂️ Multiple Notebook Tabs

Open multiple notebooks simultaneously:

- Each notebook opens in its own tab
- Click tab name to switch between notebooks
- Click **✕** to close a tab
- Tabs persist until explicitly closed

### 📝 Edit & View Modes

Toggle between two modes for each notebook:

**View Mode (📊)**:
- Shows rendered exhibits (charts, tables, metrics)
- Interactive visualizations
- Apply filters to update exhibits

**Edit Mode (📝)**:
- Direct YAML editor
- Syntax highlighting
- **Save** button to persist changes
- **Reload** button to discard changes
- Real-time YAML validation

### 🎛️ Nested Filter Sidebar

Filters appear in a scrollable section when a notebook is open:

```
┌─────────────────────┐
│ 📚 Notebook Vault   │
├─────────────────────┤
│ 📁 Financial...     │
│   📖 stock_analysis │
│   📄 portfolio...   │
├─────────────────────┤
│ 🎛️ Filters          │
│ ┌─────────────────┐ │
│ │ Date Range      │ │
│ │ [2024-01-01]    │ │
│ │ [2024-01-05]    │ │
│ │                 │ │
│ │ Stock Tickers   │ │
│ │ ☑ AAPL          │ │
│ │ ☑ GOOGL         │ │
│ │ ☑ MSFT          │ │
│ │                 │ │
│ │ Minimum Volume  │ │
│ │ [0]             │ │
│ └─────────────────┘ │
└─────────────────────┘
```

- Filters are specific to the active notebook
- Scrollable to accommodate many filters
- Changes immediately update exhibits

## Running the New UX

```bash
# Run the enhanced vault app
streamlit run src/ui/notebook_app_v2.py
```

Or update the old app:
```bash
# Replace old app with new one
mv src/ui/notebook_app.py src/ui/notebook_app_old.py
mv src/ui/notebook_app_v2.py src/ui/notebook_app.py

# Run normally
streamlit run src/ui/notebook_app.py
```

## Workflow Examples

### Creating a New Notebook

1. Create a YAML file in `configs/notebooks/` or a subfolder
2. It automatically appears in the directory tree
3. Click to open and view
4. Toggle to Edit mode to refine

### Editing an Existing Notebook

1. Click on notebook in tree to open
2. Click **📝 Edit** button
3. Modify YAML in the text editor
4. Click **💾 Save** to persist changes
5. Notebook automatically reloads with new config
6. Click **📊 View** to see updated exhibits

### Comparing Multiple Notebooks

1. Click first notebook to open (opens in Tab 1)
2. Click second notebook to open (opens in Tab 2)
3. Switch between tabs to compare
4. Each has its own filter state
5. Close tabs with **✕** when done

### Organizing Notebooks

Create folders to organize by:
- **Category**: `Financial Analysis/`, `Market Research/`, `Risk Management/`
- **Asset Class**: `Equities/`, `Fixed Income/`, `Derivatives/`
- **Time Period**: `2024 Q1/`, `2024 Q2/`
- **Team**: `Team Alpha/`, `Team Beta/`

## UI Components

### Sidebar

**Top Section**: Directory Tree
- Expandable folders
- Clickable notebook items
- Visual indicators (icons, bold/italic text)

**Bottom Section**: Filters (when notebook active)
- Scrollable container
- All filter types supported
- Real-time updates

### Main Content

**Tab Bar**:
- Horizontal tabs for open notebooks
- Close button (✕) on each tab
- Active tab highlighted

**Notebook Header**:
- Title and description
- Mode toggle button (📝 Edit / 📊 View)

**Content Area**:
- Edit mode: YAML editor with save/reload
- View mode: Rendered exhibits with sections

## Keyboard Shortcuts

While typing in YAML editor:
- `Ctrl+S` / `Cmd+S`: Save (if browser allows)
- `Ctrl+Z` / `Cmd+Z`: Undo
- `Tab`: Insert 2 spaces (YAML-friendly)

## Tips & Tricks

### 1. Quick Navigation
Click notebook names to instantly switch - no load button needed!

### 2. Iterative Development
- Open notebook in View mode
- See what needs changing
- Toggle to Edit mode
- Make changes
- Save and toggle back to View
- See results immediately

### 3. Filter Presets
- Set filters to create a specific view
- Save the notebook config with those filter defaults
- Share the YAML file with teammates

### 4. Multi-Notebook Analysis
- Open related notebooks in separate tabs
- Compare different time periods
- Analyze different assets
- Cross-reference metrics

### 5. Folder Organization
Use subfolders for:
- **Draft** notebooks (in `Draft/` folder)
- **Archived** analyses (in `Archive/` folder)
- **Template** notebooks (in `Templates/` folder)

## Advantages Over Old UX

| Feature | Old UX | Vault UX |
|---------|--------|----------|
| Navigation | Dropdown + Load button | Directory tree, click to open |
| Multiple notebooks | One at a time | Multiple tabs |
| Editing | External editor | Built-in YAML editor |
| Filters | Always visible | Nested, scrollable |
| Organization | Flat list | Hierarchical folders |
| Workflow | Load → View → Edit externally | View ↔ Edit seamlessly |

## Future Enhancements

Planned features:
- **Search**: Search notebooks by name or content
- **Favorites**: Star frequently-used notebooks
- **Recent**: Quick access to recently opened
- **Duplicate**: Clone notebook as template
- **Export**: Export rendered notebook as PDF
- **Collaboration**: Share notebook with specific filter state
- **Version History**: View previous versions of YAML
- **Syntax Validation**: Real-time YAML error highlighting

## Troubleshooting

**Notebook not appearing in tree?**
- Ensure file has `.yaml` extension
- Check it's in `configs/notebooks/` or a subfolder
- Refresh the page (F5)

**Tab won't close?**
- Click the **✕** button on the tab
- Or navigate to another notebook and back

**Edit changes not saving?**
- Check YAML syntax is valid
- Look for error message below Save button
- Try Reload button to discard and start over

**Filters not appearing?**
- Ensure a notebook is open and active
- Check notebook has variables defined in YAML
- Scroll down in sidebar to see all filters

## Best Practices

1. **Organize by purpose**: Group related notebooks in folders
2. **Use descriptive names**: `stock_analysis.yaml` not `nb1.yaml`
3. **Test in Edit mode**: Validate YAML before saving
4. **Close unused tabs**: Keep workspace clean
5. **Consistent formatting**: Use 2-space indentation in YAML

---

**Happy analyzing!** 📊
