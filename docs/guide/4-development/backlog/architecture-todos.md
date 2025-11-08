# Architecture TODOs

This document tracks architectural improvements, refactoring tasks, and technical debt items for de_Funk.

**Based on:** ARCHITECTURE_TODO.md, ARCHITECTURE_IMPROVEMENTS.md
**Last Updated:** 2025-11-08

---

## Table of Contents

- [Critical Technical Debt](#critical-technical-debt)
- [Architecture Refactoring](#architecture-refactoring)
- [Performance Optimizations](#performance-optimizations)
- [Infrastructure](#infrastructure)
- [Testing and Quality](#testing-and-quality)
- [Migration Tasks](#migration-tasks)

---

## Critical Technical Debt

### ARCH-DEBT-001: Eliminate company_silver_builder.py

**Status:** Not Started
**Priority:** Critical
**Effort:** 1-2 days

**Description:**
The `company_silver_builder.py` file is legacy code that duplicates functionality now provided by `BaseModel.write_tables()`. This violates the DRY principle and contradicts our config-driven architecture.

**Problem:**
```python
# models/implemented/company/company_silver_builder.py
class CompanySilverBuilder:
    def build_dim_company(self):
        # Manual table building - 300+ lines of duplicate code
        ...

    def build_fact_prices(self):
        # Manual transformations that should be in YAML
        ...

    def build_and_write(self):
        # Manual writing that BaseModel.write_tables() handles
        ...
```

**Solution:**
All functionality is already in `BaseModel.write_tables()`. Simply delete the file and update any scripts that reference it.

**Migration Steps:**
- [x] Implement `BaseModel.write_tables()` ✅ (Completed)
- [x] Update `run_full_pipeline.py` to use new pattern ✅ (Completed)
- [ ] Verify all scripts no longer reference `company_silver_builder.py`
- [ ] Delete `models/implemented/company/company_silver_builder.py`
- [ ] Update documentation to remove references
- [ ] Add deprecation notice if needed

**Files to Check:**
```bash
# Find all references to company_silver_builder
grep -r "company_silver_builder" --include="*.py" .
```

**Success Criteria:**
- File deleted
- No references in codebase
- All tests pass
- Pipeline still works

---

### ARCH-DEBT-002: Standardize Path Resolution

**Status:** Not Started
**Priority:** Critical
**Effort:** 3-5 days

**Description:**
Storage path resolution is inconsistent across the codebase. Some components use hardcoded paths, others use relative paths, and the `StorageRouter` logic is not well documented.

**Current Problems:**
- Bronze paths: `storage/bronze/{provider}/{table}/`
- Silver paths: `storage/silver/{model}/dims/{table}/` or `storage/silver/{model}/facts/{table}/`
- Some code hardcodes these patterns
- StorageRouter logic is implicit
- Difficult to change storage structure

**Proposed Solution:**
Centralize all path resolution in `StorageRouter` with clear documentation.

**Implementation:**
```python
# models/api/dal.py
class StorageRouter:
    """
    Centralized storage path resolution.

    Path patterns:
    - Bronze: {bronze_root}/{provider}/{table}/
    - Silver Dims: {model_root}/dims/{table}/
    - Silver Facts: {model_root}/facts/{table}/
    """

    def get_bronze_path(self, provider: str, table: str) -> str:
        """Get path to Bronze table."""
        return f"{self.bronze_root}/{provider}/{table}"

    def get_silver_path(self, model: str, table: str, table_type: str) -> str:
        """Get path to Silver table."""
        return f"{self.silver_root}/{model}/{table_type}/{table}"
```

**Tasks:**
- [ ] Document all path patterns
- [ ] Audit codebase for hardcoded paths
- [ ] Refactor to use StorageRouter everywhere
- [ ] Add tests for path resolution
- [ ] Support configurable path patterns

**Benefits:**
- Single source of truth for paths
- Easy to change storage structure
- Better error messages
- Consistent behavior

---

### ARCH-DEBT-003: Add Structured Logging

**Status:** Not Started
**Priority:** Critical
**Effort:** 5-7 days

**Description:**
Current logging is inconsistent - mix of print statements, manual logging, and no structured format. Need a unified logging framework.

**Current Problems:**
```python
# Inconsistent logging across codebase
print("Building model...")  # Some use print
logger.info("Building model")  # Some use logging
# No structured context
# No log levels consistency
# Difficult to debug
```

**Proposed Solution:**
Implement structured logging with context throughout the codebase.

**Features:**
- [ ] Use Python `logging` module consistently
- [ ] Structured JSON logging for production
- [ ] Pretty console logging for development
- [ ] Contextual information (model, table, operation)
- [ ] Timing information for performance
- [ ] Log levels: DEBUG, INFO, WARNING, ERROR
- [ ] Configurable via environment/config

**Implementation:**
```python
# defunk/logging.py
import logging
import json
from datetime import datetime

class StructuredLogger:
    """Structured logging with context."""

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)

    def info(self, message: str, **context):
        """Log with structured context."""
        self.logger.info(json.dumps({
            'timestamp': datetime.utcnow().isoformat(),
            'level': 'INFO',
            'message': message,
            **context
        }))

# Usage
logger = StructuredLogger('defunk.models')
logger.info("Building model", model='company', operation='build', nodes=10)
```

**Output (Development):**
```
[2024-11-08 10:30:45] INFO  Building model (model=company, nodes=10)
```

**Output (Production):**
```json
{"timestamp": "2024-11-08T10:30:45Z", "level": "INFO", "message": "Building model", "model": "company", "nodes": 10}
```

**Tasks:**
- [ ] Implement logging framework
- [ ] Replace print statements with logging
- [ ] Add logging to all modules
- [ ] Document logging best practices
- [ ] Add log rotation configuration

---

## Architecture Refactoring

### ARCH-REF-001: Unify Spark and DuckDB Backends

**Status:** Not Started
**Priority:** High
**Effort:** 2-3 weeks

**Description:**
Currently, Spark and DuckDB code paths are intertwined. Need a cleaner abstraction layer.

**Current Problems:**
- Backend detection is ad-hoc
- Different code paths for same operations
- Hard to add new backends
- Testing requires both backends

**Proposed Architecture:**
```python
# models/backends/base.py
class Backend(ABC):
    @abstractmethod
    def read_parquet(self, path: str) -> DataFrame:
        pass

    @abstractmethod
    def write_parquet(self, df: DataFrame, path: str, **kwargs):
        pass

    @abstractmethod
    def select(self, df: DataFrame, columns: list) -> DataFrame:
        pass

# models/backends/spark.py
class SparkBackend(Backend):
    def read_parquet(self, path: str):
        return self.spark.read.parquet(path)

# models/backends/duckdb.py
class DuckDBBackend(Backend):
    def read_parquet(self, path: str):
        return self.conn.read_parquet(path)
```

**Usage:**
```python
# BaseModel uses backend abstraction
class BaseModel:
    def __init__(self, connection, ...):
        self.backend = BackendFactory.create(connection)

    def _load_bronze_table(self, table: str):
        return self.backend.read_parquet(path)
```

**Benefits:**
- Clean separation of concerns
- Easy to add new backends (Polars, Pandas)
- Consistent testing
- Better error messages

**Tasks:**
- [ ] Design backend abstraction
- [ ] Implement SparkBackend
- [ ] Implement DuckDBBackend
- [ ] Migrate BaseModel to use backends
- [ ] Add backend-specific tests
- [ ] Document backend architecture

---

### ARCH-REF-002: Standardize Configuration Loading

**Status:** Not Started
**Priority:** High
**Effort:** 1 week

**Description:**
Configuration loading is scattered and inconsistent. Need a unified config management system.

**Current Problems:**
```python
# Different patterns across codebase
config = yaml.safe_load(open('config.yaml'))  # Some load directly
config = load_config('config.yaml')  # Some use helper
config = Config.from_file('config.yaml')  # Some use class
```

**Proposed Solution:**
```python
# defunk/config.py
class ConfigLoader:
    """Centralized configuration loading."""

    @staticmethod
    def load_model_config(model_name: str, repo_root: Path) -> dict:
        """Load model configuration with validation."""
        path = repo_root / "configs" / "models" / f"{model_name}.yaml"
        return ConfigLoader._load_and_validate(path, ModelConfigSchema)

    @staticmethod
    def load_storage_config(repo_root: Path) -> dict:
        """Load storage configuration."""
        path = repo_root / "configs" / "storage.yaml"
        return ConfigLoader._load_and_validate(path, StorageConfigSchema)

    @staticmethod
    def _load_and_validate(path: Path, schema: Schema) -> dict:
        """Load YAML and validate against schema."""
        if not path.exists():
            raise ConfigError(f"Config not found: {path}")

        with open(path) as f:
            data = yaml.safe_load(f)

        errors = schema.validate(data)
        if errors:
            raise ConfigValidationError(path, errors)

        return data
```

**Features:**
- [ ] Centralized config loading
- [ ] Schema validation (via Pydantic or similar)
- [ ] Environment variable substitution
- [ ] Config inheritance/merging
- [ ] Clear error messages

**Tasks:**
- [ ] Implement ConfigLoader
- [ ] Define config schemas
- [ ] Migrate all config loading to use it
- [ ] Add tests
- [ ] Document config structure

---

### ARCH-REF-003: Improve Error Handling

**Status:** Not Started
**Priority:** High
**Effort:** 1 week

**Description:**
Error handling is inconsistent. Need custom exception hierarchy with helpful messages.

**Current Problems:**
```python
# Generic exceptions
raise Exception("Error building model")
# No context
# Stack traces overwhelming
# Hard to debug
```

**Proposed Exception Hierarchy:**
```python
# defunk/exceptions.py
class DeFunkError(Exception):
    """Base exception for de_Funk."""
    pass

class ConfigError(DeFunkError):
    """Configuration errors."""
    pass

class ConfigValidationError(ConfigError):
    """Configuration validation failed."""
    def __init__(self, path: Path, errors: list):
        message = f"Invalid config: {path}\n"
        for error in errors:
            message += f"  - {error}\n"
        super().__init__(message)

class ModelError(DeFunkError):
    """Model-related errors."""
    pass

class ModelBuildError(ModelError):
    """Model build failed."""
    def __init__(self, model_name: str, reason: str, suggestions: list = None):
        message = f"Failed to build model '{model_name}': {reason}\n"
        if suggestions:
            message += "\nSuggestions:\n"
            for suggestion in suggestions:
                message += f"  - {suggestion}\n"
        super().__init__(message)
```

**Usage:**
```python
try:
    model.build()
except KeyError as e:
    raise ModelBuildError(
        model_name='company',
        reason=f"Missing table: {e}",
        suggestions=[
            "Check that Bronze tables exist",
            "Verify table names in YAML config",
            "Run: model.list_bronze_tables()"
        ]
    )
```

**Error Message:**
```
Failed to build model 'company': Missing table: dim_company

Suggestions:
  - Check that Bronze tables exist
  - Verify table names in YAML config
  - Run: model.list_bronze_tables()
```

**Tasks:**
- [ ] Define exception hierarchy
- [ ] Add helpful error messages
- [ ] Wrap low-level exceptions
- [ ] Add suggestions to errors
- [ ] Document common errors

---

## Performance Optimizations

### ARCH-PERF-001: Optimize Parquet File Sizing

**Status:** Not Started
**Priority:** High
**Effort:** 1 week

**Description:**
ParquetLoader currently uses fixed file sizing. Should dynamically adjust based on data volume.

**Current Behavior:**
```python
# Fixed coalesce to 5 partitions
df = df.coalesce(5)
```

**Proposed Solution:**
```python
class ParquetLoader:
    def _optimal_partitions(self, df: DataFrame, target_file_size_mb: int = 128) -> int:
        """Calculate optimal partition count."""
        # Estimate data size
        row_count = df.count()
        estimated_size_mb = self._estimate_size(df, row_count)

        # Calculate partitions
        num_partitions = max(1, int(estimated_size_mb / target_file_size_mb))

        return num_partitions
```

**Features:**
- [ ] Dynamic partition calculation
- [ ] Configurable target file size
- [ ] Size estimation based on schema and row count
- [ ] Respect min/max partition limits
- [ ] Optimize for small tables (avoid overhead)

**Benefits:**
- Optimal file sizes for DuckDB
- Better query performance
- Reduced storage overhead
- Faster writes

---

### ARCH-PERF-002: Implement Query Result Caching

**Status:** Not Started
**Priority:** Medium
**Effort:** 1 week

**Description:**
Cache expensive query results to avoid recomputation.

**Features:**
- [ ] In-memory cache with LRU eviction
- [ ] Persistent cache to disk
- [ ] Cache key based on query + filters
- [ ] Automatic invalidation on data change
- [ ] Configurable cache size and TTL

**Implementation:**
```python
class QueryCache:
    def __init__(self, max_size_mb: int = 1024, ttl_seconds: int = 3600):
        self.cache = {}
        self.max_size = max_size_mb
        self.ttl = ttl_seconds

    def get(self, key: str) -> Optional[DataFrame]:
        if key in self.cache:
            entry = self.cache[key]
            if not self._is_expired(entry):
                return entry['data']
        return None

    def put(self, key: str, data: DataFrame):
        self.cache[key] = {
            'data': data,
            'timestamp': time.time(),
            'size_mb': self._estimate_size(data)
        }
        self._evict_if_needed()
```

---

### ARCH-PERF-003: Add Connection Pooling

**Status:** Not Started
**Priority:** Medium
**Effort:** 3-5 days

**Description:**
Reuse database connections instead of creating new ones.

**Current Problem:**
```python
# New DuckDB connection per query
conn = duckdb.connect(db_path)
result = conn.execute(query)
conn.close()  # Expensive
```

**Solution:**
```python
class ConnectionPool:
    """Connection pooling for DuckDB."""

    def __init__(self, db_path: str, pool_size: int = 5):
        self.db_path = db_path
        self.pool = Queue(maxsize=pool_size)
        self._initialize_pool(pool_size)

    def get_connection(self):
        return self.pool.get()

    def return_connection(self, conn):
        self.pool.put(conn)
```

---

## Infrastructure

### ARCH-INFRA-001: Add Health Checks

**Status:** Not Started
**Priority:** High
**Effort:** 3-5 days

**Description:**
Implement health check endpoints for monitoring.

**Health Checks:**
- [ ] Database connectivity
- [ ] Storage accessibility
- [ ] API availability
- [ ] Model readiness
- [ ] Memory usage
- [ ] Disk space

**Implementation:**
```python
class HealthChecker:
    def check_database(self) -> HealthStatus:
        try:
            conn.execute("SELECT 1")
            return HealthStatus.HEALTHY
        except Exception as e:
            return HealthStatus.UNHEALTHY(str(e))

    def check_storage(self) -> HealthStatus:
        # Verify storage paths exist and are writable
        pass

    def check_all(self) -> dict:
        return {
            'database': self.check_database(),
            'storage': self.check_storage(),
            'apis': self.check_apis(),
            'models': self.check_models()
        }
```

**Endpoint:**
```
GET /health
{
  "status": "healthy",
  "checks": {
    "database": "healthy",
    "storage": "healthy",
    "apis": "healthy",
    "models": "healthy"
  },
  "timestamp": "2024-11-08T10:30:45Z"
}
```

---

### ARCH-INFRA-002: Add Metrics Collection

**Status:** Not Started
**Priority:** Medium
**Effort:** 1 week

**Description:**
Collect and expose metrics for monitoring and alerting.

**Metrics to Track:**
- [ ] Query latency (p50, p95, p99)
- [ ] Pipeline run times
- [ ] Data volume processed
- [ ] Error rates
- [ ] Cache hit rates
- [ ] API call counts
- [ ] Resource usage (CPU, memory, disk)

**Implementation:**
Use Prometheus client or similar:
```python
from prometheus_client import Counter, Histogram

# Define metrics
queries_total = Counter('queries_total', 'Total queries executed')
query_duration = Histogram('query_duration_seconds', 'Query execution time')

# Instrument code
@query_duration.time()
def execute_query(query):
    queries_total.inc()
    return conn.execute(query)
```

**Endpoint:**
```
GET /metrics
# HELP queries_total Total queries executed
# TYPE queries_total counter
queries_total 1543

# HELP query_duration_seconds Query execution time
# TYPE query_duration_seconds histogram
query_duration_seconds_bucket{le="0.1"} 892
query_duration_seconds_bucket{le="0.5"} 1234
...
```

---

### ARCH-INFRA-003: Docker Compose Setup

**Status:** Not Started
**Priority:** Medium
**Effort:** 3-5 days

**Description:**
Complete Docker Compose setup for easy local development.

**Services:**
- [ ] de_Funk app (Streamlit)
- [ ] Spark master
- [ ] Spark worker(s)
- [ ] DuckDB (embedded, no separate service)
- [ ] Jupyter (optional)

**docker-compose.yml:**
```yaml
version: '3.8'
services:
  app:
    build: .
    ports:
      - "8501:8501"
    volumes:
      - ./storage:/app/storage
      - ./configs:/app/configs
    depends_on:
      - spark-master

  spark-master:
    image: bitnami/spark:latest
    environment:
      - SPARK_MODE=master
    ports:
      - "7077:7077"
      - "8080:8080"

  spark-worker:
    image: bitnami/spark:latest
    environment:
      - SPARK_MODE=worker
      - SPARK_MASTER_URL=spark://spark-master:7077
    depends_on:
      - spark-master
```

**Features:**
- [ ] One command startup: `docker-compose up`
- [ ] Pre-loaded sample data
- [ ] Environment variables for config
- [ ] Volume mounts for development
- [ ] Health checks

---

## Testing and Quality

### ARCH-TEST-001: Integration Test Framework

**Status:** Not Started
**Priority:** High
**Effort:** 1-2 weeks

**Description:**
End-to-end integration tests for the full pipeline.

**Test Scenarios:**
- [ ] Full pipeline run (Bronze → Silver)
- [ ] Model building from config
- [ ] Query execution
- [ ] Notebook rendering
- [ ] API ingestion
- [ ] Error handling

**Framework:**
```python
class PipelineIntegrationTest:
    def test_full_pipeline_run(self):
        # 1. Ingest sample data to Bronze
        # 2. Build model
        # 3. Write to Silver
        # 4. Query results
        # 5. Verify correctness
        pass

    def test_model_building(self):
        # Test model building from YAML
        pass

    def test_cross_model_queries(self):
        # Test joining data from multiple models
        pass
```

---

### ARCH-TEST-002: Property-Based Testing

**Status:** Not Started
**Priority:** Medium
**Effort:** 1 week

**Description:**
Use property-based testing (Hypothesis) for transformations and aggregations.

**Example:**
```python
from hypothesis import given, strategies as st

@given(st.lists(st.floats(min_value=0, max_value=1e6)))
def test_aggregation_never_negative(values):
    df = create_dataframe(values)
    result = calculate_sum(df)
    assert result >= 0
```

---

## Migration Tasks

### ARCH-MIG-001: Migrate to Pydantic for Configs

**Status:** Not Started
**Priority:** Medium
**Effort:** 1 week

**Description:**
Use Pydantic for config validation and type safety.

**Benefits:**
- Automatic validation
- Type hints
- Clear error messages
- Documentation generation
- IDE support

**Example:**
```python
from pydantic import BaseModel, Field

class ModelConfig(BaseModel):
    model: str
    tags: List[str] = []
    storage: StorageConfig
    graph: GraphConfig
    measures: Dict[str, MeasureConfig] = {}

    class Config:
        extra = 'forbid'  # Reject unknown fields

# Usage
config = ModelConfig.parse_file('configs/models/company.yaml')
```

---

### ARCH-MIG-002: Migrate to Delta Lake

**Status:** Not Started
**Priority:** Low
**Effort:** 2-3 weeks

**Description:**
Consider migrating from Parquet to Delta Lake for ACID transactions.

**Benefits:**
- ACID transactions
- Time travel
- Schema evolution
- Better updates/deletes
- Audit history

**Challenges:**
- DuckDB doesn't support Delta (yet)
- Migration effort
- Increased complexity
- Storage overhead

**Decision:** Deferred pending DuckDB Delta support

---

## Success Metrics

### Code Quality
- [ ] 90%+ test coverage
- [ ] No critical tech debt items
- [ ] All legacy code removed
- [ ] Consistent coding style

### Performance
- [ ] 50%+ reduction in file count (optimal sizing)
- [ ] 10x speedup from query caching
- [ ] <100ms connection overhead (pooling)

### Maintainability
- [ ] All paths via StorageRouter
- [ ] All logging structured
- [ ] All configs via ConfigLoader
- [ ] Clear exception hierarchy

---

## Related Documents

- [TODO Tracker](../todo-tracker.md) - All development tasks
- [Roadmap](../roadmap.md) - Product roadmap
- [Models TODOs](./models-todos.md) - Model improvements
- [Architecture Guide](../../3-architecture/README.md) - Architecture docs
- [ARCHITECTURE_TODO.md](/home/user/de_Funk/ARCHITECTURE_TODO.md) - Original notes
- [ARCHITECTURE_IMPROVEMENTS.md](/home/user/de_Funk/ARCHITECTURE_IMPROVEMENTS.md) - Completed improvements
