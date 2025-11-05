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
        import pandas as pd
        from datetime import datetime

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

        # Collect forecasts and metrics for batch saving
        all_forecasts = []
        all_metrics = []

        # Run each model
        for config_name in model_configs:
            try:
                config = all_configs[config_name]

                # Determine model type from config name
                if 'arima' in config_name.lower():
                    model, metadata = self.train_arima(entity_id, config_name)
                elif 'prophet' in config_name.lower():
                    model, metadata = self.train_prophet(entity_id, config_name)
                elif 'random_forest' in config_name.lower() or 'rf' in config_name.lower():
                    model, metadata = self.train_random_forest(entity_id, config_name)
                else:
                    raise ValueError(f"Unknown model type for config: {config_name}")

                results['models_trained'] += 1

                # Generate forecast from trained model
                forecast_df = self.generate_forecast(
                    model,
                    metadata,
                    config.get('forecast_horizon', 7)
                )
                all_forecasts.append(forecast_df)
                results['forecasts_generated'] += len(forecast_df)

                # Calculate metrics
                metrics_dict = self.calculate_metrics(model, metadata)
                metrics_df = pd.DataFrame([{
                    self.get_entity_column(): entity_id,
                    'model_name': metadata.get('model_name', config_name),
                    'metric_date': datetime.now().date(),
                    'training_start': (pd.Timestamp(metadata['training_end']) - pd.Timedelta(days=metadata['lookback_days'])).date(),
                    'training_end': metadata['training_end'],
                    **metrics_dict
                }])
                all_metrics.append(metrics_df)

            except Exception as e:
                error_msg = f"{config_name}: {str(e)}"
                results['errors'].append(error_msg)

        # Save all forecasts and metrics
        if all_forecasts:
            combined_forecasts = pd.concat(all_forecasts, ignore_index=True)
            self.save_forecasts(combined_forecasts)

        if all_metrics:
            combined_metrics = pd.concat(all_metrics, ignore_index=True)
            self.save_metrics(combined_metrics)

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

    # ============================================================
    # FORECAST GENERATION AND PERSISTENCE
    # ============================================================

    def generate_forecast(
        self,
        model: object,
        metadata: Dict,
        forecast_horizon: int
    ):
        """
        Generate forecast from a trained model.

        Args:
            model: Trained model (ARIMA, Prophet, or RandomForest)
            metadata: Model metadata
            forecast_horizon: Number of days to forecast

        Returns:
            pandas DataFrame with forecast results
        """
        import pandas as pd
        from datetime import datetime

        model_type = metadata['model_type']
        entity_id = metadata['ticker']  # Using 'ticker' from metadata
        target = metadata['target']
        forecast_date = datetime.now().date()

        if model_type == 'ARIMA':
            # ARIMA forecast
            dates = pd.date_range(
                start=pd.Timestamp(metadata['training_end']) + pd.Timedelta(days=1),
                periods=forecast_horizon,
                freq='D'
            )

            # Prepare exogenous variables if day_of_week_adj was used
            exog_forecast = None
            if metadata.get('day_of_week_adj', False):
                exog_forecast = pd.DataFrame({
                    'day_of_week': dates.dayofweek
                }, index=dates)

            # Generate forecast
            forecast_obj = model.get_forecast(steps=forecast_horizon, exog=exog_forecast)
            predictions = forecast_obj.predicted_mean
            conf_int = forecast_obj.conf_int()

            results = pd.DataFrame({
                self.get_entity_column(): entity_id,
                'forecast_date': forecast_date,
                'prediction_date': dates.date,
                'horizon': range(1, forecast_horizon + 1),
                'model_name': metadata.get('model_name', f"ARIMA_{metadata['lookback_days']}d"),
                'predicted_value': predictions.values,
                'lower_bound': conf_int.iloc[:, 0].values,
                'upper_bound': conf_int.iloc[:, 1].values,
                'target': target,
                'confidence': 0.95
            })

        elif model_type == 'Prophet':
            # Prophet forecast
            future = model.make_future_dataframe(periods=forecast_horizon, freq='D')
            forecast = model.predict(future)

            # Get only future predictions
            forecast = forecast.tail(forecast_horizon)

            results = pd.DataFrame({
                self.get_entity_column(): entity_id,
                'forecast_date': forecast_date,
                'prediction_date': forecast['ds'].dt.date,
                'horizon': range(1, forecast_horizon + 1),
                'model_name': metadata.get('model_name', f"Prophet_{metadata['lookback_days']}d"),
                'predicted_value': forecast['yhat'].values,
                'lower_bound': forecast['yhat_lower'].values,
                'upper_bound': forecast['yhat_upper'].values,
                'target': target,
                'confidence': 0.95
            })

        elif model_type == 'RandomForest':
            # RandomForest - simplified one-step forecast
            # Production version would use iterative forecasting
            results = pd.DataFrame({
                self.get_entity_column(): entity_id,
                'forecast_date': forecast_date,
                'prediction_date': [forecast_date + pd.Timedelta(days=i) for i in range(1, forecast_horizon + 1)],
                'horizon': range(1, forecast_horizon + 1),
                'model_name': metadata.get('model_name', f"RF_{metadata['lookback_days']}d"),
                'predicted_value': [0.0] * forecast_horizon,  # Placeholder
                'lower_bound': [0.0] * forecast_horizon,
                'upper_bound': [0.0] * forecast_horizon,
                'target': target,
                'confidence': 0.95
            })

        return results

    def calculate_metrics(self, model: object, metadata: Dict) -> Dict:
        """
        Calculate forecast accuracy metrics.

        Args:
            model: Trained model
            metadata: Model metadata

        Returns:
            Dictionary with metrics (MAE, RMSE, R2, etc.)
        """
        from datetime import datetime

        # For now, return placeholder metrics
        # Production would calculate actual metrics on holdout data
        return {
            'mae': 0.0,
            'rmse': 0.0,
            'mape': 0.0,
            'r2_score': 0.0,
            'num_predictions': metadata.get('training_samples', 0),
            'avg_error_pct': 0.0,
            'test_start': metadata.get('training_end', datetime.now().date()),
            'test_end': datetime.now().date()
        }

    def save_forecasts(self, forecasts_df):
        """
        Save forecast results to Silver layer.

        Saves to appropriate table based on target (price vs volume).

        Args:
            forecasts_df: pandas DataFrame with forecast results
        """
        from pathlib import Path
        import pandas as pd
        import os

        # Get forecast Silver root
        forecast_root = self.storage_cfg['roots'].get(
            'forecast_silver',
            'storage/silver/forecast'
        )

        # Convert to absolute path if relative
        forecast_root = Path(forecast_root).resolve()

        print(f"    Saving forecasts to: {forecast_root}")

        # Separate by target
        for target in forecasts_df['target'].unique():
            target_df = forecasts_df[forecasts_df['target'] == target].copy()

            # Determine table name and column name based on target
            if target == 'close':
                table_name = 'forecast_price'
                # Rename predicted_value to predicted_close
                target_df = target_df.rename(columns={'predicted_value': 'predicted_close'})
            elif target == 'volume':
                table_name = 'forecast_volume'
                # Rename predicted_value to predicted_volume
                target_df = target_df.rename(columns={'predicted_value': 'predicted_volume'})
            else:
                print(f"    Warning: Unknown target '{target}', skipping")
                continue

            # Drop the target column as it's implicit in the table name
            target_df = target_df.drop(columns=['target'])

            # Determine output path according to schema
            output_path = Path(forecast_root) / 'facts' / table_name

            # Partition by forecast_date
            forecast_date = target_df['forecast_date'].iloc[0]
            partition_path = output_path / f"forecast_date={forecast_date}"
            partition_path.mkdir(parents=True, exist_ok=True)

            # Save to parquet
            file_path = partition_path / "data.parquet"
            target_df.to_parquet(file_path, index=False, compression='snappy')

            print(f"    → Saved {len(target_df)} {table_name} records")
            print(f"      File: {file_path}")

    def save_metrics(self, metrics_df):
        """
        Save forecast metrics to Silver layer.

        Args:
            metrics_df: pandas DataFrame with metrics
        """
        from pathlib import Path

        # Get forecast Silver root
        forecast_root = self.storage_cfg['roots'].get(
            'forecast_silver',
            'storage/silver/forecast'
        )

        # Determine output path according to schema
        output_path = Path(forecast_root) / 'facts' / 'forecast_metrics'

        # Partition by metric_date
        metric_date = metrics_df['metric_date'].iloc[0]
        partition_path = output_path / f"metric_date={metric_date}"
        partition_path.mkdir(parents=True, exist_ok=True)

        # Save to parquet
        file_path = partition_path / "data.parquet"
        metrics_df.to_parquet(file_path, index=False, compression='snappy')

        print(f"    Saved {len(metrics_df)} metric records to {file_path}")
