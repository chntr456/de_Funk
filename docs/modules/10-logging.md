---
title: "Logging"
last_updated: "2026-03-30"
status: "draft"
source_files:
  - src/de_funk/config/logging.py
---

# Logging

> Structured + colored logging, LogTimer context manager, file + console output.

## Purpose & Design Decisions

### What Problem This Solves

<!-- TODO: Explain the problem this group addresses. -->

### Key Design Decisions

| Decision | Rationale | Alternative Considered |
|----------|-----------|----------------------|
| <!-- TODO --> | | |

### Config-Driven Aspects

| Behavior | Controlled By | Location |
|----------|--------------|----------|
| <!-- TODO --> | | |

## Architecture

### Where This Fits

```
[Upstream] --> [THIS GROUP] --> [Downstream]
```

<!-- TODO: Brief explanation of data/control flow. -->

### Dependencies

| Depends On | What For |
|------------|----------|
| <!-- TODO --> | |

| Depended On By | What For |
|----------------|----------|
| <!-- TODO --> | |

## Key Classes

### LogConfig

**File**: `src/de_funk/config/logging.py:41`

**Purpose**: Logging configuration with sensible defaults.

| Attribute | Type |
|-----------|------|
| `console_level` | `str` |
| `file_level` | `str` |
| `log_dir` | `Path` |
| `log_file` | `str` |
| `json_log_file` | `str` |
| `max_bytes` | `int` |
| `backup_count` | `int` |
| `console_format` | `str` |
| `file_format` | `str` |
| `date_format` | `str` |
| `enable_json` | `bool` |
| `module_levels` | `Dict[str, str]` |

| Method | Description |
|--------|-------------|
| `from_env(repo_root: Optional[Path]) -> 'LogConfig'` | Create LogConfig from environment variables. |

### StructuredFormatter (Formatter)

**File**: `src/de_funk/config/logging.py:115`

**Purpose**: JSON formatter for structured logging.

| Method | Description |
|--------|-------------|
| `format(record: logging.LogRecord) -> str` | Format log record as JSON. |

### ColoredFormatter (Formatter)

**File**: `src/de_funk/config/logging.py:144`

**Purpose**: Colored console output for better readability.

| Attribute | Type |
|-----------|------|
| `COLORS` | `—` |
| `RESET` | `—` |

| Method | Description |
|--------|-------------|
| `format(record: logging.LogRecord) -> str` | Format with optional colors. |

### LogTimer

**File**: `src/de_funk/config/logging.py:290`

**Purpose**: Context manager for timing operations with automatic logging.

## How to Use

### Common Operations

<!-- TODO: Runnable code examples with expected output -->

### Integration Examples

<!-- TODO: Show cross-group usage -->

## Triage & Debugging

### Symptom Table

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| <!-- TODO --> | | |

### Debug Checklist

- [ ] <!-- TODO -->

### Common Pitfalls

1. <!-- TODO -->

## File Reference

| File | Purpose | Key Exports |
|------|---------|-------------|
| `src/de_funk/config/logging.py` | Centralized Logging Configuration for de_Funk. | `LogConfig`, `StructuredFormatter`, `ColoredFormatter`, `LogTimer` |
