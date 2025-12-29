"""
Model Build DAG - Dynamic builder discovery.

Discovers model builders from BuilderRegistry and creates tasks
with proper dependencies based on each builder's depends_on attribute.

This DAG uses the existing infrastructure:
- models/base/builder.py - BuilderRegistry
- models/foundation/temporal/builder.py - TemporalBuilder
- models/domain/company/builder.py - CompanyBuilder
- models/domain/stocks/builder.py - StocksBuilder

Schedule: Daily at 5 AM UTC (after market data settles)
"""

from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sensors.external_task import ExternalTaskSensor
from airflow.models import Variable

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

# Models to build and their dependencies (mirrors BuilderRegistry)
# This is static for DAG parsing, but matches the registered builders
MODELS = {
    'temporal': {'depends_on': [], 'spark': True},
    'company': {'depends_on': [], 'spark': True},
    'stocks': {'depends_on': ['company'], 'spark': True},
}

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
    dag_id='build_models',
    default_args=default_args,
    description='Build Silver layer models using Spark cluster',
    schedule='0 5 * * *',  # Daily at 5 AM UTC
    start_date=datetime(2025, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=['build', 'silver', 'spark'],
) as dag:

    # Wait for ingestion to complete (optional - can be disabled)
    wait_for_ingest = ExternalTaskSensor(
        task_id='wait_for_ingest',
        external_dag_id='ingest_alpha_vantage',
        external_task_id='ingest_complete',
        mode='reschedule',
        timeout=3600,  # 1 hour
        poke_interval=60,
        allowed_states=['success'],
        failed_states=['failed', 'skipped'],
    )

    # Create build tasks for each model
    build_tasks = {}

    for model_name, config in MODELS.items():
        task = BashOperator(
            task_id=f'build_{model_name}',
            bash_command=f"""
                cd {PROJECT_ROOT} && \
                source {VENV_PATH}/bin/activate && \
                export SPARK_MASTER_URL="{SPARK_MASTER}" && \
                python -m scripts.build.build_models \
                    --models {model_name} \
                    --storage-path {STORAGE_PATH}
            """,
        )
        build_tasks[model_name] = task

    # Set dependencies based on model configuration
    for model_name, config in MODELS.items():
        task = build_tasks[model_name]

        if not config['depends_on']:
            # No model dependencies - depends on ingestion
            wait_for_ingest >> task
        else:
            # Depends on other models
            for dep in config['depends_on']:
                if dep in build_tasks:
                    build_tasks[dep] >> task

    # Ensure temporal runs after ingest (it has no model deps but needs bronze)
    wait_for_ingest >> build_tasks['temporal']

    # Mark build complete
    build_complete = BashOperator(
        task_id='build_complete',
        bash_command='echo "All models built successfully"',
    )

    # All build tasks lead to completion
    for task in build_tasks.values():
        task >> build_complete
