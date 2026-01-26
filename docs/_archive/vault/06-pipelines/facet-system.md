# Facet System Reference

**Data normalization layer for Bronze ingestion**

Files:
- `datapipelines/facets/base_facet.py` - Base Facet class
- `datapipelines/facets/alpha_vantage/alpha_vantage_base_facet.py` - Alpha Vantage base
- `datapipelines/facets/alpha_vantage/*.py` - Alpha Vantage facet implementations
- `datapipelines/facets/bls/*.py` - BLS facet implementations
- `datapipelines/facets/chicago/*.py` - Chicago facet implementations

---

## Overview

**Facets** are the data normalization layer in de_Funk's pipeline architecture. They transform raw API responses into clean, type-safe DataFrames suitable for storage in the Bronze layer.

### Key Responsibilities

1. **Schema Normalization**: Convert inconsistent JSON to predictable Spark schemas
2. **Type Coercion**: Handle numeric type mismatches (int vs float, long vs double)
3. **Column Mapping**: Rename API fields to standardized column names
4. **Batch Union**: Combine multiple API responses into single DataFrame
5. **Derived Columns**: Add computed columns (dates, flags, etc.)
6. **Quality Control**: Enforce final schema and column order

### Design Philosophy

```
┌──────────────┐
│ Raw API JSON │  ← Messy, inconsistent types
└──────┬───────┘
       │
       ▼
  ┌─────────┐
  │  Facet  │  ← Normalize + transform
  └────┬────┘
       │
       ▼
┌──────────────┐
│ Clean Spark  │  ← Type-safe, predictable schema
│  DataFrame   │
└──────────────┘
```

**Problem Solved:** API responses have inconsistent types (sometimes `1`, sometimes `1.0`, sometimes `"1"`). Without normalization, Spark throws `CANNOT_DETERMINE_TYPE` errors during schema inference.

---

## Base Facet Class

**File:** `datapipelines/facets/base_facet.py:40-162`

### Class Definition

```python
class Facet:
    """
    Lightweight base:
      1) Pre-coerces python dicts for numeric keys to stable types
      2) Unions batches
      3) Lets child facet do vectorized postprocess()
      4) Enforces final Spark casts & optional final column order
    """

    # Child facet configures these class attributes
    NUMERIC_COERCE: Dict[str, str] = {}
    SPARK_CASTS: Dict[str, str] = {}
    FINAL_COLUMNS: Optional[List[Tuple[str, str]]] = None

    def __init__(self, spark, **kwargs):
        self.spark = spark
        self._extra = kwargs
```

---

## Class Attributes

### `NUMERIC_COERCE`

**Type:** `Dict[str, str]`

**Purpose:** Pre-coerce numeric fields in raw JSON rows before Spark schema inference.

**Problem:** API might return `{"open": 150}` (int) in one response and `{"open": 150.25}` (float) in another. Spark sees inconsistent types and fails.

**Solution:** Define numeric coercion to normalize types before DataFrame creation.

**Example:**
```python
class SecuritiesPricesFacet(Facet):
    NUMERIC_COERCE = {
        "open": "double",
        "high": "double",
        "low": "double",
        "close": "double",
        "volume": "double"
    }
```

**Supported Types:**
- `"double"`, `"float"`, `"decimal"` - Convert to Python float
- `"long"`, `"bigint"`, `"int"`, `"integer"` - Convert to Python int

---

### `SPARK_CASTS`

**Type:** `Dict[str, str]`

**Purpose:** Final Spark column casts applied after postprocessing.

**Usage:** Ensure columns have correct Spark types in final DataFrame.

**Example:**
```python
class SecuritiesPricesFacet(Facet):
    SPARK_CASTS = {
        "open": "double",
        "high": "double",
        "close": "double",
        "trade_date": "date",
        "ticker": "string"
    }
```

**Note:** If column doesn't exist, it's created as NULL with specified type.

---

### `FINAL_COLUMNS`

**Type:** `Optional[List[Tuple[str, str]]]`

**Purpose:** Enforce stable column set and order in final DataFrame.

**Usage:** Define exact schema with column names and types.

**Example:**
```python
class SecuritiesPricesFacet(Facet):
    FINAL_COLUMNS = [
        ("trade_date", "date"),
        ("ticker", "string"),
        ("open", "double"),
        ("high", "double"),
        ("low", "double"),
        ("close", "double"),
        ("volume", "double"),
        ("volume_weighted", "double")
    ]
```

**Behavior:**
- Missing columns: Created as NULL with specified type
- Extra columns: Dropped
- Column order: Enforced as specified

---

## Public Methods

### `__init__(spark, **kwargs)`

Initialize facet instance.

**Parameters:**
- `spark` - SparkSession for DataFrame creation
- `**kwargs` - Additional parameters (stored in `self._extra`)

**Example:**
```python
from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()
facet = SecuritiesPricesFacet(
    spark,
    tickers=['AAPL', 'MSFT'],
    date_from='2024-01-01',
    date_to='2024-12-31'
)
```

---

### `normalize(raw_batches: List[List[dict]]) -> DataFrame`

**Main normalization pipeline** - converts raw API responses to clean DataFrame.

**Process:**
1. For each batch of raw rows:
   - Apply `_coerce_rows()` to normalize numeric types
   - Create DataFrame with schema inference (`samplingRatio=1.0`)
2. Union all batch DataFrames with `unionByName(allowMissingColumns=True)`
3. Apply `postprocess()` (child facet override)
4. Apply `_apply_final_casts()` (enforce SPARK_CASTS)
5. Apply `_apply_final_columns()` (enforce FINAL_COLUMNS)
6. Return clean DataFrame

**Parameters:**
- `raw_batches` - List of batches, where each batch is a list of dicts

**Returns:** Spark DataFrame with normalized schema

**Example:**
```python
# Raw API responses (from ingestor)
raw_batches = [
    [
        {"trade_date": "2024-01-01", "open": 185.5, "high": 187.2, "close": 186.8, "volume": 45000000},
        {"trade_date": "2024-01-02", "open": 186.9, "high": 188.5, "close": 188.1, "volume": 52000000}
    ],
    [
        {"trade_date": "2024-01-03", "open": 188.2, "high": 189.0, "close": 187.5, "volume": 48000000}
    ]
]

# Normalize
df = facet.normalize(raw_batches)

# Result: Clean DataFrame with columns [trade_date, ticker, open, high, close, volume]
```

---

### `postprocess(df: DataFrame) -> DataFrame`

**Override in child facets** to apply custom transformations.

Called after batch union but before final casts.

**Default Implementation:**
```python
def postprocess(self, df):
    return df
```

**Common Use Cases:**
- Column renaming
- Derived columns (computed fields)
- Filtering invalid rows
- Deduplication

**Example:**
```python
class SecuritiesPricesFacet(Facet):
    def postprocess(self, df):
        # Add derived column
        df = df.withColumn("trade_date", F.to_date(F.col("timestamp")))

        # Filter invalid rows
        df = df.filter(F.col("open") > 0)

        return df
```

---

## Protected Methods

### `_coerce_rows(rows: List[dict]) -> List[dict]`

Pre-coerce numeric fields in raw JSON rows to ensure consistent types.

**Parameters:**
- `rows` - List of raw JSON dictionaries

**Returns:** List of coerced dictionaries

**Logic:**
- For each row, for each field in `NUMERIC_COERCE`:
  - If type is `"double"`: Convert to Python `float`
  - If type is `"long"`: Convert to Python `int`
  - Handle string representations (e.g., `"150.5"` → `150.5`)

**Example:**
```python
# Input (inconsistent types)
rows = [
    {"open": 150, "high": 155, "close": 152},      # ints
    {"open": 151.5, "high": 156.2, "close": 154}   # floats
]

# Output (consistent types)
coerced = facet._coerce_rows(rows)
# [
#     {"open": 150.0, "high": 155.0, "close": 152.0},
#     {"open": 151.5, "high": 156.2, "close": 154.0}
# ]
```

---

### `_apply_final_casts(df: DataFrame) -> DataFrame`

Apply final Spark column casts based on `SPARK_CASTS`.

**Parameters:**
- `df` - DataFrame to cast

**Returns:** DataFrame with columns cast to specified types

**Behavior:**
- If column exists: Cast to specified type
- If column missing: Create as NULL with specified type

---

### `_apply_final_columns(df: DataFrame) -> DataFrame`

Ensure stable column set and order based on `FINAL_COLUMNS`.

**Parameters:**
- `df` - DataFrame to restructure

**Returns:** DataFrame with exact columns in specified order

**Behavior:**
- Selects only columns in `FINAL_COLUMNS`
- Creates missing columns as NULL
- Enforces column order

---

### `_empty_df() -> DataFrame`

Produce empty DataFrame matching `FINAL_COLUMNS` schema.

**Returns:** Empty DataFrame with schema

**Use Cases:**
- No data returned from API
- All batches filtered out
- Error handling

---

## Helper Functions

### `coalesce_existing(df: DataFrame, candidates: Iterable[str])`

**File:** `datapipelines/facets/base_facet.py:11-14`

Coalesce over columns that actually exist (safe version).

**Parameters:**
- `df` - DataFrame
- `candidates` - Column names to coalesce

**Returns:** Spark Column expression

**Example:**
```python
# API might have 'name' or 'company_name'
df = df.withColumn("name", coalesce_existing(df, ["company_name", "name"]))
```

---

### `first_existing(df: DataFrame, candidates: Iterable[str])`

**File:** `datapipelines/facets/base_facet.py:16-21`

Return first existing column as Column, else NULL literal.

**Parameters:**
- `df` - DataFrame
- `candidates` - Column names to check

**Returns:** Spark Column expression

**Example:**
```python
# API might have 'ticker' or 'symbol'
df = df.withColumn("ticker", first_existing(df, ["ticker", "symbol"]))
```

---

### `_type_from_str(t: str)`

**File:** `datapipelines/facets/base_facet.py:23-36`

Convert type string to Spark DataType.

**Parameters:**
- `t` - Type string (e.g., `"double"`, `"string"`, `"date"`)

**Returns:** Spark DataType instance

**Supported Types:**
- `"string"` → `StringType()`
- `"double"`, `"float"` → `DoubleType()`
- `"int"`, `"integer"` → `IntegerType()`
- `"long"`, `"bigint"` → `LongType()`
- `"boolean"` → `BooleanType()`
- `"date"` → `DateType()`
- `"timestamp"` → `TimestampType()`

---

## Facet Hierarchy

```
Facet (base)
├── AlphaVantageFacet (provider-specific base)
│   ├── SecuritiesReferenceFacet
│   ├── SecuritiesPricesDailyFacet
│   └── TechnicalIndicatorsFacet
├── BLSFacet (provider-specific base)
│   ├── UnemploymentFacet
│   └── CPIFacet
└── ChicagoFacet (provider-specific base)
    ├── UnemploymentRatesFacet
    └── BuildingPermitsFacet
```

---

## Usage Patterns

### Basic Facet Implementation

```python
from datapipelines.facets.base_facet import Facet
from pyspark.sql import functions as F

class MyDataFacet(Facet):
    """Normalize MyData API responses."""

    # Define type coercion
    NUMERIC_COERCE = {
        "price": "double",
        "quantity": "long",
        "timestamp": "long"
    }

    # Define final schema
    FINAL_COLUMNS = [
        ("date", "date"),
        ("ticker", "string"),
        ("price", "double"),
        ("quantity", "long")
    ]

    def __init__(self, spark, tickers, date_from, date_to):
        super().__init__(spark)
        self.tickers = tickers
        self.date_from = date_from
        self.date_to = date_to

    def postprocess(self, df):
        # Rename columns
        df = df.withColumnRenamed("price", "close_price")

        # Add derived column
        df = df.withColumn("date", F.to_date(F.col("timestamp") / 1000))

        return df
```

---

### Provider-Specific Base Facet

```python
class MyProviderFacet(Facet):
    """Base facet for MyProvider API."""

    def __init__(self, spark, tickers=None, date_from=None, date_to=None):
        super().__init__(spark)
        self.tickers = tickers or []
        self.date_from = date_from
        self.date_to = date_to

    def calls(self):
        """Generate API call specifications."""
        raise NotImplementedError("Child facets must implement calls()")
```

---

### Enriching Rows Before Normalization

**Problem:** API doesn't return ticker symbol in response, only in URL.

**Solution:** Enrich rows before passing to `normalize()`.

**Example:**
```python
class SecuritiesPricesFacet(AlphaVantageFacet):
    def __init__(self, spark, tickers, date_from, date_to):
        super().__init__(spark, tickers=tickers, date_from=date_from, date_to=date_to)
        self._call_contexts = []  # Track which call returned which data

    def calls(self):
        """Generate API calls (one per ticker)."""
        self._call_contexts = []
        for ticker in self.tickers:
            params = {"ticker": ticker, "from": self.date_from, "to": self.date_to}
            self._call_contexts.append({"ticker": ticker})
            yield {"ep_name": "securities_prices_daily", "params": params}

    def normalize(self, raw_batches):
        """Enrich rows with ticker before normalizing."""
        enriched = []

        # Match batches to call contexts
        for i, rows in enumerate(raw_batches):
            ticker = None
            if i < len(self._call_contexts):
                ticker = self._call_contexts[i].get("ticker")

            # Inject ticker into each row
            if ticker:
                rows = [{**r, "ticker": ticker} for r in (rows or [])]

            enriched.append(rows or [])

        # Now use base normalization
        return super().normalize(enriched)
```

---

### Handling Empty Responses

```python
# Empty batch
raw_batches = [[], []]

# Facet returns empty DataFrame with correct schema
df = facet.normalize(raw_batches)

# df.count() == 0
# df.schema matches FINAL_COLUMNS
```

---

### Complex Postprocessing

```python
class NewsFacet(Facet):
    def postprocess(self, df):
        # Rename columns
        df = df.withColumnRenamed("published_utc", "published_timestamp")

        # Parse nested JSON
        df = df.withColumn(
            "publisher_name",
            F.get_json_object(F.col("publisher"), "$.name")
        )

        # Add derived columns
        df = df.withColumn(
            "published_date",
            F.to_date(F.col("published_timestamp"))
        )

        # Filter out invalid rows
        df = df.filter(F.col("title").isNotNull())

        # Deduplicate by article URL
        df = df.dropDuplicates(["article_url"])

        return df
```

---

## Integration with Ingestors

Facets are used by Ingestors to normalize API responses:

```
┌───────────┐
│ Ingestor  │
└─────┬─────┘
      │
      ├─ 1. Generate API calls (facet.calls())
      │
      ├─ 2. Fetch data from API
      │
      ├─ 3. Collect raw batches
      │
      └─ 4. Normalize (facet.normalize(batches))
         │
         ▼
    ┌──────────────┐
    │ Clean DataFrame│
    └───────┬────────┘
            │
            ▼
       Write to Bronze
```

**Example:**
```python
from datapipelines.ingestors.base_ingestor import BaseIngestor

class MyIngestor(BaseIngestor):
    def run(self, tickers, date_from, date_to):
        # Create facet
        facet = SecuritiesPricesFacet(
            self.spark,
            tickers=tickers,
            date_from=date_from,
            date_to=date_to
        )

        # Generate API calls
        calls = list(facet.calls())

        # Fetch data from API
        raw_batches = []
        for call_spec in calls:
            response = self.api_client.fetch(call_spec)
            raw_batches.append(response)

        # Normalize
        df = facet.normalize(raw_batches)

        # Write to Bronze
        bronze_path = self.storage_router.bronze_path("securities_prices_daily")
        df.write.mode("overwrite").parquet(bronze_path)
```

---

## Best Practices

1. **Always define NUMERIC_COERCE**: Prevent schema inference errors
2. **Use FINAL_COLUMNS**: Enforce stable schema across runs
3. **Leverage postprocess()**: Keep transformation logic in facet
4. **Enrich context data**: Inject metadata (ticker, date) before normalization
5. **Use helper functions**: `coalesce_existing()`, `first_existing()` for robust column handling
6. **Test with empty batches**: Ensure facet handles no data gracefully
7. **Set samplingRatio=1.0**: Sample all rows for schema inference (prevents CANNOT_DETERMINE_TYPE)

---

## Common Patterns

### Date Conversion from Epoch

```python
def postprocess(self, df):
    # Convert Unix timestamp (ms) to date
    df = df.withColumn(
        "trade_date",
        F.to_date(F.col("timestamp_ms") / 1000)
    )
    return df
```

---

### Nested JSON Extraction

```python
def postprocess(self, df):
    # Extract fields from nested JSON
    df = df.withColumn(
        "company_name",
        F.get_json_object(F.col("company_info"), "$.name")
    )
    df = df.withColumn(
        "company_country",
        F.get_json_object(F.col("company_info"), "$.country")
    )
    return df
```

---

### Column Coalescing

```python
def postprocess(self, df):
    # API might have 'name' or 'company_name' or 'entity_name'
    df = df.withColumn(
        "name",
        F.coalesce(
            F.col("entity_name"),
            F.col("company_name"),
            F.col("name")
        )
    )
    return df
```

---

### Filtering Invalid Data

```python
def postprocess(self, df):
    # Remove rows with invalid prices
    df = df.filter(
        (F.col("open") > 0) &
        (F.col("close") > 0) &
        (F.col("volume") >= 0)
    )
    return df
```

---

## Troubleshooting

### CANNOT_DETERMINE_TYPE Error

**Error:** `pyspark.sql.utils.AnalysisException: CANNOT_DETERMINE_TYPE`

**Cause:** Inconsistent types in raw JSON (int vs float)

**Solution:** Define `NUMERIC_COERCE` to normalize types before DataFrame creation:
```python
NUMERIC_COERCE = {
    "price": "double",
    "volume": "long"
}
```

---

### Missing Columns After Union

**Error:** Columns missing after `unionByName()`

**Cause:** Not using `allowMissingColumns=True`

**Solution:** Base Facet already uses `allowMissingColumns=True`:
```python
out = out.unionByName(d, allowMissingColumns=True)
```

---

### Schema Mismatch Across Batches

**Error:** Different schemas in different batches

**Cause:** API returns different fields for different tickers/dates

**Solution:** Use `FINAL_COLUMNS` to enforce schema:
```python
FINAL_COLUMNS = [
    ("date", "date"),
    ("ticker", "string"),
    ("price", "double")
]
```

---

### Empty DataFrame Schema

**Error:** Empty DataFrame has wrong schema

**Cause:** `_empty_df()` doesn't match `FINAL_COLUMNS`

**Solution:** Ensure `FINAL_COLUMNS` is defined - `_empty_df()` uses it automatically

---

## Related Documentation

- [Pipeline Architecture](pipeline-architecture.md) - Overall pipeline design
- [Ingestors](ingestors.md) - Facet consumers
- [Providers](providers.md) - Provider-specific implementations
- [Bronze Layer](../00-overview/architecture.md#bronze-layer-raw-data) - Facet output destination
