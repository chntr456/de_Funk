"""
Training methods for ForecastModel.

These methods implement ARIMA, Prophet, and RandomForest forecasting algorithms.
Extracted from original forecast_model.py and adapted for BaseModel architecture.
"""

import warnings
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import pandas as pd
import numpy as np

# Suppress warnings from forecasting libraries
warnings.filterwarnings('ignore')

# Forecasting libraries
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.statespace.sarimax import SARIMAX
try:
    from pmdarima import auto_arima
    HAS_AUTO_ARIMA = True
except ImportError:
    HAS_AUTO_ARIMA = False

try:
    from prophet import Prophet
    HAS_PROPHET = True
except ImportError:
    HAS_PROPHET = False

from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


def prepare_time_series(df: pd.DataFrame, target: str) -> pd.DataFrame:
    """
    Prepare time series data for forecasting.

    Args:
        df: Input dataframe with trade_date and target columns
        target: Target column (close or volume)

    Returns:
        Prepared time series DataFrame
    """
    ts = df[['trade_date', target]].copy()
    ts = ts.sort_values('trade_date')
    ts = ts.set_index('trade_date')
    ts.index = pd.to_datetime(ts.index)

    # Fill missing dates (market holidays)
    ts = ts.asfreq('D', method='ffill')

    return ts


def add_day_of_week_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add day-of-week features for models that support them."""
    df = df.copy()
    df['day_of_week'] = df.index.dayofweek
    df['is_monday'] = (df.index.dayofweek == 0).astype(int)
    df['is_friday'] = (df.index.dayofweek == 4).astype(int)
    return df


def create_lagged_features(df: pd.DataFrame, target: str, lags: List[int]) -> pd.DataFrame:
    """Create lagged features for ML models based on available data."""
    df_feat = df.copy()
    data_length = len(df)

    # Only create lags if we have enough data
    for lag in lags:
        if data_length > lag:
            df_feat[f'lag_{lag}'] = df_feat[target].shift(lag)

    # Only create rolling statistics if we have enough data
    if data_length >= 7:
        df_feat['rolling_mean_7'] = df_feat[target].rolling(window=7).mean()
        df_feat['rolling_std_7'] = df_feat[target].rolling(window=7).std()

    if data_length >= 30:
        df_feat['rolling_mean_30'] = df_feat[target].rolling(window=30).mean()
        df_feat['rolling_std_30'] = df_feat[target].rolling(window=30).std()

    # Drop rows with NaN due to lagging
    df_feat = df_feat.dropna()

    return df_feat


def train_arima_model(
    data_pdf: pd.DataFrame,
    ticker: str,
    target: str,
    lookback_days: int,
    forecast_horizon: int,
    day_of_week_adj: bool = True,
    seasonal: bool = False,
    auto: bool = True
) -> Tuple[object, Dict]:
    """
    Train ARIMA model for a single ticker.

    Args:
        data_pdf: Pandas DataFrame with training data
        ticker: Stock ticker
        target: Target variable (close or volume)
        lookback_days: Number of days to use for training
        forecast_horizon: Number of days to forecast
        day_of_week_adj: Whether to include day-of-week adjustments
        seasonal: Whether to use seasonal ARIMA
        auto: Whether to use auto_arima for parameter selection

    Returns:
        Tuple of (fitted_model, metadata)
    """
    if data_pdf.empty:
        raise ValueError(f"No data available for ticker {ticker}")

    # Prepare time series
    ts = prepare_time_series(data_pdf, target)

    # Use only the specified lookback period
    ts = ts.tail(lookback_days)

    if day_of_week_adj:
        ts = add_day_of_week_features(ts)
        exog = ts[['day_of_week']]
    else:
        exog = None

    # Train model
    if auto and HAS_AUTO_ARIMA:
        model = auto_arima(
            ts[target],
            exogenous=exog,
            seasonal=seasonal,
            m=5 if seasonal else 1,  # Weekly seasonality (5 trading days)
            suppress_warnings=True,
            stepwise=True,
            error_action='ignore'
        )
    else:
        # Default ARIMA parameters
        order = (1, 1, 1)
        if seasonal:
            model = SARIMAX(ts[target], exog=exog, order=order, seasonal_order=(1, 1, 1, 5))
        else:
            model = ARIMA(ts[target], exog=exog, order=order)
        model = model.fit()

    metadata = {
        'ticker': ticker,
        'target': target,
        'lookback_days': lookback_days,
        'forecast_horizon': forecast_horizon,
        'model_type': 'ARIMA',
        'training_samples': len(ts),
        'training_end': ts.index[-1].strftime('%Y-%m-%d'),
        'day_of_week_adj': day_of_week_adj
    }

    return model, metadata


def train_prophet_model(
    data_pdf: pd.DataFrame,
    ticker: str,
    target: str,
    lookback_days: int,
    forecast_horizon: int,
    day_of_week_adj: bool = True,
    seasonality_mode: str = 'multiplicative'
) -> Tuple[object, Dict]:
    """
    Train Prophet model for a single ticker.

    Args:
        data_pdf: Pandas DataFrame with training data
        ticker: Stock ticker
        target: Target variable (close or volume)
        lookback_days: Number of days to use for training
        forecast_horizon: Number of days to forecast
        day_of_week_adj: Whether to include day-of-week adjustments
        seasonality_mode: Seasonality mode ('additive' or 'multiplicative')

    Returns:
        Tuple of (fitted_model, metadata)
    """
    if not HAS_PROPHET:
        raise ImportError("Prophet library not installed. Install with: pip install prophet")

    if data_pdf.empty:
        raise ValueError(f"No data available for ticker {ticker}")

    # Prepare data for Prophet (requires 'ds' and 'y' columns)
    ts = prepare_time_series(data_pdf, target)
    ts = ts.tail(lookback_days)

    prophet_df = ts.reset_index()
    prophet_df.columns = ['ds', 'y']

    # Initialize Prophet model
    model = Prophet(
        seasonality_mode=seasonality_mode,
        daily_seasonality=False,
        weekly_seasonality=day_of_week_adj,
        yearly_seasonality=False
    )

    # Train model
    model.fit(prophet_df)

    metadata = {
        'ticker': ticker,
        'target': target,
        'lookback_days': lookback_days,
        'forecast_horizon': forecast_horizon,
        'model_type': 'Prophet',
        'training_samples': len(prophet_df),
        'training_end': prophet_df['ds'].max().strftime('%Y-%m-%d'),
        'seasonality_mode': seasonality_mode
    }

    return model, metadata


def train_random_forest_model(
    data_pdf: pd.DataFrame,
    ticker: str,
    target: str,
    lookback_days: int,
    forecast_horizon: int,
    n_estimators: int = 100,
    max_depth: int = 10
) -> Tuple[object, Dict]:
    """
    Train Random Forest model for a single ticker.

    Args:
        data_pdf: Pandas DataFrame with training data
        target: Target variable (close or volume)
        lookback_days: Number of days to use for training
        forecast_horizon: Number of days to forecast
        n_estimators: Number of trees in the forest
        max_depth: Maximum depth of trees

    Returns:
        Tuple of (fitted_model, metadata)
    """
    if data_pdf.empty:
        raise ValueError(f"No data available for ticker {ticker}")

    # Prepare time series
    ts = prepare_time_series(data_pdf, target)
    ts = ts.tail(lookback_days + 30)  # Extra data for lagging

    # Add features
    ts = add_day_of_week_features(ts)

    # Create lagged features
    lags = [1, 2, 3, 5, 7]
    ts_feat = create_lagged_features(ts, target, lags)

    # Keep only the lookback period after feature creation
    ts_feat = ts_feat.tail(lookback_days)

    # Prepare X and y
    feature_cols = [col for col in ts_feat.columns if col != target]
    X = ts_feat[feature_cols]
    y = ts_feat[target]

    # Train model
    model = RandomForestRegressor(
        n_estimators=n_estimators,
        max_depth=max_depth,
        random_state=42
    )
    model.fit(X, y)

    # Reset index to make it a regular column for the metadata
    ts_feat_reset = ts_feat.reset_index()
    ts_feat_reset = ts_feat_reset.rename(columns={'index': 'trade_date'})

    metadata = {
        'ticker': ticker,
        'target': target,
        'lookback_days': lookback_days,
        'forecast_horizon': forecast_horizon,
        'model_type': 'RandomForest',
        'training_samples': len(ts_feat),
        'training_end': ts_feat.index[-1].strftime('%Y-%m-%d'),
        'n_estimators': n_estimators,
        'max_depth': max_depth,
        'feature_cols': feature_cols,
        'training_data': ts_feat_reset  # Include training data for iterative forecasting
    }

    return model, metadata
