# Notebook System - Folder Context

## Overview

**FolderFilterContextManager** manages filter contexts per notebook folder, enabling filter sharing within folders while maintaining isolation across folders.

## Architecture

```
configs/notebooks/
├── Finance/              # Folder 1 (shared context)
│   ├── stock_analysis.md
│   ├── forecast_analysis.md
│   └── (shared ticker filter)
│
├── Economics/            # Folder 2 (isolated context)
│   ├── gdp_analysis.md
│   ├── inflation_analysis.md
│   └── (separate filters)
│
└── root_notebook.md      # Root folder (own context)
```

## Implementation

```python
# File: app/notebook/folder_context.py:40-200

class FolderFilterContextManager:
    """Manages filter contexts per notebook folder."""

    def __init__(self, notebooks_root: Path):
        self.notebooks_root = notebooks_root
        self._contexts: Dict[str, FilterContext] = {}
        self._current_folder: Optional[str] = None

    def switch_folder(self, notebook_path: Path):
        """
        Switch to folder context for a notebook.

        Args:
            notebook_path: Path to notebook file

        Returns:
            FilterContext for the folder
        """
        # Determine folder key
        try:
            rel_path = notebook_path.relative_to(self.notebooks_root)
            folder_key = str(rel_path.parent) if rel_path.parent != Path('.') else 'root'
        except ValueError:
            folder_key = 'root'

        # Switch current context
        self._current_folder = folder_key

        # Initialize context if not exists
        if folder_key not in self._contexts:
            self._contexts[folder_key] = FilterContext()

        return self._contexts[folder_key]

    def get_current_context(self) -> FilterContext:
        """Get current folder's filter context."""
        if self._current_folder is None:
            return FilterContext()  # Empty context

        return self._contexts.get(self._current_folder, FilterContext())

    def update_filter(self, dimension: str, values: List[str]):
        """
        Update filter in current folder context.

        Args:
            dimension: Filter dimension
            values: Filter values
        """
        context = self.get_current_context()
        context.dimensions[dimension] = values

    def clear_filters(self):
        """Clear all filters in current folder."""
        context = self.get_current_context()
        context.clear()

    def clear_all_folders(self):
        """Clear filters for all folders."""
        for context in self._contexts.values():
            context.clear()

    def list_folders(self) -> List[str]:
        """List all folder keys with active contexts."""
        return list(self._contexts.keys())

    def get_folder_filters(self, folder_key: str) -> FilterContext:
        """Get filter context for specific folder."""
        return self._contexts.get(folder_key, FilterContext())
```

## Usage Examples

### Example 1: Shared Filters in Folder

```python
manager = NotebookManager(session, repo_root)

# Load first notebook in Finance folder
manager.load_notebook("configs/notebooks/Finance/stock_analysis.md")
manager.update_filter('ticker', ['AAPL', 'GOOGL'])
manager.update_filter('date', {'start': '2024-01-01', 'end': '2024-12-31'})

# Load second notebook in same folder
manager.load_notebook("configs/notebooks/Finance/forecast_analysis.md")

# Filters still active!
filters = manager.get_active_filters()
print(filters.dimensions['ticker'])  # ['AAPL', 'GOOGL']
```

### Example 2: Isolated Folders

```python
# Finance folder
manager.load_notebook("configs/notebooks/Finance/stock_analysis.md")
manager.update_filter('ticker', ['AAPL'])

# Switch to Economics folder
manager.load_notebook("configs/notebooks/Economics/gdp_analysis.md")

# Finance filters not applied here
filters = manager.get_active_filters()
print(filters.dimensions)  # {} (empty - different folder)
```

### Example 3: Clear Folder Filters

```python
# Clear current folder
manager.clear_filters()

# Clear all folders
manager.folder_context_manager.clear_all_folders()
```

**File**: `/home/user/de_Funk/docs/guide/3-architecture/components/notebook-system/folder-context.md`
