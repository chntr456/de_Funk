"""
Simplified notebook session for executing and rendering notebooks.

This is a temporary stub that provides the interface needed by notebook_app_professional.py
without dependencies on deleted graph/measures modules.

TODO: Migrate to use NotebookService from src.services instead.
"""

from typing import Dict, List, Optional, Any
from pathlib import Path
from pyspark.sql import DataFrame, SparkSession
import pyspark.sql.functions as F

from ..schema import NotebookConfig, Exhibit
from ..parser import NotebookParser
from ..filters.context import FilterContext
from ...model.api.session import ModelSession


class NotebookSession:
    """
    Simplified session for executing a YAML notebook.

    Provides:
    - Notebook loading and parsing
    - Filter management
    - Exhibit data preparation (basic implementation)
    """

    def __init__(
        self,
        spark: SparkSession,
        model_session: ModelSession,
        repo_root: Optional[Path] = None,
    ):
        """
        Initialize notebook session.

        Args:
            spark: Spark session
            model_session: Model session for accessing backend models
            repo_root: Repository root for resolving paths
        """
        self.spark = spark
        self.model_session = model_session
        self.repo_root = repo_root or Path.cwd()

        # Initialize components
        self.parser = NotebookParser(self.repo_root)
        self.filter_context = FilterContext()

        # Current notebook
        self.notebook_config: Optional[NotebookConfig] = None

    def load_notebook(self, notebook_path: str) -> NotebookConfig:
        """
        Load and parse a notebook.

        Args:
            notebook_path: Path to notebook YAML file

        Returns:
            NotebookConfig object
        """
        # Parse notebook
        self.notebook_config = self.parser.parse_file(notebook_path)

        # Initialize filter context with defaults
        default_filters = {}
        for var_id, variable in self.notebook_config.variables.items():
            default_filters[var_id] = variable.default

        self.filter_context.set_filters(default_filters)

        return self.notebook_config

    def get_filter_context(self) -> Dict[str, Any]:
        """Get current filter context."""
        return self.filter_context.filters

    def update_filters(self, filter_values: Dict[str, Any]):
        """
        Update filter values.

        Args:
            filter_values: Dictionary of filter_id -> value
        """
        self.filter_context.set_filters(filter_values)

    def get_exhibit_data(self, exhibit_id: str) -> DataFrame:
        """
        Get data for an exhibit (simplified implementation).

        Args:
            exhibit_id: ID of the exhibit

        Returns:
            Spark DataFrame with exhibit data
        """
        if not self.notebook_config:
            raise ValueError("No notebook loaded")

        # Find the exhibit
        exhibit = None
        for ex in self.notebook_config.exhibits:
            if ex.id == exhibit_id:
                exhibit = ex
                break

        if not exhibit:
            raise ValueError(f"Exhibit not found: {exhibit_id}")

        # Get the source table from model_session
        # For simplified version, we'll get the first model's first table
        # This is a stub - real implementation would use exhibit.source

        # Parse source if available (format: "model.table")
        if hasattr(exhibit, 'source') and exhibit.source:
            parts = exhibit.source.split('.')
            if len(parts) == 2:
                model_name, table_name = parts
                # Try to get the table from model session
                # This is a simplified approach - would need proper implementation
                pass

        # Fallback: Get data from model_session's backend
        # For now, return a simple DataFrame to make the app work
        # In reality, this should query the proper table based on exhibit config

        # Get the backend storage
        from ...services.storage_service import SilverStorageService

        # This is a hack to make it work - ideally would use proper service
        # Return empty dataframe for now to prevent crashes
        return self.spark.createDataFrame([], "dummy STRING")
