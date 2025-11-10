"""
CompanyForecastModel - Time series forecasting for company stock data.

Specific implementation of TimeSeriesForecastModel that forecasts:
- Stock prices (close)
- Trading volumes

Data source: CompanyModel (fact_prices table)
"""

from typing import Dict
from pyspark.sql import DataFrame, Row
from pyspark.sql.types import StructType
from models.base.forecast_model import TimeSeriesForecastModel


class CompanyForecastModel(TimeSeriesForecastModel):
    """
    Company-specific forecast model.

    Forecasts stock prices and volumes using data from the CompanyModel.
    Inherits all training methods from TimeSeriesForecastModel.
    """

    # ============================================================
    # IMPLEMENT ABSTRACT METHODS
    # ============================================================

    def get_source_model_name(self) -> str:
        """Company forecasts use data from the company model."""
        return 'company'

    def get_source_table_name(self) -> str:
        """Load price data from fact_prices table."""
        return 'fact_prices'

    def get_entity_column(self) -> str:
        """Entity identifier is 'ticker' for company forecasts."""
        return 'ticker'

    def get_date_column(self) -> str:
        """Date column is 'trade_date' for company forecasts."""
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
                from pyspark.sql.types import (
                    StructType, StructField, StringType, IntegerType,
                    DoubleType, DateType, LongType, BooleanType
                )

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
    # VIEW REGISTRATION
    # ============================================================

    def register_views(self):
        """
        Register SQL views for forecast model.

        Creates unified views that combine actuals from company model
        with predictions from forecast model.
        """
        # Only works with DuckDB (has execute method)
        if not hasattr(self.connection, 'execute'):
            return

        try:
            # Ensure schemas exist in DuckDB
            self.connection.execute("CREATE SCHEMA IF NOT EXISTS company")
            self.connection.execute("CREATE SCHEMA IF NOT EXISTS forecast")
            print(f"✓ Ensured schemas exist: company, forecast")
        except Exception as e:
            print(f"⚠ Could not create schemas: {e}")
            return

        # CRITICAL: Register the _facts relations in DuckDB's catalog
        # Tables loaded from Parquet exist as relation objects but aren't in SQL catalog
        try:
            # Get the underlying DuckDB connection
            duckdb_conn = self.connection.conn if hasattr(self.connection, 'conn') else self.connection

            # Register fact_prices from company model
            fact_prices_registered = False
            if 'fact_prices' in self._facts:
                print(f"DEBUG: Registering fact_prices from local _facts")
                duckdb_conn.register('fact_prices', self._facts['fact_prices'])
                fact_prices_registered = True
            else:
                # Try to get it from company model via session
                try:
                    # Debug session state
                    print(f"DEBUG: Checking session availability...")
                    print(f"  - hasattr(self, 'session'): {hasattr(self, 'session')}")
                    if hasattr(self, 'session'):
                        print(f"  - self.session is None: {self.session is None}")
                        print(f"  - self.session type: {type(self.session)}")

                    if hasattr(self, 'session') and self.session:
                        print(f"DEBUG: ✓ Session available, loading company model...")
                        company_model = self.session.load_model('company')
                        if company_model:
                            # Ensure company model is built
                            company_model.ensure_built()
                            if hasattr(company_model, '_facts') and 'fact_prices' in company_model._facts:
                                duckdb_conn.register('fact_prices', company_model._facts['fact_prices'])
                                print(f"✓ Registered fact_prices from company model")
                                fact_prices_registered = True
                            else:
                                print(f"⚠ fact_prices not in company model _facts")
                        else:
                            print(f"⚠ Could not load company model")
                    else:
                        if not hasattr(self, 'session'):
                            print(f"⚠ No 'session' attribute - need to update BaseModel with set_session()")
                        else:
                            print(f"⚠ session is None - set_session() was not called by UniversalSession")
                except Exception as e:
                    print(f"⚠ Could not get fact_prices from company model: {e}")
                    import traceback
                    traceback.print_exc()

            if not fact_prices_registered:
                print(f"⚠ fact_prices could not be registered - view will only show predictions")

            # Register fact_forecasts from forecast model
            if 'fact_forecasts' in self._facts:
                print(f"DEBUG: Registering fact_forecasts in DuckDB catalog")
                duckdb_conn.register('fact_forecasts', self._facts['fact_forecasts'])
                print(f"✓ Registered fact_forecasts")
            else:
                print(f"⚠ fact_forecasts not found in _facts, cannot create view")
                return

        except Exception as e:
            print(f"⚠ Could not register tables in DuckDB catalog: {e}")
            import traceback
            traceback.print_exc()
            return

        # Check what columns actually exist in fact_forecasts
        try:
            result = duckdb_conn.execute("SELECT * FROM fact_forecasts LIMIT 0").description
            columns = [col[0] for col in result]
            print(f"DEBUG: fact_forecasts columns: {columns}")

            # Determine which predicted column to use
            if 'predicted_close' in columns:
                predicted_col = 'predicted_close'
            elif 'predicted_value' in columns:
                predicted_col = 'predicted_value'
            else:
                print(f"⚠ Neither predicted_close nor predicted_value found in fact_forecasts")
                return

            print(f"DEBUG: Using predicted column: {predicted_col}")
        except Exception as e:
            print(f"⚠ Could not inspect fact_forecasts columns: {e}")
            # Default to predicted_close
            predicted_col = 'predicted_close'

        # Build view SQL with actual or predictions-only based on fact_prices availability
        if fact_prices_registered:
            view_sql = f"""
            CREATE OR REPLACE VIEW forecast.vw_price_predictions AS

            -- Historical actuals (from company model)
            WITH actuals AS (
                SELECT
                    trade_date as date,
                    ticker,
                    NULL as model_name,
                    close as actual,
                    NULL as predicted,
                    NULL as upper_bound,
                    NULL as lower_bound
                FROM fact_prices
            ),

            -- Future predictions (from forecast model)
            predictions AS (
                SELECT
                    prediction_date as date,
                    ticker,
                    model_name,
                    NULL as actual,
                    {predicted_col} as predicted,
                    upper_bound,
                    lower_bound
                FROM fact_forecasts
                WHERE target = 'close'
            )

            -- Combine both
            SELECT * FROM actuals
            UNION ALL
            SELECT * FROM predictions
            ORDER BY date, ticker, model_name
            """
        else:
            # Predictions-only view if we don't have actuals
            view_sql = f"""
            CREATE OR REPLACE VIEW forecast.vw_price_predictions AS
            SELECT
                prediction_date as date,
                ticker,
                model_name,
                NULL as actual,
                {predicted_col} as predicted,
                upper_bound,
                lower_bound
            FROM fact_forecasts
            WHERE target = 'close'
            ORDER BY date, ticker, model_name
            """
            print(f"ℹ Creating predictions-only view (fact_prices not available)")

        try:
            self.connection.execute(view_sql)
            print(f"✓ Created view: forecast.vw_price_predictions")

            # Register the view in the model's _facts dictionary so it's discoverable
            # via get_table() and can be used as a filter source
            if hasattr(self, '_facts'):
                # Query the view to make it available as a DuckDB relation
                try:
                    # Use SQL query to get relation (DuckDB's .table() doesn't support schema-qualified names)
                    view_df = duckdb_conn.sql("SELECT * FROM forecast.vw_price_predictions")
                    self._facts['vw_price_predictions'] = view_df
                    print(f"✓ Registered view in _facts: vw_price_predictions")
                except Exception as e:
                    print(f"⚠ Could not register view in _facts: {e}")
                    # Still continue - view exists in database even if not in _facts

        except Exception as e:
            # Log the error but don't fail - views are optional (tables might not exist yet)
            print(f"⚠ Could not create view vw_price_predictions: {e}")
            print(f"   This is normal if company or forecast tables don't exist yet")
            import traceback
            traceback.print_exc()

    def ensure_built(self):
        """Override to register views after building."""
        super().ensure_built()

        # Register views after model is built
        print(f"DEBUG: CompanyForecastModel.ensure_built() - calling register_views()")
        print(f"DEBUG: Connection type: {type(self.connection)}")
        print(f"DEBUG: Has execute: {hasattr(self.connection, 'execute')}")
        print(f"DEBUG: Has _facts: {hasattr(self, '_facts')}")
        if hasattr(self, '_facts'):
            print(f"DEBUG: Current _facts keys: {list(self._facts.keys())}")

        self.register_views()

        if hasattr(self, '_facts'):
            print(f"DEBUG: After register_views, _facts keys: {list(self._facts.keys())}")

    # ============================================================
    # TABLE ACCESS (override to handle views)
    # ============================================================

    def get_table(self, table_name: str):
        """
        Override get_table to support lazy view registration.

        If view doesn't exist in _facts but is a known view name,
        try to register it lazily.
        """
        # Try parent implementation first
        try:
            return super().get_table(table_name)
        except KeyError:
            # If it's the view we know about, try to register it
            if table_name == 'vw_price_predictions':
                print(f"DEBUG: View '{table_name}' not found, attempting lazy registration")
                self.register_views()

                # Try again after registration
                if table_name in self._facts:
                    return self._facts[table_name]
                else:
                    # Registration failed, re-raise original error
                    raise

            # Not a view we know about, re-raise
            raise

    # ============================================================
    # CONVENIENCE METHODS (company-specific)
    # ============================================================

    def get_forecasts(
        self,
        ticker: str = None,
        model_name: str = None
    ) -> DataFrame:
        """
        Get forecast predictions for companies.

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
        ticker: str = None,
        model_name: str = None
    ) -> DataFrame:
        """
        Get forecast accuracy metrics for companies.

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

    # ============================================================
    # ALIAS METHODS (for backward compatibility)
    # ============================================================

    def run_forecast_for_ticker(self, ticker: str, model_configs: list = None) -> dict:
        """
        Alias for run_forecast_for_entity (backward compatibility).

        Args:
            ticker: Ticker symbol
            model_configs: List of model configs to run

        Returns:
            Results dictionary
        """
        result = self.run_forecast_for_entity(ticker, model_configs)
        # Add 'ticker' key for backward compatibility
        result['ticker'] = result['entity_id']
        return result
