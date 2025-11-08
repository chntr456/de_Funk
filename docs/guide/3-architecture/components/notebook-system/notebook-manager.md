# Notebook System - Notebook Manager

## Overview

**NotebookManager** orchestrates the notebook lifecycle, managing loading, parsing, filter contexts, and exhibit execution. It delegates data access to UniversalSession and filter application to FilterEngine.

## Class Definition

```python
# File: app/notebook/managers/notebook_manager.py:28-200

class NotebookManager:
    """Manager for notebook lifecycle and execution."""

    def __init__(
        self,
        universal_session: UniversalSession,
        repo_root: Optional[Path] = None,
        notebooks_root: Optional[Path] = None
    ):
        self.session = universal_session
        self.repo_root = repo_root or Path.cwd()
        
        # Markdown parser
        self.markdown_parser = MarkdownNotebookParser(self.repo_root)
        
        # Folder-based filter contexts
        if notebooks_root is None:
            notebooks_root = self.repo_root / "configs" / "notebooks"
        self.folder_context_manager = FolderFilterContextManager(notebooks_root)
        
        # Current notebook state
        self.notebook_config: Optional[NotebookConfig] = None
        self.current_notebook_path: Optional[Path] = None
        self.current_folder: Optional[Path] = None
```

## Notebook Loading

```python
def load_notebook(self, notebook_path: str) -> NotebookConfig:
    """
    Load and parse markdown notebook.

    Steps:
    1. Parse markdown file
    2. Extract exhibits and filters
    3. Switch folder context
    4. Return notebook config

    Args:
        notebook_path: Path to .md file

    Returns:
        NotebookConfig with all exhibits
    """
    path = Path(notebook_path).resolve()
    
    # Only support markdown
    if path.suffix not in ['.md', '.markdown']:
        raise ValueError(f"Unsupported format: {path.suffix}")
    
    # Parse notebook
    self.notebook_config = self.markdown_parser.parse_file(notebook_path)
    self.current_notebook_path = path
    
    # Switch folder context
    self.current_folder = path.parent
    self.folder_context_manager.switch_folder(path)
    
    return self.notebook_config
```

## Filter Management

```python
def update_filter(self, dimension: str, values: List[str]):
    """
    Update filter in current folder context.

    Args:
        dimension: Filter dimension (e.g., 'ticker', 'date')
        values: Filter values
    """
    self.folder_context_manager.update_filter(dimension, values)

def get_active_filters(self) -> FilterContext:
    """Get current active filter context."""
    return self.folder_context_manager.get_current_context()

def clear_filters(self):
    """Clear all filters in current folder."""
    self.folder_context_manager.clear_filters()
```

## Exhibit Execution

```python
def execute_exhibit(self, exhibit: Exhibit) -> pd.DataFrame:
    """
    Execute an exhibit and return data.

    Steps:
    1. Get model and table from session
    2. Get active filter context
    3. Apply filters via FilterEngine
    4. Execute query
    5. Return results

    Args:
        exhibit: Exhibit definition

    Returns:
        Pandas DataFrame with results
    """
    # Extract query spec
    query = exhibit.query
    model_name = query.get('model', 'company')
    table_name = query.get('table')
    
    # Get table from session
    df = self.session.get_table(model_name, table_name)
    
    # Get active filters
    filter_context = self.get_active_filters()
    
    # Apply filters
    from core.session.filters import FilterEngine
    df = FilterEngine.apply_from_session(df, filter_context.to_dict(), self.session)
    
    # Apply exhibit-specific filters
    if 'filters' in query:
        df = FilterEngine.apply_from_session(df, query['filters'], self.session)
    
    # Select measures
    if 'measures' in query:
        measures = query['measures']
        # Select specific columns
        if self.session.backend == 'spark':
            from pyspark.sql import functions as F
            df = df.select(*[F.col(m) for m in measures])
        else:
            df = df.select(*measures)
    
    # Apply aggregations
    if 'aggregation' in query:
        agg_spec = query['aggregation']
        group_by = query.get('group_by', [])
        df = self._apply_aggregation(df, group_by, agg_spec)
    
    # Convert to Pandas
    pdf = self.session.connection.to_pandas(df)
    
    return pdf

def _apply_aggregation(self, df, group_by, agg_spec):
    """Apply aggregation to dataframe."""
    if self.session.backend == 'spark':
        from pyspark.sql import functions as F
        
        # Parse aggregation (e.g., "avg(close)")
        if isinstance(agg_spec, str):
            # Simple aggregation
            if group_by:
                df = df.groupBy(group_by).agg(F.expr(agg_spec))
            else:
                df = df.agg(F.expr(agg_spec))
        
        return df
    else:
        # DuckDB aggregation
        if group_by:
            df = df.aggregate(agg_spec, by=group_by)
        else:
            df = df.aggregate(agg_spec)
        
        return df
```

## Usage Examples

### Example 1: Load and Execute

```python
# Initialize
manager = NotebookManager(session, repo_root)

# Load notebook
notebook = manager.load_notebook("configs/notebooks/stock_analysis.md")

# Set filters
manager.update_filter('ticker', ['AAPL'])
manager.update_filter('date', {'start': '2024-01-01', 'end': '2024-12-31'})

# Execute first exhibit
if notebook.exhibits:
    data = manager.execute_exhibit(notebook.exhibits[0])
    print(data.head())
```

### Example 2: Multiple Notebooks in Folder

```python
# Each notebook in same folder shares filter context
manager.load_notebook("configs/notebooks/Finance/stock_analysis.md")
manager.update_filter('ticker', ['AAPL'])  # Applied to folder

# Switch to another notebook in same folder
manager.load_notebook("configs/notebooks/Finance/forecast_analysis.md")
# Ticker filter still active!

# Switch to different folder
manager.load_notebook("configs/notebooks/Economics/gdp_analysis.md")
# New folder context - no ticker filter
```

**File**: `/home/user/de_Funk/docs/guide/3-architecture/components/notebook-system/notebook-manager.md`
