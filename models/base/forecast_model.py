"""
TimeSeriesForecastModel - Generic base class for time series forecasting.

This base class provides forecasting capabilities for ANY time series data source.
Specific implementations (CompanyForecastModel, MacroForecastModel, etc.) specify:
- Which source model to read data from
- Which columns to forecast
- Where to store forecast results
"""

from typing import Dict, Optional, Tuple, List
from abc import abstractmethod
from pyspark.sql import DataFrame
from models.base.model import BaseModel
from models.implemented.forecast import training_methods


class TimeSeriesForecastModel(BaseModel):
    """
    Generic time series forecasting model.

    This abstract base class provides:
    - Training orchestration (ARIMA, Prophet, RandomForest)
    - Generic forecast method dispatch
    - Config-driven model parameters
    - Cross-model data access pattern

    Subclasses must implement:
    - get_source_data() - Define where training data comes from
    - get_forecast_columns() - Define which columns to forecast
    """

    def __init__(self, connection, storage_cfg: Dict, model_cfg: Dict, params: Dict = None):
        """
        Initialize Time Series Forecast Model.

        Args:
            connection: Database connection (Spark or DuckDB)
            storage_cfg: Storage configuration
            model_cfg: Model configuration from YAML
            params: Runtime parameters
        """
        super().__init__(connection, storage_cfg, model_cfg, params)
        self._session: Optional['UniversalSession'] = None

    def set_session(self, session):
        """
        Inject session for cross-model access.

        Forecast models typically need access to other models for training data.

        Args:
            session: UniversalSession instance
        """
        self._session = session

    # ============================================================
    # ABSTRACT METHODS (must be implemented by subclasses)
    # ============================================================

    @abstractmethod
    def get_source_model_name(self) -> str:
        """
        Get the name of the source model to load data from.

        Returns:
            Model name (e.g., 'company', 'macro', 'city_finance')

        Example:
            return 'company'
        """
        pass

    @abstractmethod
    def get_source_table_name(self) -> str:
        """
        Get the name of the source table to load from.

        Returns:
            Table name (e.g., 'fact_prices', 'fact_indicators')

        Example:
            return 'fact_prices'
        """
        pass

    @abstractmethod
    def get_entity_column(self) -> str:
        """
        Get the column name that identifies entities (e.g., ticker, indicator_code).

        Returns:
            Column name for entity identifier

        Example:
            return 'ticker'  # for company forecasts
            return 'indicator_code'  # for macro forecasts
        """
        pass

    @abstractmethod
    def get_date_column(self) -> str:
        """
        Get the column name for the date/timestamp.

        Returns:
            Column name for date

        Example:
            return 'trade_date'  # for company forecasts
            return 'date'  # for macro forecasts
        """
        pass

    # ============================================================
    # DATA ACCESS (uses abstract methods)
    # ============================================================

    def get_training_data(
        self,
        entity_id: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        lookback_days: Optional[int] = None
    ) -> DataFrame:
        """
        Get training data for forecasting.

        This is a generic implementation that works for any source model.

        Args:
            entity_id: Entity identifier (ticker, indicator_code, etc.)
            date_from: Start date (optional)
            date_to: End date (optional)
            lookback_days: Number of days to look back from today (optional)

        Returns:
            DataFrame with time series data for training
        """
        if not self._session:
            raise RuntimeError(
                f"{self.__class__.__name__} requires session for cross-model access. "
                "Call set_session() first."
            )

        # Calculate date_from from lookback_days if provided
        if lookback_days:
            from datetime import datetime, timedelta
            date_from = (datetime.now() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')

        # Get source model
        source_model_name = self.get_source_model_name()
        source_model = self._session.load_model(source_model_name)

        # Get source table
        table_name = self.get_source_table_name()
        df = source_model.get_table(table_name)

        # Filter by entity
        entity_col = self.get_entity_column()
        df = df.filter(df[entity_col] == entity_id)

        # Filter by date
        date_col = self.get_date_column()
        if date_from:
            df = df.filter(df[date_col] >= date_from)
        if date_to:
            df = df.filter(df[date_col] <= date_to)

        return df.orderBy(date_col)

    # ============================================================
    # ORCHESTRATION METHODS
    # ============================================================

    def run_forecast_for_entity(
        self,
        entity_id: str,
        model_configs: Optional[List[str]] = None
    ) -> dict:
        """
        Run all configured forecast models for an entity.

        This is the main orchestration method that runs multiple forecast models
        for a single entity (ticker, indicator, etc.).

        Args:
            entity_id: Entity identifier to forecast
            model_configs: List of model config names to run
                          If None, runs all configured models

        Returns:
            Dictionary with results:
            {
                'entity_id': str,
                'models_trained': int,
                'forecasts_generated': int,
                'errors': List[str]
            }
        """
        results = {
            'entity_id': entity_id,
            'models_trained': 0,
            'forecasts_generated': 0,
            'errors': []
        }

        # Get model configs to run
        all_configs = self.get_model_configs()
        if model_configs is None:
            model_configs = list(all_configs.keys())

        # Run each model
        for config_name in model_configs:
            try:
                # Determine model type from config name
                if 'arima' in config_name.lower():
                    self.train_arima(entity_id, config_name)
                elif 'prophet' in config_name.lower():
                    self.train_prophet(entity_id, config_name)
                elif 'random_forest' in config_name.lower() or 'rf' in config_name.lower():
                    self.train_random_forest(entity_id, config_name)
                else:
                    raise ValueError(f"Unknown model type for config: {config_name}")

                results['models_trained'] += 1
                # Assuming each model generates forecasts for the horizon
                config = all_configs.get(config_name, {})
                horizon = config.get('horizon', 7)
                results['forecasts_generated'] += horizon

            except Exception as e:
                error_msg = f"{config_name}: {str(e)}"
                results['errors'].append(error_msg)

        return results

    # ============================================================
    # CONVENIENCE METHODS
    # ============================================================

    def get_model_configs(self) -> Dict:
        """
        Get all model configurations from YAML.

        Returns:
            Dictionary of model configs (ARIMA, Prophet, etc.)
        """
        return self.model_cfg.get('models', {})

    def get_model_config(self, model_name: str) -> Dict:
        """
        Get configuration for a specific model.

        Args:
            model_name: Model name (e.g., 'arima_7d')

        Returns:
            Model configuration dictionary
        """
        models = self.get_model_configs()
        if model_name not in models:
            raise ValueError(
                f"Model config '{model_name}' not found. "
                f"Available: {list(models.keys())}"
            )
        return models[model_name]

    # ============================================================
    # ML TRAINING METHODS
    # ============================================================

    def train_arima(self, entity_id: str, config_name: str = 'arima_7d') -> Tuple[object, Dict]:
        """
        Train ARIMA model for an entity.

        Args:
            entity_id: Entity identifier
            config_name: ARIMA config name from YAML

        Returns:
            Tuple of (fitted_model, metadata)
        """
        config = self.get_model_config(config_name)

        # Get training data as Spark DataFrame
        training_data = self.get_training_data(
            entity_id,
            lookback_days=config.get('lookback_days', 60)
        )

        # Convert to pandas for ML training
        data_pdf = training_data.toPandas()

        # Rename date column to standard name for training
        date_col = self.get_date_column()
        if date_col != 'trade_date':
            data_pdf = data_pdf.rename(columns={date_col: 'trade_date'})

        # Extract target from config (default to 'close')
        target = config.get('target', 'close')
        if isinstance(target, list):
            target = target[0]  # Use first target if multiple specified

        # Train using helper function
        return training_methods.train_arima_model(
            data_pdf=data_pdf,
            ticker=entity_id,
            target=target,
            lookback_days=config.get('lookback_days', 60),
            forecast_horizon=config.get('forecast_horizon', 7),
            day_of_week_adj=config.get('day_of_week_adj', True),
            seasonal=config.get('seasonal', False),
            auto=config.get('auto_arima', True)
        )

    def train_prophet(self, entity_id: str, config_name: str = 'prophet_7d') -> Tuple[object, Dict]:
        """
        Train Prophet model for an entity.

        Args:
            entity_id: Entity identifier
            config_name: Prophet config name from YAML

        Returns:
            Tuple of (fitted_model, metadata)
        """
        config = self.get_model_config(config_name)

        # Get training data as Spark DataFrame
        training_data = self.get_training_data(
            entity_id,
            lookback_days=config.get('lookback_days', 60)
        )

        # Convert to pandas for ML training
        data_pdf = training_data.toPandas()

        # Rename date column to standard name for training
        date_col = self.get_date_column()
        if date_col != 'trade_date':
            data_pdf = data_pdf.rename(columns={date_col: 'trade_date'})

        # Extract target from config (default to 'close')
        target = config.get('target', 'close')
        if isinstance(target, list):
            target = target[0]  # Use first target if multiple specified

        # Train using helper function
        return training_methods.train_prophet_model(
            data_pdf=data_pdf,
            ticker=entity_id,
            target=target,
            lookback_days=config.get('lookback_days', 60),
            forecast_horizon=config.get('forecast_horizon', 7),
            day_of_week_adj=config.get('day_of_week_adj', True),
            seasonality_mode=config.get('seasonality_mode', 'multiplicative')
        )

    def train_random_forest(self, entity_id: str, config_name: str = 'random_forest_14d') -> Tuple[object, Dict]:
        """
        Train Random Forest model for an entity.

        Args:
            entity_id: Entity identifier
            config_name: RF config name from YAML

        Returns:
            Tuple of (fitted_model, metadata)
        """
        config = self.get_model_config(config_name)

        # Get training data as Spark DataFrame
        training_data = self.get_training_data(
            entity_id,
            lookback_days=config.get('lookback_days', 60)
        )

        # Convert to pandas for ML training
        data_pdf = training_data.toPandas()

        # Rename date column to standard name for training
        date_col = self.get_date_column()
        if date_col != 'trade_date':
            data_pdf = data_pdf.rename(columns={date_col: 'trade_date'})

        # Extract target from config (default to 'close')
        target = config.get('target', 'close')
        if isinstance(target, list):
            target = target[0]  # Use first target if multiple specified

        # Train using helper function
        return training_methods.train_random_forest_model(
            data_pdf=data_pdf,
            ticker=entity_id,
            target=target,
            lookback_days=config.get('lookback_days', 60),
            forecast_horizon=config.get('forecast_horizon', 7),
            n_estimators=config.get('n_estimators', 100),
            max_depth=config.get('max_depth', 10)
        )
