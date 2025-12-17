"""
CompanyForecastModel - Time series forecasting for stock price data.

Specific implementation of TimeSeriesForecastModel that forecasts:
- Stock prices (close)
- Trading volumes

Data source: StocksModel (fact_stock_prices table from silver layer)
"""
from __future__ import annotations

from typing import Dict, TYPE_CHECKING

# Optional PySpark import - allows DuckDB-only usage
if TYPE_CHECKING:
    from pyspark.sql import DataFrame as SparkDataFrame, Row as SparkRow
    from pyspark.sql.types import StructType as SparkStructType

try:
    from pyspark.sql import DataFrame, Row
    from pyspark.sql.types import (
        StructType, StructField, StringType, IntegerType,
        DoubleType, DateType, LongType, BooleanType
    )
    HAS_SPARK = True
except ImportError:
    HAS_SPARK = False
    DataFrame = None  # type: ignore
    Row = None  # type: ignore
    StructType = None  # type: ignore
    StructField = None  # type: ignore
    StringType = None  # type: ignore
    IntegerType = None  # type: ignore
    DoubleType = None  # type: ignore
    DateType = None  # type: ignore
    LongType = None  # type: ignore
    BooleanType = None  # type: ignore

from models.base.forecast_model import TimeSeriesForecastModel


class CompanyForecastModel(TimeSeriesForecastModel):
    """
    Stock forecast model.

    Forecasts stock prices and volumes using data from the stocks model.
    Inherits all training methods from TimeSeriesForecastModel.
    """

    # ============================================================
    # IMPLEMENT ABSTRACT METHODS
    # ============================================================

    def get_source_model_name(self) -> str:
        """Stock forecasts use price data from the stocks model."""
        return 'stocks'

    def get_source_table_name(self) -> str:
        """Load price data from fact_stock_prices table."""
        return 'fact_stock_prices'

    def get_entity_column(self) -> str:
        """Entity identifier is 'ticker' for stock forecasts."""
        return 'ticker'

    def get_date_column(self) -> str:
        """Date column is 'trade_date' for stock forecasts."""
        return 'trade_date'

    # ============================================================
    # CUSTOM NODE LOADING (override BaseModel)
    # ============================================================

    def custom_node_loading(self, node_id: str, node_config: Dict) -> DataFrame:
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
        if 'from' in node_config:
            layer, table = node_config['from'].split('.', 1)
            if layer == 'silver':
                return self._load_from_silver(table)

        return None

    def _load_from_silver(self, table_name: str) -> DataFrame:
        """
        Load a table from Silver storage.

        Args:
            table_name: Table name (e.g., 'forecasts', 'metrics')

        Returns:
            DataFrame
        """
        table_path_map = {
            'forecasts': 'facts/forecast_price',
            'forecast_price': 'facts/forecast_price',
            'metrics': 'facts/forecast_metrics',
            'forecast_metrics': 'facts/forecast_metrics',
            'model_registry': 'facts/model_registry',
        }

        actual_path = table_path_map.get(table_name, table_name)
        forecast_root = self.storage_cfg['roots'].get(
            'forecast_silver',
            'storage/silver/forecast'
        )
        path = f"{forecast_root}/{actual_path}"

        if self.backend == 'spark':
            try:
                # Auto-detect Delta vs Parquet
                from pathlib import Path as PathLib
                if (PathLib(path) / "_delta_log").exists():
                    return self.connection.spark.read.format("delta").load(path)
                return self.connection.spark.read.parquet(path)
            except Exception:
                return self._create_empty_table(table_name)
        else:
            try:
                # DuckDB read_table auto-detects format
                return self.connection.read_table(path)
            except Exception:
                return self._create_empty_table(table_name)

    def _create_empty_table(self, table_name: str):
        """
        Create empty table with proper schema.

        Used when forecast tables don't exist yet.

        Args:
            table_name: Table name

        Returns:
            Empty DataFrame with schema
        """
        import pandas as pd

        name_to_fact_map = {
            'forecasts': 'fact_forecasts',
            'forecast_price': 'fact_forecasts',
            'metrics': 'fact_forecast_metrics',
            'forecast_metrics': 'fact_forecast_metrics',
            'model_registry': 'fact_model_registry',
        }

        fact_table_name = name_to_fact_map.get(table_name, f"fact_{table_name}")
        schema_config = self.model_cfg.get('schema', {}).get('facts', {})
        table_def = schema_config.get(fact_table_name)

        if not HAS_SPARK or self.backend != 'spark':
            if table_def:
                columns = list(table_def['columns'].keys())
                return pd.DataFrame(columns=columns)
            return pd.DataFrame()

        type_map = {
            'string': StringType(),
            'int': IntegerType(),
            'double': DoubleType(),
            'date': DateType(),
            'long': LongType(),
            'boolean': BooleanType(),
        }

        if table_def:
            fields = [
                StructField(col_name, type_map.get(col_type, StringType()), True)
                for col_name, col_type in table_def['columns'].items()
            ]
            schema = StructType(fields)
            return self.connection.spark.createDataFrame([], schema)

        return self.connection.spark.createDataFrame([], StructType([]))

    # ============================================================
    # VIEW REGISTRATION (for DuckDB analytics)
    # ============================================================

    def register_views(self):
        """
        Register SQL views for forecast model in DuckDB.

        Creates unified views that combine actuals from stocks model
        with predictions from forecast model. Only used for analytics.
        """
        if not hasattr(self.connection, 'execute'):
            return

        try:
            self.connection.execute("CREATE SCHEMA IF NOT EXISTS stocks")
            self.connection.execute("CREATE SCHEMA IF NOT EXISTS forecast")
        except Exception:
            return

        duckdb_conn = self.connection.conn if hasattr(self.connection, 'conn') else self.connection

        try:
            if 'fact_forecasts' in self._facts:
                duckdb_conn.register('temp_fact_forecasts', self._facts['fact_forecasts'])
                duckdb_conn.execute("CREATE OR REPLACE TABLE fact_forecasts AS SELECT * FROM temp_fact_forecasts")
            else:
                return
        except Exception:
            return

        fact_prices_registered = False
        if hasattr(self, 'session') and self.session:
            try:
                stocks_model = self.session.load_model('stocks')
                if stocks_model:
                    stocks_model.ensure_built()
                    if hasattr(stocks_model, '_facts') and 'fact_stock_prices' in stocks_model._facts:
                        duckdb_conn.execute("DROP TABLE IF EXISTS fact_prices")
                        duckdb_conn.execute("DROP VIEW IF EXISTS fact_prices")
                        duckdb_conn.register('temp_fact_prices', stocks_model._facts['fact_stock_prices'])
                        duckdb_conn.execute("CREATE TABLE fact_prices AS SELECT * FROM temp_fact_prices")
                        fact_prices_registered = True
            except Exception:
                pass

        try:
            result = duckdb_conn.execute("SELECT * FROM fact_forecasts LIMIT 0").description
            columns = [col[0] for col in result]

            if 'predicted_close' in columns:
                predicted_col = 'predicted_close'
            elif 'predicted_value' in columns:
                predicted_col = 'predicted_value'
            else:
                return

            has_target_column = 'target' in columns
            where_clause = "WHERE target = 'close'" if has_target_column else ""

            if fact_prices_registered:
                view_sql = f"""
                CREATE OR REPLACE VIEW forecast.vw_price_predictions AS
                WITH actuals AS (
                    SELECT trade_date as date, ticker, NULL as model_name,
                           close as actual, NULL as predicted, NULL as upper_bound, NULL as lower_bound
                    FROM fact_prices
                ),
                predictions AS (
                    SELECT prediction_date as date, ticker, model_name,
                           NULL as actual, {predicted_col} as predicted, upper_bound, lower_bound
                    FROM fact_forecasts {where_clause}
                )
                SELECT * FROM actuals UNION ALL SELECT * FROM predictions
                ORDER BY date, ticker, model_name
                """
            else:
                view_sql = f"""
                CREATE OR REPLACE VIEW forecast.vw_price_predictions AS
                SELECT prediction_date as date, ticker, model_name,
                       NULL as actual, {predicted_col} as predicted, upper_bound, lower_bound
                FROM fact_forecasts {where_clause}
                ORDER BY date, ticker, model_name
                """

            self.connection.execute(view_sql)

            if hasattr(self, '_facts'):
                try:
                    view_df = duckdb_conn.sql("SELECT * FROM forecast.vw_price_predictions")
                    self._facts['vw_price_predictions'] = view_df
                except Exception:
                    pass

        except Exception:
            pass

    def ensure_built(self):
        """Override to register views after building."""
        super().ensure_built()
        self.register_views()

    # ============================================================
    # TABLE ACCESS
    # ============================================================

    def get_table(self, table_name: str):
        """
        Override get_table to support lazy view registration.
        """
        try:
            return super().get_table(table_name)
        except KeyError:
            if table_name == 'vw_price_predictions':
                self.register_views()
                if table_name in self._facts:
                    return self._facts[table_name]
            raise

    # ============================================================
    # CONVENIENCE METHODS
    # ============================================================

    def get_forecasts(self, ticker: str = None, model_name: str = None) -> DataFrame:
        """Get forecast predictions."""
        df = self.get_table('fact_forecasts')
        if ticker:
            df = df.filter(df.ticker == ticker)
        if model_name:
            df = df.filter(df.model_name == model_name)
        return df

    def get_metrics(self, ticker: str = None, model_name: str = None) -> DataFrame:
        """Get forecast accuracy metrics."""
        df = self.get_table('fact_forecast_metrics')
        if ticker:
            df = df.filter(df.ticker == ticker)
        if model_name:
            df = df.filter(df.model_name == model_name)
        return df

    def run_forecast_for_ticker(self, ticker: str, model_configs: list = None) -> dict:
        """Alias for run_forecast_for_entity (backward compatibility)."""
        result = self.run_forecast_for_entity(ticker, model_configs)
        result['ticker'] = result['entity_id']
        return result
