"""
de_Funk Production Pipeline DAG.

This DAG orchestrates the full data pipeline:
1. Seed reference data (tickers, calendar)
2. Ingest Bronze layer from APIs
3. Build Silver layer models via Spark
4. Compute technical indicators

Schedule: Daily at 6 AM UTC (after market close)

To use:
1. Install Airflow: pip install apache-airflow
2. Set AIRFLOW_HOME: export AIRFLOW_HOME=~/airflow
3. Initialize: airflow db init
4. Copy this file to $AIRFLOW_HOME/dags/
5. Start: airflow standalone
6. UI at: http://localhost:8080
"""

from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from airflow.providers.standard.operators.bash import BashOperator
from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator
from airflow.utils.task_group import TaskGroup


# =============================================================================
# Configuration
# =============================================================================

# Paths
PROJECT_ROOT = "/shared/de_Funk"
STORAGE_PATH = "/shared/storage"
VENV_PATH = "/home/ms_trixie/venv"
SPARK_HOME = f"{VENV_PATH}/lib/python3.11/site-packages/pyspark"

# Spark cluster
SPARK_MASTER = "spark://192.168.1.212:7077"
SPARK_CONN_ID = "spark_default"  # Configure in Airflow UI

# Forecast configuration
# Set via Airflow Variables or override here
FORECAST_MAX_TICKERS = 100  # Top N by market cap
FORECAST_HORIZON = 30  # Days to forecast

# Default args for all tasks
default_args = {
    'owner': 'de_funk',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}


# =============================================================================
# Task Functions (for PythonOperator)
# =============================================================================

def seed_tickers(**context):
    """Seed tickers from Alpha Vantage LISTING_STATUS."""
    import subprocess
    result = subprocess.run(
        [f"{VENV_PATH}/bin/python", "-m", "scripts.seed.seed_tickers",
         "--storage-path", STORAGE_PATH],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        raise Exception(f"Seed tickers failed: {result.stderr}")
    return result.stdout


def seed_calendar(**context):
    """Seed calendar dimension."""
    import subprocess
    result = subprocess.run(
        [f"{VENV_PATH}/bin/python", "-m", "scripts.seed.seed_calendar",
         "--storage-path", STORAGE_PATH],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        raise Exception(f"Seed calendar failed: {result.stderr}")
    return result.stdout


def ingest_endpoint(endpoint: str, max_tickers: int = None, **context):
    """Ingest a specific endpoint to Bronze."""
    import subprocess
    cmd = [
        f"{VENV_PATH}/bin/python", "-m", "scripts.ingest.run_bronze_ingestion",
        "--storage-path", STORAGE_PATH,
        "--endpoints", endpoint
    ]
    if max_tickers:
        cmd.extend(["--max-tickers", str(max_tickers)])

    result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"Ingest {endpoint} failed: {result.stderr}")
    return result.stdout


# =============================================================================
# DAG Definition
# =============================================================================

with DAG(
    dag_id='de_funk_pipeline',
    default_args=default_args,
    description='de_Funk Bronze → Silver data pipeline',
    schedule='0 6 * * *',  # Daily at 6 AM UTC (Airflow 3.x uses 'schedule' not 'schedule_interval')
    start_date=datetime(2025, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=['de_funk', 'etl', 'spark'],
) as dag:

    # -------------------------------------------------------------------------
    # Step 1: Seed Reference Data
    # -------------------------------------------------------------------------
    with TaskGroup(group_id='seed') as seed_group:
        seed_tickers_task = PythonOperator(
            task_id='seed_tickers',
            python_callable=seed_tickers,
        )

        seed_calendar_task = PythonOperator(
            task_id='seed_calendar',
            python_callable=seed_calendar,
        )

        # Can run in parallel
        [seed_tickers_task, seed_calendar_task]

    # -------------------------------------------------------------------------
    # Step 2: Bronze Ingestion (API calls)
    # -------------------------------------------------------------------------
    with TaskGroup(group_id='ingest') as ingest_group:
        # These are rate-limited, so they run sequentially within each group
        # but different endpoints can run in parallel if you have multiple API keys

        ingest_prices = PythonOperator(
            task_id='ingest_prices',
            python_callable=ingest_endpoint,
            op_kwargs={'endpoint': 'prices'},
        )

        ingest_overview = PythonOperator(
            task_id='ingest_overview',
            python_callable=ingest_endpoint,
            op_kwargs={'endpoint': 'overview'},
        )

        ingest_financials = PythonOperator(
            task_id='ingest_financials',
            python_callable=ingest_endpoint,
            op_kwargs={'endpoint': 'income,balance,cashflow,earnings'},
        )

        # Run in parallel (if you have multiple API keys)
        # Or sequentially if single key:
        ingest_prices >> ingest_overview >> ingest_financials

    # -------------------------------------------------------------------------
    # Step 3: Silver Layer Build (Spark Cluster)
    # -------------------------------------------------------------------------
    with TaskGroup(group_id='silver') as silver_group:
        # Using SparkSubmitOperator for true cluster submission
        # Alternative: BashOperator calling submit-job.sh

        build_temporal = BashOperator(
            task_id='build_temporal',
            bash_command=f"""
                cd {PROJECT_ROOT} && \
                source {VENV_PATH}/bin/activate && \
                ./scripts/spark-cluster/submit-job.sh \
                    scripts/build/build_models.py \
                    --models temporal \
                    --storage-root {STORAGE_PATH}
            """,
        )

        build_company = BashOperator(
            task_id='build_company',
            bash_command=f"""
                cd {PROJECT_ROOT} && \
                source {VENV_PATH}/bin/activate && \
                ./scripts/spark-cluster/submit-job.sh \
                    scripts/build/build_models.py \
                    --models company \
                    --storage-root {STORAGE_PATH}
            """,
        )

        build_stocks = BashOperator(
            task_id='build_stocks',
            bash_command=f"""
                cd {PROJECT_ROOT} && \
                source {VENV_PATH}/bin/activate && \
                ./scripts/spark-cluster/submit-job.sh \
                    scripts/build/build_models.py \
                    --models stocks \
                    --storage-root {STORAGE_PATH}
            """,
        )

        # Respect dependencies: temporal first, then company, then stocks
        build_temporal >> build_company >> build_stocks

    # -------------------------------------------------------------------------
    # Step 4: Technical Indicators
    # -------------------------------------------------------------------------
    compute_technicals = BashOperator(
        task_id='compute_technicals',
        bash_command=f"""
            cd {PROJECT_ROOT} && \
            source {VENV_PATH}/bin/activate && \
            ./scripts/spark-cluster/submit-job.sh \
                scripts/build/compute_technicals.py \
                --storage-path {STORAGE_PATH}
        """,
    )

    # -------------------------------------------------------------------------
    # Step 5: Forecasting (Distributed)
    # -------------------------------------------------------------------------
    with TaskGroup(group_id='forecasting') as forecast_group:
        # ARIMA via Spark distributed (pandas_udf)
        # Runs on Spark cluster - distributes across all workers
        # Uses top N tickers by market cap for efficiency
        forecast_arima = BashOperator(
            task_id='forecast_arima',
            bash_command=f"""
                cd {PROJECT_ROOT} && \
                source {VENV_PATH}/bin/activate && \
                ./scripts/spark-cluster/submit-job.sh \
                    scripts/forecast/run_distributed_forecast.py \
                    --storage-path {STORAGE_PATH} \
                    --horizon {FORECAST_HORIZON} \
                    --max-tickers {FORECAST_MAX_TICKERS}
            """,
        )

        # Prophet via multiprocessing (doesn't serialize well for Spark)
        # Runs on head node with parallel workers
        # Uses top N tickers by market cap for efficiency
        forecast_prophet = BashOperator(
            task_id='forecast_prophet',
            bash_command=f"""
                cd {PROJECT_ROOT} && \
                source {VENV_PATH}/bin/activate && \
                python -m scripts.forecast.run_batched_prophet \
                    --storage-path {STORAGE_PATH} \
                    --horizon {FORECAST_HORIZON} \
                    --max-tickers {FORECAST_MAX_TICKERS} \
                    --workers 8
            """,
        )

        # ARIMA and Prophet can run in parallel
        [forecast_arima, forecast_prophet]

    # -------------------------------------------------------------------------
    # DAG Flow
    # -------------------------------------------------------------------------
    seed_group >> ingest_group >> silver_group >> compute_technicals >> forecast_group


# =============================================================================
# Additional DAGs (Optional)
# =============================================================================

# You could also create separate DAGs for:
# - Hourly price updates (intraday)
# - Weekly full refresh
# - Monthly data quality checks
# - GPU forecasting (when ready): add forecast_gpu task using Chronos
