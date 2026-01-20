"""
TimeSeriesForecastModel - Generic base class for time series forecasting.

This base class provides forecasting capabilities for ANY time series data source.
Specific implementations (CompanyForecastModel, MacroForecastModel, etc.) specify:
- Which source model to read data from
- Which columns to forecast
- Where to store forecast results
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple, List, TYPE_CHECKING
from abc import abstractmethod
from pathlib import Path
import pandas as pd
import numpy as np

# Optional PySpark import - allows DuckDB-only usage
if TYPE_CHECKING:
    from pyspark.sql import DataFrame as SparkDataFrame

try:
    from pyspark.sql import DataFrame
    HAS_SPARK = True
except ImportError:
    HAS_SPARK = False
    DataFrame = None  # type: ignore

from models.base.model import BaseModel
from models.domains.securities.forecast import training_methods


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

    def __init__(
        self,
        connection,
        storage_cfg: Dict,
        model_cfg: Dict,
        params: Dict = None,
        repo_root: Optional[Path] = None,
        quiet: bool = False
    ):
        """
        Initialize Time Series Forecast Model.

        Args:
            connection: Database connection (Spark or DuckDB)
            storage_cfg: Storage configuration
            model_cfg: Model configuration from YAML
            params: Runtime parameters
            repo_root: Repository root path
            quiet: Suppress verbose output (for clean progress display)
        """
        super().__init__(connection, storage_cfg, model_cfg, params, repo_root=repo_root)
        # Note: self.session is already initialized in BaseModel.__init__
        # No need to re-initialize it here
        self._quiet = quiet

    def _print(self, msg: str):
        """Print message if not in quiet mode."""
        if not self._quiet:
            print(msg)

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
        Uses get_denormalized() to join in dimension columns (like ticker)
        that may have been removed from normalized fact tables.

        Args:
            entity_id: Entity identifier (ticker, indicator_code, etc.)
            date_from: Start date (optional)
            date_to: End date (optional)
            lookback_days: Number of days to look back from today (optional)

        Returns:
            DataFrame with time series data for training
        """
        if not self.session:
            raise RuntimeError(
                f"{self.__class__.__name__} requires session for cross-model access. "
                "Call set_session() first."
            )

        # Calculate date_from from lookback_days if provided
        if lookback_days:
            from datetime import datetime, timedelta
            date_from = (datetime.now() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')

        # Get source model and table info
        source_model_name = self.get_source_model_name()
        table_name = self.get_source_table_name()
        entity_col = self.get_entity_column()
        date_col = self.get_date_column()

        # Load the source model
        source_model = self.session.load_model(source_model_name)

        # Check if entity column exists in the fact table
        # If not, use get_denormalized() to join in dimension columns
        try:
            fact_df = source_model.get_table(table_name)
            fact_columns = set(fact_df.columns) if hasattr(fact_df, 'columns') else set()

            if entity_col not in fact_columns:
                # Entity column not in fact table - use denormalized view
                # This joins in dimension tables which have the natural keys (ticker, etc.)
                df = source_model.get_denormalized(table_name)
            else:
                df = fact_df
        except Exception as e:
            # Fall back to session.get_table() if model access fails
            df = self.session.get_table(source_model_name, table_name)

        # Filter by entity
        df = df.filter(df[entity_col] == entity_id)

        # Filter by date
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
        model_configs: Optional[List[str]] = None,
        validate_data: bool = True
    ) -> dict:
        """
        Run all configured forecast models for an entity.

        This is the main orchestration method that runs multiple forecast models
        for a single entity (ticker, indicator, etc.).

        Args:
            entity_id: Entity identifier to forecast
            model_configs: List of model config names to run
                          If None, runs all configured models
            validate_data: Whether to validate training data before training

        Returns:
            Dictionary with results:
            {
                'entity_id': str,
                'models_trained': int,
                'forecasts_generated': int,
                'errors': List[str],
                'validation': Optional[dict]
            }
        """
        import pandas as pd
        from datetime import datetime

        results = {
            'entity_id': entity_id,
            'models_trained': 0,
            'forecasts_generated': 0,
            'errors': [],
            'validation': None
        }

        # Get model configs to run
        all_configs = self.get_model_configs()
        if model_configs is None:
            model_configs = list(all_configs.keys())

        # Get max lookback for validation
        max_lookback = max(
            all_configs.get(m, {}).get('lookback_days', 60)
            for m in model_configs
        )

        # Validate training data if enabled
        if validate_data:
            try:
                validation_result = self._validate_training_data(
                    entity_id, max_lookback, model_configs
                )
                results['validation'] = validation_result

                if not validation_result.get('is_valid', False):
                    # Add validation errors to results
                    for error in validation_result.get('errors', []):
                        results['errors'].append(f"validation: {error}")
                    return results

            except Exception as e:
                results['errors'].append(f"validation failed: {str(e)[:50]}")
                # Continue anyway - validation is advisory

        # Collect forecasts, metrics, and registry entries for batch saving
        all_forecasts = []
        all_metrics = []
        all_registry = []

        # Run each model
        for config_name in model_configs:
            try:
                config = all_configs[config_name]

                # Determine model type from config name
                if 'arima' in config_name.lower():
                    model, metadata = self.train_arima(entity_id, config_name)
                    model_type = 'ARIMA'
                elif 'prophet' in config_name.lower():
                    model, metadata = self.train_prophet(entity_id, config_name)
                    model_type = 'Prophet'
                elif 'random_forest' in config_name.lower() or 'rf' in config_name.lower():
                    model, metadata = self.train_random_forest(entity_id, config_name)
                    model_type = 'RandomForest'
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

                # Build model registry entry
                import json
                registry_df = pd.DataFrame([{
                    'model_id': f"{entity_id}_{config_name}_{datetime.now().strftime('%Y%m%d')}",
                    'model_name': metadata.get('model_name', config_name),
                    'model_type': model_type,
                    self.get_entity_column(): entity_id,
                    'target_variable': config.get('target', ['close'])[0] if isinstance(config.get('target'), list) else config.get('target', 'close'),
                    'lookback_days': config.get('lookback_days', 7),
                    'forecast_horizon': config.get('forecast_horizon', 7),
                    'day_of_week_adj': config.get('day_of_week_adj', False),
                    'parameters': json.dumps({k: v for k, v in config.items() if k not in ['type', 'target']}),
                    'trained_date': datetime.now().date(),
                    'training_samples': metadata.get('training_samples', 0),
                    'status': 'active'
                }])
                all_registry.append(registry_df)

            except Exception as e:
                import traceback
                error_msg = f"{config_name}: {str(e)}"
                results['errors'].append(error_msg)
                # Log full traceback for debugging
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Training failed for {entity_id}/{config_name}: {e}")
                logger.debug(f"Full traceback: {traceback.format_exc()}")

        # Save all forecasts, metrics, and registry entries
        if all_forecasts:
            combined_forecasts = pd.concat(all_forecasts, ignore_index=True)
            self.save_forecasts(combined_forecasts)

        if all_metrics:
            combined_metrics = pd.concat(all_metrics, ignore_index=True)
            self.save_metrics(combined_metrics)

        if all_registry:
            combined_registry = pd.concat(all_registry, ignore_index=True)
            self.save_model_registry(combined_registry)

        return results

    def _validate_training_data(
        self,
        entity_id: str,
        lookback_days: int,
        model_configs: List[str]
    ) -> dict:
        """
        Validate training data before ML training.

        Args:
            entity_id: Entity to validate (ticker, etc.)
            lookback_days: Lookback window for training
            model_configs: List of model configs to validate for

        Returns:
            Dictionary with validation results:
            {
                'is_valid': bool,
                'errors': List[str],
                'warnings': List[str],
                'metrics': Dict
            }
        """
        result = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'metrics': {}
        }

        try:
            # Get training data
            training_df = self.get_training_data(
                entity_id=entity_id,
                lookback_days=lookback_days
            )

            # Convert to pandas for validation
            if hasattr(training_df, 'toPandas'):
                data_pdf = training_df.toPandas()
            else:
                data_pdf = training_df

            # Check row count
            row_count = len(data_pdf)
            result['metrics']['row_count'] = row_count

            if row_count == 0:
                result['is_valid'] = False
                result['errors'].append(f"No data for {entity_id}")
                return result

            # Check minimum rows for models
            min_rows = {'arima': 30, 'prophet': 60, 'random_forest': 90}
            for config_name in model_configs:
                model_type = config_name.split('_')[0].lower()
                min_required = min_rows.get(model_type, 30)

                if row_count < min_required:
                    result['warnings'].append(
                        f"{config_name} needs {min_required} rows, only {row_count} available"
                    )

            # Check required columns
            date_col = self.get_date_column()
            required_cols = ['close', date_col]
            missing_cols = [c for c in required_cols if c not in data_pdf.columns]
            if missing_cols:
                result['is_valid'] = False
                result['errors'].append(f"Missing columns: {missing_cols}")
                return result

            # Check for nulls in close price
            null_count = data_pdf['close'].isna().sum()
            if null_count > 0:
                null_pct = null_count / row_count
                if null_pct > 0.1:  # >10% nulls
                    result['is_valid'] = False
                    result['errors'].append(f"Too many null close prices: {null_pct:.1%}")
                else:
                    result['warnings'].append(f"{null_count} null close prices")

            result['metrics']['null_close_pct'] = null_count / row_count if row_count > 0 else 0

            # Check date range
            if date_col in data_pdf.columns:
                min_date = data_pdf[date_col].min()
                max_date = data_pdf[date_col].max()
                result['metrics']['date_range'] = f"{min_date} to {max_date}"

            # Check close price stats
            result['metrics']['close_mean'] = float(data_pdf['close'].mean())
            result['metrics']['close_std'] = float(data_pdf['close'].std())

        except Exception as e:
            result['is_valid'] = False
            result['errors'].append(f"Validation error: {str(e)}")

        return result

    # ============================================================
    # CONVENIENCE METHODS
    # ============================================================

    def get_model_configs(self) -> Dict:
        """
        Get all model configurations from YAML.

        Returns:
            Dictionary of model configs (ARIMA, Prophet, etc.)
        """
        # Support both 'ml_models' (v2.0 config) and 'models' (legacy) keys
        return self.model_cfg.get('ml_models', self.model_cfg.get('models', {}))

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

        # Get training data
        training_data = self.get_training_data(
            entity_id,
            lookback_days=config.get('lookback_days', 60)
        )

        # Convert to pandas for ML training
        if hasattr(training_data, 'toPandas'):
            data_pdf = training_data.toPandas()
        else:
            # Already a pandas DataFrame
            data_pdf = training_data.copy() if hasattr(training_data, 'copy') else training_data

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

        # Get training data
        training_data = self.get_training_data(
            entity_id,
            lookback_days=config.get('lookback_days', 60)
        )

        # Convert to pandas for ML training
        if hasattr(training_data, 'toPandas'):
            data_pdf = training_data.toPandas()
        else:
            data_pdf = training_data.copy() if hasattr(training_data, 'copy') else training_data

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

        # Get training data
        training_data = self.get_training_data(
            entity_id,
            lookback_days=config.get('lookback_days', 60)
        )

        # Convert to pandas for ML training
        if hasattr(training_data, 'toPandas'):
            data_pdf = training_data.toPandas()
        else:
            data_pdf = training_data.copy() if hasattr(training_data, 'copy') else training_data

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
            # Handle both pmdarima (auto_arima) and statsmodels ARIMA
            try:
                # Try statsmodels API first (get_forecast)
                if hasattr(model, 'get_forecast'):
                    forecast_obj = model.get_forecast(steps=forecast_horizon, exog=exog_forecast)
                    predictions = forecast_obj.predicted_mean
                    conf_int = forecast_obj.conf_int()
                    lower = conf_int.iloc[:, 0].values
                    upper = conf_int.iloc[:, 1].values
                elif hasattr(model, 'predict'):
                    # pmdarima auto_arima uses predict()
                    predictions, conf_int = model.predict(
                        n_periods=forecast_horizon,
                        exogenous=exog_forecast.values if exog_forecast is not None else None,
                        return_conf_int=True
                    )
                    lower = conf_int[:, 0]
                    upper = conf_int[:, 1]
                else:
                    raise AttributeError(f"Model has no forecast method: {type(model)}")
            except Exception as e:
                self._print(f"  Warning: ARIMA forecast failed: {e}")
                return None

            results = pd.DataFrame({
                self.get_entity_column(): entity_id,
                'forecast_date': forecast_date,
                'prediction_date': dates.date,
                'horizon': range(1, forecast_horizon + 1),
                'model_name': metadata.get('model_name', f"ARIMA_{metadata['lookback_days']}d"),
                'predicted_value': predictions if isinstance(predictions, np.ndarray) else predictions.values,
                'lower_bound': lower,
                'upper_bound': upper,
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
            # RandomForest - iterative multi-step forecasting using lag features
            # Note: numpy already imported at module level (line 16)

            # Get feature columns and training data from metadata
            feature_cols = metadata.get('feature_cols', [])
            training_data = metadata.get('training_data')

            if training_data is None or training_data.empty:
                # Fallback if no training data available
                results = pd.DataFrame({
                    self.get_entity_column(): entity_id,
                    'forecast_date': forecast_date,
                    'prediction_date': [forecast_date + pd.Timedelta(days=i) for i in range(1, forecast_horizon + 1)],
                    'horizon': range(1, forecast_horizon + 1),
                    'model_name': metadata.get('model_name', f"RF_{metadata['lookback_days']}d"),
                    'predicted_value': [np.nan] * forecast_horizon,
                    'lower_bound': [np.nan] * forecast_horizon,
                    'upper_bound': [np.nan] * forecast_horizon,
                    'target': target,
                    'confidence': 0.95
                })
            else:
                # Build forecast iteratively using lag features
                last_known_values = training_data[target].tail(30).tolist()  # Keep last 30 values for lags
                predictions = []

                # Get the last feature row as a template
                last_features = training_data[feature_cols].iloc[-1].to_dict()

                for step in range(forecast_horizon):
                    # Update lag features with predicted/known values
                    for col in feature_cols:
                        if col.startswith('lag_'):
                            lag_num = int(col.split('_')[1])
                            if lag_num <= len(last_known_values):
                                last_features[col] = last_known_values[-lag_num]
                        elif col == 'day_of_week':
                            future_date = pd.Timestamp(metadata['training_end']) + pd.Timedelta(days=step + 1)
                            last_features[col] = future_date.dayofweek
                        elif col == 'is_monday':
                            future_date = pd.Timestamp(metadata['training_end']) + pd.Timedelta(days=step + 1)
                            last_features[col] = 1 if future_date.dayofweek == 0 else 0
                        elif col == 'is_friday':
                            future_date = pd.Timestamp(metadata['training_end']) + pd.Timedelta(days=step + 1)
                            last_features[col] = 1 if future_date.dayofweek == 4 else 0
                        elif col.startswith('rolling_mean_'):
                            window = int(col.split('_')[-1])
                            if len(last_known_values) >= window:
                                last_features[col] = np.mean(last_known_values[-window:])
                        elif col.startswith('rolling_std_'):
                            window = int(col.split('_')[-1])
                            if len(last_known_values) >= window:
                                last_features[col] = np.std(last_known_values[-window:])

                    # Make prediction
                    feature_vector = pd.DataFrame([last_features])[feature_cols]
                    pred = model.predict(feature_vector)[0]
                    predictions.append(pred)

                    # Update history with new prediction
                    last_known_values.append(pred)

                # Calculate confidence intervals using OOB score or residual std
                # Use training residuals to estimate prediction uncertainty
                train_preds = model.predict(training_data[feature_cols])
                residuals = training_data[target].values - train_preds
                std_error = np.std(residuals)

                # Widen confidence interval for longer horizons (uncertainty grows)
                horizon_multipliers = [1 + 0.1 * h for h in range(forecast_horizon)]

                results = pd.DataFrame({
                    self.get_entity_column(): entity_id,
                    'forecast_date': forecast_date,
                    'prediction_date': [pd.Timestamp(metadata['training_end']) + pd.Timedelta(days=i) for i in range(1, forecast_horizon + 1)],
                    'horizon': range(1, forecast_horizon + 1),
                    'model_name': metadata.get('model_name', f"RF_{metadata['lookback_days']}d"),
                    'predicted_value': predictions,
                    'lower_bound': [p - 1.96 * std_error * m for p, m in zip(predictions, horizon_multipliers)],
                    'upper_bound': [p + 1.96 * std_error * m for p, m in zip(predictions, horizon_multipliers)],
                    'target': target,
                    'confidence': 0.95
                })

        return results

    def calculate_metrics(self, model: object, metadata: Dict, holdout_data: pd.DataFrame = None) -> Dict:
        """
        Calculate forecast accuracy metrics.

        Calculates metrics on holdout/validation data or using cross-validation
        on training data if no holdout is available.

        Args:
            model: Trained model
            metadata: Model metadata
            holdout_data: Optional holdout data for validation

        Returns:
            Dictionary with metrics:
            - mae: Mean Absolute Error
            - rmse: Root Mean Square Error
            - mape: Mean Absolute Percentage Error
            - r2_score: Coefficient of Determination
            - directional_accuracy: % of correct direction predictions
            - num_predictions: Number of predictions made
            - avg_error_pct: Average error as percentage
        """
        import numpy as np
        from datetime import datetime
        from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

        model_type = metadata.get('model_type', 'Unknown')
        target = metadata.get('target', 'close')
        training_data = metadata.get('training_data')

        # Default empty metrics
        empty_metrics = {
            'mae': np.nan,
            'rmse': np.nan,
            'mape': np.nan,
            'r2_score': np.nan,
            'directional_accuracy': np.nan,
            'num_predictions': 0,
            'avg_error_pct': np.nan,
            'test_start': metadata.get('training_end', datetime.now().date()),
            'test_end': datetime.now().date()
        }

        # Use holdout data if provided, otherwise use cross-validation on training data
        if holdout_data is not None and not holdout_data.empty:
            validation_data = holdout_data
        elif training_data is not None and not training_data.empty:
            # Use last 20% of training data as validation (walk-forward)
            split_idx = int(len(training_data) * 0.8)
            if split_idx < 10:  # Need at least 10 points for validation
                return empty_metrics
            validation_data = training_data.iloc[split_idx:]
        else:
            return empty_metrics

        try:
            # Get actual values
            y_true = validation_data[target].values

            # Generate predictions based on model type
            if model_type == 'ARIMA':
                # ARIMA: Use in-sample fitted values for the validation period
                try:
                    # Get fitted values
                    fitted = model.fittedvalues
                    if len(fitted) >= len(y_true):
                        y_pred = fitted[-len(y_true):].values
                    else:
                        return empty_metrics
                except Exception:
                    return empty_metrics

            elif model_type == 'Prophet':
                # Prophet: Generate predictions for validation dates
                try:
                    if 'ds' in validation_data.columns:
                        future = validation_data[['ds']].copy()
                    else:
                        # Create ds column from index or trade_date
                        future = pd.DataFrame({'ds': pd.to_datetime(validation_data.index)})
                    forecast = model.predict(future)
                    y_pred = forecast['yhat'].values
                except Exception:
                    return empty_metrics

            elif model_type == 'RandomForest':
                # RandomForest: Predict using feature columns
                try:
                    feature_cols = metadata.get('feature_cols', [])
                    if not feature_cols or not all(col in validation_data.columns for col in feature_cols):
                        return empty_metrics
                    X_val = validation_data[feature_cols]
                    y_pred = model.predict(X_val)
                except Exception:
                    return empty_metrics

            else:
                return empty_metrics

            # Ensure arrays are the same length
            min_len = min(len(y_true), len(y_pred))
            y_true = y_true[:min_len]
            y_pred = y_pred[:min_len]

            if min_len == 0:
                return empty_metrics

            # Calculate metrics
            mae = mean_absolute_error(y_true, y_pred)
            rmse = np.sqrt(mean_squared_error(y_true, y_pred))
            r2 = r2_score(y_true, y_pred)

            # MAPE (handle zeros)
            non_zero_mask = y_true != 0
            if non_zero_mask.any():
                mape = np.mean(np.abs((y_true[non_zero_mask] - y_pred[non_zero_mask])
                                      / y_true[non_zero_mask])) * 100
            else:
                mape = np.nan

            # Directional accuracy (did we predict the direction correctly?)
            if len(y_true) > 1:
                actual_direction = np.diff(y_true) > 0
                pred_direction = np.diff(y_pred) > 0
                directional_accuracy = np.mean(actual_direction == pred_direction) * 100
            else:
                directional_accuracy = np.nan

            # Average error percentage
            avg_error_pct = mape if not np.isnan(mape) else 0.0

            # Convert index values to date objects for parquet compatibility
            test_start_val = validation_data.index[0]
            test_end_val = validation_data.index[-1]

            # Handle various date/timestamp types
            if hasattr(test_start_val, 'date'):
                test_start_date = test_start_val.date()
            elif hasattr(test_start_val, 'to_pydatetime'):
                test_start_date = test_start_val.to_pydatetime().date()
            else:
                test_start_date = datetime.now().date()

            if hasattr(test_end_val, 'date'):
                test_end_date = test_end_val.date()
            elif hasattr(test_end_val, 'to_pydatetime'):
                test_end_date = test_end_val.to_pydatetime().date()
            else:
                test_end_date = datetime.now().date()

            return {
                'mae': float(mae),
                'rmse': float(rmse),
                'mape': float(mape) if not np.isnan(mape) else 0.0,
                'r2_score': float(r2),
                'directional_accuracy': float(directional_accuracy) if not np.isnan(directional_accuracy) else 0.0,
                'num_predictions': int(min_len),
                'avg_error_pct': float(avg_error_pct),
                'test_start': test_start_date,
                'test_end': test_end_date
            }

        except Exception as e:
            # Log error but don't fail
            import traceback
            traceback.print_exc()
            return empty_metrics

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

        self._print(f"    Saving forecasts to: {forecast_root}")

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
                self._print(f"    Warning: Unknown target '{target}', skipping")
                continue

            # Drop the target column as it's implicit in the table name
            target_df = target_df.drop(columns=['target'])

            # Determine output path according to schema
            output_path = Path(forecast_root) / 'facts' / table_name

            # Partition by forecast_date
            forecast_date = target_df['forecast_date'].iloc[0]
            partition_path = output_path / f"forecast_date={forecast_date}"
            partition_path.mkdir(parents=True, exist_ok=True)

            # Append to existing data or create new file
            file_path = partition_path / "data.parquet"

            if file_path.exists():
                # Read existing data and append new data
                existing_df = pd.read_parquet(file_path)
                combined_df = pd.concat([existing_df, target_df], ignore_index=True)
                combined_df.to_parquet(file_path, index=False, compression='snappy')
                self._print(f"    → Appended {len(target_df)} {table_name} records (total: {len(combined_df)})")
            else:
                # Create new file
                target_df.to_parquet(file_path, index=False, compression='snappy')
                self._print(f"    → Saved {len(target_df)} {table_name} records")

            self._print(f"      File: {file_path}")

    def save_metrics(self, metrics_df):
        """
        Save forecast metrics to Silver layer.

        Args:
            metrics_df: pandas DataFrame with metrics
        """
        from pathlib import Path
        from datetime import date

        # Get forecast Silver root
        forecast_root = self.storage_cfg['roots'].get(
            'forecast_silver',
            'storage/silver/forecast'
        )

        # Normalize date columns to ensure consistent types
        date_columns = ['metric_date', 'training_start', 'training_end', 'test_start', 'test_end']
        for col in date_columns:
            if col in metrics_df.columns:
                metrics_df[col] = pd.to_datetime(metrics_df[col]).dt.date

        # Determine output path according to schema
        output_path = Path(forecast_root) / 'facts' / 'forecast_metrics'

        # Partition by metric_date
        metric_date = metrics_df['metric_date'].iloc[0]
        partition_path = output_path / f"metric_date={metric_date}"
        partition_path.mkdir(parents=True, exist_ok=True)

        # Append to existing data or create new file
        file_path = partition_path / "data.parquet"

        if file_path.exists():
            # Read existing data and append new data
            existing_df = pd.read_parquet(file_path)

            # Normalize date columns in existing data as well
            for col in date_columns:
                if col in existing_df.columns:
                    existing_df[col] = pd.to_datetime(existing_df[col]).dt.date

            combined_df = pd.concat([existing_df, metrics_df], ignore_index=True)
            combined_df.to_parquet(file_path, index=False, compression='snappy')
            self._print(f"    Appended {len(metrics_df)} metric records (total: {len(combined_df)}) to {file_path}")
        else:
            # Create new file
            metrics_df.to_parquet(file_path, index=False, compression='snappy')
            self._print(f"    Saved {len(metrics_df)} metric records to {file_path}")

    def save_model_registry(self, registry_df):
        """
        Save model registry to Silver layer.

        Tracks trained models with their parameters and status.

        Args:
            registry_df: pandas DataFrame with model registry records
        """
        from pathlib import Path
        import pandas as pd

        # Get forecast Silver root
        forecast_root = self.storage_cfg['roots'].get(
            'forecast_silver',
            'storage/silver/forecast'
        )

        # Normalize date columns
        if 'trained_date' in registry_df.columns:
            registry_df['trained_date'] = pd.to_datetime(registry_df['trained_date']).dt.date

        # Determine output path according to schema
        output_path = Path(forecast_root) / 'facts' / 'model_registry'

        # Partition by trained_date
        trained_date = registry_df['trained_date'].iloc[0]
        partition_path = output_path / f"trained_date={trained_date}"
        partition_path.mkdir(parents=True, exist_ok=True)

        # Append to existing data or create new file
        file_path = partition_path / "data.parquet"

        if file_path.exists():
            existing_df = pd.read_parquet(file_path)
            if 'trained_date' in existing_df.columns:
                existing_df['trained_date'] = pd.to_datetime(existing_df['trained_date']).dt.date
            combined_df = pd.concat([existing_df, registry_df], ignore_index=True)
            # Deduplicate by model_id
            combined_df = combined_df.drop_duplicates(subset=['model_id'], keep='last')
            combined_df.to_parquet(file_path, index=False, compression='snappy')
            self._print(f"    Updated model registry: {len(combined_df)} models in {file_path}")
        else:
            registry_df.to_parquet(file_path, index=False, compression='snappy')
            self._print(f"    Saved {len(registry_df)} model registry records to {file_path}")
