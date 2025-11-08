# Data Pipeline - Bronze Storage

## Overview

The **Bronze Layer** is the landing zone for raw data from external APIs. It stores data in its original form with minimal transformations, serving as an immutable historical record.

## Storage Architecture

### Directory Structure

```
storage/bronze/
├── polygon/                         # Provider name
│   ├── prices_daily/                # Dataset name
│   │   ├── ticker=AAPL/             # Partition level 1
│   │   │   ├── date=2024-01-01/     # Partition level 2
│   │   │   │   └── data.parquet
│   │   │   ├── date=2024-01-02/
│   │   │   │   └── data.parquet
│   │   │   └── ...
│   │   ├── ticker=GOOGL/
│   │   │   └── ...
│   │   └── _metadata.json
│   │
│   ├── ref_tickers/
│   │   ├── ingestion_date=2024-01-01/
│   │   │   └── data.parquet
│   │   └── _metadata.json
│   │
│   └── news/
│       └── ...
│
├── bls/
│   ├── unemployment/
│   └── cpi/
│
└── chicago/
    ├── building_permits/
    └── unemployment_rates/
```

### Partition Strategy

**Time-based partitioning**: Most datasets partition by date
```
prices_daily/
  date=2024-01-01/
  date=2024-01-02/
  ...
```

**Entity-based partitioning**: High-volume datasets add entity partitions
```
prices_daily/
  ticker=AAPL/
    date=2024-01-01/
    date=2024-01-02/
  ticker=GOOGL/
    ...
```

**Ingestion-based partitioning**: Reference data partitions by ingestion date
```
ref_tickers/
  ingestion_date=2024-01-01/
  ingestion_date=2024-02-01/
  ...
```

## Bronze Sink Implementation

```python
# File: datapipelines/ingestors/bronze_sink.py

class BronzeSink:
    """Handles writes to Bronze layer."""

    def __init__(self, storage_cfg):
        self.storage_cfg = storage_cfg
        self.bronze_root = Path(storage_cfg['roots']['bronze'])

    def write(self, provider, dataset, df, partition_keys=None):
        """
        Write DataFrame to Bronze with partitioning.

        Args:
            provider: Provider name (e.g., 'polygon')
            dataset: Dataset name (e.g., 'prices_daily')
            df: Spark or Pandas DataFrame
            partition_keys: Dict of partition columns and values
        """
        # Build output path
        output_path = self.bronze_root / provider / dataset

        # Add partition directories
        if partition_keys:
            for key, value in partition_keys.items():
                output_path = output_path / f"{key}={value}"

        # Add ingestion metadata
        df = self._add_metadata(df, provider, dataset)

        # Write Parquet
        output_path.mkdir(parents=True, exist_ok=True)

        if hasattr(df, 'write'):  # Spark DataFrame
            df.write.mode('overwrite').parquet(str(output_path))
        else:  # Pandas DataFrame
            df.to_parquet(
                output_path / "data.parquet",
                compression='snappy',
                index=False
            )

        # Write metadata file
        self._write_metadata(provider, dataset, output_path, df)

    def write_partitioned(self, provider, dataset, df, partition_cols):
        """
        Write DataFrame with Spark partitioning.

        Args:
            provider: Provider name
            dataset: Dataset name
            df: Spark DataFrame
            partition_cols: List of columns to partition by
        """
        output_path = self.bronze_root / provider / dataset

        # Add metadata
        df = self._add_metadata(df, provider, dataset)

        # Write with Spark partitioning
        (
            df.write
            .mode('overwrite')
            .partitionBy(*partition_cols)
            .parquet(str(output_path))
        )

        # Write metadata
        self._write_metadata(provider, dataset, output_path, df)

    def _add_metadata(self, df, provider, dataset):
        """Add ingestion metadata columns."""
        from pyspark.sql import functions as F

        return df.withColumn(
            "ingestion_timestamp", F.current_timestamp()
        ).withColumn(
            "source_provider", F.lit(provider)
        ).withColumn(
            "source_dataset", F.lit(dataset)
        )

    def _write_metadata(self, provider, dataset, path, df):
        """Write dataset metadata file."""
        import json

        metadata = {
            "provider": provider,
            "dataset": dataset,
            "path": str(path),
            "row_count": df.count() if hasattr(df, 'count') else len(df),
            "schema": self._get_schema(df),
            "ingestion_time": datetime.now().isoformat(),
            "format": "parquet",
            "compression": "snappy"
        }

        metadata_path = self.bronze_root / provider / dataset / "_metadata.json"
        metadata_path.parent.mkdir(parents=True, exist_ok=True)

        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)

    def _get_schema(self, df):
        """Extract schema from DataFrame."""
        if hasattr(df, 'schema'):  # Spark
            return {field.name: str(field.dataType) for field in df.schema.fields}
        else:  # Pandas
            return {col: str(dtype) for col, dtype in df.dtypes.items()}
```

## Data Retention

### Immutability

Bronze data is **append-only** and never modified:

```python
# Good - append new data
df.write.mode('append').parquet(bronze_path)

# Bad - overwriting historical data
df.write.mode('overwrite').parquet(bronze_path)
```

### Archival Strategy

Old data moves to cold storage after retention period:

```python
def archive_old_data(dataset, retention_days=365):
    """Archive data older than retention period."""
    cutoff_date = datetime.now() - timedelta(days=retention_days)

    for partition in list_partitions(dataset):
        partition_date = parse_partition_date(partition)

        if partition_date < cutoff_date:
            # Move to archive
            archive_path = f"s3://archive-bucket/{dataset}/{partition}"
            move_partition(partition, archive_path)

            # Delete from active storage
            delete_partition(partition)
```

## Performance Optimization

### Partition Pruning

Queries benefit from partition pruning:

```python
# Only reads January 2024 partition
df = spark.read.parquet("bronze/polygon/prices_daily") \
    .filter("date >= '2024-01-01' AND date < '2024-02-01'")

# Performance: 100x faster than full scan
```

### Compression

Use Snappy compression for balance of speed and size:

```python
df.write \
    .option('compression', 'snappy') \  # Fast compression
    .parquet(output_path)

# Alternatives:
# - 'gzip': Better compression, slower
# - 'none': No compression, fastest but largest
```

### File Sizing

Target 128MB-256MB files for optimal Spark performance:

```python
# Repartition before write
df.repartition(50).write.parquet(output_path)

# Or use coalesce for fewer partitions
df.coalesce(10).write.parquet(output_path)
```

## Monitoring & Auditing

### Ingestion Logs

```python
def log_ingestion(provider, dataset, status, row_count, error=None):
    """Log ingestion metadata."""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "provider": provider,
        "dataset": dataset,
        "status": status,  # success, failed, partial
        "row_count": row_count,
        "error": str(error) if error else None
    }

    # Append to log file
    log_path = bronze_root / "_logs" / f"{provider}_{dataset}.jsonl"
    with open(log_path, 'a') as f:
        f.write(json.dumps(log_entry) + '\n')
```

### Data Quality Checks

```python
def validate_bronze_data(df, expected_schema):
    """Validate Bronze data quality."""
    issues = []

    # Check schema
    for col, expected_type in expected_schema.items():
        if col not in df.columns:
            issues.append(f"Missing column: {col}")
        elif str(df.schema[col].dataType) != expected_type:
            issues.append(f"Type mismatch for {col}")

    # Check nulls in required fields
    required_fields = ['date', 'ticker']
    for field in required_fields:
        null_count = df.filter(F.col(field).isNull()).count()
        if null_count > 0:
            issues.append(f"Found {null_count} nulls in required field: {field}")

    return issues
```

---

**File**: `/home/user/de_Funk/docs/guide/3-architecture/components/data-pipeline/bronze-storage.md`
