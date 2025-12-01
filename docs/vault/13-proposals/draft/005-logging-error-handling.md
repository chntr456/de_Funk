# Proposal: Centralized Logging & Error Handling Framework

**Status**: In Progress (Phases 1-4 Partial Complete)
**Author**: Claude
**Date**: 2025-11-29
**Updated**: 2025-12-01
**Priority**: High

**Implementation Progress**:
- ✅ Phase 1: Foundation (config/logging.py, core/exceptions.py, core/error_handling.py)
- ✅ Phase 2: Core Module Migration (config/loader.py, core/context.py, core/duckdb_connection.py)
- ✅ Phase 3: Pipeline Migration (datapipelines/base/http_client.py, alpha_vantage_ingestor.py)
- 🔄 Phase 4: Script Migration (3/27 scripts migrated: diagnose_silver_data, diagnose_bronze_data, validate_all_scripts)
- ✅ Phase 6: Test Suite (71 tests: test_logging.py, test_exceptions.py, test_error_handling.py)
- ⏳ Phase 5: Documentation

---

## Summary

This proposal establishes a centralized logging and error handling framework to replace the current ad-hoc approach. Analysis revealed 3,274 print statements across 84 files and 290 bare exception catches (79% of all handlers). This proposal provides a structured approach to observability, debugging, and error recovery.

---

## Motivation

### Current State Analysis

| Metric | Current Value | Target |
|--------|---------------|--------|
| Print statements | 3,274 in 84 files | <100 (user-facing only) |
| Logger calls | 404 in 17 files | 100% coverage |
| Print-to-Log ratio | 8:1 | 0:1 |
| Bare `except:` | 290 (79%) | 0% |
| Centralized config | None | Single config |
| Log rotation | None | Automatic |
| Structured logging | None | JSON format |

### Problem Categories

#### 1. Excessive Print Statements

**Top Offenders**:
```
scripts/diagnose_silver_data.py         79 prints
scripts/forecast/run_forecasts_large_cap.py  64 prints
run_app.py                              28 prints
scripts/forecast/verify_forecast_config.py   18 prints
```

**Impact**:
- No log level filtering
- Can't redirect to files
- No timestamps or context
- Difficult to debug production issues

#### 2. Bare Exception Catches

**Examples**:
```python
# config/loader.py:154
except Exception as e:
    warnings.warn(f"Failed to load .env file: {e}")

# core/duckdb_connection.py:705
except Exception:
    pass  # Silent failure!

# datapipelines/base/http_client.py:71
except Exception:
    pass  # Swallows all errors
```

**Impact**:
- Catches `KeyboardInterrupt`, `SystemExit`
- Masks programming errors
- Makes debugging impossible

#### 3. Inconsistent Patterns

| File | Pattern | Issue |
|------|---------|-------|
| `config/loader.py` | Specific exceptions + logging | Good |
| `run_app.py` | Print statements | Bad |
| `app/ui/notebook_app.py` | `st.error()` only | No persistence |
| `datapipelines/ingestors/` | Mix of print + logger | Inconsistent |

---

## Detailed Design

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                      LOGGING CONFIGURATION                          │
├─────────────────────────────────────────────────────────────────────┤
│  config/logging.py                                                  │
│    ├── LogConfig (dataclass)                                        │
│    ├── setup_logging()                                              │
│    └── get_logger(__name__)                                         │
└─────────────────────────────────────────────────────────────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Console       │    │     File        │    │   Structured    │
│   Handler       │    │    Handler      │    │    Handler      │
│  (DEBUG+)       │    │   (INFO+)       │    │   (JSON)        │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
    Terminal            logs/de_funk.log           logs/json/
```

### Component 1: Centralized Logging Configuration

**File**: `config/logging.py`

```python
"""
Centralized Logging Configuration for de_Funk.

Usage:
    from config.logging import setup_logging, get_logger

    # In main entry point (run_app.py, scripts, etc.)
    setup_logging()

    # In any module
    logger = get_logger(__name__)
    logger.info("Processing started", extra={'ticker': 'AAPL'})
"""

import logging
import logging.handlers
import sys
import json
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

@dataclass
class LogConfig:
    """Logging configuration with sensible defaults."""

    # Log levels
    console_level: str = "INFO"
    file_level: str = "DEBUG"

    # Output settings
    log_dir: Path = field(default_factory=lambda: Path("logs"))
    log_file: str = "de_funk.log"
    json_log_file: str = "de_funk.json"

    # Rotation settings
    max_bytes: int = 10 * 1024 * 1024  # 10 MB
    backup_count: int = 5

    # Format settings
    console_format: str = "%(asctime)s [%(levelname)8s] %(name)s: %(message)s"
    file_format: str = "%(asctime)s [%(levelname)8s] %(name)s (%(filename)s:%(lineno)d): %(message)s"
    date_format: str = "%Y-%m-%d %H:%M:%S"

    # Structured logging
    enable_json: bool = False

    # Module-specific levels (for noisy modules)
    module_levels: Dict[str, str] = field(default_factory=lambda: {
        'urllib3': 'WARNING',
        'duckdb': 'WARNING',
        'pyspark': 'WARNING',
        'streamlit': 'WARNING',
    })


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }

        # Add extra fields
        if hasattr(record, 'ticker'):
            log_data['ticker'] = record.ticker
        if hasattr(record, 'model'):
            log_data['model'] = record.model
        if hasattr(record, 'duration_ms'):
            log_data['duration_ms'] = record.duration_ms

        # Add exception info
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        return json.dumps(log_data)


class ColoredFormatter(logging.Formatter):
    """Colored console output for better readability."""

    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, '')
        record.levelname = f"{color}{record.levelname:8s}{self.RESET}"
        return super().format(record)


def setup_logging(config: Optional[LogConfig] = None) -> None:
    """
    Configure logging for the application.

    Should be called once at application startup.
    """
    if config is None:
        config = LogConfig()

    # Create log directory
    config.log_dir.mkdir(parents=True, exist_ok=True)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Clear existing handlers
    root_logger.handlers.clear()

    # Console handler with colors
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, config.console_level))
    console_handler.setFormatter(ColoredFormatter(
        config.console_format,
        datefmt=config.date_format
    ))
    root_logger.addHandler(console_handler)

    # File handler with rotation
    file_path = config.log_dir / config.log_file
    file_handler = logging.handlers.RotatingFileHandler(
        file_path,
        maxBytes=config.max_bytes,
        backupCount=config.backup_count,
    )
    file_handler.setLevel(getattr(logging, config.file_level))
    file_handler.setFormatter(logging.Formatter(
        config.file_format,
        datefmt=config.date_format
    ))
    root_logger.addHandler(file_handler)

    # JSON handler (optional)
    if config.enable_json:
        json_path = config.log_dir / config.json_log_file
        json_handler = logging.handlers.RotatingFileHandler(
            json_path,
            maxBytes=config.max_bytes,
            backupCount=config.backup_count,
        )
        json_handler.setLevel(logging.DEBUG)
        json_handler.setFormatter(StructuredFormatter())
        root_logger.addHandler(json_handler)

    # Set module-specific levels
    for module, level in config.module_levels.items():
        logging.getLogger(module).setLevel(getattr(logging, level))

    # Log startup
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized: console={config.console_level}, file={config.file_level}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for the given module.

    Usage:
        logger = get_logger(__name__)
        logger.info("Something happened")
    """
    return logging.getLogger(name)


# Context managers for performance logging
class LogTimer:
    """Context manager for timing operations."""

    def __init__(self, logger: logging.Logger, operation: str, level: int = logging.DEBUG):
        self.logger = logger
        self.operation = operation
        self.level = level
        self.start_time = None

    def __enter__(self):
        self.start_time = datetime.now()
        self.logger.log(self.level, f"Starting: {self.operation}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = (datetime.now() - self.start_time).total_seconds() * 1000
        if exc_type:
            self.logger.error(
                f"Failed: {self.operation} ({duration:.2f}ms)",
                exc_info=True
            )
        else:
            self.logger.log(
                self.level,
                f"Completed: {self.operation} ({duration:.2f}ms)",
                extra={'duration_ms': duration}
            )
```

### Component 2: Custom Exception Hierarchy

**File**: `core/exceptions.py`

```python
"""
Custom Exception Hierarchy for de_Funk.

Provides:
- Typed exceptions for different error categories
- Consistent error messages
- Logging integration
- Error recovery hints
"""

from typing import Optional, Dict, Any


class DeFunkError(Exception):
    """Base exception for all de_Funk errors."""

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        recovery_hint: Optional[str] = None
    ):
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.recovery_hint = recovery_hint

    def __str__(self) -> str:
        result = self.message
        if self.details:
            result += f" Details: {self.details}"
        if self.recovery_hint:
            result += f" Hint: {self.recovery_hint}"
        return result


# ============================================
# Configuration Errors
# ============================================

class ConfigurationError(DeFunkError):
    """Error in configuration loading or validation."""
    pass


class MissingConfigError(ConfigurationError):
    """Required configuration is missing."""

    def __init__(self, config_key: str, config_file: Optional[str] = None):
        super().__init__(
            f"Missing required configuration: {config_key}",
            details={'key': config_key, 'file': config_file},
            recovery_hint=f"Add '{config_key}' to your configuration file or environment"
        )


class InvalidConfigError(ConfigurationError):
    """Configuration value is invalid."""

    def __init__(self, config_key: str, value: Any, expected: str):
        super().__init__(
            f"Invalid configuration value for '{config_key}': {value}",
            details={'key': config_key, 'value': value, 'expected': expected},
            recovery_hint=f"Expected {expected}"
        )


# ============================================
# Data Pipeline Errors
# ============================================

class PipelineError(DeFunkError):
    """Error in data pipeline execution."""
    pass


class IngestionError(PipelineError):
    """Error during data ingestion from API."""

    def __init__(self, provider: str, endpoint: str, error: str):
        super().__init__(
            f"Ingestion failed for {provider}/{endpoint}: {error}",
            details={'provider': provider, 'endpoint': endpoint},
            recovery_hint="Check API credentials and rate limits"
        )


class RateLimitError(PipelineError):
    """API rate limit exceeded."""

    def __init__(self, provider: str, retry_after: Optional[int] = None):
        super().__init__(
            f"Rate limit exceeded for {provider}",
            details={'provider': provider, 'retry_after': retry_after},
            recovery_hint=f"Wait {retry_after or 60} seconds before retrying"
        )
        self.retry_after = retry_after


class TransformationError(PipelineError):
    """Error during data transformation."""

    def __init__(self, stage: str, error: str, record_count: Optional[int] = None):
        super().__init__(
            f"Transformation failed at stage '{stage}': {error}",
            details={'stage': stage, 'records': record_count}
        )


# ============================================
# Model Errors
# ============================================

class ModelError(DeFunkError):
    """Error in model operations."""
    pass


class ModelNotFoundError(ModelError):
    """Requested model does not exist."""

    def __init__(self, model_name: str):
        super().__init__(
            f"Model not found: {model_name}",
            details={'model': model_name},
            recovery_hint="Check available models with ModelRegistry.list_models()"
        )


class TableNotFoundError(ModelError):
    """Requested table does not exist in model."""

    def __init__(self, model_name: str, table_name: str):
        super().__init__(
            f"Table '{table_name}' not found in model '{model_name}'",
            details={'model': model_name, 'table': table_name}
        )


class MeasureError(ModelError):
    """Error calculating a measure."""

    def __init__(self, measure_name: str, error: str):
        super().__init__(
            f"Failed to calculate measure '{measure_name}': {error}",
            details={'measure': measure_name}
        )


class DependencyError(ModelError):
    """Model dependency not satisfied."""

    def __init__(self, model_name: str, missing_deps: list):
        super().__init__(
            f"Model '{model_name}' has unmet dependencies: {missing_deps}",
            details={'model': model_name, 'missing': missing_deps},
            recovery_hint="Build dependent models first"
        )


# ============================================
# Query Errors
# ============================================

class QueryError(DeFunkError):
    """Error executing a query."""
    pass


class FilterError(QueryError):
    """Error applying filters."""

    def __init__(self, filter_spec: Dict, error: str):
        super().__init__(
            f"Invalid filter specification: {error}",
            details={'filter': filter_spec}
        )


class JoinError(QueryError):
    """Error joining tables."""

    def __init__(self, left_table: str, right_table: str, error: str):
        super().__init__(
            f"Failed to join '{left_table}' with '{right_table}': {error}",
            details={'left': left_table, 'right': right_table}
        )


# ============================================
# Storage Errors
# ============================================

class StorageError(DeFunkError):
    """Error in storage operations."""
    pass


class DataNotFoundError(StorageError):
    """Requested data does not exist."""

    def __init__(self, path: str, table: Optional[str] = None):
        super().__init__(
            f"Data not found at: {path}",
            details={'path': path, 'table': table},
            recovery_hint="Run ingestion pipeline to populate data"
        )


class WriteError(StorageError):
    """Error writing data to storage."""

    def __init__(self, path: str, error: str):
        super().__init__(
            f"Failed to write to '{path}': {error}",
            details={'path': path}
        )


# ============================================
# Forecast Errors
# ============================================

class ForecastError(DeFunkError):
    """Error in forecasting operations."""
    pass


class InsufficientDataError(ForecastError):
    """Not enough data for forecasting."""

    def __init__(self, required: int, available: int, ticker: Optional[str] = None):
        super().__init__(
            f"Insufficient data for forecast: need {required}, have {available}",
            details={'required': required, 'available': available, 'ticker': ticker}
        )


class ModelTrainingError(ForecastError):
    """Error training forecast model."""

    def __init__(self, model_type: str, error: str):
        super().__init__(
            f"Failed to train {model_type} model: {error}",
            details={'model_type': model_type}
        )
```

### Component 3: Error Handler Decorator

**File**: `core/error_handling.py`

```python
"""
Error Handling Utilities.

Provides decorators and utilities for consistent error handling.
"""

import functools
import traceback
from typing import Callable, Type, Tuple, Optional, Any
from config.logging import get_logger

logger = get_logger(__name__)


def handle_exceptions(
    *exception_types: Type[Exception],
    default_return: Any = None,
    log_level: str = 'error',
    reraise: bool = False
) -> Callable:
    """
    Decorator for consistent exception handling.

    Usage:
        @handle_exceptions(ValueError, KeyError, default_return=[])
        def risky_function():
            ...

        @handle_exceptions(reraise=True)  # Log and reraise
        def must_succeed():
            ...
    """
    if not exception_types:
        exception_types = (Exception,)

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except exception_types as e:
                log_func = getattr(logger, log_level)
                log_func(
                    f"Exception in {func.__name__}: {type(e).__name__}: {e}",
                    exc_info=True
                )
                if reraise:
                    raise
                return default_return
        return wrapper
    return decorator


def retry_on_exception(
    *exception_types: Type[Exception],
    max_retries: int = 3,
    delay_seconds: float = 1.0,
    backoff_factor: float = 2.0,
    on_retry: Optional[Callable] = None
) -> Callable:
    """
    Decorator for automatic retry with exponential backoff.

    Usage:
        @retry_on_exception(ConnectionError, max_retries=3)
        def fetch_data():
            ...
    """
    import time

    if not exception_types:
        exception_types = (Exception,)

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            delay = delay_seconds

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exception_types as e:
                    last_exception = e

                    if attempt < max_retries:
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_retries + 1} failed for "
                            f"{func.__name__}: {e}. Retrying in {delay:.1f}s..."
                        )

                        if on_retry:
                            on_retry(attempt, e)

                        time.sleep(delay)
                        delay *= backoff_factor
                    else:
                        logger.error(
                            f"All {max_retries + 1} attempts failed for {func.__name__}",
                            exc_info=True
                        )

            raise last_exception
        return wrapper
    return decorator


class ErrorContext:
    """
    Context manager for detailed error reporting.

    Usage:
        with ErrorContext("Loading model", model_name=name):
            model = load_model(name)
    """

    def __init__(self, operation: str, **context):
        self.operation = operation
        self.context = context

    def __enter__(self):
        logger.debug(f"Starting: {self.operation}", extra=self.context)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            logger.error(
                f"Failed: {self.operation}",
                extra={
                    **self.context,
                    'exception_type': exc_type.__name__,
                    'exception_message': str(exc_val),
                }
            )
            # Don't suppress the exception
            return False
        else:
            logger.debug(f"Completed: {self.operation}", extra=self.context)
            return False
```

### Component 4: Migration Guide

**Converting Print to Logger**:

```python
# BEFORE
print(f"Loading model: {model_name}")
print(f"Found {len(records)} records")
print(f"Error: {e}")

# AFTER
from config.logging import get_logger
logger = get_logger(__name__)

logger.info(f"Loading model: {model_name}")
logger.debug(f"Found {len(records)} records")
logger.error(f"Error occurred", exc_info=True)
```

**Converting Bare Exceptions**:

```python
# BEFORE
try:
    do_something()
except Exception as e:
    print(f"Error: {e}")
    pass  # Silent failure

# AFTER
from core.exceptions import TransformationError
from config.logging import get_logger

logger = get_logger(__name__)

try:
    do_something()
except ValueError as e:
    logger.warning(f"Value error in transformation: {e}")
    # Handle gracefully
except IOError as e:
    logger.error(f"IO error: {e}")
    raise TransformationError("data_load", str(e))
except Exception as e:
    logger.critical(f"Unexpected error: {e}", exc_info=True)
    raise  # Reraise unexpected errors
```

---

## Implementation Plan

### Phase 1: Foundation (Week 1)
1. Create `config/logging.py` with LogConfig
2. Create `core/exceptions.py` with exception hierarchy
3. Create `core/error_handling.py` with decorators
4. Update `run_app.py` to initialize logging

### Phase 2: Core Migration (Week 2)
1. Replace prints in `config/` modules (loader.py, model_loader.py)
2. Replace prints in `core/` modules
3. Replace prints in `models/base/` modules
4. Add proper exception handling in configuration loading

### Phase 3: Pipeline Migration (Week 3)
1. Replace prints in `datapipelines/`
2. Add structured logging for API calls
3. Implement retry decorators for HTTP client
4. Add timing logs for ingestion operations

### Phase 4: UI/Scripts Migration (Week 4)
1. Replace prints in `scripts/`
2. Add Streamlit → file logging bridge
3. Migrate `run_app.py`, `run_full_pipeline.py`
4. Update forecast scripts

### Phase 5: Testing & Documentation (Week 5)
1. Add logging tests
2. Update CLAUDE.md with logging guidelines
3. Create logging troubleshooting guide
4. Performance testing of logging overhead

---

## Files to Modify (Priority Order)

| Priority | File | Print Count | Action |
|----------|------|-------------|--------|
| 1 | `run_app.py` | 28 | Initialize logging, replace prints |
| 2 | `config/loader.py` | 5 | Already has logger, enhance |
| 3 | `core/context.py` | 12 | Add logger, replace prints |
| 4 | `datapipelines/base/http_client.py` | 8 | Add structured logging |
| 5 | `models/base/model.py` | 15 | Add logger |
| 6 | `scripts/forecast/run_forecasts.py` | 64 | Full migration |
| 7 | `app/ui/notebook_app_duckdb.py` | 20 | Add file logging bridge |

---

## Open Questions

1. Should we use JSON logging in production (vs. human-readable)?
2. What log retention policy (7 days? 30 days?)?
3. Should we integrate with external logging (Datadog, CloudWatch)?
4. How to handle Streamlit's own logging?

---

## References

- Python logging docs: https://docs.python.org/3/library/logging.html
- Structlog (alternative): https://www.structlog.org/
- Current print locations: See analysis above
