"""
Company Silver Layer Builder.

Builds the Silver layer from Bronze data with pre-computed measures and aggregations.

This is the ETL layer - runs offline to materialize the Silver layer.
"""

from typing import Dict
from pyspark.sql import DataFrame, SparkSession
import pyspark.sql.functions as F
from pathlib import Path
import yaml

from ..loaders.parquet_loader import ParquetLoader


class CompanySilverBuilder:
    """
    Builds Silver layer for company model.

    Responsibilities:
    - Read from Bronze layer
    - Build dimension tables
    - Build fact tables with pre-computed measures
    - Materialize joined paths
    - Write to Silver layer

    Usage:
        builder = CompanySilverBuilder(spark, storage_cfg, model_cfg)
        builder.build_and_write(snapshot_date="2024-01-31")
    """

    def __init__(
        self,
        spark: SparkSession,
        storage_cfg: Dict,
        model_cfg: Dict,
    ):
        """
        Initialize Silver builder.

        Args:
            spark: Spark session
            storage_cfg: Storage configuration (storage.json)
            model_cfg: Model configuration (company.yaml)
        """
        self.spark = spark
        self.storage_cfg = storage_cfg
        self.model_cfg = model_cfg
        self.loader = ParquetLoader()

    def _bronze_path(self, table: str) -> str:
        """Get Bronze layer path for a table."""
        root = self.storage_cfg["roots"]["bronze"]
        rel = self.storage_cfg["tables"][table]["rel"]
        return f"{root.rstrip('/')}/{rel}"

    def _load_bronze(self, table: str) -> DataFrame:
        """
        Load Bronze table with schema merging.

        The mergeSchema option prevents 'CANNOT_DETERMINE_TYPE' errors when
        different partitions have slightly different schemas.
        """
        path = self._bronze_path(table)
        return (
            self.spark.read
            .option("mergeSchema", "true")
            .option("basePath", path)
            .parquet(path)
        )

    def build_dim_company(self) -> DataFrame:
        """
        Build dim_company dimension table.

        Transforms Bronze ref_ticker into Silver dim_company with:
        - ticker
        - company_name
        - exchange_code
        - company_id (sha1 of ticker)
        """
        df = self._load_bronze("ref_ticker")

        # Select and rename columns
        df = df.select(
            F.col("ticker").alias("ticker"),
            F.col("name").alias("company_name"),
            F.col("exchange_code").alias("exchange_code"),
        )

        # Derive company_id
        df = df.withColumn("company_id", F.sha1(F.col("ticker")))

        # Remove duplicates by ticker
        df = df.dropDuplicates(["ticker"])

        return df

    def build_dim_exchange(self) -> DataFrame:
        """
        Build dim_exchange dimension table.

        Transforms Bronze exchanges into Silver dim_exchange with:
        - exchange_code
        - exchange_name
        """
        df = self._load_bronze("exchanges")

        df = df.select(
            F.col("code").alias("exchange_code"),
            F.col("name").alias("exchange_name"),
        )

        df = df.dropDuplicates(["exchange_code"])

        return df

    def build_fact_prices(self) -> DataFrame:
        """
        Build fact_prices fact table with raw daily prices.

        Contains:
        - trade_date
        - ticker
        - open, high, low, close
        - volume
        - volume_weighted (VWAP)
        """
        df = self._load_bronze("prices_daily")

        df = df.select(
            F.col("trade_date"),
            F.col("ticker"),
            F.col("open"),
            F.col("high"),
            F.col("low"),
            F.col("close"),
            F.col("volume_weighted"),
            F.col("volume"),
        )

        return df

    def build_prices_with_company(
        self,
        fact_prices: DataFrame,
        dim_company: DataFrame,
        dim_exchange: DataFrame,
    ) -> DataFrame:
        """
        Build prices_with_company materialized path.

        Joins fact_prices -> dim_company -> dim_exchange.

        Contains all columns from fact_prices plus:
        - company_name
        - exchange_name
        """
        # Join fact_prices with dim_company
        df = fact_prices.join(
            dim_company,
            fact_prices["ticker"] == dim_company["ticker"],
            how="left"
        ).select(
            fact_prices["*"],
            dim_company["company_name"],
            dim_company["exchange_code"],
        )

        # Join with dim_exchange
        df = df.join(
            dim_exchange,
            df["exchange_code"] == dim_exchange["exchange_code"],
            how="left"
        ).select(
            F.col("trade_date"),
            F.col("ticker"),
            F.col("company_name"),
            F.col("exchange_name"),
            F.col("open"),
            F.col("high"),
            F.col("low"),
            F.col("close"),
            F.col("volume_weighted"),
            F.col("volume"),
        )

        return df

    def build_and_write(self):
        """
        Build all Silver layer tables and write to storage.

        Args:
            snapshot_date: Snapshot date for versioning (YYYY-MM-DD)
        """
        print(f"Building Silver layer:")

        # Build dimensions
        print("Building dim_company...")
        dim_company = self.build_dim_company()
        dim_company.cache()
        print(f"  Rows: {dim_company.count()}")

        print("Building dim_exchange...")
        dim_exchange = self.build_dim_exchange()
        dim_exchange.cache()
        print(f"  Rows: {dim_exchange.count()}")

        # Build facts
        print("Building fact_prices...")
        fact_prices = self.build_fact_prices()
        fact_prices.cache()
        print(f"  Rows: {fact_prices.count()}")

        # Build paths
        print("Building prices_with_company...")
        prices_with_company = self.build_prices_with_company(
            fact_prices,
            dim_company,
            dim_exchange,
        )
        prices_with_company.cache()
        print(f"  Rows: {prices_with_company.count()}")

        # Write to Silver
        print("\nWriting to Silver layer...")

        print("Writing dim_company...")
        self.loader.write_dim("dim_company", dim_company)

        print("Writing dim_exchange...")
        self.loader.write_dim("dim_exchange", dim_exchange)

        print("Writing fact_prices...")
        self.loader.write_fact("fact_prices", fact_prices,
        sort_by=["trade_date", "ticker"])

        print("Writing prices_with_company...")
        self.loader.write_fact("prices_with_company", prices_with_company,
        sort_by=["trade_date", "ticker"])

        print("\n✓ Silver layer build complete!")

        # Unpersist cached data
        dim_company.unpersist()
        dim_exchange.unpersist()
        fact_prices.unpersist()
        prices_with_company.unpersist()


def load_config(repo_root: Path):
    """Load storage and model configurations."""
    import json

    storage_cfg = json.loads((repo_root / "configs" / "storage.json").read_text())
    model_cfg = yaml.safe_load((repo_root / "configs" / "models" / "company.yaml").read_text())

    return storage_cfg, model_cfg
