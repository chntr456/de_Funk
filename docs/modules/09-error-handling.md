---
title: "Error Handling"
last_updated: "2026-03-30"
status: "draft"
source_files:
  - src/de_funk/core/exceptions.py
  - src/de_funk/core/error_handling.py
  - src/de_funk/core/validation.py
---

# Error Handling

> Exception hierarchy (23 typed errors), ErrorContext for structured debugging, and validation utilities.

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

### DeFunkError (Exception)

**File**: `src/de_funk/core/exceptions.py:57`

**Purpose**: Base exception for all de_Funk errors.

### ConfigurationError (DeFunkError)

**File**: `src/de_funk/core/exceptions.py:107`

**Purpose**: Error in configuration loading or validation.

### MissingConfigError (ConfigurationError)

**File**: `src/de_funk/core/exceptions.py:112`

**Purpose**: Required configuration is missing.

### InvalidConfigError (ConfigurationError)

**File**: `src/de_funk/core/exceptions.py:136`

**Purpose**: Configuration value is invalid.

### PipelineError (DeFunkError)

**File**: `src/de_funk/core/exceptions.py:162`

**Purpose**: Error in data pipeline execution.

### IngestionError (PipelineError)

**File**: `src/de_funk/core/exceptions.py:167`

**Purpose**: Error during data ingestion from API.

### RateLimitError (PipelineError)

**File**: `src/de_funk/core/exceptions.py:189`

**Purpose**: API rate limit exceeded.

### TransformationError (PipelineError)

**File**: `src/de_funk/core/exceptions.py:210`

**Purpose**: Error during data transformation.

### ModelError (DeFunkError)

**File**: `src/de_funk/core/exceptions.py:239`

**Purpose**: Error in model operations.

### ModelNotFoundError (ModelError)

**File**: `src/de_funk/core/exceptions.py:244`

**Purpose**: Requested model does not exist.

### TableNotFoundError (ModelError)

**File**: `src/de_funk/core/exceptions.py:269`

**Purpose**: Requested table does not exist in model.

### MeasureError (ModelError)

**File**: `src/de_funk/core/exceptions.py:296`

**Purpose**: Error calculating a measure.

### DependencyError (ModelError)

**File**: `src/de_funk/core/exceptions.py:322`

**Purpose**: Model dependency not satisfied.

### QueryError (DeFunkError)

**File**: `src/de_funk/core/exceptions.py:346`

**Purpose**: Error executing a query.

### FilterError (QueryError)

**File**: `src/de_funk/core/exceptions.py:351`

**Purpose**: Error applying filters.

### JoinError (QueryError)

**File**: `src/de_funk/core/exceptions.py:370`

**Purpose**: Error joining tables.

### StorageError (DeFunkError)

**File**: `src/de_funk/core/exceptions.py:395`

**Purpose**: Error in storage operations.

### DataNotFoundError (StorageError)

**File**: `src/de_funk/core/exceptions.py:400`

**Purpose**: Requested data does not exist.

### WriteError (StorageError)

**File**: `src/de_funk/core/exceptions.py:424`

**Purpose**: Error writing data to storage.

### ForecastError (DeFunkError)

**File**: `src/de_funk/core/exceptions.py:448`

**Purpose**: Error in forecasting operations.

### InsufficientDataError (ForecastError)

**File**: `src/de_funk/core/exceptions.py:453`

**Purpose**: Not enough data for forecasting.

### ModelTrainingError (ForecastError)

**File**: `src/de_funk/core/exceptions.py:478`

**Purpose**: Error training forecast model.

### ConnectionError (DeFunkError)

**File**: `src/de_funk/core/exceptions.py:507`

**Purpose**: Error in database connection.

### ErrorContext

**File**: `src/de_funk/core/error_handling.py:204`

**Purpose**: Context manager for detailed error reporting.

### ValidationError

**File**: `src/de_funk/core/validation.py:20`

**Purpose**: Represents a validation error.

| Attribute | Type |
|-----------|------|
| `level` | `str` |
| `message` | `str` |
| `location` | `Optional[str]` |

### NotebookValidator

**File**: `src/de_funk/core/validation.py:27`

**Purpose**: Validates notebook configuration against available models.

| Method | Description |
|--------|-------------|
| `validate(notebook_config: NotebookConfig) -> List[ValidationError]` | Validate notebook configuration. |
| `validate_and_raise(notebook_config: NotebookConfig)` | Validate and raise exception if errors found. |
| `get_warnings(notebook_config: NotebookConfig) -> List[ValidationError]` | Get only validation warnings. |
| `get_errors(notebook_config: NotebookConfig) -> List[ValidationError]` | Get only validation errors. |
| `is_valid(notebook_config: NotebookConfig) -> bool` | Check if notebook is valid (no errors). |

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
| `src/de_funk/core/exceptions.py` | Custom Exception Hierarchy for de_Funk. | `DeFunkError`, `ConfigurationError`, `MissingConfigError`, `InvalidConfigError`, `PipelineError`, `IngestionError`, `RateLimitError`, `TransformationError`, `ModelError`, `ModelNotFoundError`, `TableNotFoundError`, `MeasureError`, `DependencyError`, `QueryError`, `FilterError`, `JoinError`, `StorageError`, `DataNotFoundError`, `WriteError`, `ForecastError`, `InsufficientDataError`, `ModelTrainingError`, `ConnectionError` |
| `src/de_funk/core/error_handling.py` | Error Handling Utilities for de_Funk. | `ErrorContext` |
| `src/de_funk/core/validation.py` | Validation layer for notebooks. | `ValidationError`, `NotebookValidator` |
