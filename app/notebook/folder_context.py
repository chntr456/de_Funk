"""
Folder-based filter context manager.

Manages filter contexts at the folder level, allowing notebooks within the same
folder to share filters while maintaining isolation across folders.

Features:
- Persists filter state to .filter_context.yaml in each folder
- Supports copying folders to recreate views
- Isolates filter sessions across folder boundaries
- Enables multiple concurrent filter sessions (one per folder)
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field, asdict


@dataclass
class FilterContext:
    """Filter context for a folder."""
    folder_path: Path
    filters: Dict[str, Any] = field(default_factory=dict)
    created: Optional[datetime] = None
    last_updated: Optional[datetime] = None

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
                'last_updated': self.last_updated.isoformat() if self.last_updated else None
            }
        }

    @classmethod
    def from_dict(cls, folder_path: Path, data: Dict[str, Any]) -> 'FilterContext':
        """Create from dictionary."""
        metadata = data.get('metadata', {})
        return cls(
            folder_path=folder_path,
            filters=data.get('filters', {}),
            created=datetime.fromisoformat(metadata['created']) if metadata.get('created') else None,
            last_updated=datetime.fromisoformat(metadata['last_updated']) if metadata.get('last_updated') else None
        )


class FolderFilterContextManager:
    """
    Manages filter contexts at the folder level.

    Each folder can have its own filter context that is shared by all notebooks
    within that folder. Contexts are isolated across folder boundaries.

    Usage:
        manager = FolderFilterContextManager(notebooks_root)

        # Get context for a notebook
        context = manager.get_context_for_notebook(notebook_path)

        # Update filters
        manager.update_filters(folder_path, {'ticker': 'AAPL'})

        # Save to disk
        manager.save_context(folder_path)
    """

    CONTEXT_FILENAME = '.filter_context.yaml'

    def __init__(self, notebooks_root: Path):
        """
        Initialize folder filter context manager.

        Args:
            notebooks_root: Root directory for notebooks
        """
        self.notebooks_root = Path(notebooks_root)
        self._contexts: Dict[str, FilterContext] = {}

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

    def update_filters(self, folder_path: Path, filters: Dict[str, Any], auto_save: bool = True):
        """
        Update filters for a folder.

        Args:
            folder_path: Path to folder
            filters: Filter values to update
            auto_save: Whether to auto-save to disk
        """
        context = self.get_context(folder_path)
        context.filters.update(filters)
        context.last_updated = datetime.now()

        if auto_save:
            self.save_context(folder_path)

    def get_filters(self, folder_path: Path) -> Dict[str, Any]:
        """
        Get current filters for a folder.

        Args:
            folder_path: Path to folder

        Returns:
            Dictionary of filter values
        """
        context = self.get_context(folder_path)
        return context.filters.copy()

    def clear_filters(self, folder_path: Path, auto_save: bool = True):
        """
        Clear all filters for a folder.

        Args:
            folder_path: Path to folder
            auto_save: Whether to auto-save to disk
        """
        context = self.get_context(folder_path)
        context.filters.clear()
        context.last_updated = datetime.now()

        if auto_save:
            self.save_context(folder_path)

    def save_context(self, folder_path: Path):
        """
        Save filter context to disk.

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
