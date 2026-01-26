# Logging & Error Handling Framework

**Centralized observability and error management for de_Funk**

---

## Overview

The logging and error handling framework provides:

- **Centralized logging** with file rotation and colored console output
- **Custom exception hierarchy** with recovery hints
- **Error handling decorators** for automatic retry and graceful fallbacks

---

## Components

| Component | Location | Purpose |
|-----------|----------|---------|
| Logging Framework | `config/logging.py` | setup_logging(), get_logger(), LogTimer |
| Exception Hierarchy | `core/exceptions.py` | DeFunkError and 18+ specific types |
| Error Handling | `core/error_handling.py` | Decorators and context managers |

---

## Logging Framework

### Quick Start

```python
from config.logging import setup_logging, get_logger, LogTimer

# Initialize once at script startup
setup_logging()

# Get module-specific logger
logger = get_logger(__name__)

# Use appropriate log levels
logger.debug("Detailed info (file only)")
logger.info("Progress update (console + file)")
logger.warning("Issue that doesn't stop execution")
logger.error("Error with stack trace", exc_info=True)
```

### Log Levels

| Level | Console | File | Use Case |
|-------|---------|------|----------|
| DEBUG | No | Yes | Detailed debugging info |
| INFO | Yes | Yes | Progress updates, milestones |
| WARNING | Yes | Yes | Non-critical issues |
| ERROR | Yes | Yes | Failures, exceptions |
| CRITICAL | Yes | Yes | System-level failures |

### LogTimer Context Manager

Time operations automatically:

```python
from config.logging import LogTimer

with LogTimer(logger, "Building model"):
    model.build()
# Output: "Building model completed in 2.35s"

# With custom level
with LogTimer(logger, "Quick operation", level='debug'):
    quick_function()
```

### Configuration

```python
from config.logging import LogConfig, setup_logging

# Custom configuration
config = LogConfig(
    console_level='DEBUG',      # More verbose console
    file_level='DEBUG',         # Default
    log_file='logs/custom.log', # Custom path
    max_bytes=20*1024*1024,     # 20MB rotation
    backup_count=10             # Keep 10 backups
)

setup_logging(config)
```

### Log File Location

- **Default Path**: `logs/de_funk.log`
- **Rotation**: 10MB max, 5 backup files
- **Format**: `2024-12-02 10:15:32 | INFO | module.name | Message`

### Formatters

**ColoredFormatter** (Console):
- INFO: White
- WARNING: Yellow
- ERROR: Red
- DEBUG: Dim

**StructuredFormatter** (JSON output for log aggregators):
```python
from config.logging import StructuredFormatter
import logging

handler = logging.FileHandler("logs/structured.json")
handler.setFormatter(StructuredFormatter())
```

---

## Exception Hierarchy

### Base Exception

All de_Funk exceptions inherit from `DeFunkError`:

```python
from core.exceptions import DeFunkError

class DeFunkError(Exception):
    def __init__(self, message, details=None, recovery_hint=None):
        self.message = message
        self.details = details or {}
        self.recovery_hint = recovery_hint
```

### Exception Categories

```
DeFunkError (base)
├── ConfigurationError
│   ├── MissingConfigError
│   └── InvalidConfigError
├── PipelineError
│   ├── IngestionError
│   ├── RateLimitError
│   └── TransformationError
├── ModelError
│   ├── ModelNotFoundError
│   ├── TableNotFoundError
│   ├── MeasureError
│   └── DependencyError
├── QueryError
│   ├── FilterError
│   └── JoinError
├── StorageError
│   ├── DataNotFoundError
│   └── WriteError
└── ForecastError
    ├── InsufficientDataError
    └── ModelTrainingError
```

### Using Exceptions

```python
from core.exceptions import ModelNotFoundError, RateLimitError

# Raising with recovery hint
raise ModelNotFoundError(
    "stocks",
    available_models=["core", "company", "macro"]
)

# Catching and using hints
try:
    model = registry.get_model("invalid")
except ModelNotFoundError as e:
    print(e)               # "Model not found: 'invalid'"
    print(e.recovery_hint) # "Available models: core, company, macro"
    print(e.details)       # {'model': 'invalid', 'available': [...]}
```

### Common Exceptions

| Exception | Use Case | Details Included |
|-----------|----------|------------------|
| `ModelNotFoundError` | Model doesn't exist | model, available |
| `TableNotFoundError` | Table doesn't exist | table, model, available |
| `MeasureError` | Measure calculation failed | measure, model, reason |
| `RateLimitError` | API rate limit hit | provider, limit, retry_after |
| `MissingConfigError` | Required config missing | key, config_file |
| `DataNotFoundError` | Expected data missing | path, query |

---

## Error Handling Utilities

### @handle_exceptions Decorator

Catch specific exceptions and return defaults:

```python
from core.error_handling import handle_exceptions

@handle_exceptions(ValueError, TypeError, default_return=None)
def parse_config(data):
    return json.loads(data)

# With logging
@handle_exceptions(
    ValueError,
    default_return=[],
    log_level='warning'
)
def fetch_items():
    ...
```

### @retry_on_exception Decorator

Automatic retry with exponential backoff:

```python
from core.error_handling import retry_on_exception

@retry_on_exception(
    ConnectionError,
    max_retries=3,
    delay_seconds=1.0,
    backoff_multiplier=2.0
)
def fetch_api_data(url):
    return requests.get(url)

# Retries: 0s, 1s, 2s, 4s (exponential backoff)
```

### ErrorContext Manager

Add context to errors without changing exception type:

```python
from core.error_handling import ErrorContext

with ErrorContext("Processing ticker data", ticker="AAPL", step="transform"):
    process_data(ticker)
# If error occurs: logs context, re-raises original exception
```

### safe_call Function

Execute functions safely with default fallback:

```python
from core.error_handling import safe_call

# Returns "default" if risky_function raises any exception
result = safe_call(risky_function, default="default")

# With arguments
result = safe_call(parse_json, args=(data,), default={})
```

---

## Best Practices

### 1. Initialize Logging Early

```python
# At script startup, before other imports that might log
from config.logging import setup_logging
setup_logging()
```

### 2. Use Module-Specific Loggers

```python
# Each module gets its own logger
logger = get_logger(__name__)
# Produces: "module.submodule.file" in log output
```

### 3. Log Exceptions with Stack Traces

```python
try:
    risky_operation()
except Exception as e:
    logger.error(f"Operation failed: {e}", exc_info=True)
    raise  # Re-raise after logging
```

### 4. Use Specific Exceptions

```python
# Instead of generic Exception
from core.exceptions import ConfigurationError, MissingConfigError

if not config.get('api_key'):
    raise MissingConfigError('api_key', config_file='.env')
```

### 5. Include Recovery Hints

```python
raise ModelNotFoundError(
    "invalid_model",
    available_models=list(registry.models.keys())
)
# User sees: "Available models: core, company, stocks"
```

### 6. Chain Exceptions

```python
try:
    load_config()
except FileNotFoundError as e:
    raise ConfigurationError("Config file missing") from e
# Preserves original exception in traceback
```

---

## Validation

Run the validation script to verify the framework:

```bash
python -m scripts.test.validate_logging_framework
```

Expected output: 6/6 tests pass

---

## Migration Guide

### From print() to logger

```python
# Before
print(f"Processing {ticker}...")
print(f"Error: {e}")

# After
logger.info(f"Processing {ticker}")
logger.error(f"Processing failed: {e}", exc_info=True)
```

### From bare except to specific

```python
# Before
try:
    do_something()
except:
    pass

# After
try:
    do_something()
except ValueError as e:
    logger.warning(f"Invalid value: {e}")
except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
    raise
```

---

## Related Documentation

- [Proposal 005](../13-proposals/accepted/005-logging-error-handling.md) - Original proposal
- [Configuration](../11-configuration/) - Config system
- [Troubleshooting](../12-troubleshooting/) - Debug guide
