"""
Folder-based filter context manager.

Manages filter contexts at the folder level, allowing notebooks within the same
folder to share filters while maintaining isolation across folders.

Features:
- Persists filter state to .filter_context.yaml in each folder
- Supports copying folders to recreate views
- Isolates filter sessions across folder boundaries
- Enables multiple concurrent filter sessions (one per folder)
- Global context for ticker and date_range (shared across all folders)
- Folder-specific context for all other filters
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional, Set
from datetime import datetime
from dataclasses import dataclass, field, asdict


# Filters that are shared globally across all folders
GLOBAL_FILTERS = {'ticker', 'date_range', 'tickers', 'date'}


@dataclass
class FilterContext:
    """Filter context for a folder or global scope."""
    folder_path: Optional[Path] = None  # None for global context
    filters: Dict[str, Any] = field(default_factory=dict)
    created: Optional[datetime] = None
    last_updated: Optional[datetime] = None
    is_global: bool = False

    def __post_init__(self):
        """Initialize timestamps if not provided."""
        if self.created is None:
            self.created = datetime.now()
        if self.last_updated is None:
            self.last_updated = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'filters': self.filters,
            'metadata': {
                'created': self.created.isoformat() if self.created else None,
                'last_updated': self.last_updated.isoformat() if self.last_updated else None,
                'is_global': self.is_global
            }
        }

    @classmethod
    def from_dict(cls, folder_path: Optional[Path], data: Dict[str, Any]) -> 'FilterContext':
        """Create from dictionary."""
        metadata = data.get('metadata', {})
        return cls(
            folder_path=folder_path,
            filters=data.get('filters', {}),
            created=datetime.fromisoformat(metadata['created']) if metadata.get('created') else None,
            last_updated=datetime.fromisoformat(metadata['last_updated']) if metadata.get('last_updated') else None,
            is_global=metadata.get('is_global', False)
        )


class FolderFilterContextManager:
    """
    Manages filter contexts at the folder level with global context support.

    Two-tier filter system:
    1. Global context: ticker, date_range (shared across ALL folders)
    2. Folder context: all other filters (shared within folder, isolated across folders)

    Usage:
        manager = FolderFilterContextManager(notebooks_root)

        # Update global filter
        manager.update_filters(folder_path, {'ticker': 'AAPL'})  # → Global

        # Update folder filter
        manager.update_filters(folder_path, {'volume_min': 1000})  # → Folder

        # Get merged filters
        filters = manager.get_filters(folder_path)  # → {ticker: AAPL, volume_min: 1000}
    """

    CONTEXT_FILENAME = '.filter_context.yaml'
    GLOBAL_CONTEXT_FILENAME = '.global_filter_context.yaml'

    def __init__(self, notebooks_root: Path):
        """
        Initialize folder filter context manager.

        Args:
            notebooks_root: Root directory for notebooks
        """
        self.notebooks_root = Path(notebooks_root)
        self._contexts: Dict[str, FilterContext] = {}
        self._global_context: Optional[FilterContext] = None

    def get_folder_for_notebook(self, notebook_path: Path) -> Path:
        """
        Get the folder containing a notebook.

        Args:
            notebook_path: Path to notebook file

        Returns:
            Parent folder path
        """
        if notebook_path.is_file():
            return notebook_path.parent
        return notebook_path

    def get_context_for_notebook(self, notebook_path: Path) -> FilterContext:
        """
        Get filter context for a notebook (based on its folder).

        Args:
            notebook_path: Path to notebook file

        Returns:
            FilterContext for the notebook's folder
        """
        folder_path = self.get_folder_for_notebook(notebook_path)
        return self.get_context(folder_path)

    def get_context(self, folder_path: Path) -> FilterContext:
        """
        Get or create filter context for a folder.

        Args:
            folder_path: Path to folder

        Returns:
            FilterContext for the folder
        """
        folder_key = str(folder_path)

        if folder_key not in self._contexts:
            # Try to load from disk
            context = self._load_context(folder_path)
            if context is None:
                # Create new context
                context = FilterContext(folder_path=folder_path)
            self._contexts[folder_key] = context

        return self._contexts[folder_key]

    def get_global_context(self) -> FilterContext:
        """
        Get or create global filter context.

        Returns:
            Global FilterContext
        """
        if self._global_context is None:
            # Try to load from disk
            context = self._load_global_context()
            if context is None:
                # Create new global context
                context = FilterContext(folder_path=None, is_global=True)
            self._global_context = context

        return self._global_context

    def update_filters(self, folder_path: Path, filters: Dict[str, Any], auto_save: bool = True):
        """
        Update filters - routes to global or folder context based on filter type.

        Global filters (ticker, date_range): Saved to global context
        Other filters: Saved to folder context

        Args:
            folder_path: Path to folder
            filters: Filter values to update
            auto_save: Whether to auto-save to disk
        """
        # Split filters into global and folder-specific
        global_filters = {}
        folder_filters = {}

        for key, value in filters.items():
            if key in GLOBAL_FILTERS:
                global_filters[key] = value
            else:
                folder_filters[key] = value

        # Update global context
        if global_filters:
            global_context = self.get_global_context()
            global_context.filters.update(global_filters)
            global_context.last_updated = datetime.now()
            if auto_save:
                self.save_global_context()

        # Update folder context
        if folder_filters:
            folder_context = self.get_context(folder_path)
            folder_context.filters.update(folder_filters)
            folder_context.last_updated = datetime.now()
            if auto_save:
                self.save_context(folder_path)

    def get_filters(self, folder_path: Path) -> Dict[str, Any]:
        """
        Get merged filters (global + folder-specific).

        Returns:
            Dictionary combining global and folder filters
        """
        # Start with global filters
        merged = self.get_global_context().filters.copy()

        # Add folder-specific filters (they override global if there's overlap)
        folder_context = self.get_context(folder_path)
        merged.update(folder_context.filters)

        return merged

    def get_global_filters(self) -> Dict[str, Any]:
        """
        Get only global filters.

        Returns:
            Dictionary of global filter values
        """
        return self.get_global_context().filters.copy()

    def get_folder_specific_filters(self, folder_path: Path) -> Dict[str, Any]:
        """
        Get only folder-specific filters (excluding global).

        Args:
            folder_path: Path to folder

        Returns:
            Dictionary of folder-specific filter values
        """
        context = self.get_context(folder_path)
        return context.filters.copy()

    def clear_filters(self, folder_path: Path, auto_save: bool = True):
        """
        Clear folder-specific filters only (preserves global filters).

        Args:
            folder_path: Path to folder
            auto_save: Whether to auto-save to disk
        """
        context = self.get_context(folder_path)
        context.filters.clear()
        context.last_updated = datetime.now()

        if auto_save:
            self.save_context(folder_path)

    def clear_global_filters(self, auto_save: bool = True):
        """
        Clear global filters (ticker, date_range).

        Args:
            auto_save: Whether to auto-save to disk
        """
        global_context = self.get_global_context()
        global_context.filters.clear()
        global_context.last_updated = datetime.now()

        if auto_save:
            self.save_global_context()

    def clear_all_filters(self, folder_path: Path, auto_save: bool = True):
        """
        Clear both global and folder-specific filters.

        Args:
            folder_path: Path to folder
            auto_save: Whether to auto-save to disk
        """
        self.clear_global_filters(auto_save=auto_save)
        self.clear_filters(folder_path, auto_save=auto_save)

    def save_context(self, folder_path: Path):
        """
        Save folder-specific filter context to disk.

        Args:
            folder_path: Path to folder
        """
        context = self.get_context(folder_path)
        context_file = folder_path / self.CONTEXT_FILENAME

        # Ensure folder exists
        folder_path.mkdir(parents=True, exist_ok=True)

        # Save to YAML
        with open(context_file, 'w') as f:
            yaml.dump(context.to_dict(), f, default_flow_style=False, sort_keys=False)

    def save_global_context(self):
        """
        Save global filter context to disk (in notebooks root).
        """
        global_context = self.get_global_context()
        context_file = self.notebooks_root / self.GLOBAL_CONTEXT_FILENAME

        # Ensure directory exists
        self.notebooks_root.mkdir(parents=True, exist_ok=True)

        # Save to YAML
        with open(context_file, 'w') as f:
            yaml.dump(global_context.to_dict(), f, default_flow_style=False, sort_keys=False)

    def _load_context(self, folder_path: Path) -> Optional[FilterContext]:
        """
        Load filter context from disk.

        Args:
            folder_path: Path to folder

        Returns:
            FilterContext if found, None otherwise
        """
        context_file = folder_path / self.CONTEXT_FILENAME

        if not context_file.exists():
            return None

        try:
            with open(context_file, 'r') as f:
                data = yaml.safe_load(f)

            if data:
                return FilterContext.from_dict(folder_path, data)
        except Exception as e:
            print(f"Warning: Could not load filter context from {context_file}: {e}")

        return None

    def _load_global_context(self) -> Optional[FilterContext]:
        """
        Load global filter context from disk.

        Returns:
            FilterContext if found, None otherwise
        """
        context_file = self.notebooks_root / self.GLOBAL_CONTEXT_FILENAME

        if not context_file.exists():
            return None

        try:
            with open(context_file, 'r') as f:
                data = yaml.safe_load(f)

            if data:
                return FilterContext.from_dict(None, data)
        except Exception as e:
            print(f"Warning: Could not load global filter context from {context_file}: {e}")

        return None

    def delete_context(self, folder_path: Path):
        """
        Delete filter context from memory and disk.

        Args:
            folder_path: Path to folder
        """
        folder_key = str(folder_path)

        # Remove from memory
        if folder_key in self._contexts:
            del self._contexts[folder_key]

        # Remove from disk
        context_file = folder_path / self.CONTEXT_FILENAME
        if context_file.exists():
            context_file.unlink()

    def list_folders_with_contexts(self) -> list[Path]:
        """
        List all folders that have saved filter contexts.

        Returns:
            List of folder paths with .filter_context.yaml files
        """
        contexts = []

        if self.notebooks_root.exists():
            for context_file in self.notebooks_root.rglob(self.CONTEXT_FILENAME):
                contexts.append(context_file.parent)

        return sorted(contexts)

    def has_context_changed(self, folder_path: Path, current_folder: Optional[Path]) -> bool:
        """
        Check if switching to a different folder context.

        Args:
            folder_path: New folder path
            current_folder: Current folder path (or None)

        Returns:
            True if folder context is changing
        """
        if current_folder is None:
            return True

        return str(folder_path) != str(current_folder)
