"""
ForecastModel - Domain model for time series forecasting.

Inherits graph building from BaseModel but extends with ML training capabilities.
"""

from typing import Dict, Optional
from pathlib import Path
from pyspark.sql import DataFrame
from models.base.model import BaseModel


class ForecastModel(BaseModel):
    """
    Forecast domain model.

    Key differences from CompanyModel:
    1. Loads from Silver (pre-computed forecasts) not Bronze
    2. Depends on company model for training data
    3. Adds ML training methods (ARIMA, Prophet, RandomForest)

    The YAML config (configs/models/forecast.yaml) defines:
    - Nodes: fact_forecasts, fact_forecast_metrics, fact_model_registry
    - Dependencies: company model
    - Model configurations: ARIMA, Prophet, RandomForest settings
    """

    def __init__(self, connection, storage_cfg: Dict, model_cfg: Dict, params: Dict = None):
        """
        Initialize Forecast Model.

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

        Forecast model needs access to company model for training data.

        Args:
            session: UniversalSession instance
        """
        self._session = session

    # ============================================================
    # CUSTOM NODE LOADING (override BaseModel)
    # ============================================================

    def custom_node_loading(self, node_id: str, node_config: Dict) -> Optional[DataFrame]:
        """
        Custom loading for forecast nodes.

        Forecast model loads from Silver (pre-computed data)
        instead of Bronze (raw data).

        Args:
            node_id: Node identifier
            node_config: Node configuration from YAML

        Returns:
            DataFrame if custom loading needed, None for default
        """
        # Check if loading from Silver
        if 'from' in node_config:
            layer, table = node_config['from'].split('.', 1)

            if layer == 'silver':
                # Load from Silver storage
                return self._load_from_silver(table)

        # Use default loading for other nodes
        return None

    def _load_from_silver(self, table_name: str) -> DataFrame:
        """
        Load a table from Silver storage.

        Args:
            table_name: Table name (e.g., 'forecasts', 'metrics')

        Returns:
            DataFrame
        """
        # Get forecast Silver root
        forecast_root = self.storage_cfg['roots'].get(
            'forecast_silver',
            'storage/silver/forecast'
        )

        # Build path
        path = f"{forecast_root}/{table_name}"

        # Load with connection
        if hasattr(self.connection, 'read'):
            # Spark
            try:
                return self.connection.read.parquet(path)
            except Exception:
                # Table doesn't exist yet - return empty DataFrame with schema
                return self._create_empty_table(table_name)
        else:
            # DuckDB or other
            try:
                return self.connection.read_parquet(path)
            except Exception:
                return self._create_empty_table(table_name)

    def _create_empty_table(self, table_name: str) -> DataFrame:
        """
        Create empty table with proper schema.

        Used when forecast tables don't exist yet.

        Args:
            table_name: Table name

        Returns:
            Empty DataFrame with schema
        """
        # Get schema from config
        schema_config = self.model_cfg.get('schema', {}).get('facts', {})

        # Find matching table
        for table_id, table_def in schema_config.items():
            if table_def['path'].endswith(table_name):
                # Create empty DataFrame with schema
                from pyspark.sql.types import StructType, StructField, StringType, IntegerType, DoubleType, DateType, LongType, BooleanType

                type_map = {
                    'string': StringType(),
                    'int': IntegerType(),
                    'double': DoubleType(),
                    'date': DateType(),
                    'long': LongType(),
                    'boolean': BooleanType(),
                }

                fields = [
                    StructField(col_name, type_map.get(col_type, StringType()), True)
                    for col_name, col_type in table_def['columns'].items()
                ]

                schema = StructType(fields)
                return self.connection.createDataFrame([], schema)

        # Fallback: empty DataFrame
        return self.connection.createDataFrame([], StructType([]))

    # ============================================================
    # CROSS-MODEL DATA ACCESS
    # ============================================================

    def get_training_data(
        self,
        ticker: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> DataFrame:
        """
        Get training data from company model.

        Args:
            ticker: Ticker symbol
            date_from: Start date (optional)
            date_to: End date (optional)

        Returns:
            DataFrame with price data for training

        Raises:
            RuntimeError: If session not set
        """
        if not self._session:
            raise RuntimeError(
                "ForecastModel requires session for cross-model access. "
                "Call set_session() first."
            )

        # Get company model
        company_model = self._session.load_model('company')

        # Get prices
        df = company_model.get_table('fact_prices')
        df = df.filter(df.ticker == ticker)

        # Apply date filters if provided
        if date_from:
            df = df.filter(df.trade_date >= date_from)
        if date_to:
            df = df.filter(df.trade_date <= date_to)

        return df.orderBy('trade_date')

    # ============================================================
    # CONVENIENCE METHODS
    # ============================================================

    def get_forecasts(
        self,
        ticker: Optional[str] = None,
        model_name: Optional[str] = None
    ) -> DataFrame:
        """
        Get forecast predictions.

        Args:
            ticker: Optional ticker filter
            model_name: Optional model name filter (e.g., 'ARIMA_7d')

        Returns:
            DataFrame with forecasts
        """
        df = self.get_table('fact_forecasts')

        if ticker:
            df = df.filter(df.ticker == ticker)
        if model_name:
            df = df.filter(df.model_name == model_name)

        return df

    def get_metrics(
        self,
        ticker: Optional[str] = None,
        model_name: Optional[str] = None
    ) -> DataFrame:
        """
        Get forecast accuracy metrics.

        Args:
            ticker: Optional ticker filter
            model_name: Optional model name filter

        Returns:
            DataFrame with metrics
        """
        df = self.get_table('fact_forecast_metrics')

        if ticker:
            df = df.filter(df.ticker == ticker)
        if model_name:
            df = df.filter(df.model_name == model_name)

        return df

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
    # ML TRAINING METHODS (to be implemented)
    # ============================================================

    def train_arima(self, ticker: str, config_name: str = 'arima_7d'):
        """
        Train ARIMA model for a ticker.

        Args:
            ticker: Ticker symbol
            config_name: ARIMA config name from YAML

        Returns:
            Trained model and metadata

        Note: Implementation to be added based on existing forecast_model.py
        """
        config = self.get_model_config(config_name)
        training_data = self.get_training_data(
            ticker,
            lookback_days=config['lookback_days']
        )

        # TODO: Implement ARIMA training
        # (Will port from existing forecast_model.py)
        raise NotImplementedError("ARIMA training to be implemented")

    def train_prophet(self, ticker: str, config_name: str = 'prophet_7d'):
        """
        Train Prophet model for a ticker.

        Args:
            ticker: Ticker symbol
            config_name: Prophet config name from YAML

        Returns:
            Trained model and metadata

        Note: Implementation to be added based on existing forecast_model.py
        """
        config = self.get_model_config(config_name)
        training_data = self.get_training_data(
            ticker,
            lookback_days=config['lookback_days']
        )

        # TODO: Implement Prophet training
        raise NotImplementedError("Prophet training to be implemented")

    def train_random_forest(self, ticker: str, config_name: str = 'random_forest_14d'):
        """
        Train Random Forest model for a ticker.

        Args:
            ticker: Ticker symbol
            config_name: RF config name from YAML

        Returns:
            Trained model and metadata

        Note: Implementation to be added based on existing forecast_model.py
        """
        config = self.get_model_config(config_name)
        training_data = self.get_training_data(
            ticker,
            lookback_days=config['lookback_days']
        )

        # TODO: Implement RandomForest training
        raise NotImplementedError("RandomForest training to be implemented")
