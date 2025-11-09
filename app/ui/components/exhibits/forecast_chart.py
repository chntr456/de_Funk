"""
Forecast chart exhibit component for displaying time series predictions.

Renders forecast data with:
- Historical actual values
- Predicted values from multiple models
- Confidence intervals (shaded areas)
- Interactive hover tooltips
- Model comparison
- Theme support
- BaseExhibitRenderer pattern with tabbed configuration
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import duckdb
from .base_renderer import BaseExhibitRenderer


def load_forecast_data(ticker: str, target: str = "price") -> pd.DataFrame:
    """
    Load forecast data for a ticker (case-insensitive).

    Args:
        ticker: Stock ticker symbol (case-insensitive)
        target: "price" or "volume"

    Returns:
        DataFrame with forecast data
    """
    forecast_path = f"storage/silver/forecast/facts/forecast_{target}"

    try:
        con = duckdb.connect(database=':memory:')
        # Use UPPER() for case-insensitive ticker matching
        query = f"""
        SELECT *
        FROM read_parquet('{forecast_path}/**/*.parquet')
        WHERE UPPER(ticker) = UPPER('{ticker}')
        ORDER BY prediction_date, model_name
        """
        df = con.execute(query).fetchdf()
        con.close()
        return df
    except Exception as e:
        st.warning(f"Could not load forecast data: {e}")
        return pd.DataFrame()


def load_actual_data(ticker: str, days: int = 90, start_date: str = None, end_date: str = None) -> pd.DataFrame:
    """
    Load actual historical data for comparison (case-insensitive).

    Args:
        ticker: Stock ticker symbol (case-insensitive)
        days: Number of days of history to load (used if start_date/end_date not provided)
        start_date: Optional start date (YYYY-MM-DD format or date object)
        end_date: Optional end date (YYYY-MM-DD format or date object)

    Returns:
        DataFrame with actual prices/volumes
    """
    # Try Silver layer first, fallback to Bronze
    silver_path = "storage/silver/company/facts/fact_prices"
    bronze_path = "storage/bronze/prices_daily"

    try:
        con = duckdb.connect(database=':memory:')

        # Try Silver layer first
        try:
            query_check = f"""
            SELECT COUNT(*) as cnt FROM read_parquet('{silver_path}/**/*.parquet')
            WHERE UPPER(ticker) = UPPER('{ticker}')
            """
            con.execute(query_check)
            prices_path = silver_path
        except:
            # Fallback to Bronze
            prices_path = bronze_path

        # Build query based on date parameters
        if start_date and end_date:
            # Use explicit date range from filter
            query = f"""
            SELECT trade_date, ticker, close, volume
            FROM read_parquet('{prices_path}/**/*.parquet')
            WHERE UPPER(ticker) = UPPER('{ticker}')
              AND trade_date >= DATE '{start_date}'
              AND trade_date <= DATE '{end_date}'
            ORDER BY trade_date
            """
        else:
            # Get the latest N days of data (don't use datetime.now() - use actual data max date)
            query = f"""
            WITH ticker_data AS (
                SELECT trade_date, ticker, close, volume
                FROM read_parquet('{prices_path}/**/*.parquet')
                WHERE UPPER(ticker) = UPPER('{ticker}')
            ),
            date_range AS (
                SELECT MAX(trade_date) as max_date FROM ticker_data
            )
            SELECT t.trade_date, t.ticker, t.close, t.volume
            FROM ticker_data t
            CROSS JOIN date_range dr
            WHERE t.trade_date >= DATE_SUB(dr.max_date, INTERVAL {days} DAYS)
            ORDER BY t.trade_date
            """
        df = con.execute(query).fetchdf()
        con.close()
        return df
    except Exception as e:
        st.warning(f"Could not load actual data from {prices_path}: {e}")
        return pd.DataFrame()


def load_forecast_metrics(ticker: str = None) -> pd.DataFrame:
    """
    Load forecast accuracy metrics (case-insensitive).

    Args:
        ticker: Optional ticker filter (case-insensitive)

    Returns:
        DataFrame with metrics
    """
    metrics_path = "storage/silver/forecast/facts/forecast_metrics"

    try:
        con = duckdb.connect(database=':memory:')
        query = f"""
        SELECT *
        FROM read_parquet('{metrics_path}/**/*.parquet')
        """
        if ticker:
            # Use UPPER() for case-insensitive ticker matching
            query += f" WHERE UPPER(ticker) = UPPER('{ticker}')"
        query += " ORDER BY metric_date DESC, ticker, model_name"

        df = con.execute(query).fetchdf()
        con.close()
        return df
    except Exception as e:
        st.warning(f"Could not load metrics: {e}")
        return pd.DataFrame()


class ForecastChartRenderer(BaseExhibitRenderer):
    """Forecast chart renderer with BaseExhibitRenderer pattern."""

    def __init__(self, exhibit, pdf: pd.DataFrame = None, in_collapsible: bool = False):
        """
        Initialize forecast chart renderer.

        Args:
            exhibit: Exhibit configuration
            pdf: Optional pre-loaded data (not used, we load forecast data directly)
            in_collapsible: True if already rendering inside a collapsible section
        """
        # Create empty DataFrame for base class
        super().__init__(exhibit, pd.DataFrame())
        self.ticker = None
        self.target = getattr(exhibit, 'target', 'price')
        self.selected_models = []
        self.in_collapsible = in_collapsible
        # Configurable parameters
        self.history_days = getattr(exhibit, 'history_days', 90)  # Days of historical data to show
        self.default_ticker = getattr(exhibit, 'default_ticker', None)  # Optional default ticker

    def render(self):
        """Override render to add custom ticker/target selection."""
        # Render title and description
        if self.exhibit.title:
            st.subheader(self.exhibit.title)

        if self.exhibit.description:
            st.caption(self.exhibit.description)

        # Define the configuration UI rendering function
        def render_configuration_ui():
            # Create tabs
            tabs = st.tabs(["➖ Hide", "🎯 Stock & Target", "📊 Models"])

            # Tab 0: Hide (empty)
            with tabs[0]:
                pass

            # Tab 1: Stock & Target selection
            with tabs[1]:
                # Get available tickers from actual data
                available_tickers = self._get_available_tickers()

                col1, col2 = st.columns([2, 1])

                with col1:
                    # Determine default ticker from multiple sources (priority order):
                    # 1. Session state (user's last selection)
                    # 2. Global filter
                    # 3. Exhibit config default_ticker
                    # 4. First available ticker
                    default_ticker = st.session_state.get('selected_ticker')

                    if not default_ticker and 'filter_ticker' in st.session_state and st.session_state['filter_ticker']:
                        # Use first ticker from global filter
                        ticker_options = st.session_state['filter_ticker']
                        if isinstance(ticker_options, list) and ticker_options:
                            default_ticker = ticker_options[0]
                        elif isinstance(ticker_options, str):
                            default_ticker = ticker_options

                    if not default_ticker:
                        # Use exhibit config default
                        default_ticker = self.default_ticker

                    if not default_ticker and available_tickers:
                        # Use first available ticker
                        default_ticker = available_tickers[0]

                    # Use selectbox if we have available tickers, otherwise text input
                    if available_tickers:
                        # Ensure default is in available tickers
                        if default_ticker and default_ticker not in available_tickers:
                            default_ticker = available_tickers[0]

                        self.ticker = st.selectbox(
                            "Ticker Symbol",
                            options=available_tickers,
                            index=available_tickers.index(default_ticker) if default_ticker and default_ticker in available_tickers else 0,
                            key=f"ticker_{self.exhibit.id}",
                            help=f"Select from {len(available_tickers)} available tickers with historical data"
                        )
                    else:
                        self.ticker = st.text_input(
                            "Ticker Symbol",
                            value=default_ticker or "",
                            key=f"ticker_{self.exhibit.id}",
                            help="Enter a ticker symbol"
                        )

                    st.session_state['selected_ticker'] = self.ticker

                with col2:
                    target_options = ["price", "volume"]
                    default_idx = target_options.index(self.target) if self.target in target_options else 0
                    self.target = st.selectbox(
                        "Forecast Target",
                        target_options,
                        index=default_idx,
                        key=f"target_{self.exhibit.id}"
                    )

            # Tab 2: Model selection
            with tabs[2]:
                # Load forecast data to get available models
                forecast_df = load_forecast_data(self.ticker, self.target)

                if forecast_df.empty:
                    st.info(f"No forecast data available for {self.ticker}. Run forecasts first using: python scripts/run_forecasts.py --tickers {self.ticker}")
                    return

                # Get available models
                available_models = forecast_df['model_name'].unique().tolist()

                # Check for global model filter
                default_models = available_models[:3] if len(available_models) > 3 else available_models
                if 'filter_model_name' in st.session_state and st.session_state['filter_model_name']:
                    global_models = st.session_state['filter_model_name']
                    if isinstance(global_models, list):
                        default_models = [m for m in global_models if m in available_models]
                    elif isinstance(global_models, str) and global_models in available_models:
                        default_models = [global_models]

                self.selected_models = st.multiselect(
                    "Select Models to Display",
                    options=available_models,
                    default=default_models,
                    key=f"models_{self.exhibit.id}",
                    help="Choose which forecast models to compare"
                )

                if not self.selected_models:
                    st.warning("Please select at least one model to display")
                    return

            # Render chart
            if self.ticker and self.selected_models:
                self.render_chart()

        # If already in a collapsible section, don't create another expander
        if self.in_collapsible:
            render_configuration_ui()
        else:
            # Create configuration expander
            with st.expander("⚙️ Configuration", expanded=True):
                render_configuration_ui()

    def _get_available_tickers(self) -> list:
        """
        Get list of available tickers from historical price data.

        Returns:
            List of ticker symbols
        """
        try:
            con = duckdb.connect(database=':memory:')

            # Try Silver first, fallback to Bronze
            for path in ["storage/silver/company/facts/fact_prices", "storage/bronze/prices_daily"]:
                try:
                    query = f"""
                    SELECT DISTINCT ticker
                    FROM read_parquet('{path}/**/*.parquet')
                    ORDER BY ticker
                    """
                    df = con.execute(query).fetchdf()
                    con.close()
                    return df['ticker'].tolist()
                except:
                    continue

            con.close()
            return []
        except:
            return []

    def render_chart(self):
        """Render the forecast chart with confidence intervals."""
        # Check for global date range filter
        start_date = None
        end_date = None

        # Check session state for date filters (multiple possible keys)
        date_filter_keys = ['filter_trade_date', 'filter_date_range', 'date_range']
        for key in date_filter_keys:
            if key in st.session_state:
                date_filter = st.session_state[key]
                if isinstance(date_filter, dict):
                    start_date = date_filter.get('start')
                    end_date = date_filter.get('end')
                    # Convert to string if date object
                    if start_date and hasattr(start_date, 'isoformat'):
                        start_date = start_date.isoformat()
                    if end_date and hasattr(end_date, 'isoformat'):
                        end_date = end_date.isoformat()
                    break

        # Load actual historical data
        actual_df = load_actual_data(
            self.ticker,
            days=self.history_days,
            start_date=start_date,
            end_date=end_date
        )

        if actual_df.empty:
            st.warning(f"No historical data available for {self.ticker}")
            st.info("Please ensure price data exists in storage/bronze/prices_daily or storage/silver/company/facts/fact_prices")
            return

        # Load forecast data
        forecast_df = load_forecast_data(self.ticker, self.target)

        # Check if we have forecast data
        has_forecasts = not forecast_df.empty

        if not has_forecasts:
            st.info(f"ℹ️ No forecast data available for {self.ticker}. Showing historical data only.")
            st.caption(f"To generate forecasts, run: `python scripts/run_forecasts.py --tickers {self.ticker}`")

        # Filter to selected models if we have forecasts
        if has_forecasts and self.selected_models:
            forecast_df = forecast_df[forecast_df['model_name'].isin(self.selected_models)]
            if forecast_df.empty:
                st.info(f"No data available for selected models. Showing historical data only.")
                has_forecasts = False

        # Create plotly figure
        fig = go.Figure()

        # Add actual historical data
        y_col = 'close' if self.target == 'price' else 'volume'
        fig.add_trace(go.Scatter(
            x=actual_df['trade_date'],
            y=actual_df[y_col],
            mode='lines',
            name='Actual',
            line=dict(color='#2E86AB', width=2),
            hovertemplate='<b>Actual</b><br>Date: %{x}<br>Value: %{y:,.2f}<extra></extra>'
        ))

        # Add forecast lines with confidence intervals if we have forecasts
        if has_forecasts:
            # Color palette for different models
            colors = ['#A23B72', '#F18F01', '#C73E1D', '#6A994E', '#BC4B51', '#8B5A3C']

            # Add forecast lines with confidence intervals for each model
            for i, model in enumerate(self.selected_models):
                model_data = forecast_df[forecast_df['model_name'] == model].copy()
                model_data = model_data.sort_values('prediction_date')

                if model_data.empty:
                    continue

                color = colors[i % len(colors)]

                # Confidence interval (shaded area)
                y_col_pred = 'predicted_close' if self.target == 'price' else 'predicted_volume'

                # Check if confidence bounds exist
                if 'upper_bound' in model_data.columns and 'lower_bound' in model_data.columns:
                    fig.add_trace(go.Scatter(
                        x=pd.concat([model_data['prediction_date'], model_data['prediction_date'][::-1]]),
                        y=pd.concat([model_data['upper_bound'], model_data['lower_bound'][::-1]]),
                        fill='toself',
                        fillcolor=f'rgba({int(color[1:3], 16)}, {int(color[3:5], 16)}, {int(color[5:7], 16)}, 0.2)',
                        line=dict(color='rgba(255,255,255,0)'),
                        showlegend=False,
                        name=f'{model} CI',
                        hoverinfo='skip'
                    ))

                # Forecast line
                customdata = model_data['confidence'] if 'confidence' in model_data.columns else None
                fig.add_trace(go.Scatter(
                    x=model_data['prediction_date'],
                    y=model_data[y_col_pred],
                    mode='lines+markers',
                    name=model,
                    line=dict(color=color, width=2, dash='dash'),
                    marker=dict(size=6),
                    hovertemplate=f'<b>{model}</b><br>Date: %{{x}}<br>Predicted: %{{y:,.2f}}<extra></extra>',
                    customdata=customdata
                ))

        # Apply theme from base class
        fig = self.apply_theme_to_figure(fig)

        # Update specific settings for forecast chart
        fig.update_layout(
            xaxis_title='Date',
            yaxis_title='Price ($)' if self.target == 'price' else 'Volume',
            hovermode='x unified',
            height=500,
            legend=dict(x=0.01, y=0.99)
        )

        # Render chart
        config = self.get_plotly_config()
        st.plotly_chart(fig, use_container_width=True, config=config, key=f"chart_{self.exhibit.id}")

        # Display forecast metrics only if we have forecasts
        if has_forecasts:
            st.subheader("Forecast Accuracy Metrics")

            metrics_df = load_forecast_metrics(self.ticker)

            if not metrics_df.empty and self.selected_models:
                # Filter to selected models
                metrics_display = metrics_df[metrics_df['model_name'].isin(self.selected_models)].copy()

                if not metrics_display.empty:
                    # Format metrics for display
                    metrics_display = metrics_display[[
                        'model_name', 'mae', 'rmse', 'mape', 'r2_score', 'num_predictions'
                    ]].round(4)

                    metrics_display.columns = [
                        'Model', 'MAE', 'RMSE', 'MAPE (%)', 'R²', 'Predictions'
                    ]

                    st.dataframe(
                        metrics_display,
                        use_container_width=True,
                        hide_index=True
                    )

                    # Show best model
                    best_model = metrics_display.loc[metrics_display['R²'].idxmax(), 'Model']
                    st.success(f"Best performing model: **{best_model}** (highest R² score)")
                else:
                    st.info("No accuracy metrics available for selected models")
            else:
                st.info("No accuracy metrics available. Metrics are calculated during forecast generation.")


def render_forecast_chart(exhibit, pdf: pd.DataFrame = None, in_collapsible: bool = False):
    """
    Render forecast chart with confidence intervals.

    Args:
        exhibit: Exhibit configuration
        pdf: Optional pre-loaded data (not used, we load forecast-specific data)
        in_collapsible: True if already rendering inside a collapsible section
    """
    renderer = ForecastChartRenderer(exhibit, pdf, in_collapsible=in_collapsible)
    renderer.render()


def render_forecast_metrics_table(exhibit, pdf: pd.DataFrame = None):
    """
    Render forecast metrics as a table.

    Args:
        exhibit: Exhibit configuration
        pdf: Optional pre-loaded data
    """
    st.subheader(exhibit.title)

    if exhibit.description:
        st.caption(exhibit.description)

    # Load metrics
    metrics_df = load_forecast_metrics()

    if metrics_df.empty:
        st.info("No forecast metrics available. Run forecasts first using: python scripts/run_forecasts.py")
        return

    # Add filters
    col1, col2 = st.columns(2)

    with col1:
        tickers = metrics_df['ticker'].unique().tolist()
        selected_ticker = st.selectbox(
            "Filter by Ticker",
            options=['All'] + tickers,
            key=f"metrics_ticker_{exhibit.id}"
        )

    with col2:
        models = metrics_df['model_name'].unique().tolist()
        selected_model = st.selectbox(
            "Filter by Model",
            options=['All'] + models,
            key=f"metrics_model_{exhibit.id}"
        )

    # Apply filters
    if selected_ticker != 'All':
        metrics_df = metrics_df[metrics_df['ticker'] == selected_ticker]

    if selected_model != 'All':
        metrics_df = metrics_df[metrics_df['model_name'] == selected_model]

    # Format for display
    display_df = metrics_df[[
        'ticker', 'model_name', 'mae', 'rmse', 'mape', 'r2_score',
        'num_predictions', 'avg_error_pct', 'metric_date'
    ]].copy()

    display_df.columns = [
        'Ticker', 'Model', 'MAE', 'RMSE', 'MAPE (%)', 'R²',
        'Predictions', 'Avg Error (%)', 'Date'
    ]

    # Round numeric columns
    numeric_cols = ['MAE', 'RMSE', 'MAPE (%)', 'R²', 'Avg Error (%)']
    for col in numeric_cols:
        if col in display_df.columns:
            display_df[col] = display_df[col].round(4)

    # Display table
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True
    )

    # Summary statistics
    st.subheader("Summary Statistics")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Avg MAE", f"{display_df['MAE'].mean():.2f}")

    with col2:
        st.metric("Avg RMSE", f"{display_df['RMSE'].mean():.2f}")

    with col3:
        st.metric("Avg MAPE", f"{display_df['MAPE (%)'].mean():.2f}%")

    with col4:
        st.metric("Avg R²", f"{display_df['R²'].mean():.4f}")
