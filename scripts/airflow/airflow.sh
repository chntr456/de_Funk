#!/bin/bash
#
# Airflow CLI Wrapper - Run Airflow commands from main venv
#
# This wrapper delegates to airflow-venv while staying in your main venv.
#
# Usage:
#   ./scripts/airflow/airflow.sh dags list
#   ./scripts/airflow/airflow.sh dags trigger ingest_alpha_vantage
#   ./scripts/airflow/airflow.sh dags list-runs -d build_models
#   ./scripts/airflow/airflow.sh tasks list ingest_alpha_vantage
#

AIRFLOW_VENV="${AIRFLOW_VENV:-$HOME/airflow-venv}"
AIRFLOW_HOME="${AIRFLOW_HOME:-$HOME/airflow}"

if [ ! -f "$AIRFLOW_VENV/bin/airflow" ]; then
    echo "ERROR: Airflow not found at $AIRFLOW_VENV"
    echo "Run: ./orchestration/airflow/setup-airflow.sh"
    exit 1
fi

export AIRFLOW_HOME
exec "$AIRFLOW_VENV/bin/airflow" "$@"
