"""
Notebook Service.

Simplified service for loading and executing notebooks without measure calculation.

All measures are pre-computed in Silver layer. This service just filters and retrieves.
"""

from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime
import pandas as pd
from pyspark.sql import DataFrame

from .storage_service import SilverStorageService
from ..notebook.schema import NotebookConfig, Exhibit, Variable, VariableType
from ..notebook.parsers import NotebookParser
from ..core.validation import NotebookValidator, ValidationError


class NotebookService:
    """
    Simplified notebook service.

    Responsibilities ONLY:
    - Load and parse notebook YAML
    - Validate against models
    - Manage filter state
    - Fetch pre-computed data from SilverStorageService
    - Apply filters
    - Return Pandas DataFrames for UI

    Does NOT:
    - Calculate measures (done in Silver layer)
    - Build graphs (not needed)
    - Compute aggregations (done in Silver layer)
    """

    def __init__(
        self,
        storage_service: SilverStorageService,
        repo_root: Optional[Path] = None,
        validate_on_load: bool = True,
    ):
        """
        Initialize notebook service.

        Args:
            storage_service: Silver storage service for data access
            repo_root: Repository root for resolving paths
            validate_on_load: Whether to validate notebooks on load (default: True)
        """
        self.storage_service = storage_service
        if repo_root is None:
            from de_funk.utils.repo import get_repo_root
            repo_root = get_repo_root()
        self.repo_root = repo_root
        self.parser = NotebookParser(repo_root)
        self.validate_on_load = validate_on_load

        # Get validator from storage service
        model_registry = storage_service.get_model_registry()
        self.validator = NotebookValidator(model_registry)

        # State
        self.notebook_config: Optional[NotebookConfig] = None
        self.filter_values: Dict[str, Any] = {}
        self.validation_errors: List[ValidationError] = []
        self.validation_warnings: List[ValidationError] = []

    def load_notebook(self, notebook_path: str) -> NotebookConfig:
        """
        Load notebook from YAML file with validation.

        Args:
            notebook_path: Path to notebook YAML

        Returns:
            Parsed notebook configuration

        Raises:
            ValueError: If validation fails (when validate_on_load=True)
        """
        self.notebook_config = self.parser.parse_file(notebook_path)

        # Validate
        if self.validate_on_load:
            self.validation_errors = self.validator.get_errors(self.notebook_config)
            self.validation_warnings = self.validator.get_warnings(self.notebook_config)

            if self.validation_errors:
                error_messages = '\n'.join([
                    f"  [{e.level.upper()}] {e.location}: {e.message}"
                    for e in self.validation_errors
                ])
                raise ValueError(f"Notebook validation failed:\n{error_messages}")

        self._initialize_filters()
        return self.notebook_config

    def get_validation_status(self) -> Dict[str, Any]:
        """
        Get validation status.

        Returns:
            Dict with validation results
        """
        return {
            'is_valid': len(self.validation_errors) == 0,
            'errors': [
                {'level': e.level, 'location': e.location, 'message': e.message}
                for e in self.validation_errors
            ],
            'warnings': [
                {'level': e.level, 'location': e.location, 'message': e.message}
                for e in self.validation_warnings
            ]
        }

    def _initialize_filters(self):
        """Initialize filter values with defaults from notebook."""
        if not self.notebook_config:
            return

        for var_id, variable in self.notebook_config.variables.items():
            # Set default values
            if variable.default is not None:
                self.filter_values[var_id] = variable.default

    def update_filters(self, values: Dict[str, Any]):
        """
        Update filter values.

        Args:
            values: Dictionary of variable_id -> value
        """
        self.filter_values.update(values)

    def get_filter_values(self) -> Dict[str, Any]:
        """Get current filter values."""
        return self.filter_values.copy()

    def get_exhibit_data(self, exhibit_id: str) -> pd.DataFrame:
        """
        Get data for an exhibit as Pandas DataFrame.

        Args:
            exhibit_id: Exhibit ID

        Returns:
            Pandas DataFrame ready for rendering
        """
        if not self.notebook_config:
            raise ValueError("No notebook loaded")

        # Find exhibit
        exhibit = next(
            (ex for ex in self.notebook_config.exhibits if ex.id == exhibit_id),
            None
        )

        if not exhibit:
            raise ValueError(f"Exhibit not found: {exhibit_id}")

        # Get filters for this exhibit
        filters = self._resolve_exhibit_filters(exhibit)

        # Fetch data from storage service
        spark_df = self._fetch_exhibit_data(exhibit, filters)

        # Convert to Pandas
        return spark_df.toPandas()

    def _resolve_exhibit_filters(self, exhibit: Exhibit) -> Dict[str, Any]:
        """
        Resolve filters for an exhibit.

        Combines notebook-level filters with exhibit-specific filters.

        Args:
            exhibit: Exhibit configuration

        Returns:
            Resolved filter values
        """
        filters = self.filter_values.copy()

        # Apply exhibit-specific filters
        if hasattr(exhibit, 'filters') and exhibit.filters:
            for filter_id, filter_ref in exhibit.filters.items():
                # Handle variable references ($variable_name)
                if isinstance(filter_ref, str) and filter_ref.startswith('$'):
                    var_name = filter_ref[1:]
                    if var_name in self.filter_values:
                        filters[filter_id] = self.filter_values[var_name]
                else:
                    filters[filter_id] = filter_ref

        return filters

    def _fetch_exhibit_data(
        self,
        exhibit: Exhibit,
        filters: Dict[str, Any]
    ) -> DataFrame:
        """
        Fetch data for exhibit from storage service.

        Args:
            exhibit: Exhibit configuration
            filters: Resolved filters

        Returns:
            Spark DataFrame with exhibit data
        """
        # Extract common filters
        start_date = None
        end_date = None
        tickers = None

        # Handle date range filter
        if 'time' in filters and isinstance(filters['time'], dict):
            start_date = filters['time'].get('start')
            end_date = filters['time'].get('end')

            # Convert datetime to string if needed
            if isinstance(start_date, datetime):
                start_date = start_date.strftime('%Y-%m-%d')
            if isinstance(end_date, datetime):
                end_date = end_date.strftime('%Y-%m-%d')

        # Handle tickers filter
        if 'tickers' in filters:
            tickers = filters['tickers']

        # Fetch from storage service
        # For now, always fetch from prices_with_company (the most common case)
        df = self.storage_service.get_prices_with_company(
            start_date=start_date,
            end_date=end_date,
            tickers=tickers,
        )

        # Apply any aggregations needed for the exhibit
        df = self._apply_exhibit_aggregations(df, exhibit)

        return df

    def _apply_exhibit_aggregations(
        self,
        df: DataFrame,
        exhibit: Exhibit
    ) -> DataFrame:
        """
        Apply aggregations specified in exhibit.

        For metric cards: aggregate across all dimensions
        For charts: aggregate by exhibit dimensions

        Args:
            df: Source DataFrame
            exhibit: Exhibit configuration

        Returns:
            Aggregated DataFrame
        """
        from pyspark.sql import functions as F

        # For metric cards without grouping
        if exhibit.type.value == 'metric_cards':
            # Aggregate across all rows
            if hasattr(exhibit, 'metrics'):
                agg_exprs = []
                for metric in exhibit.metrics:
                    measure_id = metric.measure

                    # Map measure IDs to column operations
                    if measure_id == 'avg_close_price':
                        agg_exprs.append(F.avg('close').alias('avg_close_price'))
                    elif measure_id == 'total_volume':
                        agg_exprs.append(F.sum('volume').alias('total_volume'))
                    elif measure_id == 'max_high':
                        agg_exprs.append(F.max('high').alias('max_high'))
                    elif measure_id == 'min_low':
                        agg_exprs.append(F.min('low').alias('min_low'))
                    elif measure_id == 'vwap':
                        agg_exprs.append(F.avg('volume_weighted').alias('vwap'))

                if agg_exprs:
                    df = df.agg(*agg_exprs)

        # For charts and tables with dimensions
        elif hasattr(exhibit, 'x_axis') and exhibit.x_axis:
            x_col = exhibit.x_axis.dimension

            # Group by x-axis dimension
            if hasattr(exhibit, 'y_axis') and exhibit.y_axis:
                # Get measures from y_axis
                measures = []
                if hasattr(exhibit.y_axis, 'measures') and exhibit.y_axis.measures:
                    measures = exhibit.y_axis.measures
                elif hasattr(exhibit.y_axis, 'measure'):
                    measures = [exhibit.y_axis.measure]

                # Build aggregations
                agg_exprs = []
                for measure_id in measures:
                    if measure_id == 'avg_close_price':
                        agg_exprs.append(F.avg('close').alias('avg_close_price'))
                    elif measure_id == 'total_volume':
                        agg_exprs.append(F.sum('volume').alias('total_volume'))
                    elif measure_id == 'max_high':
                        agg_exprs.append(F.max('high').alias('max_high'))
                    elif measure_id == 'min_low':
                        agg_exprs.append(F.min('low').alias('min_low'))

                if agg_exprs:
                    df = df.groupBy(x_col).agg(*agg_exprs)

        # For data tables, return raw data (already filtered)
        return df

    @property
    def notebook(self) -> Optional[NotebookConfig]:
        """Get loaded notebook config."""
        return self.notebook_config
