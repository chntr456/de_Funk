# Configurable Debugging System Proposal

**Version**: 1.0
**Date**: 2025-11-21
**Status**: Proposal for Implementation
**Author**: Architecture Review Team

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current State Analysis](#current-state-analysis)
3. [Proposed Architecture](#proposed-architecture)
4. [Implementation Plan](#implementation-plan)
5. [Usage Examples](#usage-examples)
6. [Configuration Reference](#configuration-reference)
7. [Migration Guide](#migration-guide)

---

## Executive Summary

### Problem Statement

The de_Funk codebase currently lacks a unified, configurable debugging system. Debug logging is scattered across modules with:
- **Inconsistent approaches**: Some modules use `print()`, others use `logging`, some have no debugging
- **No centralized control**: Can't enable/disable debug output by module or component
- **Production pollution**: Debug statements left in production code
- **Performance impact**: Debug logging runs even when not needed
- **Hard to troubleshoot**: Can't selectively enable debugging for specific processes

### Proposed Solution

A **layered, configurable debugging system** with:
- ✅ **Centralized configuration**: Single YAML file controls all debug settings
- ✅ **Per-process toggles**: Enable/disable by module (models, ingestion, session, notebook)
- ✅ **Multiple log levels**: TRACE, DEBUG, INFO, WARN, ERROR, CRITICAL
- ✅ **Context-aware logging**: Automatic enrichment with module, function, line number
- ✅ **Performance-aware**: Zero overhead when disabled (lazy evaluation)
- ✅ **Environment-based**: Different configs for dev, test, prod
- ✅ **Runtime control**: Toggle debugging without code changes

### Benefits

| Benefit | Impact |
|---------|--------|
| **Faster debugging** | Enable only relevant modules (not entire codebase) |
| **Production-ready** | No debug statements in production output |
| **Performance** | Zero overhead when disabled |
| **Consistency** | Single pattern across all modules |
| **Maintainability** | Centralized configuration |
| **Developer UX** | Simple API: `debug.log("message", key=value)` |

---

## Current State Analysis

### Existing Debug Patterns

**Pattern 1: print() statements** (Found in ~15 files)
```python
# app/ui/notebook_app_duckdb.py (multiple locations)
print(f"Debug: filters = {filters}")  # Line 234
print(f"Debug: exhibit config = {exhibit_config}")  # Line 567
```

**Issues:**
- ❌ Always runs (can't disable)
- ❌ No log levels
- ❌ Hard to find and remove
- ❌ Pollutes stdout

**Pattern 2: logging module** (Found in ~30 files)
```python
# models/base/model.py
logger = logging.getLogger(__name__)
logger.debug("Loading model config")
```

**Issues:**
- ✅ Standard library
- ✅ Log levels supported
- ❌ Not configured consistently
- ❌ No centralized control
- ❌ Verbose setup per module

**Pattern 3: Conditional debug flags** (Found in ~5 files)
```python
# datapipelines/facets/base_facet.py
if os.getenv("DEBUG_FACETS") == "true":
    print(f"Facet input: {df.head()}")
```

**Issues:**
- ❌ Environment variable per module
- ❌ No log levels
- ❌ Inconsistent naming

### Coverage Gaps

| Component | Current Debug Support | Issues |
|-----------|----------------------|--------|
| **Models** | Basic `logging` | No per-model control |
| **Ingestion** | `print()` statements | Always runs, no levels |
| **Universal Session** | None | Can't debug query execution |
| **Notebook Parsing** | `print()` everywhere | Pollutes output |
| **Facets** | Env var conditionals | Inconsistent |
| **Providers** | Basic `logging` | No rate limit debugging |
| **Measures** | None | Can't debug calculations |

---

## Proposed Architecture

### System Design

```
┌─────────────────────────────────────────────────────────────┐
│                      Application Code                        │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐            │
│  │   Models   │  │ Ingestion  │  │  Session   │  ...       │
│  └──────┬─────┘  └──────┬─────┘  └──────┬─────┘            │
│         │                │                │                  │
│         └────────────────┴────────────────┘                  │
│                          │                                   │
│                    debug.log()                               │
│                          │                                   │
└──────────────────────────┼───────────────────────────────────┘
                           │
              ┌────────────▼─────────────┐
              │     DebugManager         │
              │  (Centralized Control)   │
              └────────────┬─────────────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
     ┌────▼────┐    ┌──────▼──────┐  ┌─────▼─────┐
     │ Config  │    │  Formatters │  │  Filters  │
     │ Loader  │    │             │  │           │
     └─────────┘    └─────────────┘  └───────────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
     ┌────▼────┐    ┌──────▼──────┐  ┌─────▼──────┐
     │  File   │    │   Console   │  │  Syslog    │
     │ Handler │    │   Handler   │  │  Handler   │
     └─────────┘    └─────────────┘  └────────────┘
```

### Core Components

#### 1. DebugManager (Singleton)

**Responsibilities:**
- Load configuration from YAML
- Manage log handlers (file, console, syslog)
- Check if debug is enabled for a module
- Route log messages to appropriate handlers
- Support runtime configuration updates

**API:**
```python
from utils.debug import debug

# Basic logging
debug.log("Processing started")

# With context
debug.log("Loaded config", model="stocks", tables=["dim_stock", "fact_prices"])

# Conditional (zero overhead if disabled)
if debug.enabled("models.stocks"):
    expensive_debug_operation()

# Log levels
debug.trace("Entering function", params=locals())
debug.debug("Intermediate value", x=42)
debug.info("Operation complete")
debug.warn("Slow query detected", duration_ms=5000)
debug.error("Failed to load data", exception=e)
```

#### 2. Configuration File

**Location**: `configs/debug.yaml`

```yaml
# Global debug settings
debug:
  enabled: true  # Master switch
  level: DEBUG   # TRACE, DEBUG, INFO, WARN, ERROR, CRITICAL

  # Environment-specific overrides
  environments:
    development:
      level: DEBUG
      console: true
      file: true
    production:
      level: WARN
      console: false
      file: true
      syslog: true
    testing:
      level: TRACE
      console: true
      file: false

  # Per-module configuration
  modules:
    models:
      enabled: true
      level: DEBUG
      modules:
        stocks:
          enabled: true
          level: TRACE  # More verbose for stocks
        company:
          enabled: true
          level: DEBUG
        options:
          enabled: false  # Disable options debugging

    ingestion:
      enabled: true
      level: INFO
      modules:
        providers:
          enabled: true
          level: DEBUG
        facets:
          enabled: true
          level: DEBUG
        sinks:
          enabled: false

    session:
      enabled: true
      level: DEBUG
      modules:
        query:
          enabled: true
          level: TRACE  # Trace SQL queries
        filters:
          enabled: true
          level: DEBUG
        joins:
          enabled: true
          level: DEBUG

    notebook:
      enabled: true
      level: WARN  # Only warnings in notebook parsing
      modules:
        parser:
          enabled: true
          level: DEBUG
        exhibits:
          enabled: false
        filters:
          enabled: true
          level: DEBUG

  # Output handlers
  handlers:
    console:
      enabled: true
      level: DEBUG
      format: "%(asctime)s [%(levelname)s] [%(module)s:%(funcName)s:%(lineno)d] %(message)s"
      colorize: true

    file:
      enabled: true
      level: DEBUG
      path: "logs/debug.log"
      max_bytes: 10485760  # 10 MB
      backup_count: 5
      format: "%(asctime)s [%(levelname)s] [%(module)s:%(funcName)s:%(lineno)d] %(message)s"

    syslog:
      enabled: false
      level: WARN
      host: "localhost"
      port: 514
      facility: "local0"

  # Performance settings
  performance:
    lazy_evaluation: true  # Don't format strings if debug disabled
    max_message_length: 10000  # Truncate long messages
    log_stack_trace: true  # Include stack trace for errors
```

#### 3. DebugManager Implementation

**File**: `utils/debug_manager.py`

```python
import logging
import yaml
from pathlib import Path
from typing import Any, Dict, Optional
from functools import lru_cache
import os

class DebugManager:
    """Centralized debug logging manager with per-module control."""

    _instance: Optional['DebugManager'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._config: Dict[str, Any] = {}
        self._loggers: Dict[str, logging.Logger] = {}
        self._load_config()
        self._setup_handlers()
        self._initialized = True

    def _load_config(self):
        """Load debug configuration from YAML file."""
        config_path = Path("configs/debug.yaml")

        if not config_path.exists():
            # Use defaults
            self._config = self._get_default_config()
            return

        with open(config_path) as f:
            self._config = yaml.safe_load(f).get("debug", {})

        # Apply environment-specific overrides
        env = os.getenv("DE_FUNK_ENV", "development")
        if env in self._config.get("environments", {}):
            env_config = self._config["environments"][env]
            self._config.update(env_config)

    def _get_default_config(self) -> Dict[str, Any]:
        """Return default configuration if no YAML file exists."""
        return {
            "enabled": True,
            "level": "DEBUG",
            "modules": {},
            "handlers": {
                "console": {"enabled": True, "level": "DEBUG"}
            }
        }

    def _setup_handlers(self):
        """Setup logging handlers based on configuration."""
        # Console handler
        if self._config.get("handlers", {}).get("console", {}).get("enabled"):
            console_handler = logging.StreamHandler()
            console_handler.setLevel(self._get_log_level(
                self._config["handlers"]["console"].get("level", "DEBUG")
            ))
            formatter = logging.Formatter(
                self._config["handlers"]["console"].get(
                    "format",
                    "%(asctime)s [%(levelname)s] %(message)s"
                )
            )
            console_handler.setFormatter(formatter)
            logging.root.addHandler(console_handler)

        # File handler
        if self._config.get("handlers", {}).get("file", {}).get("enabled"):
            from logging.handlers import RotatingFileHandler

            file_config = self._config["handlers"]["file"]
            log_path = Path(file_config.get("path", "logs/debug.log"))
            log_path.parent.mkdir(parents=True, exist_ok=True)

            file_handler = RotatingFileHandler(
                log_path,
                maxBytes=file_config.get("max_bytes", 10485760),
                backupCount=file_config.get("backup_count", 5)
            )
            file_handler.setLevel(self._get_log_level(
                file_config.get("level", "DEBUG")
            ))
            formatter = logging.Formatter(
                file_config.get(
                    "format",
                    "%(asctime)s [%(levelname)s] %(message)s"
                )
            )
            file_handler.setFormatter(formatter)
            logging.root.addHandler(file_handler)

    @staticmethod
    def _get_log_level(level_str: str) -> int:
        """Convert string log level to logging constant."""
        levels = {
            "TRACE": 5,  # Custom level
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARN": logging.WARN,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL
        }
        return levels.get(level_str.upper(), logging.DEBUG)

    @lru_cache(maxsize=256)
    def enabled(self, module_path: str) -> bool:
        """Check if debug is enabled for a specific module.

        Args:
            module_path: Dot-separated module path (e.g., "models.stocks", "ingestion.providers")

        Returns:
            True if debug is enabled for this module
        """
        # Check master switch
        if not self._config.get("enabled", True):
            return False

        # Walk module hierarchy
        parts = module_path.split(".")
        config = self._config.get("modules", {})

        for part in parts:
            if part not in config:
                # Use parent's setting
                return config.get("enabled", True)

            config = config[part]
            if "modules" in config:
                config = config["modules"]

        return config.get("enabled", True)

    def log(self, message: str, level: str = "DEBUG", module: Optional[str] = None, **context):
        """Log a debug message.

        Args:
            message: The log message
            level: Log level (TRACE, DEBUG, INFO, WARN, ERROR, CRITICAL)
            module: Module path (auto-detected if not provided)
            **context: Additional context to include in log
        """
        # Auto-detect module if not provided
        if module is None:
            import inspect
            frame = inspect.currentframe().f_back
            module = frame.f_globals.get("__name__", "unknown")

        # Check if enabled
        if not self.enabled(module):
            return

        # Get or create logger
        logger = self._get_logger(module)

        # Format message with context
        if context:
            context_str = " ".join(f"{k}={v}" for k, v in context.items())
            full_message = f"{message} | {context_str}"
        else:
            full_message = message

        # Log at appropriate level
        log_level = self._get_log_level(level)
        logger.log(log_level, full_message)

    def _get_logger(self, module: str) -> logging.Logger:
        """Get or create a logger for a module."""
        if module not in self._loggers:
            logger = logging.getLogger(module)
            logger.setLevel(logging.DEBUG)  # Let handlers control level
            self._loggers[module] = logger
        return self._loggers[module]

    # Convenience methods
    def trace(self, message: str, **context):
        """Log at TRACE level."""
        self.log(message, level="TRACE", **context)

    def debug(self, message: str, **context):
        """Log at DEBUG level."""
        self.log(message, level="DEBUG", **context)

    def info(self, message: str, **context):
        """Log at INFO level."""
        self.log(message, level="INFO", **context)

    def warn(self, message: str, **context):
        """Log at WARN level."""
        self.log(message, level="WARN", **context)

    def error(self, message: str, **context):
        """Log at ERROR level."""
        self.log(message, level="ERROR", **context)

    def critical(self, message: str, **context):
        """Log at CRITICAL level."""
        self.log(message, level="CRITICAL", **context)

# Global singleton instance
debug = DebugManager()
```

#### 4. Simple API Wrapper

**File**: `utils/debug.py`

```python
"""Simple debug API for use throughout the codebase."""

from utils.debug_manager import debug

# Export convenience functions
__all__ = ["debug", "log", "trace", "debug", "info", "warn", "error", "critical", "enabled"]

# Convenience exports
log = debug.log
trace = debug.trace
debug_log = debug.debug
info = debug.info
warn = debug.warn
error = debug.error
critical = debug.critical
enabled = debug.enabled
```

---

## Implementation Plan

### Phase 1: Foundation (Week 1)

**Goal**: Core infrastructure in place

**Tasks**:
1. ✅ Create `utils/debug_manager.py` with DebugManager class
2. ✅ Create `utils/debug.py` wrapper
3. ✅ Create default `configs/debug.yaml`
4. ✅ Add unit tests for DebugManager
5. ✅ Update `.gitignore` to exclude `logs/`

**Deliverables**:
- Working DebugManager
- Configuration file
- Unit tests (>90% coverage)
- Documentation

### Phase 2: Migration (Week 2)

**Goal**: Replace existing debug patterns

**Priority 1: High-value modules**
1. `models/base/model.py` - Replace logger with debug
2. `core/session/universal_session.py` - Add query debugging
3. `datapipelines/providers/alpha_vantage/` - Replace print()

**Priority 2: Notebook system**
1. `app/notebook/parser.py` - Remove print(), add debug
2. `app/ui/notebook_app_duckdb.py` - Clean up debug statements

**Priority 3: Ingestion pipeline**
1. `datapipelines/facets/` - Standardize on debug
2. `datapipelines/ingestors/` - Add debug logging

**Migration Script**: `scripts/migrate_to_debug_system.py`
```python
"""Automated migration helper - finds and suggests replacements."""

import ast
import re
from pathlib import Path

def find_print_statements(file_path: Path):
    """Find print() statements that look like debug logging."""
    with open(file_path) as f:
        content = f.read()

    # Pattern: print(f"Debug: ...")
    debug_prints = re.findall(r'print\(f?"Debug:.*?\)', content)

    return debug_prints

def suggest_replacement(print_stmt: str) -> str:
    """Suggest debug.log() replacement."""
    # Extract message
    match = re.search(r'print\(f?"([^"]+)"', print_stmt)
    if match:
        message = match.group(1).replace("Debug: ", "")
        return f'debug.debug("{message}")'
    return None

# Usage
for py_file in Path(".").rglob("*.py"):
    prints = find_print_statements(py_file)
    if prints:
        print(f"\n{py_file}:")
        for p in prints:
            print(f"  {p}")
            print(f"  → {suggest_replacement(p)}")
```

### Phase 3: Enhancement (Week 3)

**Goal**: Advanced features

**Tasks**:
1. Add performance profiling integration
2. Add structured logging (JSON output)
3. Add remote logging support (syslog, CloudWatch)
4. Add debug dashboard (web UI to toggle modules)
5. Add automatic context capture (SQL queries, DataFrame shapes)

### Phase 4: Documentation (Week 4)

**Goal**: Complete documentation and examples

**Tasks**:
1. Update CLAUDE.md with debug system guide
2. Create `docs/debugging-guide.md`
3. Add examples to `examples/debugging/`
4. Update contributor guide
5. Record screencast demo

---

## Usage Examples

### Example 1: Model Debugging

```python
# models/implemented/stocks/model.py

from utils.debug import debug

class StocksModel(BaseModel):
    def build(self):
        """Build stocks model from bronze layer."""
        debug.info("Starting stocks model build", model="stocks")

        # Load bronze data
        debug.debug("Loading securities reference",
                   filter="asset_type = 'stocks'",
                   table="bronze.securities_reference")

        ref_df = self.session.read_table("bronze.securities_reference")
        ref_df = ref_df.filter("asset_type = 'stocks'")

        debug.debug("Loaded reference data",
                   rows=ref_df.count(),
                   columns=len(ref_df.columns))

        # Transform
        if debug.enabled("models.stocks"):
            # Expensive operation - only if debugging enabled
            debug.trace("Reference data sample",
                       sample=ref_df.limit(5).toPandas().to_dict())

        # ... rest of build logic ...

        debug.info("Stocks model build complete",
                  tables_created=["dim_stock", "fact_stock_prices"],
                  total_rows=final_count)
```

**Output (when enabled)**:
```
2025-11-21 10:15:23 [INFO] [stocks:build:45] Starting stocks model build | model=stocks
2025-11-21 10:15:24 [DEBUG] [stocks:build:49] Loading securities reference | filter=asset_type = 'stocks' table=bronze.securities_reference
2025-11-21 10:15:25 [DEBUG] [stocks:build:54] Loaded reference data | rows=5000 columns=21
2025-11-21 10:15:26 [TRACE] [stocks:build:58] Reference data sample | sample={'ticker': ['AAPL', 'MSFT', ...]}
2025-11-21 10:16:30 [INFO] [stocks:build:89] Stocks model build complete | tables_created=['dim_stock', 'fact_stock_prices'] total_rows=5000000
```

### Example 2: Ingestion Debugging

```python
# datapipelines/providers/alpha_vantage/provider.py

from utils.debug import debug

class AlphaVantageProvider:
    def fetch_company_overview(self, ticker: str):
        """Fetch company overview data."""
        debug.debug("Fetching company overview",
                   ticker=ticker,
                   provider="alpha_vantage")

        url = self._build_url("OVERVIEW", symbol=ticker)

        debug.trace("HTTP request", url=url, method="GET")

        response = self.http_client.get(url)

        debug.trace("HTTP response",
                   status_code=response.status_code,
                   size_bytes=len(response.content))

        if response.status_code != 200:
            debug.error("API request failed",
                       ticker=ticker,
                       status_code=response.status_code,
                       error=response.text)
            raise APIError(f"Failed to fetch {ticker}")

        data = response.json()

        debug.debug("Parsed company data",
                   ticker=ticker,
                   cik=data.get("CIK"),
                   market_cap=data.get("MarketCapitalization"))

        return data
```

### Example 3: Query Debugging

```python
# core/session/universal_session.py

from utils.debug import debug

class UniversalSession:
    def query(self, sql: str, filters: Optional[List[Dict]] = None):
        """Execute cross-model SQL query."""
        debug.info("Executing query", session_type=self.backend)

        # Log query if tracing enabled
        if debug.enabled("session.query"):
            debug.trace("SQL query", sql=sql, filters=filters)

        # Apply filters
        if filters:
            debug.debug("Applying filters", count=len(filters))
            sql = self._apply_filters_to_sql(sql, filters)
            debug.trace("SQL after filters", sql=sql)

        # Execute
        start_time = time.time()
        result = self._execute_sql(sql)
        duration_ms = (time.time() - start_time) * 1000

        debug.info("Query complete",
                  duration_ms=duration_ms,
                  rows_returned=result.count())

        # Warn on slow queries
        if duration_ms > 5000:
            debug.warn("Slow query detected",
                      duration_ms=duration_ms,
                      sql=sql[:200])  # First 200 chars

        return result
```

---

## Configuration Reference

### Module Hierarchy

```
modules:
  models:                    # All models
    enabled: true
    level: DEBUG
    modules:
      stocks:               # Specific model
        enabled: true
        level: TRACE        # Override parent level
      company:
        enabled: true
      options:
        enabled: false      # Disable entirely

  ingestion:                # All ingestion
    enabled: true
    modules:
      providers:            # All providers
        enabled: true
        modules:
          alpha_vantage:    # Specific provider
            enabled: true
            level: DEBUG
      facets:               # All facets
        enabled: true
      sinks:
        enabled: false

  session:
    modules:
      query:
        enabled: true
        level: TRACE        # Log all queries
      filters:
        enabled: true
      joins:
        enabled: false      # Disable join debugging
```

### Environment Overrides

**Development** (`DE_FUNK_ENV=development`):
```yaml
environments:
  development:
    level: DEBUG
    console: true
    file: true
    handlers:
      console:
        colorize: true
        format: "%(levelname)s | %(message)s"  # Simpler format
```

**Production** (`DE_FUNK_ENV=production`):
```yaml
environments:
  production:
    level: WARN           # Only warnings and errors
    console: false        # No console output
    file: true            # File logging only
    syslog: true          # Send to syslog
    handlers:
      file:
        format: "%(asctime)s [%(levelname)s] [%(process)d] [%(module)s] %(message)s"
```

**Testing** (`DE_FUNK_ENV=testing`):
```yaml
environments:
  testing:
    level: CRITICAL       # Suppress all but critical
    console: false
    file: false
```

---

## Migration Guide

### Step 1: Install Debug System

```bash
# 1. Copy files
cp utils/debug_manager.py utils/
cp utils/debug.py utils/
cp configs/debug.yaml configs/

# 2. Set environment (optional)
export DE_FUNK_ENV=development

# 3. Test
python -c "from utils.debug import debug; debug.info('Test message')"
```

### Step 2: Update Imports

**Before**:
```python
import logging
logger = logging.getLogger(__name__)
```

**After**:
```python
from utils.debug import debug
```

### Step 3: Replace Logging Calls

**Before**:
```python
logger.debug(f"Processing {ticker}")
logger.info(f"Loaded {count} rows")
logger.error(f"Failed to load: {error}")
```

**After**:
```python
debug.debug("Processing ticker", ticker=ticker)
debug.info("Loaded rows", count=count)
debug.error("Failed to load", error=str(error))
```

### Step 4: Remove print() Statements

**Before**:
```python
print(f"Debug: filters = {filters}")
```

**After**:
```python
debug.debug("Applying filters", filters=filters)
```

### Step 5: Add Conditional Expensive Operations

**Before**:
```python
# Always runs, even in production
df_sample = df.limit(100).toPandas()
logger.debug(f"Sample data: {df_sample.to_dict()}")
```

**After**:
```python
# Only runs if debugging enabled (zero overhead otherwise)
if debug.enabled("models.stocks"):
    df_sample = df.limit(100).toPandas()
    debug.trace("Sample data", sample=df_sample.to_dict())
```

---

## Appendix: Alternative Approaches Considered

### Option 1: Use Python logging directly

**Pros**: Standard library, widely known
**Cons**: Verbose setup, no per-module toggles, requires code changes

**Verdict**: ❌ Rejected - not flexible enough

### Option 2: Use structlog library

**Pros**: Structured logging, good for JSON output
**Cons**: External dependency, overkill for current needs

**Verdict**: 🤔 Consider for Phase 3

### Option 3: Use decorator pattern

```python
@debug.trace
def expensive_function():
    pass
```

**Pros**: Clean syntax
**Cons**: Invasive, requires modifying all functions

**Verdict**: ❌ Rejected - too invasive

### Option 4: Environment variables only

```bash
export DEBUG_MODELS=true
export DEBUG_INGESTION=true
```

**Pros**: Simple, no config file
**Cons**: Can't have complex hierarchies, not version-controlled

**Verdict**: ❌ Rejected - not maintainable

---

## Summary

This debugging system proposal provides:

✅ **Centralized control** via YAML configuration
✅ **Per-module toggles** for fine-grained debugging
✅ **Zero performance overhead** when disabled
✅ **Clean API** that's easy to use
✅ **Environment-aware** (dev/test/prod)
✅ **Backward compatible** migration path

**Recommended**: Approve and implement in 4-week phased approach.

**Next Steps**:
1. Review proposal with team
2. Approve architecture
3. Begin Phase 1 implementation
4. Migrate high-priority modules first
5. Full rollout within 4 weeks

---

**End of Document**
