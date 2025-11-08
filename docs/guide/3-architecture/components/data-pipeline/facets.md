# Data Pipeline - Facets

## Overview

**Facets** are the core abstraction for defining API endpoints and data extraction logic in the de_Funk data pipeline. Each facet represents a specific API endpoint and knows how to fetch, parse, and normalize data from that endpoint.

## Architecture

### Facet Hierarchy

```
BaseFacet (Abstract)
    │
    ├─► PolygonBaseFacet
    │       ├─► PricesDailyFacet
    │       ├─► RefTickersFacet
    │       ├─► NewsByDateFacet
    │       └─► ExchangeFacet
    │
    ├─► BLSBaseFacet
    │       ├─► UnemploymentFacet
    │       └─► CPIFacet
    │
    └─► ChicagoBaseFacet
            ├─► BuildingPermitsFacet
            └─► UnemploymentRatesFacet
```

## Base Facet Class

```python
# File: datapipelines/facets/base_facet.py:40-162

class Facet:
    """
    Lightweight base facet for API endpoint definitions.

    Responsibilities:
    1. Pre-coerce numeric types to prevent schema conflicts
    2. Union batches with allowMissingColumns
    3. Apply vectorized postprocessing
    4. Enforce final schema and column order
    """

    # Numeric type coercion (prevents Long/Double merge errors)
    NUMERIC_COERCE: Dict[str, str] = {}

    # Final Spark casts by column name
    SPARK_CASTS: Dict[str, str] = {}

    # Optional final column order
    FINAL_COLUMNS: Optional[List[Tuple[str, str]]] = None

    def __init__(self, spark, **kwargs):
        self.spark = spark
        self._extra = kwargs

    def normalize(self, raw_batches):
        """
        Main normalization pipeline.

        Args:
            raw_batches: List of lists of dicts (raw API responses)

        Returns:
            Spark DataFrame with normalized schema
        """
        dfs = []
        for rows in raw_batches:
            if not rows:
                continue

            # Pre-coerce numeric types
            rows = self._coerce_rows(rows)

            # Create DataFrame with schema inference
            df = self.spark.createDataFrame(rows, samplingRatio=1.0)
            dfs.append(df)

        if not dfs:
            return self._empty_df()

        # Union all batches
        out = dfs[0]
        for d in dfs[1:]:
            out = out.unionByName(d, allowMissingColumns=True)

        # Apply transformations
        out = self.postprocess(out)
        out = self._apply_final_casts(out)
        out = self._apply_final_columns(out)

        return out

    def postprocess(self, df):
        """Override in subclass to transform DataFrame."""
        return df
```

## Example Implementations

### Polygon Prices Facet

```python
# File: datapipelines/providers/polygon/facets/prices_daily_facet.py

class PricesDailyFacet(PolygonBaseFacet):
    """
    Daily aggregate price bars from Polygon.

    Endpoint: /v2/aggs/ticker/{ticker}/range/1/day/{from}/{to}
    """

    endpoint = "v2/aggs/ticker/{ticker}/range/1/day/{from_date}/{to_date}"
    dataset = "prices_daily"

    # Numeric coercion to prevent schema errors
    NUMERIC_COERCE = {
        "o": "double",    # open
        "h": "double",    # high
        "l": "double",    # low
        "c": "double",    # close
        "v": "long",      # volume
        "vw": "double",   # VWAP
        "t": "long",      # timestamp
        "n": "int"        # transactions
    }

    # Final schema enforcement
    SPARK_CASTS = {
        "open": "double",
        "high": "double",
        "low": "double",
        "close": "double",
        "volume": "long",
        "vwap": "double",
        "timestamp": "long",
        "transactions": "int"
    }

    # Enforced column order
    FINAL_COLUMNS = [
        ("date", "date"),
        ("ticker", "string"),
        ("open", "double"),
        ("high", "double"),
        ("low", "double"),
        ("close", "double"),
        ("volume", "long"),
        ("vwap", "double"),
        ("transactions", "int"),
        ("timestamp", "long")
    ]

    def postprocess(self, df):
        """Transform Polygon schema to standardized schema."""
        from pyspark.sql import functions as F

        # Rename columns from Polygon's abbreviated names
        df = df.select(
            F.col("o").alias("open"),
            F.col("h").alias("high"),
            F.col("l").alias("low"),
            F.col("c").alias("close"),
            F.col("v").alias("volume"),
            F.col("vw").alias("vwap"),
            F.col("t").alias("timestamp"),
            F.col("n").alias("transactions")
        )

        # Add date column from timestamp
        df = df.withColumn(
            "date",
            F.to_date(F.from_unixtime(F.col("timestamp") / 1000))
        )

        # Add ticker (from query parameter)
        ticker = self._extra.get("ticker")
        if ticker:
            df = df.withColumn("ticker", F.lit(ticker))

        return df
```

### Reference Tickers Facet

```python
# File: datapipelines/providers/polygon/facets/ref_all_tickers_facet.py

class RefAllTickersFacet(PolygonBaseFacet):
    """
    Reference data for all tickers.

    Endpoint: /v3/reference/tickers
    """

    endpoint = "v3/reference/tickers"
    dataset = "ref_tickers"

    SPARK_CASTS = {
        "ticker": "string",
        "name": "string",
        "market": "string",
        "locale": "string",
        "primary_exchange": "string",
        "type": "string",
        "active": "boolean",
        "currency_name": "string",
        "cik": "string",
        "composite_figi": "string",
        "share_class_figi": "string"
    }

    def postprocess(self, df):
        """Extract and flatten nested fields."""
        from pyspark.sql import functions as F

        # Flatten nested address structure
        if "address" in df.columns:
            df = df.withColumn("address_city", F.col("address.city"))
            df = df.withColumn("address_state", F.col("address.state"))
            df = df.drop("address")

        # Ensure all expected columns exist
        for col_name, col_type in self.SPARK_CASTS.items():
            if col_name not in df.columns:
                df = df.withColumn(col_name, F.lit(None).cast(col_type))

        return df
```

### BLS Unemployment Facet

```python
# File: datapipelines/providers/bls/facets/unemployment_facet.py

class UnemploymentFacet(BLSBaseFacet):
    """
    Unemployment rate data from BLS.

    Endpoint: /publicAPI/v2/timeseries/data/
    Series: LNS14000000 (Unemployment Rate)
    """

    endpoint = "publicAPI/v2/timeseries/data/"
    dataset = "unemployment"
    series_id = "LNS14000000"

    SPARK_CASTS = {
        "year": "int",
        "period": "string",
        "value": "double",
        "footnotes": "string"
    }

    def postprocess(self, df):
        """Parse BLS-specific response format."""
        from pyspark.sql import functions as F

        # BLS returns data in nested "series" field
        if "series" in df.columns:
            # Explode series array
            df = df.withColumn("series_data", F.explode(F.col("series")))
            df = df.withColumn("data", F.explode(F.col("series_data.data")))

            # Extract fields
            df = df.select(
                F.col("data.year").cast("int").alias("year"),
                F.col("data.period").alias("period"),
                F.col("data.value").cast("double").alias("value"),
                F.col("data.footnotes").alias("footnotes")
            )

        # Convert period (M01-M12) to month number
        df = df.withColumn(
            "month",
            F.when(F.col("period").startswith("M"),
                   F.substring(F.col("period"), 2, 2).cast("int"))
        )

        # Create date column
        df = df.withColumn(
            "date",
            F.to_date(F.concat_ws("-", F.col("year"), F.col("month"), F.lit("01")))
        )

        return df
```

## Facet Configuration

### Schema Coercion

Facets use `NUMERIC_COERCE` to prevent Spark schema conflicts:

```python
NUMERIC_COERCE = {
    "price": "double",   # Ensures price is always float, not int
    "volume": "long",    # Ensures volume is always bigint, not int
    "timestamp": "long"  # Ensures timestamp is always bigint
}
```

**Why needed**: Spark's schema inference can assign different types to the same field across batches (e.g., `int` vs `long` for volume), causing union errors.

### Final Schema Enforcement

Facets use `SPARK_CASTS` and `FINAL_COLUMNS` to ensure consistent output:

```python
# Enforce types after transformations
SPARK_CASTS = {
    "date": "date",
    "ticker": "string",
    "close": "double"
}

# Enforce column order (optional)
FINAL_COLUMNS = [
    ("date", "date"),
    ("ticker", "string"),
    ("close", "double")
]
```

## Testing Facets

```python
# File: tests/test_facets.py

def test_prices_facet():
    """Test PricesDailyFacet normalization."""
    from pyspark.sql import SparkSession

    spark = SparkSession.builder.getOrCreate()
    facet = PricesDailyFacet(spark, ticker="AAPL")

    # Mock API response
    raw_data = [[
        {"o": 100.5, "h": 102.0, "l": 99.0, "c": 101.5, "v": 1000000, "t": 1704067200000},
        {"o": 101.5, "h": 103.0, "l": 100.5, "c": 102.5, "v": 1100000, "t": 1704153600000}
    ]]

    # Normalize
    df = facet.normalize(raw_data)

    # Verify schema
    assert "date" in df.columns
    assert "ticker" in df.columns
    assert df.schema["open"].dataType == DoubleType()
    assert df.count() == 2

    # Verify data
    rows = df.collect()
    assert rows[0]["ticker"] == "AAPL"
    assert rows[0]["open"] == 100.5
```

## Best Practices

### 1. Always Define NUMERIC_COERCE

```python
# Good
NUMERIC_COERCE = {
    "price": "double",
    "volume": "long"
}

# Bad - can cause schema conflicts
# (no coercion)
```

### 2. Use postprocess for Transformations

```python
def postprocess(self, df):
    """Keep transformation logic in postprocess."""
    return df.select(
        F.col("raw_field").alias("standard_field"),
        F.to_date(F.col("timestamp")).alias("date")
    )
```

### 3. Handle Missing Fields

```python
def postprocess(self, df):
    """Always check for field existence."""
    if "optional_field" in df.columns:
        df = df.withColumn("parsed_field", F.col("optional_field"))
    else:
        df = df.withColumn("parsed_field", F.lit(None))
    return df
```

### 4. Document Endpoint

```python
class MyFacet(BaseFacet):
    """
    Brief description.

    Endpoint: /v1/endpoint/path
    Documentation: https://api.example.com/docs
    Rate Limit: 5 requests/second
    Pagination: cursor-based
    """
```

---

## Related Documentation

- [Overview](./overview.md)
- [Ingestors](./ingestors.md)
- [Providers](./providers.md)

**File**: `/home/user/de_Funk/docs/guide/3-architecture/components/data-pipeline/facets.md`
