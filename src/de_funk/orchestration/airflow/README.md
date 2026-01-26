# Airflow Orchestration

Alternative to Ray-based orchestration using Apache Airflow.

## Why Airflow?

| Feature | Ray | Airflow |
|---------|-----|---------|
| DAG visualization | ❌ | ✅ Full UI |
| Scheduling | Manual | ✅ Cron-like |
| Retries | Custom | ✅ Declarative |
| Alerting | Custom | ✅ Built-in |
| Spark integration | Subprocess | ✅ Native operator |
| Learning curve | Medium | Low-Medium |

## Quick Setup

```bash
# 1. Install Airflow
pip install apache-airflow apache-airflow-providers-apache-spark

# 2. Initialize database
export AIRFLOW_HOME=~/airflow
airflow db init

# 3. Create admin user
airflow users create \
    --username admin \
    --firstname Admin \
    --lastname User \
    --role Admin \
    --email admin@example.com \
    --password admin

# 4. Copy DAG
cp orchestration/airflow/dags/de_funk_pipeline.py ~/airflow/dags/

# 5. Start Airflow (standalone mode for dev)
airflow standalone

# Or production mode (separate scheduler + webserver)
airflow scheduler &
airflow webserver -p 8080 &
```

## Web UI

Access at: http://localhost:8080

- **DAGs**: View all pipelines
- **Grid**: Task execution history
- **Graph**: Visual DAG dependencies
- **Logs**: Per-task logs

## DAG Structure

```
de_funk_pipeline
├── seed (TaskGroup)
│   ├── seed_tickers
│   └── seed_calendar
├── ingest (TaskGroup)
│   ├── ingest_prices
│   ├── ingest_overview
│   └── ingest_financials
├── silver (TaskGroup)
│   ├── build_temporal
│   ├── build_company
│   └── build_stocks
└── compute_technicals
```

## Configuration

Edit `dags/de_funk_pipeline.py`:

```python
PROJECT_ROOT = "/shared/de_Funk"
STORAGE_PATH = "/shared/storage"
SPARK_MASTER = "spark://192.168.1.212:7077"
```

## Scheduling

Default: Daily at 6 AM UTC

```python
schedule_interval='0 6 * * *'  # Cron format
```

Other options:
- `'@hourly'` - Every hour
- `'@daily'` - Every day at midnight
- `'0 */4 * * *'` - Every 4 hours
- `None` - Manual trigger only

## Production Deployment

For production, consider:

1. **Docker Compose** (easiest)
   ```bash
   curl -LfO 'https://airflow.apache.org/docs/apache-airflow/stable/docker-compose.yaml'
   docker-compose up -d
   ```

2. **Kubernetes** (scalable)
   ```bash
   helm repo add apache-airflow https://airflow.apache.org
   helm install airflow apache-airflow/airflow
   ```

## Spark Integration

The DAG uses `BashOperator` calling `submit-job.sh`. For direct integration:

```python
from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator

build_stocks = SparkSubmitOperator(
    task_id='build_stocks',
    application=f'{PROJECT_ROOT}/scripts/build/build_models.py',
    conn_id='spark_default',
    application_args=['--models', 'stocks', '--storage-root', STORAGE_PATH],
    packages='io.delta:delta-spark_2.13:4.0.0',
)
```

Configure Spark connection in Airflow UI:
- Admin → Connections → Add
- Conn Type: Spark
- Host: spark://192.168.1.212
- Port: 7077
