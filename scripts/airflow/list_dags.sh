#!/bin/bash
#
# List Airflow DAGs from main venv
#

AIRFLOW_VENV="${AIRFLOW_VENV:-$HOME/airflow-venv}"
AIRFLOW_HOME="${AIRFLOW_HOME:-$HOME/airflow}"

export AIRFLOW_HOME
exec "$AIRFLOW_VENV/bin/airflow" dags list "$@"
