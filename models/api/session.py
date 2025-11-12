from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set
from pyspark.sql import DataFrame

from models.api.dal import StorageRouter, BronzeTable

try:
    import yaml  # type: ignore
except Exception:
    yaml = None


# ============================================================
# UNIVERSAL SESSION (Model-Agnostic)
# ============================================================

class UniversalSession:
    """
    Model-agnostic session that works with any BaseModel.

    Key features:
    - Dynamic model loading from registry
    - Works with any model (company, forecast, etc.)
    - Cross-model queries and joins
    - Session injection for model dependencies

    Usage:
        session = UniversalSession(
            connection=spark,
            storage_cfg=storage_cfg,
            repo_root=Path.cwd(),
            models=['company', 'forecast']
        )

        # Get table from any model
        prices = session.get_table('company', 'fact_prices')
        forecasts = session.get_table('forecast', 'fact_forecasts')

        # Models can access each other via session injection
    """

    def __init__(
        self,
        connection,
        storage_cfg: Dict[str, Any],
        repo_root: Path,
        models: list[str] | None = None
    ):
        """
        Initialize universal session.

        Args:
            connection: Database connection (Spark or DuckDB)
            storage_cfg: Storage configuration
            repo_root: Repository root path
            models: List of model names to pre-load (optional)
        """
        self.connection = connection
        self.storage_cfg = storage_cfg
        self.repo_root = repo_root

        # Model registry for dynamic loading
        from models.registry import ModelRegistry
        models_dir = repo_root / "configs" / "models"
        self.registry = ModelRegistry(models_dir)

        # Cache loaded models
        self._models: Dict[str, Any] = {}  # model_name -> BaseModel instance

        # Build model dependency graph
        from models.api.graph import ModelGraph
        self.model_graph = ModelGraph()
        try:
            self.model_graph.build_from_config_dir(models_dir)
        except Exception as e:
            print(f"Warning: Could not build model graph: {e}")

        # Pre-load specified models
        if models:
            for model_name in models:
                self.load_model(model_name)

    @property
    def backend(self) -> str:
        """
        Detect backend type from connection.

        Returns:
            'spark' or 'duckdb'

        Raises:
            ValueError: If connection type is unknown
        """
        connection_type = str(type(self.connection))

        # Check for Spark
        if 'spark' in connection_type.lower() or hasattr(self.connection, 'sql'):
            return 'spark'

        # Check for DuckDB
        if 'duckdb' in connection_type.lower() or (
            hasattr(self.connection, '_conn') and 'duckdb' in str(type(self.connection._conn)).lower()
        ):
            return 'duckdb'

        # Unknown connection type
        raise ValueError(f"Unknown connection type: {connection_type}")

    def load_model(self, model_name: str):
        """
        Dynamically load a model by name.

        Steps:
        1. Get model config from registry (YAML)
        2. Get model class from registry (Python class)
        3. Instantiate model
        4. Inject session for cross-model access
        5. Cache instance

        Args:
            model_name: Name of model to load

        Returns:
            BaseModel instance
        """
        # Return cached if already loaded
        if model_name in self._models:
            return self._models[model_name]

        # Get config and class from registry
        model_config = self.registry.get_model_config(model_name)
        model_class = self.registry.get_model_class(model_name)

        # Instantiate model
        model = model_class(
            connection=self.connection,
            storage_cfg=self.storage_cfg,
            model_cfg=model_config,
            params={}
        )

        # Inject session for cross-model access
        if hasattr(model, 'set_session'):
            print(f"DEBUG: Injecting session into {model_name} model via set_session()")
            model.set_session(self)
            print(f"DEBUG: Session injected successfully, model.session = {model.session}")
        else:
            print(f"⚠ Model {model_name} has no set_session() method - need to update BaseModel")

        # Cache
        self._models[model_name] = model

        return model

    def get_table(
        self,
        model_name: str,
        table_name: str,
        required_columns: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
        group_by: Optional[List[str]] = None,
        aggregations: Optional[Dict[str, str]] = None,
        use_cache: bool = True
    ) -> DataFrame:
        """
        Get a table from any model with transparent auto-join and aggregation support.

        If required_columns are specified and some don't exist in the base table,
        the system automatically uses the model graph to find join paths and
        retrieve the missing columns.

        If group_by is specified, the data is aggregated to the new grain using
        measure metadata from the model configuration.

        This makes materialized views a performance optimization rather than
        a user-facing concept - users just specify what columns they need and
        at what grain.

        Args:
            model_name: Name of the model
            table_name: Name of the base table
            required_columns: Optional list of columns needed. If specified and some
                            columns don't exist in base table, auto-joins are performed
            filters: Optional filters to apply (not yet implemented)
            group_by: Optional list of columns to group by (dimensions at new grain)
            aggregations: Optional dict mapping measure columns to aggregation functions
                        (avg, sum, max, min, count, first). If not provided, uses measure
                        metadata from model config.
            use_cache: Whether to use cached data (kept for backwards compatibility)

        Returns:
            DataFrame with requested columns (auto-joined and aggregated if needed)

        Examples:
            # Simple usage - get full table
            df = session.get_table('company', 'fact_prices')

            # Auto-join usage - exchange_name not in fact_prices, auto-joins via graph
            df = session.get_table(
                'company', 'fact_prices',
                required_columns=['ticker', 'close', 'exchange_name']
            )
            # System transparently joins: fact_prices -> dim_company -> dim_exchange

            # Aggregation usage - change grain from ticker to exchange
            df = session.get_table(
                'company', 'fact_prices',
                required_columns=['trade_date', 'exchange_name', 'close', 'volume'],
                group_by=['trade_date', 'exchange_name'],
                aggregations={'close': 'avg', 'volume': 'sum'}
            )
            # System auto-joins exchange_name, then aggregates to exchange-level

        Note:
            The use_cache parameter is kept for backwards compatibility with old
            SilverStorageService API but is not used. Model caching is handled
            automatically via the _models cache in UniversalSession.
        """
        model = self.load_model(model_name)

        # If no specific columns requested, return full table (backward compatible)
        if not required_columns:
            return model.get_table(table_name)

        # Check which columns exist in base table
        try:
            schema = model.get_table_schema(table_name)
            base_columns = set(schema.keys())
        except Exception as e:
            # If can't get schema, fall back to simple table access
            print(f"Warning: Could not get schema for {model_name}.{table_name}: {e}")
            return model.get_table(table_name)

        # Find missing columns
        missing = [col for col in required_columns if col not in base_columns]

        # No missing columns - direct table access
        if not missing:
            df = model.get_table(table_name)
            # Select only requested columns
            df = self._select_columns(df, required_columns)

            # Apply aggregation if group_by specified
            if group_by:
                df = self._aggregate_data(model_name, df, required_columns, group_by, aggregations)

            return df

        # Missing columns - try auto-join strategies
        print(f"🔗 Auto-join: {missing} not in {table_name}, searching for join path...")

        # Strategy 1: Check if a materialized view has all columns
        materialized_table = self._find_materialized_view(model_name, required_columns)
        if materialized_table:
            print(f"✓ Using materialized view: {materialized_table}")
            df = model.get_table(materialized_table)
            return self._select_columns(df, required_columns)

        # Strategy 2: Build joins from graph
        try:
            join_plan = self._plan_auto_joins(model_name, table_name, missing)
            print(f"✓ Join plan: {' -> '.join(join_plan['table_sequence'])}")
            df = self._execute_auto_joins(model_name, join_plan, required_columns, filters)
        except Exception as e:
            print(f"❌ Auto-join failed: {e}")
            print(f"   Falling back to base table {table_name}")
            df = model.get_table(table_name)

        # Apply aggregation if group_by specified
        if group_by:
            df = self._aggregate_data(model_name, df, required_columns, group_by, aggregations)

        return df

    def get_filter_column_mappings(self, model_name: str, table_name: str) -> Dict[str, str]:
        """
        Get automatic filter column mappings based on model graph edges.

        Examines graph edges to find joins to dim_calendar and extracts
        column mappings. This allows filters like 'trade_date' to be
        automatically mapped to table-specific columns like 'metric_date'.

        Args:
            model_name: Name of the model
            table_name: Name of the table

        Returns:
            Dictionary mapping standard filter columns to table columns
            Example: {'trade_date': 'metric_date'}

        Example:
            If forecast model has this edge:
                from: fact_forecast_metrics
                to: core.dim_calendar
                on: [metric_date = trade_date]

            Then get_filter_column_mappings('forecast', 'fact_forecast_metrics')
            returns: {'trade_date': 'metric_date'}
        """
        mappings = {}

        # Get model config
        try:
            model_config = self.registry.get_model_config(model_name)
        except Exception as e:
            print(f"DEBUG: Failed to get model config for {model_name}: {e}")
            return mappings  # No model config, no mappings

        # DEBUG
        print(f"\nDEBUG get_filter_column_mappings: model_name={model_name}, table_name={table_name}")
        print(f"DEBUG: Has 'graph' in config: {'graph' in model_config}")
        if 'graph' in model_config:
            print(f"DEBUG: Has 'edges' in graph: {'edges' in model_config['graph']}")
            if 'edges' in model_config['graph']:
                print(f"DEBUG: Number of edges: {len(model_config['graph']['edges'])}")
                for i, e in enumerate(model_config['graph']['edges']):
                    print(f"DEBUG: Edge {i}: {e}")

        # Check if model has graph metadata
        if 'graph' not in model_config or 'edges' not in model_config['graph']:
            print(f"DEBUG: No graph or edges found")
            return mappings

        # Look for edges from this table to dim_calendar
        for edge in model_config['graph']['edges']:
            edge_from = edge.get('from', '')
            edge_to = edge.get('to', '')

            print(f"DEBUG: Checking edge: from='{edge_from}', to='{edge_to}' (looking for table_name='{table_name}')")

            # Check if this edge is from our table to dim_calendar
            if edge_from == table_name and 'dim_calendar' in edge_to:
                print(f"DEBUG: FOUND MATCHING EDGE!")
                # Extract column mapping from 'on' condition
                # Note: YAML parser converts 'on:' to boolean True (reserved word)
                # So we need to check both 'on' and True keys
                on_conditions = edge.get('on', edge.get(True, []))
                print(f"DEBUG: on_conditions={on_conditions}, type={type(on_conditions)}")

                for condition in on_conditions:
                    print(f"DEBUG: Processing condition={condition}, type={type(condition)}")
                    if isinstance(condition, str):
                        # Format: "metric_date = trade_date"
                        parts = condition.split('=')
                        if len(parts) == 2:
                            table_col = parts[0].strip()
                            calendar_col = parts[1].strip()
                            # Map calendar column to table column
                            # e.g., trade_date → metric_date
                            mappings[calendar_col] = table_col
                            print(f"DEBUG: Added mapping: {calendar_col} -> {table_col}")

        print(f"DEBUG: Final mappings: {mappings}\n")
        return mappings

    def get_dimension_df(self, model_name: str, dim_id: str) -> DataFrame:
        """Get a dimension table from a model"""
        model = self.load_model(model_name)
        return model.get_dimension_df(dim_id)

    def get_fact_df(self, model_name: str, fact_id: str) -> DataFrame:
        """Get a fact table from a model"""
        model = self.load_model(model_name)
        return model.get_fact_df(fact_id)

    def list_models(self) -> list[str]:
        """List all available models"""
        return self.registry.list_models()

    def list_tables(self, model_name: str) -> Dict[str, list[str]]:
        """
        List all tables in a model.

        Returns:
            Dictionary with 'dimensions' and 'facts' keys
        """
        model = self.load_model(model_name)
        return model.list_tables()

    def get_model_metadata(self, model_name: str) -> Dict[str, Any]:
        """Get metadata for a model"""
        model = self.load_model(model_name)
        return model.get_metadata()

    def get_model_instance(self, model_name: str):
        """
        Get the model instance directly.

        Useful for accessing model-specific methods.

        Args:
            model_name: Name of the model

        Returns:
            BaseModel instance
        """
        return self.load_model(model_name)

    # ============================================================
    # AUTO-JOIN SUPPORT (Transparent Graph Traversal)
    # ============================================================

    def _select_columns(self, df: DataFrame, columns: List[str]) -> DataFrame:
        """
        Select specific columns from DataFrame (backend agnostic).

        Args:
            df: DataFrame (Spark or DuckDB)
            columns: List of column names to select

        Returns:
            DataFrame with only specified columns
        """
        if self.backend == 'spark':
            return df.select(*columns)
        else:
            # DuckDB - use project() method
            return df.project(','.join(columns))

    def _find_materialized_view(
        self,
        model_name: str,
        required_columns: List[str]
    ) -> Optional[str]:
        """
        Find a materialized view that contains all required columns.

        This allows the system to use pre-computed joins when available,
        making materialized views a performance optimization.

        Args:
            model_name: Model to search in
            required_columns: Columns needed

        Returns:
            Table name of materialized view, or None if not found
        """
        try:
            model = self.load_model(model_name)
            tables = model.list_tables()

            # Search in facts (where materialized paths are stored)
            for table_name in tables.get('facts', []):
                try:
                    schema = model.get_table_schema(table_name)
                    table_columns = set(schema.keys())

                    # Check if this table has all required columns
                    if all(col in table_columns for col in required_columns):
                        return table_name
                except Exception:
                    continue

            return None
        except Exception as e:
            print(f"Warning: Error finding materialized view: {e}")
            return None

    def _plan_auto_joins(
        self,
        model_name: str,
        base_table: str,
        missing_columns: List[str]
    ) -> Dict[str, Any]:
        """
        Plan join sequence to get missing columns using model graph.

        Args:
            model_name: Model name
            base_table: Starting table
            missing_columns: Columns to find

        Returns:
            Join plan dict with:
                - table_sequence: List of tables to join
                - join_keys: List of (left_col, right_col) pairs for each join
                - target_columns: Which columns come from which table

        Raises:
            ValueError: If no join path found
        """
        model_config = self.registry.get_model_config(model_name)
        graph_config = model_config.get('graph', {})

        if not graph_config or 'edges' not in graph_config:
            raise ValueError(f"No graph edges defined for model {model_name}")

        # Build column-to-table index
        column_index = self._build_column_index(model_name)

        # Find which tables have the missing columns
        target_tables = {}
        for col in missing_columns:
            if col in column_index:
                target_tables[col] = column_index[col][0]  # Use first table that has it
            else:
                raise ValueError(f"Column '{col}' not found in any table in model {model_name}")

        # Find join path from base_table to target tables
        table_sequence = [base_table]
        join_keys = []
        seen_tables = {base_table}

        # Simple greedy algorithm: find edges from current tables to target tables
        edges = graph_config.get('edges', [])
        current_tables = {base_table}

        # Keep adding tables until we have all target tables
        while not all(tbl in seen_tables for tbl in target_tables.values()):
            added_table = False

            for edge in edges:
                edge_from = edge.get('from', '')
                edge_to = edge.get('to', '')

                # Skip cross-model edges for now
                if '.' in edge_to:
                    continue

                # Check if this edge connects a current table to a new table
                if edge_from in current_tables and edge_to not in seen_tables:
                    # Add this table to sequence
                    table_sequence.append(edge_to)
                    seen_tables.add(edge_to)
                    current_tables.add(edge_to)

                    # Extract join keys
                    on_conditions = edge.get('on', edge.get(True, []))
                    if on_conditions:
                        # Parse "col1=col2" format
                        join_pair = self._parse_join_condition(on_conditions[0])
                        join_keys.append(join_pair)

                    added_table = True
                    break

            if not added_table:
                raise ValueError(
                    f"Cannot find join path from {base_table} to {missing_columns}. "
                    f"Reached: {seen_tables}, Need: {set(target_tables.values())}"
                )

        return {
            'table_sequence': table_sequence,
            'join_keys': join_keys,
            'target_columns': target_tables
        }

    def _build_column_index(self, model_name: str) -> Dict[str, List[str]]:
        """
        Build reverse index: column_name -> [table_names].

        Args:
            model_name: Model to index

        Returns:
            Dict mapping column names to list of tables that have that column
        """
        index = {}
        model = self.load_model(model_name)
        tables = model.list_tables()

        # Index all tables (dims and facts)
        for table_name in tables.get('dimensions', []) + tables.get('facts', []):
            try:
                schema = model.get_table_schema(table_name)
                for column_name in schema.keys():
                    if column_name not in index:
                        index[column_name] = []
                    index[column_name].append(table_name)
            except Exception:
                continue

        return index

    def _parse_join_condition(self, condition: str) -> Tuple[str, str]:
        """
        Parse join condition like "ticker=ticker" or "exchange_code=exchange_code".

        Args:
            condition: Join condition string

        Returns:
            Tuple of (left_column, right_column)
        """
        parts = condition.split('=')
        if len(parts) == 2:
            return (parts[0].strip(), parts[1].strip())
        raise ValueError(f"Invalid join condition: {condition}")

    def _execute_auto_joins(
        self,
        model_name: str,
        join_plan: Dict[str, Any],
        required_columns: List[str],
        filters: Optional[Dict[str, Any]] = None
    ) -> DataFrame:
        """
        Execute the join plan to get required columns.

        Args:
            model_name: Model name
            join_plan: Join plan from _plan_auto_joins
            required_columns: Columns to return
            filters: Optional filters (not yet implemented)

        Returns:
            DataFrame with required columns
        """
        model = self.load_model(model_name)
        table_sequence = join_plan['table_sequence']
        join_keys = join_plan['join_keys']

        if self.backend == 'spark':
            # Spark: Use DataFrame API
            df = model.get_table(table_sequence[0])

            # Join each subsequent table
            for i, next_table in enumerate(table_sequence[1:]):
                right_df = model.get_table(next_table)
                left_col, right_col = join_keys[i]
                df = df.join(right_df, df[left_col] == right_df[right_col], 'left')

            # Select only required columns
            return self._select_columns(df, required_columns)

        else:
            # DuckDB: Use SQL for joins (more efficient)
            # Build SQL query with LEFT JOINS
            base_table = table_sequence[0]

            # Create temporary views from the tables
            temp_tables = {}
            try:
                for table_name in table_sequence:
                    df_temp = model.get_table(table_name)
                    temp_name = f"_autojoin_{table_name}"
                    # Register as temp table in DuckDB
                    temp_df = df_temp.df()  # Convert to pandas
                    print(f"DEBUG: Registering {temp_name}: shape={temp_df.shape}, columns={list(temp_df.columns)}")
                    self.connection.conn.register(temp_name, temp_df)
                    temp_tables[table_name] = temp_name

                # Build SQL with proper qualified column names to avoid ambiguity
                base_temp = temp_tables[base_table]
                select_cols = []
                for col in required_columns:
                    # Try to find which table has this column
                    found = False
                    for table_name in table_sequence:
                        try:
                            df = model.get_table(table_name)
                            if col in df.columns:
                                select_cols.append(f"{temp_tables[table_name]}.{col}")
                                found = True
                                break
                        except:
                            continue
                    if not found:
                        # If not found, just use unqualified column name
                        select_cols.append(col)

                sql = f"SELECT {', '.join(select_cols)} FROM {base_temp}"

                # Add each join - use PREVIOUS table, not base table
                # For chain: fact_prices -> dim_company -> dim_exchange
                # Join 1: fact_prices.ticker = dim_company.ticker
                # Join 2: dim_company.exchange_code = dim_exchange.exchange_code (NOT fact_prices!)
                for i in range(1, len(table_sequence)):
                    left_table = table_sequence[i - 1]
                    right_table = table_sequence[i]
                    left_temp = temp_tables[left_table]
                    right_temp = temp_tables[right_table]
                    left_col, right_col = join_keys[i - 1]
                    sql += f" LEFT JOIN {right_temp} ON {left_temp}.{left_col} = {right_temp}.{right_col}"

                print(f"DEBUG: Auto-join SQL: {sql}")

                # Execute the join query
                result = self.connection.conn.execute(sql)
                result_df = result.fetchdf()
                print(f"DEBUG: Query result: shape={result_df.shape}, columns={list(result_df.columns)}")
                print(f"DEBUG: First few rows:\n{result_df.head()}")

                # Unregister temp tables
                for temp_name in temp_tables.values():
                    try:
                        self.connection.conn.unregister(temp_name)
                    except:
                        pass

                # Convert to DuckDB relation
                final_relation = self.connection.conn.from_df(result_df)
                print(f"DEBUG: Final relation columns: {final_relation.columns}")
                return final_relation

            except Exception as e:
                print(f"ERROR: Auto-join SQL failed: {e}")
                import traceback
                traceback.print_exc()

                # Clean up temp tables
                for temp_name in temp_tables.values():
                    try:
                        self.connection.conn.unregister(temp_name)
                    except:
                        pass

                # Fall back to base table
                return model.get_table(table_sequence[0])

    def _aggregate_data(
        self,
        model_name: str,
        df: DataFrame,
        required_columns: List[str],
        group_by: List[str],
        aggregations: Optional[Dict[str, str]] = None
    ) -> DataFrame:
        """
        Aggregate data to a new grain using group_by and measure aggregations.

        Args:
            model_name: Name of the model (for measure metadata lookup)
            df: DataFrame to aggregate
            required_columns: All columns that should be in result
            group_by: Columns to group by (dimensions at new grain)
            aggregations: Optional dict mapping measure columns to agg functions.
                        If not provided, infers from measure metadata.

        Returns:
            Aggregated DataFrame

        Example:
            Input df: ticker-level daily prices (10M rows)
            group_by: ['trade_date', 'exchange_name']
            aggregations: {'close': 'avg', 'volume': 'sum'}
            Output: exchange-level daily prices (5 exchanges * 365 days = 1,825 rows)
        """
        print(f"🔢 Aggregating to grain: {group_by}")

        # Determine which columns are measures (need aggregation)
        measure_cols = [col for col in required_columns if col not in group_by]

        if not measure_cols:
            # No measures, just distinct dimensions
            if self.backend == 'spark':
                return df.select(*group_by).distinct()
            else:  # duckdb
                # DuckDB relations don't have .select(), need to use SQL
                distinct_query = f"SELECT DISTINCT {', '.join(group_by)} FROM df"
                return self.connection.conn.execute(distinct_query).df()

        # Get or infer aggregations for each measure
        if not aggregations:
            aggregations = self._infer_aggregations(model_name, measure_cols)

        print(f"   Measures: {aggregations}")

        # Apply aggregations based on backend
        if self.backend == 'spark':
            return self._aggregate_spark(df, group_by, aggregations)
        else:  # duckdb
            return self._aggregate_duckdb(df, group_by, aggregations)

    def _infer_aggregations(self, model_name: str, measure_cols: List[str]) -> Dict[str, str]:
        """
        Infer aggregation functions for measures from model metadata.

        Checks model config for measure definitions and uses specified aggregations.
        Falls back to sensible defaults: avg for prices, sum for volumes/counts.

        Args:
            model_name: Model to look up metadata
            measure_cols: Measure columns to infer aggregations for

        Returns:
            Dict mapping measure column to aggregation function
        """
        aggregations = {}

        try:
            model_config = self.registry.get_model_config(model_name)
            measures = model_config.get('measures', {})

            for col in measure_cols:
                # Check if measure is defined in config
                if col in measures:
                    measure_def = measures[col]
                    # Use configured aggregation if available
                    agg_func = measure_def.get('aggregation', 'avg')
                    aggregations[col] = agg_func
                else:
                    # Fallback defaults based on column name
                    aggregations[col] = self._default_aggregation(col)

        except Exception as e:
            print(f"   Warning: Could not load measure metadata: {e}")
            # Use defaults for all
            for col in measure_cols:
                aggregations[col] = self._default_aggregation(col)

        return aggregations

    def _default_aggregation(self, column_name: str) -> str:
        """
        Determine default aggregation based on column name.

        Args:
            column_name: Name of the measure column

        Returns:
            Aggregation function: avg, sum, max, min, or first
        """
        col_lower = column_name.lower()

        # Sum aggregations
        if any(term in col_lower for term in ['volume', 'count', 'total', 'quantity', 'qty']):
            return 'sum'

        # Max aggregations
        if any(term in col_lower for term in ['high', 'max', 'peak']):
            return 'max'

        # Min aggregations
        if any(term in col_lower for term in ['low', 'min']):
            return 'min'

        # Default to average for prices and other numeric measures
        return 'avg'

    def _aggregate_spark(
        self,
        df: DataFrame,
        group_by: List[str],
        aggregations: Dict[str, str]
    ) -> DataFrame:
        """
        Aggregate Spark DataFrame using groupBy and agg.

        Args:
            df: Spark DataFrame
            group_by: Columns to group by
            aggregations: Dict of column -> agg function

        Returns:
            Aggregated Spark DataFrame
        """
        from pyspark.sql import functions as F

        # Build aggregation expressions
        agg_exprs = []
        for col, agg_func in aggregations.items():
            if agg_func == 'avg':
                agg_exprs.append(F.avg(col).alias(col))
            elif agg_func == 'sum':
                agg_exprs.append(F.sum(col).alias(col))
            elif agg_func == 'max':
                agg_exprs.append(F.max(col).alias(col))
            elif agg_func == 'min':
                agg_exprs.append(F.min(col).alias(col))
            elif agg_func == 'count':
                agg_exprs.append(F.count(col).alias(col))
            elif agg_func == 'first':
                agg_exprs.append(F.first(col).alias(col))
            else:
                # Default to avg if unknown function
                print(f"   Warning: Unknown aggregation '{agg_func}' for {col}, using avg")
                agg_exprs.append(F.avg(col).alias(col))

        # Group and aggregate
        result = df.groupBy(*group_by).agg(*agg_exprs)

        # Reorder columns to match group_by + measures order
        measure_order = list(aggregations.keys())
        result = result.select(*group_by, *measure_order)

        return result

    def _aggregate_duckdb(
        self,
        df,
        group_by: List[str],
        aggregations: Dict[str, str]
    ) -> DataFrame:
        """
        Aggregate DuckDB relation using SQL GROUP BY.

        Args:
            df: DuckDB relation or pandas DataFrame
            group_by: Columns to group by
            aggregations: Dict of column -> agg function

        Returns:
            Aggregated DuckDB relation
        """
        # Build aggregation SQL
        select_parts = []

        # Add group by columns
        for col in group_by:
            select_parts.append(col)

        # Add aggregated measures
        for col, agg_func in aggregations.items():
            if agg_func == 'avg':
                select_parts.append(f"AVG({col}) as {col}")
            elif agg_func == 'sum':
                select_parts.append(f"SUM({col}) as {col}")
            elif agg_func == 'max':
                select_parts.append(f"MAX({col}) as {col}")
            elif agg_func == 'min':
                select_parts.append(f"MIN({col}) as {col}")
            elif agg_func == 'count':
                select_parts.append(f"COUNT({col}) as {col}")
            elif agg_func == 'first':
                select_parts.append(f"FIRST({col}) as {col}")
            else:
                # Default to AVG
                print(f"   Warning: Unknown aggregation '{agg_func}' for {col}, using AVG")
                select_parts.append(f"AVG({col}) as {col}")

        # Build complete SQL
        select_clause = ", ".join(select_parts)
        group_clause = ", ".join(group_by)
        sql = f"SELECT {select_clause} FROM df GROUP BY {group_clause}"

        print(f"   Aggregation SQL: {sql}")

        # Execute query
        try:
            result = self.connection.conn.execute(sql)
            return result.df()
        except Exception as e:
            print(f"   Error in DuckDB aggregation: {e}")
            # Return original data if aggregation fails
            return df
