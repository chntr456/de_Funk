"""
Folder-based filter context manager.

Simple folder-level filter sharing:
- Each folder has .filter_context.yaml (YAML-based, editable)
- Filters shared within folder only
- Complete isolation across folders (no global sharing)
- Editable in UI like notebooks

Architecture:
  notebooks/company_analysis/.filter_context.yaml → Used by all notebooks in that folder
  notebooks/market_trends/.filter_context.yaml → Completely separate

When switching folders, filters completely reset to that folder's context.
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass


@dataclass
class FolderFilterContext:
    """Filter context for a folder (YAML-based)."""
    folder_path: Path
    filters: Dict[str, Any]
    created: Optional[datetime] = None
    last_updated: Optional[datetime] = None

    def __post_init__(self):
        """Initialize timestamps if not provided."""
        if self.created is None:
            self.created = datetime.now()
        if self.last_updated is None:
            self.last_updated = datetime.now()

    def to_yaml_dict(self) -> Dict[str, Any]:
        """Convert to YAML-serializable dictionary."""
        return {
            'filters': self.filters,
            'metadata': {
                'created': self.created.isoformat() if self.created else None,
                'last_updated': self.last_updated.isoformat() if self.last_updated else None,
                'folder': str(self.folder_path.name)
            }
        }

    @classmethod
    def from_yaml_dict(cls, folder_path: Path, data: Dict[str, Any]) -> 'FolderFilterContext':
        """Create from YAML dictionary."""
        metadata = data.get('metadata', {})
        return cls(
            folder_path=folder_path,
            filters=data.get('filters', {}),
            created=datetime.fromisoformat(metadata['created']) if metadata.get('created') else None,
            last_updated=datetime.fromisoformat(metadata['last_updated']) if metadata.get('last_updated') else None
        )


class FolderFilterContextManager:
    """
    Simple folder-based filter context manager.

    Each folder has ONE .filter_context.yaml file that defines filters
    for ALL notebooks in that folder.

    NO global context, NO cross-folder sharing. Clean isolation.
    """

    CONTEXT_FILENAME = '.filter_context.yaml'

    def __init__(self, notebooks_root: Path):
        """
        Initialize folder filter context manager.

        Args:
            notebooks_root: Root directory for notebooks
        """
        self.notebooks_root = Path(notebooks_root)
        self._contexts: Dict[str, FolderFilterContext] = {}

    def get_folder_for_notebook(self, notebook_path: Path) -> Path:
        """Get the folder containing a notebook."""
        if notebook_path.is_file():
            return notebook_path.parent
        return notebook_path

    def get_context(self, folder_path: Path) -> FolderFilterContext:
        """
        Get or create filter context for a folder.

        Loads from .filter_context.yaml if exists.

        Args:
            folder_path: Path to folder

        Returns:
            FolderFilterContext for the folder
        """
        folder_key = str(folder_path)

        if folder_key not in self._contexts:
            # Try to load from disk
            context = self._load_context(folder_path)
            if context is None:
                # Create new empty context
                context = FolderFilterContext(folder_path=folder_path, filters={})
            self._contexts[folder_key] = context

        return self._contexts[folder_key]

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
        Save folder filter context to .filter_context.yaml

        Args:
            folder_path: Path to folder
        """
        context = self.get_context(folder_path)
        context_file = folder_path / self.CONTEXT_FILENAME

        # Ensure folder exists
        folder_path.mkdir(parents=True, exist_ok=True)

        # Save to YAML
        with open(context_file, 'w') as f:
            yaml.dump(context.to_yaml_dict(), f, default_flow_style=False, sort_keys=False)

    def _load_context(self, folder_path: Path) -> Optional[FolderFilterContext]:
        """
        Load filter context from .filter_context.yaml

        Args:
            folder_path: Path to folder

        Returns:
            FolderFilterContext if found, None otherwise
        """
        context_file = folder_path / self.CONTEXT_FILENAME

        if not context_file.exists():
            return None

        try:
            with open(context_file, 'r') as f:
                data = yaml.safe_load(f)

            if data:
                return FolderFilterContext.from_yaml_dict(folder_path, data)
        except Exception as e:
            print(f"Warning: Could not load filter context from {context_file}: {e}")

        return None

    def get_context_file_path(self, folder_path: Path) -> Path:
        """
        Get path to .filter_context.yaml file for a folder.

        Args:
            folder_path: Path to folder

        Returns:
            Path to .filter_context.yaml
        """
        return folder_path / self.CONTEXT_FILENAME

    def get_context_yaml_content(self, folder_path: Path) -> str:
        """
        Get YAML content of filter context file for editing.

        Args:
            folder_path: Path to folder

        Returns:
            YAML string content
        """
        context_file = self.get_context_file_path(folder_path)

        if context_file.exists():
            with open(context_file, 'r') as f:
                return f.read()
        else:
            # Return template
            return """# Folder Filter Context
# Filters defined here are shared by all notebooks in this folder

filters:
  # Example filters (edit as needed):
  # ticker: AAPL
  # date_range:
  #   start: 2024-10-01
  #   end: 2024-11-01
  # volume_min: 1000000

metadata:
  created: """ + datetime.now().isoformat() + """
  last_updated: """ + datetime.now().isoformat() + """
  folder: """ + folder_path.name + """
"""

    def save_context_yaml_content(self, folder_path: Path, yaml_content: str):
        """
        Save YAML content to filter context file.

        Args:
            folder_path: Path to folder
            yaml_content: YAML string to save
        """
        context_file = self.get_context_file_path(folder_path)

        # Ensure folder exists
        folder_path.mkdir(parents=True, exist_ok=True)

        # Save content
        with open(context_file, 'w') as f:
            f.write(yaml_content)

        # Reload context from disk
        folder_key = str(folder_path)
        if folder_key in self._contexts:
            del self._contexts[folder_key]
        self.get_context(folder_path)  # Reload

    def delete_context(self, folder_path: Path):
        """
        Delete filter context file.

        Args:
            folder_path: Path to folder
        """
        folder_key = str(folder_path)

        # Remove from memory
        if folder_key in self._contexts:
            del self._contexts[folder_key]

        # Remove from disk
        context_file = self.get_context_file_path(folder_path)
        if context_file.exists():
            context_file.unlink()

    def has_context_changed(self, new_folder: Path, current_folder: Optional[Path]) -> bool:
        """
        Check if switching to a different folder.

        Args:
            new_folder: New folder path
            current_folder: Current folder path (or None)

        Returns:
            True if folder is changing
        """
        if current_folder is None:
            return True

        return str(new_folder) != str(current_folder)
