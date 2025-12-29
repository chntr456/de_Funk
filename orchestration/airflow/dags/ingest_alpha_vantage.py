"""
Alpha Vantage Ingestion DAG.

Triggers the existing AlphaVantageIngestor to fetch data from the API.
Handles rate limiting and prioritization internally.

Schedule: Daily after market close (4:30 PM ET)
"""

from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.providers.standard.operators.bash import BashOperator
from airflow.models import Variable

# =============================================================================
# Configuration - Read from Airflow Variables or use defaults
# =============================================================================

PROJECT_ROOT = Variable.get("de_funk_project_root",
                            default_var="/home/ms_trixie/PycharmProjects/de_Funk")
VENV_PATH = Variable.get("de_funk_venv_path",
                         default_var="/home/ms_trixie/venv")
STORAGE_PATH = Variable.get("de_funk_storage_path",
                            default_var="/home/ms_trixie/PycharmProjects/de_Funk/storage")

# Ingestion settings
MAX_TICKERS = int(Variable.get("ingest_max_tickers", default_var="100"))
DAYS = int(Variable.get("ingest_days", default_var="30"))

default_args = {
    'owner': 'de_funk',
    'depends_on_past': False,
    'email_on_failure': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

# =============================================================================
# DAG Definition
# =============================================================================

with DAG(
    dag_id='ingest_alpha_vantage',
    default_args=default_args,
    description='Ingest securities data from Alpha Vantage API',
    schedule='30 21 * * 1-5',  # 4:30 PM ET (21:30 UTC) Mon-Fri
    start_date=datetime(2025, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=['ingest', 'alpha_vantage', 'bronze'],
) as dag:

    # Seed tickers from LISTING_STATUS (if needed)
    seed_tickers = BashOperator(
        task_id='seed_tickers',
        bash_command=f"""
            cd {PROJECT_ROOT} && \
            source {VENV_PATH}/bin/activate && \
            python -m scripts.seed.seed_tickers --storage-path {STORAGE_PATH}
        """,
    )

    # Ingest prices (TIME_SERIES_DAILY)
    ingest_prices = BashOperator(
        task_id='ingest_prices',
        bash_command=f"""
            cd {PROJECT_ROOT} && \
            source {VENV_PATH}/bin/activate && \
            python -m scripts.ingest.run_bronze_ingestion \
                --storage-path {STORAGE_PATH} \
                --endpoints time_series_daily \
                --max-tickers {MAX_TICKERS} \
                --days {DAYS}
        """,
    )

    # Ingest company overview
    ingest_overview = BashOperator(
        task_id='ingest_overview',
        bash_command=f"""
            cd {PROJECT_ROOT} && \
            source {VENV_PATH}/bin/activate && \
            python -m scripts.ingest.run_bronze_ingestion \
                --storage-path {STORAGE_PATH} \
                --endpoints company_overview \
                --max-tickers {MAX_TICKERS}
        """,
    )

    # Ingest financial statements
    ingest_financials = BashOperator(
        task_id='ingest_financials',
        bash_command=f"""
            cd {PROJECT_ROOT} && \
            source {VENV_PATH}/bin/activate && \
            python -m scripts.ingest.run_bronze_ingestion \
                --storage-path {STORAGE_PATH} \
                --endpoints income_statement,balance_sheet,cash_flow,earnings \
                --max-tickers {MAX_TICKERS}
        """,
    )

    # Mark ingestion complete (for downstream DAG sensors)
    ingest_complete = BashOperator(
        task_id='ingest_complete',
        bash_command='echo "Alpha Vantage ingestion complete"',
    )

    # Flow: seed -> prices -> overview -> financials -> complete
    # Sequential due to API rate limits (uses single key pool internally)
    seed_tickers >> ingest_prices >> ingest_overview >> ingest_financials >> ingest_complete
