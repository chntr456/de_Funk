"""
Ray Remote Tasks for distributed execution.

These tasks are designed to run on Ray workers across the cluster.
Each task is self-contained and loads data from shared storage.

Usage:
    from orchestration.distributed.tasks import forecast_ticker, ingest_ticker

    # Submit tasks to cluster
    futures = [forecast_ticker.remote(ticker) for ticker in tickers]
    results = ray.get(futures)

Author: de_Funk Team
Date: December 2025
"""
from __future__ import annotations

from typing import Dict, List, Any, Optional
from pathlib import Path


def _get_ray():
    """Lazy import ray to avoid import errors when ray not installed."""
    try:
        import ray
        return ray
    except ImportError:
        raise ImportError(
            "Ray is not installed. Install with: pip install 'ray[default]'"
        )


# ============================================================================
# FORECASTING TASKS
# ============================================================================

def create_forecast_task():
    """
    Create the forecast_ticker remote task.

    Returns Ray remote function for forecasting a single ticker.
    """
    ray = _get_ray()

    @ray.remote
    def forecast_ticker(
        ticker: str,
        models: List[str] = None,
        horizon: int = 30,
        storage_path: str = "/shared/storage",
        min_data_points: int = 60
    ) -> Dict[str, Any]:
        """
        Run forecast for a single ticker on a Ray worker.

        This task runs independently on a worker node, loading data
        from shared storage and returning forecast results.

        Args:
            ticker: Ticker symbol to forecast
            models: List of forecast models to run ('arima', 'prophet', 'ets')
            horizon: Forecast horizon in days
            storage_path: Path to shared storage
            min_data_points: Minimum data points required

        Returns:
            Dict with forecast results or error
        """
        import pandas as pd
        import numpy as np

        if models is None:
            models = ['arima']

        # Load price data
        prices_path = Path(storage_path) / "silver" / "stocks" / "facts" / "fact_stock_prices"

        try:
            # Try Delta first, then Parquet
            delta_log = prices_path / "_delta_log"
            if delta_log.exists():
                # Use pyarrow for Delta
                from deltalake import DeltaTable
                dt = DeltaTable(str(prices_path))
                df = dt.to_pandas()
            else:
                df = pd.read_parquet(prices_path)

            # Filter for ticker
            ticker_df = df[df['ticker'] == ticker].copy()
            ticker_df = ticker_df.sort_values('trade_date')

            if len(ticker_df) < min_data_points:
                return {
                    'ticker': ticker,
                    'status': 'skipped',
                    'reason': f'insufficient_data ({len(ticker_df)} < {min_data_points})'
                }

            # Run forecasts
            results = {
                'ticker': ticker,
                'data_points': len(ticker_df),
                'forecasts': {},
                'status': 'success'
            }

            for model_type in models:
                try:
                    if model_type == 'arima':
                        forecast = _run_arima(ticker_df['close'].values, horizon)
                        results['forecasts']['arima'] = forecast

                    elif model_type == 'prophet':
                        forecast = _run_prophet(ticker_df, horizon)
                        results['forecasts']['prophet'] = forecast

                    elif model_type == 'ets':
                        forecast = _run_ets(ticker_df['close'].values, horizon)
                        results['forecasts']['ets'] = forecast

                except Exception as e:
                    results['forecasts'][model_type] = {'error': str(e)}

            return results

        except Exception as e:
            return {
                'ticker': ticker,
                'status': 'error',
                'error': str(e)
            }

    return forecast_ticker


def _run_arima(values: Any, horizon: int) -> Dict[str, Any]:
    """Run ARIMA forecast."""
    from statsmodels.tsa.arima.model import ARIMA
    import numpy as np

    # Fit ARIMA(5,1,0)
    model = ARIMA(values, order=(5, 1, 0))
    fitted = model.fit()

    # Forecast
    forecast = fitted.forecast(steps=horizon)

    return {
        'values': forecast.tolist(),
        'model': 'ARIMA(5,1,0)',
        'aic': fitted.aic
    }


def _run_prophet(df: Any, horizon: int) -> Dict[str, Any]:
    """Run Prophet forecast."""
    try:
        from prophet import Prophet
    except ImportError:
        return {'error': 'Prophet not installed'}

    # Prepare data for Prophet
    prophet_df = df[['trade_date', 'close']].copy()
    prophet_df.columns = ['ds', 'y']
    prophet_df['ds'] = pd.to_datetime(prophet_df['ds'])

    # Fit model
    model = Prophet(daily_seasonality=False, yearly_seasonality=True)
    model.fit(prophet_df)

    # Make future dataframe and predict
    future = model.make_future_dataframe(periods=horizon)
    forecast = model.predict(future)

    return {
        'values': forecast['yhat'].tail(horizon).tolist(),
        'lower': forecast['yhat_lower'].tail(horizon).tolist(),
        'upper': forecast['yhat_upper'].tail(horizon).tolist(),
        'model': 'Prophet'
    }


def _run_ets(values: Any, horizon: int) -> Dict[str, Any]:
    """Run ETS (Exponential Smoothing) forecast."""
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    import numpy as np

    # Fit ETS model
    model = ExponentialSmoothing(
        values,
        trend='add',
        seasonal=None,
        damped_trend=True
    )
    fitted = model.fit()

    # Forecast
    forecast = fitted.forecast(horizon)

    return {
        'values': forecast.tolist(),
        'model': 'ETS(A,Ad,N)',
        'aic': fitted.aic
    }


# ============================================================================
# INGESTION TASKS
# ============================================================================

def create_ingest_task():
    """
    Create the ingest_ticker remote task.

    Returns Ray remote function for ingesting data for a single ticker.
    """
    ray = _get_ray()

    @ray.remote
    def ingest_ticker(
        ticker: str,
        key_manager_handle: Any,
        data_types: List[str] = None,
        storage_path: str = "/shared/storage"
    ) -> Dict[str, Any]:
        """
        Ingest data for a single ticker on a Ray worker.

        Uses DistributedKeyManager for coordinated rate limiting.

        Args:
            ticker: Ticker symbol
            key_manager_handle: Ray Actor handle to DistributedKeyManager
            data_types: Data types to fetch ('prices', 'overview', 'technicals')
            storage_path: Path to shared storage

        Returns:
            Dict with ingestion results
        """
        import requests
        import pandas as pd
        from pathlib import Path

        if data_types is None:
            data_types = ['prices']

        results = {
            'ticker': ticker,
            'status': 'success',
            'data_types': {},
            'errors': []
        }

        for data_type in data_types:
            try:
                # Acquire API key from distributed manager
                key = ray.get(key_manager_handle.acquire_key.remote(timeout=120.0))
                if not key:
                    results['errors'].append(f"{data_type}: timeout waiting for API key")
                    results['status'] = 'partial'
                    continue

                try:
                    # Make API call based on data type
                    if data_type == 'prices':
                        url = (
                            f"https://www.alphavantage.co/query"
                            f"?function=TIME_SERIES_DAILY"
                            f"&symbol={ticker}"
                            f"&outputsize=full"
                            f"&apikey={key}"
                        )
                    elif data_type == 'overview':
                        url = (
                            f"https://www.alphavantage.co/query"
                            f"?function=OVERVIEW"
                            f"&symbol={ticker}"
                            f"&apikey={key}"
                        )
                    elif data_type == 'technicals':
                        url = (
                            f"https://www.alphavantage.co/query"
                            f"?function=RSI"
                            f"&symbol={ticker}"
                            f"&interval=daily"
                            f"&time_period=14"
                            f"&series_type=close"
                            f"&apikey={key}"
                        )
                    else:
                        results['errors'].append(f"Unknown data_type: {data_type}")
                        continue

                    response = requests.get(url, timeout=30)
                    data = response.json()

                    # Check for rate limit error
                    if 'Note' in data or 'Information' in data:
                        results['errors'].append(f"{data_type}: rate limited")
                        results['status'] = 'partial'
                        continue

                    # Store results
                    results['data_types'][data_type] = {
                        'status': 'success',
                        'records': len(data) if isinstance(data, dict) else 0
                    }

                finally:
                    # Always release the key back to pool
                    ray.get(key_manager_handle.release_key.remote(key))

            except Exception as e:
                results['errors'].append(f"{data_type}: {str(e)}")
                results['status'] = 'partial'

        if results['errors'] and not results['data_types']:
            results['status'] = 'failed'

        return results

    return ingest_ticker


def create_batch_ingest_task():
    """
    Create a batch ingestion task that processes multiple tickers.

    More efficient than individual tasks for large batches.
    """
    ray = _get_ray()

    @ray.remote
    def batch_ingest(
        tickers: List[str],
        key_manager_handle: Any,
        data_types: List[str] = None,
        storage_path: str = "/shared/storage"
    ) -> Dict[str, Any]:
        """
        Ingest data for multiple tickers sequentially on one worker.

        Args:
            tickers: List of ticker symbols
            key_manager_handle: Ray Actor handle to DistributedKeyManager
            data_types: Data types to fetch
            storage_path: Path to shared storage

        Returns:
            Dict with batch results
        """
        import requests
        import time

        if data_types is None:
            data_types = ['prices']

        results = {
            'total': len(tickers),
            'success': 0,
            'failed': 0,
            'tickers': {}
        }

        for ticker in tickers:
            ticker_result = {'status': 'success', 'data_types': {}}

            for data_type in data_types:
                # Acquire key
                key = ray.get(key_manager_handle.acquire_key.remote(timeout=120.0))
                if not key:
                    ticker_result['status'] = 'failed'
                    ticker_result['error'] = 'timeout waiting for key'
                    break

                try:
                    if data_type == 'prices':
                        url = (
                            f"https://www.alphavantage.co/query"
                            f"?function=TIME_SERIES_DAILY"
                            f"&symbol={ticker}&outputsize=compact&apikey={key}"
                        )
                    elif data_type == 'overview':
                        url = (
                            f"https://www.alphavantage.co/query"
                            f"?function=OVERVIEW&symbol={ticker}&apikey={key}"
                        )
                    else:
                        continue

                    response = requests.get(url, timeout=30)
                    data = response.json()

                    if 'Note' in data or 'Information' in data:
                        ticker_result['data_types'][data_type] = 'rate_limited'
                    else:
                        ticker_result['data_types'][data_type] = 'success'

                except Exception as e:
                    ticker_result['data_types'][data_type] = f'error: {str(e)}'

                finally:
                    ray.get(key_manager_handle.release_key.remote(key))

            results['tickers'][ticker] = ticker_result
            if ticker_result['status'] == 'success':
                results['success'] += 1
            else:
                results['failed'] += 1

        return results

    return batch_ingest


# ============================================================================
# MODEL BUILDING TASKS
# ============================================================================

def create_build_model_task():
    """
    Create the build_model remote task.

    Returns Ray remote function for building a model.
    """
    ray = _get_ray()

    @ray.remote
    def build_model_task(
        model_name: str,
        storage_path: str = "/shared/storage",
        config_path: str = None
    ) -> Dict[str, Any]:
        """
        Build a model on a Ray worker.

        Args:
            model_name: Name of model to build
            storage_path: Path to shared storage
            config_path: Path to config directory

        Returns:
            Dict with build results
        """
        # This would initialize Spark and run model build
        # For now, return placeholder
        return {
            'model': model_name,
            'status': 'not_implemented',
            'note': 'Model building on workers requires Spark setup'
        }

    return build_model_task


# Create the remote tasks
try:
    forecast_ticker = create_forecast_task()
    ingest_ticker = create_ingest_task()
    batch_ingest = create_batch_ingest_task()
    build_model_task = create_build_model_task()
except ImportError:
    # Ray not installed - create dummy functions
    forecast_ticker = None
    ingest_ticker = None
    batch_ingest = None
    build_model_task = None
