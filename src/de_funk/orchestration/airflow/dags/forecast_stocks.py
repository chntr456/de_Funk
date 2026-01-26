"""
Stock Forecasting DAG - Distributed forecasting via Spark.

Runs distributed ARIMA and Prophet forecasting on the Spark cluster.
Uses existing forecast infrastructure:
- scripts/forecast/run_distributed_forecast.py (ARIMA via Spark pandas_udf)
- scripts/forecast/run_batched_prophet.py (Prophet via multiprocessing)

Schedule: Manual trigger only (set schedule for automation)
"""

from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sensors.external_task import ExternalTaskSensor
from airflow.models import Variable
from airflow.utils.task_group import TaskGroup

# =============================================================================
# Configuration
# =============================================================================

PROJECT_ROOT = Variable.get("de_funk_project_root",
                            default_var="/home/ms_trixie/PycharmProjects/de_Funk")
VENV_PATH = Variable.get("de_funk_venv_path",
                         default_var="/home/ms_trixie/venv")
STORAGE_PATH = Variable.get("de_funk_storage_path",
                            default_var="/home/ms_trixie/PycharmProjects/de_Funk/storage")
SPARK_MASTER = Variable.get("spark_master_url",
                            default_var="spark://192.168.1.212:7077")

# Forecast settings
MAX_TICKERS = int(Variable.get("forecast_max_tickers", default_var="100"))
HORIZON = int(Variable.get("forecast_horizon", default_var="30"))
PROPHET_WORKERS = int(Variable.get("prophet_workers", default_var="8"))

default_args = {
    'owner': 'de_funk',
    'depends_on_past': False,
    'email_on_failure': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=10),
}

# =============================================================================
# DAG Definition
# =============================================================================

with DAG(
    dag_id='forecast_stocks',
    default_args=default_args,
    description='Distributed stock price forecasting',
    schedule=None,  # Manual trigger only (set cron for automation: '0 2 * * 0')
    start_date=datetime(2025, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=['forecast', 'stocks', 'spark', 'ml'],
) as dag:

    # Wait for model build to complete
    wait_for_build = ExternalTaskSensor(
        task_id='wait_for_build',
        external_dag_id='build_models',
        external_task_id='build_complete',
        mode='reschedule',
        timeout=7200,  # 2 hours
        poke_interval=120,
        allowed_states=['success'],
        failed_states=['failed', 'skipped'],
    )

    with TaskGroup(group_id='forecasting') as forecast_group:
        # ARIMA via Spark distributed (pandas_udf)
        # Distributes forecasting across all Spark workers
        forecast_arima = BashOperator(
            task_id='forecast_arima',
            bash_command=f"""
                cd {PROJECT_ROOT} && \
                source {VENV_PATH}/bin/activate && \
                export SPARK_MASTER_URL="{SPARK_MASTER}" && \
                python -m scripts.forecast.run_distributed_forecast \
                    --storage-path {STORAGE_PATH} \
                    --horizon {HORIZON} \
                    --max-tickers {MAX_TICKERS} \
                    --model arima
            """,
        )

        # Prophet via multiprocessing (doesn't serialize well for Spark)
        # Runs on head node with parallel workers
        forecast_prophet = BashOperator(
            task_id='forecast_prophet',
            bash_command=f"""
                cd {PROJECT_ROOT} && \
                source {VENV_PATH}/bin/activate && \
                python -m scripts.forecast.run_batched_prophet \
                    --storage-path {STORAGE_PATH} \
                    --horizon {HORIZON} \
                    --max-tickers {MAX_TICKERS} \
                    --workers {PROPHET_WORKERS}
            """,
        )

        # ARIMA and Prophet can run in parallel
        [forecast_arima, forecast_prophet]

    # Mark forecast complete
    forecast_complete = BashOperator(
        task_id='forecast_complete',
        bash_command='echo "Stock forecasting complete"',
    )

    # Flow
    wait_for_build >> forecast_group >> forecast_complete
