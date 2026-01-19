# Spark Session Analysis: Delta Lake 4.x Compatibility

**Date**: 2026-01-19
**Issue**: "No active or default Spark session found" errors during Silver layer reads

## Executive Summary

The issue is that Delta Lake 4.x requires the SparkSession to be registered in JVM thread-local storage (`SparkSession.active()`). When ForecastBuilder tries to read the existing Stocks silver layer, the session becomes unregistered between operations, causing reads to fail and triggering unnecessary rebuilds from Bronze.

## Architecture Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│ build_models.py                                                          │
│   └── get_spark_session() → creates SparkSession                        │
│   └── BuildContext(spark=spark, ...)                                    │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ ForecastBuilder                                                          │
│   └── self.spark = context.spark (raw SparkSession)                     │
│   └── build():                                                          │
│       └── _ensure_active_session() ← registers session                  │
│       └── get_available_tickers():                                      │
│           └── _get_stocks_model():                                      │
│               └── _ensure_active_session() ← registers again            │
│               └── connection = get_spark_connection(self.spark)         │
│               └── StocksModel(connection=connection, ...)               │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ get_spark_connection(spark)                                             │
│   └── Returns SparkConnection(spark_session=spark)                      │
│   └── SparkConnection stores: self.spark = spark_session                │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ StocksModel                                                              │
│   └── self.connection = SparkConnection (wrapper)                       │
│   └── ensure_built():                                                   │
│       └── _ensure_active_spark_session()                                │
│           └── spark = self.connection.spark (unwrap)                    │
│           └── jvm.setActiveSession(spark._jsparkSession)                │
│       └── _load_from_silver():                                          │
│           └── for each table: _read_silver_table(path)                  │
│               └── _ensure_active_spark_session() ← AGAIN                │
│               └── spark.read.format("delta").load(path) ← FAILS!        │
└─────────────────────────────────────────────────────────────────────────┘
```

## The Problem

1. **Session Lifecycle**: SparkSession is created once by `build_models.py`
2. **Session Registration**: We call `setActiveSession(jss)` multiple times
3. **Session Unregistration**: Between our registration and the actual Delta read, something clears the session

### What "Thread-Local Storage" Means

```java
// In Spark's JVM (Scala code):
private val activeThreadSession = new ThreadLocal[SparkSession]

def setActiveSession(session: SparkSession): Unit = {
  activeThreadSession.set(session)
}

def active(): SparkSession = {
  // Delta Lake calls this internally
  Option(activeThreadSession.get()).getOrElse(
    throw new IllegalStateException("No active or default Spark session found")
  )
}
```

**Key insight**: Thread-local means the session is stored per-thread. If any operation runs on a different thread, it won't see the registered session.

## Possible Root Causes

### 1. Thread Switching (MOST LIKELY)
Delta Lake's internal operations may run on executor threads, not the driver thread where we registered the session.

```python
# We register on driver thread
jvm.setActiveSession(jss)  # Main thread

# But Delta's internal code runs on a different thread
spark.read.format("delta").load(path)  # Creates new threads internally?
```

### 2. Session Not Actually Registered
The `setActiveSession()` call might be silently failing or being overwritten.

### 3. Multiple SparkSessions
If a second SparkSession is created somewhere, it could clear the active session.

### 4. JVM/Python Bridge Issues
The py4j bridge between Python and JVM might have timing issues.

## Why Derive Functions Run

1. **Silver-first loading fails** → `_load_from_silver()` returns False
2. **Falls back to Bronze build** → calls `_graph_builder.build()`
3. **GraphBuilder processes nodes** → runs `_apply_derive()` for each derive expression
4. **Derive expressions in YAML** → things like window functions, sha1 hashes, etc.

```yaml
# From stocks/graph.yaml
nodes:
  dim_stock:
    from: bronze.alpha_vantage.securities_reference
    derive:
      security_id: "sha1(ticker)"
      market_cap_rank: "ROW_NUMBER() OVER (ORDER BY market_cap DESC)"
```

## Diagnostic Improvements Made

### 1. Enhanced `_ensure_active_spark_session()` (in 3 locations)

Now checks session state BEFORE and AFTER registration:

```python
def _ensure_active_spark_session(self) -> bool:
    # Check state BEFORE
    before_active = jvm.getActiveSession()
    before_state = "PRESENT" if before_active.isDefined() else "EMPTY"

    # Register
    jvm.setActiveSession(jss)
    jvm.setDefaultSession(jss)

    # Verify AFTER
    after_active = jvm.getActiveSession()
    after_state = "PRESENT" if after_active.isDefined() else "EMPTY"

    if after_state == "EMPTY":
        logger.error(f"Registration FAILED: before={before_state}, after={after_state}")
        return False

    return True
```

### 2. Better Error Logging in `_read_silver_table()`

Logs connection details when the specific error occurs:

```python
if "No active or default Spark session found" in error_msg:
    logger.error(
        f"SPARK SESSION ERROR reading {path}: {error_msg}\n"
        f"  Connection type: {type(self.connection)}\n"
        f"  Backend: {self.backend}\n"
        f"  Has .spark attr: {hasattr(self.connection, 'spark')}"
    )
```

### 3. Diagnostic Script

`scripts/debug/diagnose_spark_session.py` - Traces the full session lifecycle

## Next Steps for Debugging

1. **Run with diagnostics**: Execute the pipeline and look for:
   - `Session state: before=EMPTY, after=PRESENT` (normal)
   - `Session state: before=PRESENT, after=EMPTY` (registration failing!)
   - `SPARK SESSION ERROR reading ...` (see connection details)

2. **Check for thread switching**: Look at the logs to see if multiple threads are involved

3. **Test with explicit session**: Try passing the SparkSession directly instead of using the connection wrapper

## Potential Fixes

### Fix 1: Store Session Globally (Hacky but might work)
```python
# In get_spark() function
import builtins
builtins._spark_session = spark
```

### Fix 2: Use SparkSession.builder.getOrCreate()
Instead of passing the session through wrappers, always get it fresh:
```python
def _read_silver_table(self, path: str):
    from pyspark.sql import SparkSession
    spark = SparkSession.builder.getOrCreate()  # Gets existing session
    return spark.read.format("delta").load(path)
```

### Fix 3: Avoid the Connection Wrapper
Pass raw SparkSession directly to models instead of wrapping it.

### Fix 4: Different Delta Lake Configuration
Some Delta Lake configs might help:
```python
spark.conf.set("spark.databricks.delta.snapshotPartitions", "1")
spark.conf.set("spark.databricks.delta.properties.defaults.enableChangeDataFeed", "false")
```

## Files Modified

1. `models/base/model.py` - BaseModel._ensure_active_spark_session()
2. `models/base/builder.py` - BaseModelBuilder._ensure_active_session()
3. `models/api/dal.py` - Table._ensure_active_session()
4. `scripts/debug/diagnose_spark_session.py` - New diagnostic script

## How to Test

```bash
# Run with verbose logging to see session states
./scripts/test/test_pipeline.sh --profile silver_only --models forecast --skip-deps

# Look for these log messages:
# - "Session state: before=..., after=..."
# - "Session registration FAILED"
# - "SPARK SESSION ERROR reading ..."
```

## Related Code Locations

- `orchestration/common/spark_session.py` - get_spark() creates the session
- `core/connection.py` - SparkConnection wrapper class
- `models/base/graph_builder.py` - Calls Table.read() for Bronze reads
- `models/domains/securities/forecast/builder.py` - ForecastBuilder implementation
